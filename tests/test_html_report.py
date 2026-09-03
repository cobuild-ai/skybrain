import pytest
from pathlib import Path
from skybrain.review.html_report import generate_html_report, calculate_health_score
from skybrain.review.models import AggregatedReport, Finding, Severity, Category, LensResult


def test_calculate_health_score():
    assert calculate_health_score({}) == 100
    assert calculate_health_score({"CRITICAL": 1}) == 75
    assert calculate_health_score({"HIGH": 2}) == 80
    assert calculate_health_score({"CRITICAL": 4}) == 0


def test_generate_html_report_creates_valid_file(tmp_path):
    f1 = Finding(
        file="skybrain/server/supervisor.py",
        line=42,
        severity=Severity.HIGH,
        category=Category.SECURITY,
        principle_violated="CWE-78: Command Injection Risk",
        description="subprocess.Popen should use safe args list",
        suggestion="Use list of args without shell=True",
        confidence=0.95,
        verified=True,
    )
    f2 = Finding(
        file="skybrain/core/config.py",
        line=10,
        severity=Severity.LOW,
        category=Category.CLEAN_CODE,
        principle_violated="PEP 8 naming convention",
        description="Variable name is too generic",
        suggestion="Rename to settings_path",
        confidence=0.90,
        verified=True,
    )

    report = AggregatedReport(
        lens_results=[
            LensResult(lens_name="Security", category=Category.SECURITY, file_path="skybrain/server/supervisor.py", findings=[f1]),
            LensResult(lens_name="CleanCode", category=Category.CLEAN_CODE, file_path="skybrain/core/config.py", findings=[f2]),
        ],
        verified_findings=[f1, f2],
        total_files_reviewed=2,
        total_lenses_applied=4,
    )

    out_file = tmp_path / "custom_report.html"
    generated_path = generate_html_report(report, target_label="skybrain/core", output_path=out_file)

    assert generated_path.exists()
    content = generated_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "SkyBrain Code Intelligence Report" in content
    assert "CWE-78: Command Injection Risk" in content
    assert "Rename to settings_path" in content
    assert "89" in content  # 100 - 10 (HIGH) - 1 (LOW) = 89
