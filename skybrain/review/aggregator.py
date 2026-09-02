"""Finding Aggregator — Deduplication and prioritization.

Merges findings from multiple lens passes into a unified report,
removing duplicates and sorting by severity for actionable output.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from skybrain.review.models import AggregatedReport, Finding, LensResult

logger = logging.getLogger("skybrain.review.aggregator")

# Findings within this line proximity targeting the same file are
# considered potential duplicates and compared by description similarity.
LINE_PROXIMITY_THRESHOLD = 3


class FindingAggregator:
    """Merges, deduplicates, and prioritizes findings from all lenses.

    Deduplication strategy:
      - Same file + lines within ±3 + similar description → merge
      - Keep the higher severity version when merging
      - Preserve provenance (which lenses found it)
    """

    def aggregate(self, lens_results: list[LensResult]) -> AggregatedReport:
        """Combine all lens results into a single AggregatedReport."""
        all_findings: list[Finding] = []
        for result in lens_results:
            all_findings.extend(result.findings)

        deduplicated = self._deduplicate(all_findings)

        verified = [f for f in deduplicated if f.verified]
        unverified = [f for f in deduplicated if not f.verified]

        unique_files = {r.file_path for r in lens_results}

        return AggregatedReport(
            lens_results=lens_results,
            verified_findings=sorted(
                verified, key=lambda f: f.severity, reverse=True
            ),
            unverified_findings=sorted(
                unverified, key=lambda f: f.severity, reverse=True
            ),
            total_files_reviewed=len(unique_files),
            total_lenses_applied=len(lens_results),
        )

    def _deduplicate(self, findings: list[Finding]) -> list[Finding]:
        """Remove near-duplicate findings based on file + line proximity."""
        if not findings:
            return []

        # Group by file
        by_file: dict[str, list[Finding]] = defaultdict(list)
        for f in findings:
            by_file[f.file].append(f)

        unique: list[Finding] = []
        for file_findings in by_file.values():
            unique.extend(self._deduplicate_within_file(file_findings))

        return unique

    def _deduplicate_within_file(
        self, findings: list[Finding]
    ) -> list[Finding]:
        """Deduplicate findings within a single file."""
        if len(findings) <= 1:
            return findings

        # Sort by line number for proximity comparison
        sorted_findings = sorted(
            findings, key=lambda f: (f.line or 0, f.severity)
        )

        unique: list[Finding] = [sorted_findings[0]]
        for current in sorted_findings[1:]:
            is_duplicate = False
            for existing in unique:
                if self._is_near_duplicate(existing, current):
                    is_duplicate = True
                    # Keep the higher severity or verified version
                    if (
                        current.severity > existing.severity
                        or (current.verified and not existing.verified)
                    ):
                        unique.remove(existing)
                        unique.append(current)
                    break
            if not is_duplicate:
                unique.append(current)

        return unique

    @staticmethod
    def _is_near_duplicate(a: Finding, b: Finding) -> bool:
        """Check if two findings are near-duplicates."""
        # Different files → not duplicate
        if a.file != b.file:
            return False

        # Lines too far apart → not duplicate
        if a.line is not None and b.line is not None:
            if abs(a.line - b.line) > LINE_PROXIMITY_THRESHOLD:
                return False

        # Same principle → likely duplicate
        if a.principle_violated == b.principle_violated:
            return True

        # High description overlap → likely duplicate
        a_words = set(a.description.lower().split())
        b_words = set(b.description.lower().split())
        if not a_words or not b_words:
            return False
        overlap = len(a_words & b_words) / min(len(a_words), len(b_words))
        return overlap > 0.6
