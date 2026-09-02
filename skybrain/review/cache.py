"""Review Cache — Two-tier caching for the Multi-Pass Review Engine.

Tier 1: Result Cache (Disk)
  Persists lens results keyed by SHA-256(file_content) + lens_name.
  If a file hasn't changed since the last review, cached results are
  returned instantly without invoking the LLM — saving tokens and time.

Tier 2: Session Context (Memory)
  Accumulates findings within a single review session so that later
  lenses receive prior findings as additional context. This enables
  cross-lens awareness: e.g., the Performance lens can reference
  architectural issues discovered by the Architecture lens.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from skybrain.review.models import (
    Category,
    Finding,
    LensResult,
    Severity,
)

logger = logging.getLogger("skybrain.review.cache")

DEFAULT_CACHE_DIR = Path.home() / ".skybrain" / "cache" / "review"
DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24 hours


# ═══════════════════════════════════════════════════════════════
#  Tier 1: Disk-based Result Cache
# ═══════════════════════════════════════════════════════════════


class ResultCache:
    """Persistent file-based cache for lens review results.

    Storage layout::

        ~/.skybrain/cache/review/
        └── <file_content_sha256>/
            ├── clean_code.json
            ├── clean_architecture.json
            ├── security.json
            └── performance.json

    Cache keys are content-addressable: if the file changes (even by
    one byte), the hash changes and the old cache is automatically
    bypassed. This eliminates manual invalidation logic.

    TTL-based expiration ensures stale results from older model versions
    are eventually refreshed.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        enabled: bool = True,
    ) -> None:
        self._cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self._ttl_seconds = ttl_seconds
        self._enabled = enabled
        if self._enabled:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get(
        self, file_content: str, lens_name: str
    ) -> Optional[LensResult]:
        """Retrieve cached result for a file+lens combination.

        Returns None if not cached, expired, or cache is disabled.
        """
        if not self._enabled:
            return None

        cache_path = self._cache_path(file_content, lens_name)
        if not cache_path.exists():
            return None

        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Cache read error for %s: %s", cache_path, exc)
            return None

        # TTL check
        cached_at = data.get("cached_at", 0)
        age = time.time() - cached_at
        if age > self._ttl_seconds:
            logger.debug(
                "Cache expired for %s/%s (age: %.0fs > TTL: %ds)",
                self._content_hash(file_content)[:12],
                lens_name,
                age,
                self._ttl_seconds,
            )
            cache_path.unlink(missing_ok=True)
            return None

        # Deserialize
        result = self._deserialize_result(data)
        if result:
            logger.info(
                "💾 Cache HIT: %s → %d findings (age: %.0fs)",
                lens_name,
                len(result.findings),
                age,
            )
        return result

    def put(
        self, file_content: str, lens_name: str, result: LensResult
    ) -> None:
        """Store a lens result in the cache."""
        if not self._enabled:
            return

        cache_path = self._cache_path(file_content, lens_name)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        data = self._serialize_result(result)
        data["cached_at"] = time.time()
        data["content_hash"] = self._content_hash(file_content)

        try:
            cache_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug(
                "Cache STORE: %s/%s → %d findings",
                self._content_hash(file_content)[:12],
                lens_name,
                len(result.findings),
            )
        except OSError as exc:
            logger.warning("Cache write error: %s", exc)

    def invalidate(self, file_content: str) -> int:
        """Remove all cached results for a specific file content hash.

        Returns the number of cache entries removed.
        """
        content_hash = self._content_hash(file_content)
        hash_dir = self._cache_dir / content_hash
        if not hash_dir.exists():
            return 0

        count = 0
        for cache_file in hash_dir.iterdir():
            cache_file.unlink(missing_ok=True)
            count += 1

        hash_dir.rmdir()
        return count

    def clear(self) -> int:
        """Remove all cached review results. Returns count removed."""
        if not self._cache_dir.exists():
            return 0

        count = 0
        for hash_dir in self._cache_dir.iterdir():
            if hash_dir.is_dir():
                for cache_file in hash_dir.iterdir():
                    cache_file.unlink(missing_ok=True)
                    count += 1
                hash_dir.rmdir()
        return count

    def stats(self) -> dict[str, int]:
        """Return cache statistics."""
        if not self._cache_dir.exists():
            return {"total_entries": 0, "total_files": 0, "size_bytes": 0}

        total_entries = 0
        total_files = 0
        size_bytes = 0
        for hash_dir in self._cache_dir.iterdir():
            if hash_dir.is_dir():
                total_files += 1
                for cache_file in hash_dir.iterdir():
                    total_entries += 1
                    size_bytes += cache_file.stat().st_size

        return {
            "total_entries": total_entries,
            "total_files": total_files,
            "size_bytes": size_bytes,
        }

    # ── Private ──────────────────────────────────────────────

    def _cache_path(self, file_content: str, lens_name: str) -> Path:
        """Compute the disk path for a cache entry."""
        content_hash = self._content_hash(file_content)
        safe_lens = lens_name.lower().replace(" ", "_")
        return self._cache_dir / content_hash / f"{safe_lens}.json"

    @staticmethod
    def _content_hash(content: str) -> str:
        """SHA-256 hash of file content for content-addressable lookup."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _serialize_result(result: LensResult) -> dict:
        """Convert LensResult to a JSON-serializable dict."""
        return {
            "lens_name": result.lens_name,
            "category": result.category.value,
            "file_path": result.file_path,
            "execution_time_ms": result.execution_time_ms,
            "findings": [
                {
                    "file": f.file,
                    "line": f.line,
                    "severity": f.severity.name,
                    "category": f.category.value,
                    "principle_violated": f.principle_violated,
                    "description": f.description,
                    "suggestion": f.suggestion,
                    "confidence": f.confidence,
                    "verified": f.verified,
                    "finding_id": f.finding_id,
                }
                for f in result.findings
            ],
        }

    @staticmethod
    def _deserialize_result(data: dict) -> Optional[LensResult]:
        """Reconstruct LensResult from cached JSON dict."""
        try:
            findings = []
            for fd in data.get("findings", []):
                findings.append(
                    Finding(
                        file=fd["file"],
                        line=fd.get("line"),
                        severity=Severity[fd["severity"]],
                        category=Category(fd["category"]),
                        principle_violated=fd["principle_violated"],
                        description=fd["description"],
                        suggestion=fd["suggestion"],
                        confidence=fd.get("confidence", 1.0),
                        verified=fd.get("verified", False),
                        finding_id=fd.get("finding_id", ""),
                    )
                )
            return LensResult(
                lens_name=data["lens_name"],
                category=Category(data["category"]),
                file_path=data["file_path"],
                findings=findings,
                execution_time_ms=data.get("execution_time_ms", 0.0),
            )
        except (KeyError, ValueError) as exc:
            logger.debug("Cache deserialization error: %s", exc)
            return None


# ═══════════════════════════════════════════════════════════════
#  Tier 2: In-memory Session Context
# ═══════════════════════════════════════════════════════════════


@dataclass
class SessionContext:
    """Accumulated context within a single review session.

    As each lens runs, its findings are added to the session context.
    Later lenses can receive a summary of previous findings as additional
    context, enabling cross-referencing and multi-perspective awareness.

    Example flow::

        Clean Code lens → finds SRP violation at line 42
        ↓ (session context)
        Architecture lens → receives "Note: line 42 was flagged for SRP"
        ↓ (session context)
        Security lens → receives both previous findings
        ↓ (session context)
        Performance lens → receives all 3 previous findings

    This iterative context enrichment helps each subsequent lens
    build on prior discoveries, yielding more coherent analysis.
    """

    findings_by_lens: dict[str, list[Finding]] = field(default_factory=dict)
    file_metadata: dict[str, dict] = field(default_factory=dict)

    def add_result(self, result: LensResult) -> None:
        """Add a lens result to the session context."""
        self.findings_by_lens[result.lens_name] = list(result.findings)

    def add_file_metadata(self, file_path: str, metadata: dict) -> None:
        """Store file-level metadata (line count, imports, etc.)."""
        self.file_metadata[file_path] = metadata

    def get_context_summary(self, exclude_lens: Optional[str] = None) -> str:
        """Generate a concise summary of prior findings for context injection.

        Args:
            exclude_lens: Optionally exclude a specific lens's findings
                          (e.g., exclude the current lens's own prior output).

        Returns:
            A formatted string summarizing previous discoveries.
        """
        summaries: list[str] = []

        for lens_name, findings in self.findings_by_lens.items():
            if lens_name == exclude_lens:
                continue
            if not findings:
                continue

            high_severity = [
                f for f in findings if f.severity >= Severity.MEDIUM
            ]
            if not high_severity:
                continue

            finding_lines = []
            for f in high_severity[:5]:  # Cap at 5 per lens for token economy
                line_info = f"line {f.line}" if f.line else "unknown line"
                finding_lines.append(
                    f"  - [{f.severity.name}] {line_info}: "
                    f"{f.principle_violated} — {f.description}"
                )

            summaries.append(
                f"[{lens_name}] found {len(findings)} issue(s):\n"
                + "\n".join(finding_lines)
            )

        if not summaries:
            return ""

        return (
            "## Prior Review Context (from other lenses)\n"
            "The following issues were already identified by other review "
            "passes. Reference them to avoid duplicating analysis and to "
            "provide complementary insights:\n\n"
            + "\n\n".join(summaries)
        )

    @property
    def total_findings(self) -> int:
        """Total number of findings accumulated so far."""
        return sum(len(f) for f in self.findings_by_lens.values())

    def clear(self) -> None:
        """Reset the session context."""
        self.findings_by_lens.clear()
        self.file_metadata.clear()
