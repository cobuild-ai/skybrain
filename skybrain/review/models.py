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
