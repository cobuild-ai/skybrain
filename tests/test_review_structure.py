import pytest
import json
from skybrain.review.models import (
    Finding,
    Severity,
    Category,
    LensResult,
    AggregatedReport,
)


class TestReviewStructureForLeadLLM:
    def test_aggregated_report_lead_llm_payload(self):
        f1 = Finding(
            file="skybrain/core/engine.py",
            line=42,
            severity=Severity.HIGH,
            category=Category.CLEAN_CODE,
            principle_violated="Single Responsibility Principle",
            description="Class combines inference engine with network transport.",
            suggestion="Extract network transport to dedicated client.",
            confidence=0.85,
            verified=True,
        )
        f2 = Finding(
            file="skybrain/core/engine.py",
            line=99,
            severity=Severity.MEDIUM,
            category=Category.PERFORMANCE,
            principle_violated="Resource Leak Prevention",
            description="Unclosed file descriptor during weight scan.",
            suggestion="Use with statement for context management.",
            confidence=0.90,
            verified=True,
        )

        lens_res = LensResult(
            lens_name="CleanCodeLens",
            category=Category.CLEAN_CODE,
            file_path="skybrain/core/engine.py",
            findings=[f1, f2],
            execution_time_ms=150.0,
        )

        report = AggregatedReport(
            lens_results=[lens_res],
            verified_findings=[f1, f2],
            total_files_reviewed=1,
            total_lenses_applied=1,
        )

        payload = report.to_lead_llm_payload()
        assert payload["status"] == "ready_for_lead_llm_cross_check"
        assert 0 <= payload["health_score"] <= 100
        assert payload["total_findings"] == 2
        assert len(payload["findings"]) == 2

        # Check finding structure for Lead LLM parsing
        finding0 = payload["findings"][0]
        assert finding0["finding_id"] == "PRE-01"
        assert finding0["severity"] == "HIGH"
        assert finding0["file"] == "skybrain/core/engine.py"
        assert finding0["line"] == 42
        assert "lead_llm_cross_check_prompt" in finding0
        assert "Check 'skybrain/core/engine.py' line 42" in finding0["lead_llm_cross_check_prompt"]

        # Validate that payload serializes to clean, valid JSON with 0 HTML tags
        json_str = json.dumps(payload, ensure_ascii=False)
        assert "<html" not in json_str
        assert "<body" not in json_str
        assert "glassmorphism" not in json_str
