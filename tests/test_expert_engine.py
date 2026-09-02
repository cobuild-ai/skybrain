"""Unit tests for SkyBrain ExpertEngine, ExpertLens, and 2/3 Consensus Voter.

Validates the decoupling of knowledge layers, mechanical injection,
and strict 2/3 majority consensus filtering.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from skybrain.expert.engine import ExpertEngine
from skybrain.expert.models import (
    AssessmentFinding,
    ConsensusVerdict,
    EvaluationCriterion,
    ExpertLens,
    Severity,
)
from skybrain.expert.registry import LensRegistry
from skybrain.expert.specs import (
    CLEAN_ARCHITECTURE_LENS,
    CLEAN_CODE_LENS,
    TEST_RULES_LENS,
)
from skybrain.expert.voter import ConsensusVoter


# ── Helper Factory ──────────────────────────────────────────

def make_finding(
    *,
    line: int = 42,
    rule_id: str = "CC-SRP-001",
    principle: str = "Single Responsibility",
    description: str = "Violates SRP",
    severity: Severity = Severity.HIGH,
    lens_id: str = "clean_code_v1",
) -> AssessmentFinding:
    return AssessmentFinding(
        file="app.py",
        line=line,
        rule_id=rule_id,
        principle=principle,
        description=description,
        suggestion="Refactor",
        severity=severity,
        lens_id=lens_id,
    )


# ═══════════════════════════════════════════════════════════════
#  1. ExpertLens & Prompt Spec Formatting Tests
# ═══════════════════════════════════════════════════════════════

class TestExpertLensSpec:
    """Verify that ExpertLens specs are decoupled and formatted cleanly."""

    def test_lens_prompt_spec_contains_atomic_questions(self):
        lens = CLEAN_CODE_LENS
        spec = lens.format_prompt_spec()

        assert "Clean Code" in spec
        assert "CC-SRP-001" in spec
        assert "Negative Signals:" in spec
        assert "manager" in spec
        assert "Positive Signals:" in spec

    def test_lens_immutability(self):
        lens = CLEAN_ARCHITECTURE_LENS
        with pytest.raises(AttributeError):
            lens.name = "Mutated"  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════
#  2. LensRegistry Tests
# ═══════════════════════════════════════════════════════════════

class TestLensRegistry:
    """Verify dynamic registry lookup and JSON loading."""

    def test_default_registry_contains_standard_lenses(self):
        reg = LensRegistry()
        all_l = reg.all_lenses()
        assert len(all_l) >= 6

    def test_get_by_domain_search(self):
        reg = LensRegistry()
        arch_lenses = reg.get_by_name_or_domain("architecture")
        assert len(arch_lenses) >= 1
        assert arch_lenses[0].lens_id == "clean_arch_v1"

    def test_load_custom_lens_from_json(self, tmp_path):
        json_file = tmp_path / "custom_lens.json"
        data = {
            "lens_id": "compose_ui_v1",
            "name": "Compose UI Guidelines",
            "domain": "android",
            "persona": "Android Jetpack Compose Architect",
            "criteria": [
                {
                    "rule_id": "CMP-STA-001",
                    "name": "State Hoisting",
                    "question": "Does this composable manage internal state instead of hoisting?",
                    "negative_signals": ["remember { mutableStateOf } inside reusable widget"],
                    "positive_signals": ["stateless composable", "onEvent callback"],
                    "severity": "HIGH",
                }
            ],
        }
        json_file.write_text(json.dumps(data))

        reg = LensRegistry(initial_lenses=[])
        lens = reg.load_from_json(json_file)

        assert lens.lens_id == "compose_ui_v1"
        assert len(lens.criteria) == 1
        assert lens.criteria[0].severity == Severity.HIGH


# ═══════════════════════════════════════════════════════════════
#  3. 2/3 Consensus Voter Tests
# ═══════════════════════════════════════════════════════════════

class TestConsensusVoter:
    """Verify the 2/3 majority consensus filtering."""

    def test_two_out_of_three_votes_accepted(self):
        voter = ConsensusVoter()
        # 2 findings for the same defect out of 3 expected votes (66.7%)
        f1 = make_finding(line=10, description="Bad naming")
        f2 = make_finding(line=11, description="Bad naming variable")  # within tolerance ±3

        accepted, rejected, items = voter.vote([f1, f2], expected_total_votes=3)

        assert len(accepted) == 1
        assert len(rejected) == 0
        assert items[0].verdict == ConsensusVerdict.ACCEPTED
        assert items[0].favorable_votes == 2
        assert items[0].vote_ratio == pytest.approx(0.667, rel=1e-2)

    def test_three_out_of_three_votes_accepted(self):
        voter = ConsensusVoter()
        f1 = make_finding(line=20)
        f2 = make_finding(line=20)
        f3 = make_finding(line=20)

        accepted, rejected, items = voter.vote([f1, f2, f3], expected_total_votes=3)

        assert len(accepted) == 1
        assert len(rejected) == 0
        assert items[0].verdict == ConsensusVerdict.ACCEPTED
        assert items[0].vote_ratio == 1.0

    def test_one_out_of_three_votes_rejected_as_noise(self):
        voter = ConsensusVoter()
        # Only 1 vote out of 3 (33.3% < 66.7%) -> Filtered out as false positive
        f1 = make_finding(line=100, description="Random false positive")

        accepted, rejected, items = voter.vote([f1], expected_total_votes=3)

        assert len(accepted) == 0
        assert len(rejected) == 1
        assert items[0].verdict == ConsensusVerdict.REJECTED
        assert items[0].favorable_votes == 1
        assert items[0].vote_ratio == pytest.approx(0.333, rel=1e-2)

    def test_distant_lines_not_clustered(self):
        voter = ConsensusVoter(line_tolerance=3)
        f1 = make_finding(line=10)
        f2 = make_finding(line=50)  # Beyond ±3 tolerance

        accepted, rejected, items = voter.vote([f1, f2], expected_total_votes=3)

        # Both are separate clusters with 1 vote each -> Both rejected
        assert len(accepted) == 0
        assert len(rejected) == 2
        assert len(items) == 2


# ═══════════════════════════════════════════════════════════════
#  4. ExpertEngine Orchestration Tests
# ═══════════════════════════════════════════════════════════════

class TestExpertEngine:
    """Verify that ExpertEngine injects specs and applies consensus correctly."""

    def test_evaluate_file_with_consensus(self, tmp_path):
        sample_code = tmp_path / "service.py"
        sample_code.write_text("class GodManager:\n    def do_all(self): pass\n")

        # Mock LLM returning SRP finding on 2 of 3 rounds
        finding_json = json.dumps([
            {
                "line": 1,
                "rule_id": "CC-SRP-001",
                "principle": "Single Responsibility Principle",
                "description": "GodManager has multiple reasons to change",
                "suggestion": "Split into cohesive classes",
                "severity": "HIGH",
            }
        ])
        empty_json = "[]"

        mock_client = MagicMock()
        # Round 1: finding, Round 2: finding, Round 3: empty (2/3 majority)
        mock_client.query.side_effect = [finding_json, finding_json, empty_json]

        engine = ExpertEngine(client=mock_client)
        report = engine.evaluate_file(
            file_path=sample_code,
            lenses=[CLEAN_CODE_LENS],
            rounds_per_lens=3,
        )

        assert len(report.accepted_findings) == 1
        assert report.accepted_findings[0].rule_id == "CC-SRP-001"
        assert report.stats["HIGH"] == 1
        assert report.total_evaluations == 3

    def test_evaluate_rejects_single_hallucination(self, tmp_path):
        sample_code = tmp_path / "pure.py"
        sample_code.write_text("def add(a: int, b: int) -> int: return a + b\n")

        finding_json = json.dumps([
            {
                "line": 1,
                "rule_id": "CC-SRP-001",
                "principle": "Single Responsibility",
                "description": "Hallucinated issue",
                "suggestion": "Do nothing",
                "severity": "LOW",
            }
        ])

        mock_client = MagicMock()
        # Round 1: hallucinated, Round 2: empty, Round 3: empty (1/3 -> REJECTED)
        mock_client.query.side_effect = [finding_json, "[]", "[]"]

        engine = ExpertEngine(client=mock_client)
        report = engine.evaluate_file(
            file_path=sample_code,
            lenses=[CLEAN_CODE_LENS],
            rounds_per_lens=3,
        )

        assert len(report.accepted_findings) == 0
        assert len(report.rejected_findings) == 1  # Successfully quarantined
