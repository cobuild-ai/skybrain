"""Abstract ReviewLens — Strategy Pattern interface.

All concrete lenses (Clean Code, Architecture, Security, Performance)
implement this interface so the ReviewEngine can treat them uniformly.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional

from skybrain.review.client import SkyBrainClient
from skybrain.review.models import Category, Finding, LensResult, Severity

logger = logging.getLogger("skybrain.review.lens")

# ── Shared JSON output schema injected into every lens prompt ────────

STRUCTURED_OUTPUT_INSTRUCTION = """
You MUST respond with a valid JSON array only. No markdown, no explanation.
Each element must follow this exact schema:
[
  {
    "file": "filename.py",
    "line": 42,
    "severity": "HIGH",
    "principle_violated": "Single Responsibility Principle",
    "description": "Concrete description of what is wrong",
    "suggestion": "Concrete suggestion for how to fix it"
  }
]
If you find no issues, return an empty array: []
Valid severity values: CRITICAL, HIGH, MEDIUM, LOW, INFO
"""


class ReviewLens(ABC):
    """Abstract base for all review perspective lenses.

    Subclasses define:
      - ``name``: human-readable lens identifier
      - ``category``: enum category tag
      - ``system_prompt``: the expert persona and framework to apply
    """

    def __init__(self, client: Optional[SkyBrainClient] = None) -> None:
        self._client = client or SkyBrainClient()

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this lens."""

    @property
    @abstractmethod
    def category(self) -> Category:
        """Category enum for this lens."""

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Expert persona and analysis framework prompt."""

    def analyze(self, code: str, file_path: str) -> LensResult:
        """Run this lens against the given source code in strict blind isolation.

        Each lens evaluates the code independently using only its own domain criteria
        and the raw source code. Cross-lens findings are NEVER injected here to prevent
        confirmation bias and consensus contamination.

        Returns a LensResult with parsed findings and timing metadata.
        """
        user_prompt = (
            f"Review the following source code from `{file_path}`.\n"
            f"{STRUCTURED_OUTPUT_INSTRUCTION}\n\n"
            f"```python\n{code}\n```"
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        start = time.monotonic()
        raw_response = self._client.query(
            messages=messages, temperature=0.1, max_tokens=2048
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        findings = self._parse_findings(raw_response, file_path)

        return LensResult(
            lens_name=self.name,
            category=self.category,
            file_path=file_path,
            findings=findings,
            execution_time_ms=round(elapsed_ms, 1),
            raw_response=raw_response,
        )

    def _parse_findings(self, raw: str, file_path: str) -> list[Finding]:
        """Parse JSON array from LLM response into Finding objects.

        Tolerant of markdown fences and thinking blocks that Qwen may emit.
        """
        cleaned = self._extract_json_array(raw)
        if not cleaned:
            return []

        try:
            items = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(
                "Failed to parse JSON from %s lens response for %s",
                self.name,
                file_path,
            )
            return []

        if not isinstance(items, list):
            return []

        findings: list[Finding] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                severity = Severity[item.get("severity", "MEDIUM").upper()]
            except KeyError:
                severity = Severity.MEDIUM

            findings.append(
                Finding(
                    file=item.get("file", file_path),
                    line=item.get("line"),
                    severity=severity,
                    category=self.category,
                    principle_violated=item.get("principle_violated", "Unknown"),
                    description=item.get("description", ""),
                    suggestion=item.get("suggestion", ""),
                )
            )
        return findings

    @staticmethod
    def _extract_json_array(text: str) -> str:
        """Extract the first JSON array from text that may contain
        markdown fences, thinking blocks, or prose."""
        # Strip </think> blocks from Qwen's thinking mode
        if "</think>" in text:
            text = text.split("</think>", 1)[-1]

        # Strip markdown code fences
        for fence in ("```json", "```"):
            if fence in text:
                parts = text.split(fence)
                for part in parts[1:]:
                    candidate = part.split("```")[0].strip()
                    if candidate.startswith("["):
                        return candidate

        # Direct JSON array
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]

        return ""
