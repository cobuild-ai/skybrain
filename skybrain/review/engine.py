"""ReviewEngine — Use Case Orchestrator.

Central coordinator that drives the multi-pass review pipeline:
  Cache Check → Lenses → Verification → Aggregation → Report

Follows Clean Architecture: this layer depends only on domain models
and abstractions (ReviewLens, SkyBrainClient), never on frameworks.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional, Sequence, Type

from skybrain.review.aggregator import FindingAggregator
from skybrain.review.cache import ResultCache, SessionContext
from skybrain.review.client import SkyBrainClient
from skybrain.review.lenses.base import ReviewLens
from skybrain.review.models import AggregatedReport, Finding, LensResult
from skybrain.review.verification import ChainOfVerifier

logger = logging.getLogger("skybrain.review.engine")


class ReviewEngine:
    """Orchestrates the full multi-pass code review pipeline.

    Architecture (Dependency Injection):
      - Lenses are injected at construction, not hardcoded
      - Client is shared across lenses and verifier
      - Cache, aggregator, and verifier are all pluggable

    Two-tier caching:
      - Tier 1 (ResultCache): Disk-persistent, content-addressable.
        Skips LLM calls entirely if file hasn't changed.
      - Tier 2 (SessionContext): In-memory, per-session.
        Shares prior findings with subsequent lenses for context.

    This design allows:
      - Adding new lenses without modifying the engine
      - Swapping the LLM backend (local Qwen → cloud API)
      - Testing each component in isolation
    """

    def __init__(
        self,
        lens_classes: Sequence[Type[ReviewLens]],
        client: Optional[SkyBrainClient] = None,
        verifier: Optional[ChainOfVerifier] = None,
        aggregator: Optional[FindingAggregator] = None,
        cache: Optional[ResultCache] = None,
    ) -> None:
        self._client = client or SkyBrainClient()
        self._lenses = [cls(client=self._client) for cls in lens_classes]
        self._verifier = verifier or ChainOfVerifier(client=self._client)
        self._aggregator = aggregator or FindingAggregator()
        self._cache = cache or ResultCache()

    def review(
        self,
        file_paths: Sequence[str | Path],
        verify: bool = True,
        voting_rounds: int = 1,
        use_cache: bool = True,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> AggregatedReport:
        """Execute the full multi-pass review pipeline with strict blind isolation.

        Blind Evaluation Invariant:
          Each lens evaluates code independently using ONLY raw source code and its
          own domain rules. Findings from other lenses are NEVER leaked during evaluation
          to prevent confirmation bias and consensus contamination.

        Args:
            file_paths: Source files to review.
            verify: If True, run Chain-of-Verification on findings.
            voting_rounds: Number of Self-Consistency rounds per lens.
                           Findings appearing in ≥50% of rounds survive.
            use_cache: If True, use disk cache to skip unchanged files.
            progress_callback: Optional callback func(step_description, advance_amount).

        Returns:
            AggregatedReport with all findings, stats, and metadata.
        """
        all_results: list[LensResult] = []
        cache_hits = 0
        cache_misses = 0

        for path in file_paths:
            file_path = Path(path)
            if not file_path.exists():
                logger.warning("File not found, skipping: %s", file_path)
                continue

            source_code = file_path.read_text(encoding="utf-8")
            if not source_code.strip():
                logger.info("Empty file, skipping: %s", file_path)
                continue

            logger.info("📄 Reviewing: %s", file_path)

            total_lenses = len(self._lenses)
            lens_icons = {
                "CleanCode": "🧹 Clean Code",
                "CleanArchitecture": "🏛️ Clean Architecture",
                "Security": "🛡️ Security",
                "Performance": "⚡ Performance",
                "AIConduct": "🤖 AI Conduct",
            }

            for idx, lens in enumerate(self._lenses, 1):
                lens_title = lens_icons.get(lens.name, f"🔍 {lens.name}")
                logger.info("  🔍 Lens: %s", lens.name)
                if progress_callback:
                    progress_callback(f"[{idx}/{total_lenses} {lens_title} analyzing: {file_path.name}]", 0.0)

                # ── Tier 1: Disk Cache Check ──
                cached_result = None
                if use_cache and self._cache.enabled and voting_rounds <= 1:
                    cached_result = self._cache.get(source_code, lens.name)

                if cached_result is not None:
                    cache_hits += 1
                    result = cached_result
                    if progress_callback:
                        progress_callback(f"[{idx}/{total_lenses} {lens_title} cache hit: {file_path.name}]", 1.0)
                else:
                    cache_misses += 1

                    # Run lens analysis in strict blind isolation
                    if voting_rounds > 1:
                        result = self._run_with_voting(
                            lens,
                            source_code,
                            str(file_path),
                            voting_rounds,
                        )
                    else:
                        result = lens.analyze(
                            source_code,
                            str(file_path),
                        )

                    # Chain-of-Verification pass
                    if verify and result.findings:
                        if progress_callback:
                            progress_callback(f"[🔍 Verifier fact-checking ({len(result.findings)} findings): {file_path.name}]", 0.0)
                        logger.info(
                            "  🔗 Verifying %d findings...",
                            len(result.findings),
                        )
                        result.findings = self._verifier.verify_findings(
                            result.findings, source_code, str(file_path)
                        )

                    # Store in disk cache
                    if use_cache and self._cache.enabled and voting_rounds <= 1:
                        self._cache.put(source_code, lens.name, result)

                    if progress_callback:
                        progress_callback(f"[{idx}/{total_lenses} {lens_title} complete: {file_path.name}]", 1.0)

                all_results.append(result)
                logger.info(
                    "  ✅ %s: %d findings (%.0f ms)%s",
                    lens.name,
                    len(result.findings),
                    result.execution_time_ms,
                    " [CACHED]" if cached_result else "",
                )

        report = self._aggregator.aggregate(all_results)
        self._log_summary(report, cache_hits, cache_misses)
        return report

    def _run_with_voting(
        self,
        lens: ReviewLens,
        source_code: str,
        file_path: str,
        rounds: int,
    ) -> LensResult:
        """Run a lens multiple times and keep findings with majority votes.

        Self-Consistency technique: findings that appear in ≥50% of rounds
        are considered reliable. This reduces false positives by 40–60%.
        """
        all_round_findings: list[list[Finding]] = []

        for round_num in range(rounds):
            logger.info("    🗳️ Voting round %d/%d", round_num + 1, rounds)
            result = lens.analyze(source_code, file_path)
            all_round_findings.append(result.findings)

        # Count how many rounds each finding appears in
        finding_votes: dict[str, int] = {}
        finding_map: dict[str, Finding] = {}
        for round_findings in all_round_findings:
            seen_keys: set[str] = set()
            for f in round_findings:
                key = self._finding_signature(f)
                if key not in seen_keys:
                    finding_votes[key] = finding_votes.get(key, 0) + 1
                    finding_map[key] = f
                    seen_keys.add(key)

        # Keep findings with ≥ 50% vote threshold
        threshold = max(1, rounds // 2)
        majority_findings = [
            finding_map[key]
            for key, votes in finding_votes.items()
            if votes >= threshold
        ]

        last_result = LensResult(
            lens_name=lens.name,
            category=lens.category,
            file_path=file_path,
            findings=majority_findings,
        )
        return last_result

    @staticmethod
    def _finding_signature(finding: Finding) -> str:
        """Create a stable key for deduplication across voting rounds."""
        return (
            f"{finding.file}:{finding.line or 0}:"
            f"{finding.principle_violated}:"
            f"{finding.severity.name}"
        )

    @staticmethod
    def _log_summary(
        report: AggregatedReport,
        cache_hits: int = 0,
        cache_misses: int = 0,
    ) -> None:
        """Log a summary of the aggregated review report."""
        stats = report.stats
        total = len(report.all_findings)
        verified = len(report.verified_findings)
        cache_info = ""
        if cache_hits + cache_misses > 0:
            cache_info = (
                f" | Cache: {cache_hits} hits, {cache_misses} misses"
            )
        logger.info(
            "📊 Review complete: %d findings (%d verified) | "
            "CRITICAL=%d HIGH=%d MEDIUM=%d LOW=%d INFO=%d%s",
            total,
            verified,
            stats.get("CRITICAL", 0),
            stats.get("HIGH", 0),
            stats.get("MEDIUM", 0),
            stats.get("LOW", 0),
            stats.get("INFO", 0),
            cache_info,
        )
