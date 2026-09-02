"""ExpertEngine — Knowledge Layer Orchestrator with 2/3 Consensus Voting.

Drives the evaluation of code by projecting decoupled ExpertLens specifications
into the LLM, collecting atomic findings, and filtering through the 2/3 Consensus rule.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional, Sequence

from skybrain.expert.models import (
    AssessmentFinding,
    ExpertLens,
    ExpertReport,
    Severity,
)
from skybrain.expert.registry import LensRegistry, default_registry
from skybrain.expert.voter import ConsensusVoter
from skybrain.review.client import SkyBrainClient

logger = logging.getLogger("skybrain.expert.engine")

JSON_FORMAT_DIRECTIVE = """
You MUST evaluate the code strictly against the given Expert Lens criteria.
Output ONLY a valid JSON array of objects. No intro text, no markdown explanation.
Each object must follow this exact schema:
[
  {
    "line": 42,
    "rule_id": "CC-SRP-001",
    "principle": "Single Responsibility Principle",
    "description": "Concrete explanation of how the code violates this rule",
    "suggestion": "Concrete actionable refactoring advice",
    "severity": "HIGH"
  }
]
If the code fully satisfies the criteria with no violations, return an empty array: []
Valid severity values: CRITICAL, HIGH, MEDIUM, LOW, INFO
"""


class ExpertEngine:
    """Orchestrates decoupled ExpertLens projections and applies 2/3 consensus."""

    def __init__(
        self,
        client: Optional[SkyBrainClient] = None,
        registry: Optional[LensRegistry] = None,
        voter: Optional[ConsensusVoter] = None,
    ) -> None:
        self.client = client or SkyBrainClient()
        self.registry = registry or default_registry
        self.voter = voter or ConsensusVoter()

    def evaluate_file(
        self,
        file_path: str | Path,
        lenses: Sequence[ExpertLens],
        rounds_per_lens: int = 3,
    ) -> ExpertReport:
        """Evaluate a single file through one or more lenses with 2/3 consensus.

        Args:
            file_path: Target code file.
            lenses: List of ExpertLens objects to project.
            rounds_per_lens: Number of evaluation rounds for consensus (default 3, where 2/3 = 2 votes needed).

        Returns:
            ExpertReport containing accepted findings, rejected noise, and consensus stats.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        code = path.read_text(encoding="utf-8")
        start_time = time.monotonic()

        raw_findings: list[AssessmentFinding] = []
        total_evaluations = 0

        for lens in lenses:
            logger.info("🔭 Projecting Expert Lens: %s (%s)", lens.name, lens.lens_id)
            for round_num in range(1, rounds_per_lens + 1):
                logger.debug("   Round %d/%d for lens %s", round_num, rounds_per_lens, lens.lens_id)
                findings = self._execute_projection(code, str(path), lens)
                raw_findings.extend(findings)
                total_evaluations += 1

        # Calculate expected total votes: rounds_per_lens * len(lenses)
        # For single lens with 3 rounds: expected = 3, threshold 2/3 = 2 votes.
        expected_votes = rounds_per_lens if len(lenses) == 1 else len(lenses) * rounds_per_lens

        accepted, rejected, consensus_items = self.voter.vote(
            findings=raw_findings,
            expected_total_votes=expected_votes,
        )

        elapsed_ms = (time.monotonic() - start_time) * 1000

        report = ExpertReport(
            target_files=[str(path)],
            applied_lenses=[l.lens_id for l in lenses],
            accepted_findings=accepted,
            rejected_findings=rejected,
            consensus_items=consensus_items,
            total_evaluations=total_evaluations,
            execution_time_ms=round(elapsed_ms, 1),
        )

        logger.info(
            "🏁 Evaluation complete for %s: %d accepted (>=2/3), %d filtered (<2/3)",
            path.name,
            len(accepted),
            len(rejected),
        )
        return report

    def _execute_projection(
        self,
        code: str,
        file_path: str,
        lens: ExpertLens,
    ) -> list[AssessmentFinding]:
        """Project a single lens onto code and parse structured findings."""
        system_prompt = (
            f"You are {lens.persona}.\n"
            f"You are a specialized code review expert adhering to strict standards.\n\n"
            f"{lens.format_prompt_spec()}"
        )

        user_prompt = (
            f"Analyze the following Python source code from `{file_path}`:\n"
            f"{JSON_FORMAT_DIRECTIVE}\n\n"
            f"```python\n{code}\n```"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            raw_response = self.client.query(
                messages=messages,
                temperature=0.2,  # Slight variation across rounds for self-consistency voting
                max_tokens=2048,
            )
            return self._parse_json_findings(raw_response, file_path, lens.lens_id)
        except Exception as exc:
            logger.warning("Lens projection error (%s): %s", lens.lens_id, exc)
            return []

    def _parse_json_findings(
        self,
        raw_text: str,
        file_path: str,
        lens_id: str,
    ) -> list[AssessmentFinding]:
        """Robust parser extracting findings from json array."""
        cleaned = self._extract_json(raw_text)
        if not cleaned:
            return []

        try:
            items = json.loads(cleaned)
        except json.JSONDecodeError:
            return []

        if not isinstance(items, list):
            return []

        results: list[AssessmentFinding] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            try:
                sev = Severity[item.get("severity", "MEDIUM").upper()]
            except KeyError:
                sev = Severity.MEDIUM

            results.append(
                AssessmentFinding(
                    file=file_path,
                    line=item.get("line"),
                    rule_id=item.get("rule_id", "GENERAL"),
                    principle=item.get("principle", "Quality Standard"),
                    description=item.get("description", ""),
                    suggestion=item.get("suggestion", ""),
                    severity=sev,
                    lens_id=lens_id,
                )
            )
        return results

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract pure JSON array string from model output."""
        if "</think>" in text:
            text = text.split("</think>", 1)[-1]

        for fence in ("```json", "```"):
            if fence in text:
                parts = text.split(fence)
                for part in parts[1:]:
                    candidate = part.split("```")[0].strip()
                    if candidate.startswith("["):
                        return candidate

        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]

        return ""
