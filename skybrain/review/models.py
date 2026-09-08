"""SkyBrain Multi-Pass Review Engine — Domain Models.

Pure domain entities with zero external dependencies.
These models represent the core vocabulary of the review domain.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class Severity(enum.IntEnum):
    """Finding severity levels, ordered by criticality (highest first)."""

    CRITICAL = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1
    INFO = 0


class Category(str, enum.Enum):
    """Review lens category identifiers."""

    CLEAN_CODE = "clean_code"
    CLEAN_ARCHITECTURE = "clean_architecture"
    SECURITY = "security"
    PERFORMANCE = "performance"
    AI_CONDUCT = "ai_conduct"


@dataclass(frozen=True)
class Finding:
    """A single actionable code review finding.

    Immutable value object — once created, findings are never mutated.
    The structured fields (file, line, severity) enforce precision and
    naturally suppress LLM hallucination by requiring concrete evidence.
    """

    file: str
    line: Optional[int]
    severity: Severity
    category: Category
    principle_violated: str
    description: str
    suggestion: str
    confidence: float = 1.0  # 0.0–1.0, set by verification pass
    verified: bool = False
    finding_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def with_verification(self, *, verified: bool, confidence: float) -> "Finding":
        """Returns a new Finding with updated verification status."""
        return Finding(
            file=self.file,
            line=self.line,
            severity=self.severity,
            category=self.category,
            principle_violated=self.principle_violated,
            description=self.description,
            suggestion=self.suggestion,
            confidence=confidence,
            verified=verified,
            finding_id=self.finding_id,
        )


@dataclass
class LensResult:
    """Output of a single lens pass over one file.

    Captures the lens identity, its findings, and execution metadata
    so the aggregator can trace provenance.
    """

    lens_name: str
    category: Category
    file_path: str
    findings: list[Finding] = field(default_factory=list)
    execution_time_ms: float = 0.0
    raw_response: str = ""


@dataclass
class AggregatedReport:
    """Final merged review report across all lenses and files.

    This is the top-level artifact produced by the ReviewEngine
    and consumed by CLI renderers or downstream tools.
    """

    lens_results: list[LensResult] = field(default_factory=list)
    verified_findings: list[Finding] = field(default_factory=list)
    unverified_findings: list[Finding] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    total_files_reviewed: int = 0
    total_lenses_applied: int = 0

    @property
    def all_findings(self) -> list[Finding]:
        """All findings sorted by severity (highest first)."""
        combined = self.verified_findings + self.unverified_findings
        return sorted(combined, key=lambda f: f.severity, reverse=True)

    @property
    def stats(self) -> dict[str, int]:
        """Severity distribution across all findings."""
        counts: dict[str, int] = {}
        for sev in Severity:
            counts[sev.name] = sum(
                1 for f in self.all_findings if f.severity == sev
            )
        return counts

    @property
    def findings(self) -> list[Finding]:
        """Alias for all_findings."""
        return self.all_findings

    @property
    def files_reviewed(self) -> list[str]:
        """List of distinct file paths reviewed."""
        return list({r.file_path for r in self.lens_results})

    @property
    def total_duration_seconds(self) -> float:
        """Total execution time in seconds across all lenses."""
        return sum(r.execution_time_ms for r in self.lens_results) / 1000.0

    @property
    def health_score(self) -> int:
        """Calculates code health score from 0 to 100 based on severity penalties."""
        score = 100
        score -= self.stats.get("CRITICAL", 0) * 25
        score -= self.stats.get("HIGH", 0) * 15
        score -= self.stats.get("MEDIUM", 0) * 8
        score -= self.stats.get("LOW", 0) * 3
        return max(0, min(100, score))

    def to_lead_llm_payload(self) -> dict:
        """Serializes report into a structured payload optimized for Lead LLM cross-checking."""
        findings_payload = []
        for idx, f in enumerate(self.all_findings, start=1):
            findings_payload.append({
                "finding_id": f"PRE-{idx:02d}",
                "severity": f.severity.name,
                "category": f.category.value if hasattr(f.category, "value") else str(f.category),
                "file": f.file,
                "line": f.line,
                "principle": f.principle_violated,
                "description": f.description,
                "suggestion": f.suggestion,
                "confidence": round(f.confidence, 2),
                "verified": f.verified,
                "lead_llm_cross_check_prompt": (
                    f"Check '{f.file}' line {f.line or 'unknown'}: '{f.principle_violated}'. "
                    f"Validate if candidate flaw '{f.description}' is an actual issue or false positive."
                ),
            })

        return {
            "status": "ready_for_lead_llm_cross_check",
            "health_score": self.health_score,
            "total_files": self.total_files_reviewed,
            "total_findings": len(self.all_findings),
            "severity_counts": self.stats,
            "duration_seconds": round(self.total_duration_seconds, 2),
            "findings": findings_payload,
        }
