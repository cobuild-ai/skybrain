import pytest
from pathlib import Path
from skybrain.journal.generator import generate_daily_journal, collect_git_summary
from skybrain.cli.commit_helper import generate_commit_and_briefing
from skybrain.cli.inspect_helper import extract_code_skeleton, inspect_file
from skybrain.cli.testgen_helper import generate_test_scaffold

def test_generate_daily_journal_rule_based():
    journal_md = generate_daily_journal(
        date_str="2026-09-19",
        topic="Gemma 4 E2B 단일 표준 모델 아키텍처 확립",
        git_context="Recent Commits:\n21ddba3 feat(agent,ime): standardize on Gemma 4 E2B",
        extra_notes="Snapdragon 8 Gen 1 빅코어 4개 가속 적용 (2.02s)",
        use_slm=False
    )

    # 1. Obsidian Frontmatter 검증
    assert journal_md.startswith("---")
    assert "date: 2026-09-19" in journal_md
    assert "tags: " in journal_md

    # 2. H1 제목 및 3대 필수 섹션 검증
    assert "# 2026-09-19: Gemma 4 E2B 단일 표준 모델 아키텍처 확립" in journal_md
    assert "## 🚀 주요 업무 내용" in journal_md
    assert "## 📝 AI Insight (#from-ai)" in journal_md
    assert "## 🔗 관련 문서 및 링크" in journal_md
    assert "[[GEMINI.md]]" in journal_md


def test_generate_commit_and_briefing_rule_based():
    diff_sample = """diff --git a/deartalk-android/src/main/java/ai/deartalk/android/agent/DearTalkIntentEngine.kt b/deartalk-android/src/main/java/ai/deartalk/android/agent/DearTalkIntentEngine.kt
--- a/deartalk-android/src/main/java/ai/deartalk/android/agent/DearTalkIntentEngine.kt
+++ b/deartalk-android/src/main/java/ai/deartalk/android/agent/DearTalkIntentEngine.kt
@@ -10,3 +10,3 @@
- val old = 1
+ val new = 2
"""
    res = generate_commit_and_briefing(diff_sample, focus_hint="optimize inference speed", use_slm=False)
    assert "commit_msg" in res
    assert "briefing" in res
    assert "refactor(android): optimize inference speed" in res["commit_msg"]
    assert "- 📝 **변경 핵심**:" in res["briefing"]
    assert "- 📱 **영향 범위**:" in res["briefing"]
    assert "- 🧪 **사전 검증**:" in res["briefing"]
    assert "- 🌐 **거버넌스 준수**:" in res["briefing"]


def test_extract_code_skeleton_kotlin(tmp_path):
    kt_code = """package ai.deartalk.android

import android.os.Bundle

class TestEngine(private val count: Int) {
    const val DEFAULT_TIMEOUT = 5000L
    
    fun processText(input: String): String {
        return input.trim()
    }
    
    suspend fun executeAsync(): Boolean {
        return true
    }
}
"""
    kt_file = tmp_path / "TestEngine.kt"
    kt_file.write_text(kt_code)

    skeleton = extract_code_skeleton(kt_code, kt_file)
    assert "class TestEngine" in skeleton
    assert "fun processText" in skeleton
    assert "suspend fun executeAsync" in skeleton
    assert "package ai.deartalk.android" not in skeleton  # 패키지/import는 생략


def test_generate_test_scaffold_kotlin(tmp_path):
    kt_file = tmp_path / "SampleHelper.kt"
    kt_file.write_text("class SampleHelper { fun calculate(): Int = 42 }")

    scaffold = generate_test_scaffold(kt_file, use_slm=False)
    assert "class SampleHelperTest" in scaffold
    assert "@Test" in scaffold
    assert "testBasicFunctionality" in scaffold


def test_extract_code_skeleton_python(tmp_path):
    py_code = """import os
import sys

class DataProcessor:
    def __init__(self, name: str):
        self.name = name

    def process(self, items: list) -> int:
        return len(items)

    async def fetch_remote(self, url: str) -> dict:
        return {}
"""
    py_file = tmp_path / "processor.py"
    py_file.write_text(py_code)

    skeleton = extract_code_skeleton(py_code, py_file)
    assert "class DataProcessor:" in skeleton
    assert "def __init__" in skeleton
    assert "def process" in skeleton
    assert "async def fetch_remote" in skeleton
    assert "import os" not in skeleton  # 임포트 생략 검증


def test_generate_test_scaffold_python(tmp_path):
    py_file = tmp_path / "validator.py"
    py_file.write_text("def validate_input(val: str) -> bool:\n    return bool(val)\n")

    scaffold = generate_test_scaffold(py_file, use_slm=False)
    assert "import pytest" in scaffold
    assert "def test_validator_basic():" in scaffold
    assert "def test_validator_edge_cases():" in scaffold


