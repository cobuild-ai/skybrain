"""SkyBrain Expert System Domain Models.

Zero-dependency data structures for Knowledge Layers (ExpertLens)
and 2/3 Majority Consensus Voting.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


class Severity(enum.IntEnum):
    """Severity classification for findings."""

    CRITICAL = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1
    INFO = 0


@dataclass(frozen=True)
class EvaluationCriterion:
    """Atomic evaluation criterion within an ExpertLens.

    Designed for lightweight models: contains plain binary questions and
    concrete positive/negative signal patterns that can be checked mechanically.
    """

    rule_id: str
    name: str
    question: str
    negative_signals: tuple[str, ...]
    positive_signals: tuple[str, ...]
    severity: Severity = Severity.MEDIUM


@dataclass(frozen=True)
class ExpertLens:
    """A modular Knowledge Layer (Lens) defining a domain-specific expert viewpoint.

    Completely decoupled from the engine and other lenses.
    """

    lens_id: str
    name: str
    domain: str
    persona: str
    criteria: tuple[EvaluationCriterion, ...]
    version: str = "1.0.0"

    def format_prompt_spec(self) -> str:
        """Render criteria as a compact, mechanical checklist for the LLM."""
        lines = [
            f"### Expert Lens: {self.name} ({self.domain})",
            f"Persona: {self.persona}",
            "Apply the following criteria to evaluate the code:",
        ]
        for idx, c in enumerate(self.criteria, start=1):
            neg = ", ".join(c.negative_signals) if c.negative_signals else "None"
            pos = ", ".join(c.positive_signals) if c.positive_signals else "None"
            lines.append(
                f"{idx}. [{c.rule_id}] {c.name} ({c.severity.name})\n"
                f"   - Question: {c.question}\n"
                f"   - Negative Signals: {neg}\n"
                f"   - Positive Signals: {pos}"
            )
        return "\n".join(lines)


@dataclass(frozen=True)
class AssessmentFinding:
    """Finding produced by evaluating code through an ExpertLens."""

    file: str
    line: Optional[int]
    rule_id: str
    principle: str
    description: str
    suggestion: str
    severity: Severity
    lens_id: str
    confidence: float = 1.0
    finding_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


class ConsensusVerdict(str, enum.Enum):
    """Consensus voting outcome."""

    ACCEPTED = "ACCEPTED"    # Vote ratio >= 2/3 (66.7%)
    REJECTED = "REJECTED"    # Vote ratio < 2/3 (Filtered as false positive/minority)
    INSUFFICIENT = "INSUFFICIENT"  # Total votes < minimum required threshold


@dataclass(frozen=True)
class ConsensusItem:
    """Group of findings evaluated across voting rounds or distinct lenses."""

    signature: str
    findings: tuple[AssessmentFinding, ...]
    total_votes: int
    favorable_votes: int
    vote_ratio: float
    verdict: ConsensusVerdict
    final_finding: Optional[AssessmentFinding] = None


@dataclass(frozen=True)
class ConsensusContext:
    """Immutable, frozen context holding verified 2/3 consensus facts.

    Serves as the tamper-proof baseline for follow-up requests.
    Contains strictly verified findings without noise or intermediate musings.
    """

    context_id: str
    file_path: str
    source_code: str
    agreed_findings: tuple[AssessmentFinding, ...]
    generation: int = 1
    created_at: float = field(default_factory=time.time)

    def format_frozen_context(self) -> str:
        """Render the agreed facts as an authoritative, unalterable baseline."""
        lines = [
            f"### Authoritative Baseline (Consensus Generation {self.generation})",
            f"File: `{self.file_path}`",
            "The following facts have passed strict 2/3 majority consensus.",
            "They are immutable premises. Do NOT dispute, alter, or re-debate them:",
        ]
        if not self.agreed_findings:
            lines.append("No defects identified in previous consensus rounds (Code verified clean).")
        else:
            for idx, f in enumerate(self.agreed_findings, start=1):
                loc = f"Line {f.line}" if f.line else "File level"
                lines.append(
                    f"{idx}. [{f.severity.name}] {f.rule_id} ({loc}): {f.description}\n"
                    f"   Established Refactoring: {f.suggestion}"
                )
        return "\n".join(lines)


@dataclass
class ExpertReport:
    """Aggregated final report produced by ExpertEngine."""

    target_files: list[str]
    applied_lenses: list[str]
    accepted_findings: list[AssessmentFinding] = field(default_factory=list)
    rejected_findings: list[AssessmentFinding] = field(default_factory=list)
    consensus_items: list[ConsensusItem] = field(default_factory=list)
    total_evaluations: int = 0
    execution_time_ms: float = 0.0
    consensus_context: Optional[ConsensusContext] = None

    @property
    def stats(self) -> dict[str, int]:
        """Distribution of accepted findings by severity."""
        counts = {s.name: 0 for s in Severity}
        for f in self.accepted_findings:
            counts[f.severity.name] += 1
        return counts
