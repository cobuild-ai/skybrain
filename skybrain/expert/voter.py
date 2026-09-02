"""2/3 Majority Consensus Voter.

Implements the consensus algorithm:
Only findings that receive approval from at least 2/3 (>= 66.7%) of evaluating
rounds or across cross-validating lenses are accepted. Minority noise (< 2/3)
is filtered out as false-positive candidates.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Sequence

from skybrain.expert.models import (
    AssessmentFinding,
    ConsensusItem,
    ConsensusVerdict,
)

logger = logging.getLogger("skybrain.expert.voter")

CONSENSUS_THRESHOLD_RATIO = 2.0 / 3.0  # 66.666...%
DEFAULT_LINE_TOLERANCE = 3


class ConsensusVoter:
    """Consensus voting engine evaluating findings across multi-lens projections."""

    def __init__(
        self,
        threshold_ratio: float = CONSENSUS_THRESHOLD_RATIO,
        line_tolerance: int = DEFAULT_LINE_TOLERANCE,
    ) -> None:
        self.threshold_ratio = threshold_ratio
        self.line_tolerance = line_tolerance

    def vote(
        self,
        findings: Sequence[AssessmentFinding],
        expected_total_votes: int,
    ) -> tuple[list[AssessmentFinding], list[AssessmentFinding], list[ConsensusItem]]:
        """Cluster findings by signature, count votes against expected_total_votes,
        and filter by the 2/3 majority rule.

        Args:
            findings: Raw findings collected across evaluation lenses/rounds.
            expected_total_votes: Total number of opportunities/rounds (e.g. 3 rounds or 3 lenses).

        Returns:
            Tuple of (accepted_findings, rejected_findings, all_consensus_items)
        """
        if not findings or expected_total_votes <= 0:
            return [], [], []

        # 1. Cluster findings by file
        by_file: dict[str, list[AssessmentFinding]] = defaultdict(list)
        for f in findings:
            by_file[f.file].append(f)

        clusters: list[list[AssessmentFinding]] = []
        for file_findings in by_file.values():
            clusters.extend(self._cluster_findings(file_findings))

        # 2. Evaluate each cluster against the 2/3 threshold
        accepted: list[AssessmentFinding] = []
        rejected: list[AssessmentFinding] = []
        consensus_items: list[ConsensusItem] = []

        for cluster in clusters:
            favorable_votes = len(cluster)
            vote_ratio = favorable_votes / float(expected_total_votes)
            sig = self._cluster_signature(cluster[0])

            # Select the most detailed finding (highest severity, longest description)
            best_finding = max(
                cluster,
                key=lambda f: (int(f.severity), len(f.description)),
            )

            # Consensus Decision: >= 2/3 (66.7%)
            if vote_ratio >= (self.threshold_ratio - 1e-5):
                verdict = ConsensusVerdict.ACCEPTED
                accepted.append(best_finding)
            else:
                verdict = ConsensusVerdict.REJECTED
                rejected.append(best_finding)

            item = ConsensusItem(
                signature=sig,
                findings=tuple(cluster),
                total_votes=expected_total_votes,
                favorable_votes=favorable_votes,
                vote_ratio=round(vote_ratio, 3),
                verdict=verdict,
                final_finding=best_finding,
            )
            consensus_items.append(item)

        # Sort by severity descending
        accepted.sort(key=lambda f: int(f.severity), reverse=True)
        rejected.sort(key=lambda f: int(f.severity), reverse=True)

        return accepted, rejected, consensus_items

    def _cluster_findings(
        self, findings: list[AssessmentFinding]
    ) -> list[list[AssessmentFinding]]:
        """Group findings that refer to the same defect in the same file."""
        if not findings:
            return []

        # Sort by line
        sorted_f = sorted(findings, key=lambda f: f.line or 0)
        clusters: list[list[AssessmentFinding]] = [[sorted_f[0]]]

        for current in sorted_f[1:]:
            matched = False
            for cluster in clusters:
                rep = cluster[0]
                if self._is_same_defect(rep, current):
                    cluster.append(current)
                    matched = True
                    break
            if not matched:
                clusters.append([current])

        return clusters

    def _is_same_defect(self, a: AssessmentFinding, b: AssessmentFinding) -> bool:
        """Determine if two findings describe the same defect."""
        if a.file != b.file:
            return False

        # Line proximity
        if a.line is not None and b.line is not None:
            if abs(a.line - b.line) > self.line_tolerance:
                return False

        # Exact rule match
        if a.rule_id and b.rule_id and a.rule_id == b.rule_id:
            return True

        # Normalized principle match
        p_a = a.principle.lower().strip()
        p_b = b.principle.lower().strip()
        if p_a == p_b and p_a:
            return True

        # High keyword overlap in description (> 60%)
        words_a = set(a.description.lower().split())
        words_b = set(b.description.lower().split())
        if words_a and words_b:
            overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
            if overlap >= 0.6:
                return True

        return False

    @staticmethod
    def _cluster_signature(f: AssessmentFinding) -> str:
        """Create a human-readable signature for the cluster."""
        return f"{f.file}:{f.line or 0}:{f.rule_id}:{f.principle}"
