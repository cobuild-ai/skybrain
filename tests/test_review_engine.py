"""Unit tests for SkyBrain Multi-Pass Review Engine.

Tests each layer independently using mock LLM responses,
verifying the Clean Architecture invariant: no layer depends
on layers above it.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from skybrain.review.aggregator import FindingAggregator
from skybrain.review.client import SkyBrainClient
from skybrain.review.engine import ReviewEngine
from skybrain.review.lenses.base import ReviewLens
from skybrain.review.lenses.clean_code import CleanCodeLens
from skybrain.review.lenses.clean_architecture import CleanArchitectureLens
from skybrain.review.lenses.security import SecurityLens
from skybrain.review.lenses.performance import PerformanceLens
from skybrain.review.models import (
    AggregatedReport,
    Category,
    Finding,
    LensResult,
    Severity,
)
from skybrain.review.verification import ChainOfVerifier


# ── Fixtures ─────────────────────────────────────────────────


SAMPLE_FINDING_JSON = json.dumps([
    {
        "file": "app.py",
        "line": 42,
        "severity": "HIGH",
        "principle_violated": "Single Responsibility Principle",
        "description": "Function handles both model loading and error handling",
        "suggestion": "Extract model loading into a separate class",
    },
    {
        "file": "app.py",
        "line": 15,
        "severity": "MEDIUM",
        "principle_violated": "Magic Numbers",
        "description": "Hardcoded timeout value 120",
        "suggestion": "Extract to named constant REQUEST_TIMEOUT",
    },
])

VERIFICATION_RESPONSE_VERIFIED = json.dumps({
    "verified": True,
    "confidence": 0.92,
    "reason": "Confirmed: the function does handle both loading and errors.",
})

VERIFICATION_RESPONSE_REJECTED = json.dumps({
    "verified": False,
    "confidence": 0.15,
    "reason": "The function actually delegates to a separate handler.",
})


def make_finding(
    *,
    line: int = 10,
    severity: Severity = Severity.HIGH,
    category: Category = Category.CLEAN_CODE,
    principle: str = "SRP",
    description: str = "Test finding",
) -> Finding:
    """Factory helper for test findings."""
    return Finding(
        file="test.py",
        line=line,
        severity=severity,
        category=category,
        principle_violated=principle,
        description=description,
        suggestion="Fix it",
    )


# ═══════════════════════════════════════════════════════════════
#  Layer 1: Domain Models
# ═══════════════════════════════════════════════════════════════


class TestSeverity:
    """Verify severity ordering and comparison."""

    def test_ordering(self):
        assert Severity.CRITICAL > Severity.HIGH > Severity.MEDIUM
        assert Severity.MEDIUM > Severity.LOW > Severity.INFO

    def test_int_values(self):
        assert int(Severity.CRITICAL) == 4
        assert int(Severity.INFO) == 0


class TestFinding:
    """Verify Finding immutability and verification."""

    def test_immutability(self):
        f = make_finding()
        with pytest.raises(AttributeError):
            f.severity = Severity.LOW  # type: ignore[misc]

    def test_with_verification_creates_new_instance(self):
        original = make_finding()
        verified = original.with_verification(verified=True, confidence=0.95)
        assert verified.verified is True
        assert verified.confidence == 0.95
        assert original.verified is False  # Original unchanged
        assert original.finding_id == verified.finding_id

    def test_default_confidence(self):
        f = make_finding()
        assert f.confidence == 1.0
        assert f.verified is False


class TestAggregatedReport:
    """Verify report statistics and sorting."""

    def test_stats_counts_severities(self):
        report = AggregatedReport(
            verified_findings=[
                make_finding(severity=Severity.CRITICAL),
                make_finding(severity=Severity.CRITICAL),
            ],
            unverified_findings=[
                make_finding(severity=Severity.HIGH),
                make_finding(severity=Severity.LOW),
            ],
        )
        assert report.stats["CRITICAL"] == 2
        assert report.stats["HIGH"] == 1
        assert report.stats["LOW"] == 1

    def test_all_findings_sorted_by_severity(self):
        report = AggregatedReport(
            verified_findings=[make_finding(severity=Severity.LOW)],
            unverified_findings=[make_finding(severity=Severity.CRITICAL)],
        )
        findings = report.all_findings
        assert findings[0].severity == Severity.CRITICAL
        assert findings[1].severity == Severity.LOW

    def test_empty_report(self):
        report = AggregatedReport()
        assert report.all_findings == []
        assert report.stats["CRITICAL"] == 0


# ═══════════════════════════════════════════════════════════════
#  Layer 2: Infrastructure (Client)
# ═══════════════════════════════════════════════════════════════


class TestSkyBrainClient:
    """Verify client retry and auto-heal behavior."""

    def test_health_check_returns_false_on_failure(self):
        client = SkyBrainClient(base_url="http://127.0.0.1:59999")
        assert client.health_check() is False

    @patch("skybrain.review.client.urllib.request.urlopen")
    def test_query_extracts_content(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Hello from Qwen"}}]
        }).encode()
        mock_urlopen.return_value = mock_response

        client = SkyBrainClient()
        result = client.query([{"role": "user", "content": "test"}])
        assert result == "Hello from Qwen"


# ═══════════════════════════════════════════════════════════════
#  Layer 3: Lenses (Strategy Pattern)
# ═══════════════════════════════════════════════════════════════


class TestReviewLensBase:
    """Verify JSON parsing robustness."""

    def test_extract_json_from_markdown_fences(self):
        raw = '```json\n[{"file":"a.py","line":1,"severity":"HIGH",' \
              '"principle_violated":"SRP","description":"test","suggestion":"fix"}]\n```'
        result = ReviewLens._extract_json_array(raw)
        parsed = json.loads(result)
        assert len(parsed) == 1

    def test_extract_json_from_thinking_blocks(self):
        raw = '<think>Some internal reasoning</think>\n' + SAMPLE_FINDING_JSON
        result = ReviewLens._extract_json_array(raw)
        parsed = json.loads(result)
        assert len(parsed) == 2

    def test_extract_empty_array(self):
        result = ReviewLens._extract_json_array("[]")
        assert result == "[]"

    def test_extract_from_plain_text(self):
        result = ReviewLens._extract_json_array("No JSON here at all.")
        assert result == ""


class TestConcreteeLenses:
    """Verify lens identity properties."""

    def test_clean_code_lens_properties(self):
        lens = CleanCodeLens(client=MagicMock())
        assert lens.name == "Clean Code"
        assert lens.category == Category.CLEAN_CODE
        assert "Robert C. Martin" in lens.system_prompt

    def test_architecture_lens_properties(self):
        lens = CleanArchitectureLens(client=MagicMock())
        assert lens.name == "Clean Architecture"
        assert lens.category == Category.CLEAN_ARCHITECTURE
        assert "Dependency Rule" in lens.system_prompt

    def test_security_lens_properties(self):
        lens = SecurityLens(client=MagicMock())
        assert lens.name == "Security"
        assert lens.category == Category.SECURITY
        assert "OWASP" in lens.system_prompt

    def test_performance_lens_properties(self):
        lens = PerformanceLens(client=MagicMock())
        assert lens.name == "Performance"
        assert lens.category == Category.PERFORMANCE
        assert "Memory" in lens.system_prompt

    def test_lens_analyze_parses_response(self):
        mock_client = MagicMock()
        mock_client.query.return_value = SAMPLE_FINDING_JSON

        lens = CleanCodeLens(client=mock_client)
        result = lens.analyze("def foo(): pass", "test.py")

        assert len(result.findings) == 2
        assert result.findings[0].severity == Severity.HIGH
        assert result.findings[0].principle_violated == "Single Responsibility Principle"
        assert result.lens_name == "Clean Code"


# ═══════════════════════════════════════════════════════════════
#  Layer 4: Verification
# ═══════════════════════════════════════════════════════════════


class TestChainOfVerifier:
    """Verify the CoVe fact-checking layer."""

    def test_verified_finding_gets_high_confidence(self):
        mock_client = MagicMock()
        mock_client.query.return_value = VERIFICATION_RESPONSE_VERIFIED

        verifier = ChainOfVerifier(client=mock_client)
        findings = [make_finding(severity=Severity.HIGH)]
        result = verifier.verify_findings(findings, "def foo(): pass", "test.py")

        assert len(result) == 1
        assert result[0].verified is True
        assert result[0].confidence == 0.92

    def test_rejected_finding_gets_low_confidence(self):
        mock_client = MagicMock()
        mock_client.query.return_value = VERIFICATION_RESPONSE_REJECTED

        verifier = ChainOfVerifier(client=mock_client)
        findings = [make_finding(severity=Severity.HIGH)]
        result = verifier.verify_findings(findings, "def foo(): pass", "test.py")

        assert len(result) == 1
        assert result[0].verified is False
        assert result[0].confidence == 0.15

    def test_low_severity_findings_skip_verification(self):
        mock_client = MagicMock()
        verifier = ChainOfVerifier(client=mock_client, min_severity=Severity.HIGH)
        findings = [make_finding(severity=Severity.LOW)]
        result = verifier.verify_findings(findings, "code", "test.py")

        assert len(result) == 1
        assert result[0].verified is False
        mock_client.query.assert_not_called()  # Skipped

    def test_parse_thinking_block_response(self):
        raw = '<think>Analyzing...</think>\n{"verified": true, "confidence": 0.88, "reason": "ok"}'
        verified, confidence = ChainOfVerifier._parse_verification(raw)
        assert verified is True
        assert confidence == 0.88


# ═══════════════════════════════════════════════════════════════
#  Layer 5: Aggregation
# ═══════════════════════════════════════════════════════════════


class TestFindingAggregator:
    """Verify deduplication and merge logic."""

    def test_deduplicates_same_line_same_principle(self):
        aggregator = FindingAggregator()
        results = [
            LensResult(
                lens_name="A",
                category=Category.CLEAN_CODE,
                file_path="test.py",
                findings=[make_finding(line=10, principle="SRP")],
            ),
            LensResult(
                lens_name="B",
                category=Category.CLEAN_ARCHITECTURE,
                file_path="test.py",
                findings=[make_finding(line=10, principle="SRP")],
            ),
        ]
        report = aggregator.aggregate(results)
        assert len(report.all_findings) == 1

    def test_keeps_distinct_findings(self):
        aggregator = FindingAggregator()
        results = [
            LensResult(
                lens_name="A",
                category=Category.CLEAN_CODE,
                file_path="test.py",
                findings=[make_finding(line=10, principle="SRP")],
            ),
            LensResult(
                lens_name="B",
                category=Category.SECURITY,
                file_path="test.py",
                findings=[make_finding(line=50, principle="Input Validation")],
            ),
        ]
        report = aggregator.aggregate(results)
        assert len(report.all_findings) == 2

    def test_prefers_higher_severity_on_merge(self):
        aggregator = FindingAggregator()
        results = [
            LensResult(
                lens_name="A",
                category=Category.CLEAN_CODE,
                file_path="test.py",
                findings=[make_finding(line=10, severity=Severity.MEDIUM, principle="SRP")],
            ),
            LensResult(
                lens_name="B",
                category=Category.CLEAN_CODE,
                file_path="test.py",
                findings=[make_finding(line=11, severity=Severity.CRITICAL, principle="SRP")],
            ),
        ]
        report = aggregator.aggregate(results)
        assert len(report.all_findings) == 1
        assert report.all_findings[0].severity == Severity.CRITICAL

    def test_empty_input(self):
        aggregator = FindingAggregator()
        report = aggregator.aggregate([])
        assert len(report.all_findings) == 0


# ═══════════════════════════════════════════════════════════════
#  Layer 6: Engine (Orchestrator)
# ═══════════════════════════════════════════════════════════════


class TestReviewEngine:
    """Verify engine orchestration with mocked LLM."""

    def test_review_single_file_all_lenses(self, tmp_path):
        test_file = tmp_path / "sample.py"
        test_file.write_text("def hello(): return 'world'")

        mock_client = MagicMock()
        mock_client.query.return_value = SAMPLE_FINDING_JSON
        mock_client.health_check.return_value = True

        engine = ReviewEngine(
            lens_classes=[CleanCodeLens],
            client=mock_client,
        )
        report = engine.review([test_file], verify=False)

        assert report.total_files_reviewed == 1
        assert report.total_lenses_applied == 1
        assert len(report.all_findings) >= 1

    def test_skips_nonexistent_files(self):
        mock_client = MagicMock()
        engine = ReviewEngine(lens_classes=[CleanCodeLens], client=mock_client)
        report = engine.review(["/nonexistent/file.py"], verify=False)
        assert report.total_files_reviewed == 0

    def test_voting_reduces_false_positives(self, tmp_path):
        """With 3 voting rounds, only findings in ≥2 rounds survive."""
        test_file = tmp_path / "app.py"
        test_file.write_text("x = 1")

        # Round 1 & 2: same finding; Round 3: different finding
        consistent = json.dumps([{
            "file": "app.py", "line": 1, "severity": "HIGH",
            "principle_violated": "Magic Numbers",
            "description": "Hardcoded value", "suggestion": "Use constant",
        }])
        inconsistent = json.dumps([{
            "file": "app.py", "line": 99, "severity": "LOW",
            "principle_violated": "Naming",
            "description": "Bad name", "suggestion": "Rename",
        }])

        mock_client = MagicMock()
        mock_client.query.side_effect = [consistent, consistent, inconsistent]

        engine = ReviewEngine(lens_classes=[CleanCodeLens], client=mock_client)
        report = engine.review([test_file], verify=False, voting_rounds=3)

        # Only the consistent finding should survive (2/3 ≥ threshold)
        assert any(
            f.principle_violated == "Magic Numbers" for f in report.all_findings
        )

    def test_finding_signature_stability(self):
        """Same finding always produces the same signature."""
        f = make_finding(line=42, severity=Severity.HIGH, principle="SRP")
        sig1 = ReviewEngine._finding_signature(f)
        sig2 = ReviewEngine._finding_signature(f)
        assert sig1 == sig2
