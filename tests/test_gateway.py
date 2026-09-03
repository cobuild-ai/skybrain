"""Tests for skybrain.gateway — Intent Classifier, Conversation History, and Routing Stats."""

import json
import tempfile
from pathlib import Path

import pytest

from skybrain.gateway import (
    ClassificationResult,
    ConversationHistory,
    ConversationTurn,
    IntentClassifier,
    RoutingStats,
    RoutingTarget,
)


# ═══════════════════════════════════════════════════════════════
#  IntentClassifier Tests
# ═══════════════════════════════════════════════════════════════


class TestIntentClassifier:
    """Test suite for rule-based intent classification."""

    @pytest.fixture
    def classifier(self):
        return IntentClassifier()

    # ── LOCAL routing tests ──

    @pytest.mark.parametrize("prompt,expected_rule", [
        ("이 텍스트를 영어로 번역해줘", "translate"),
        ("Translate this to Korean", "translate"),
        ("이 빌드 로그 요약해줘", "log_summary"),
        ("Summarize this error traceback", "log_summary"),
        ("안녕하세요", "simple_qa"),
        ("Hello, what is Python?", "simple_qa"),
        ("DTO 보일러플레이트 생성해줘", "boilerplate"),
        ("Generate a docstring draft", "boilerplate"),
        ("이 내용 요약해줘", "summarize"),
        ("코드 리뷰 해줘", "code_review"),
    ])
    def test_local_routing(self, classifier, prompt, expected_rule):
        result = classifier.classify(prompt)
        assert result.target == RoutingTarget.LOCAL
        assert result.matched_rule == expected_rule
        assert result.confidence >= 0.8

    # ── CLOUD routing tests ──

    @pytest.mark.parametrize("prompt,expected_rule", [
        ("아키텍처 리팩토링 해줘", "architecture"),
        ("git push origin main", "git_ops"),
        ("PR 생성해줘", "git_ops"),
        ("시스템 설계 전략을 분석해줘", "complex_reasoning"),
    ])
    def test_cloud_routing(self, classifier, prompt, expected_rule):
        result = classifier.classify(prompt)
        assert result.target == RoutingTarget.CLOUD
        assert result.matched_rule == expected_rule

    # ── Short prompt heuristic ──

    def test_short_prompt_defaults_local(self, classifier):
        result = classifier.classify("hi")
        # "hi" matches simple_qa, so should be LOCAL
        assert result.target == RoutingTarget.LOCAL

    def test_very_short_unknown_prompt(self, classifier):
        result = classifier.classify("xyz")
        assert result.target == RoutingTarget.LOCAL  # Short heuristic
        assert result.confidence < 0.8

    # ── Uncertain / long prompts ──

    def test_long_ambiguous_prompt(self, classifier):
        long_prompt = "a " * 60  # > 100 chars, no pattern match
        result = classifier.classify(long_prompt)
        assert result.target == RoutingTarget.UNCERTAIN

    # ── Classification result structure ──

    def test_classification_result_is_frozen(self, classifier):
        result = classifier.classify("번역해줘")
        assert isinstance(result, ClassificationResult)
        with pytest.raises(AttributeError):
            result.target = RoutingTarget.CLOUD  # type: ignore


# ═══════════════════════════════════════════════════════════════
#  ConversationHistory Tests
# ═══════════════════════════════════════════════════════════════


class TestConversationHistory:
    """Test suite for cross-channel conversation history ring."""

    @pytest.fixture
    def history(self, tmp_path):
        return ConversationHistory(history_dir=tmp_path / "history", max_turns=5)

    def test_add_and_retrieve(self, history):
        history.add("user", "Hello", channel="terminal")
        history.add("assistant", "Hi there!", engine="skybrain")

        assert history.total_turns == 2
        recent = history.get_recent(10)
        assert len(recent) == 2
        assert recent[0].role == "user"
        assert recent[1].content == "Hi there!"

    def test_fifo_eviction(self, history):
        for i in range(10):
            history.add("user", f"message {i}")

        assert history.total_turns == 5  # max_turns=5
        recent = history.get_recent(5)
        assert recent[0].content == "message 5"
        assert recent[-1].content == "message 9"

    def test_persistence(self, tmp_path):
        dir_path = tmp_path / "history_persist"

        # Write session
        h1 = ConversationHistory(history_dir=dir_path, max_turns=10)
        h1.add("user", "persist test", channel="ide", engine="gemini")
        h1.add("assistant", "persisted!", engine="skybrain")

        # Read session (new instance, same dir)
        h2 = ConversationHistory(history_dir=dir_path, max_turns=10)
        assert h2.total_turns == 2
        assert h2.get_recent(1)[0].content == "persisted!"
        assert h2.get_recent(2)[0].channel == "ide"

    def test_context_string_format(self, history):
        history.add("user", "이 로그 분석해줘", channel="terminal")
        history.add("assistant", "에러 3건 발견했습니다.", engine="skybrain")

        ctx = history.to_context_string(max_turns=2)
        assert "Recent Conversation Context" in ctx
        assert "💻" in ctx  # terminal channel emoji
        assert "⚡" in ctx  # skybrain engine emoji

    def test_to_messages_format(self, history):
        history.add("user", "Hello")
        history.add("assistant", "Hi!")

        messages = history.to_messages(max_turns=2)
        assert len(messages) == 2
        assert messages[0] == {"role": "user", "content": "Hello"}
        assert messages[1] == {"role": "assistant", "content": "Hi!"}

    def test_clear(self, history):
        history.add("user", "test")
        history.clear()
        assert history.total_turns == 0

    def test_stats(self, history):
        history.add("user", "q1", channel="terminal", engine="skybrain")
        history.add("assistant", "a1", channel="terminal", engine="skybrain")
        history.add("user", "q2", channel="ide", engine="gemini")

        s = history.stats()
        assert s["total_turns"] == 3
        assert s["channels"]["terminal"] == 2
        assert s["channels"]["ide"] == 1
        assert s["engines"]["skybrain"] == 2
        assert s["engines"]["gemini"] == 1

    def test_cross_channel_context(self, tmp_path):
        """Verify IDE ↔ Terminal context sharing via shared history."""
        shared_dir = tmp_path / "shared"

        # IDE session writes
        ide_session = ConversationHistory(history_dir=shared_dir)
        ide_session.add("user", "Refactor detectLanguage function",
                        channel="ide", engine="gemini")
        ide_session.add("assistant", "Done! Extracted to LanguageDetector class.",
                        channel="ide", engine="gemini")

        # Terminal session reads the same history
        terminal_session = ConversationHistory(history_dir=shared_dir)
        ctx = terminal_session.to_context_string(max_turns=5)
        assert "Refactor detectLanguage" in ctx
        assert "📝" in ctx  # ide channel emoji


# ═══════════════════════════════════════════════════════════════
#  RoutingStats Tests
# ═══════════════════════════════════════════════════════════════


class TestRoutingStats:
    """Test suite for routing statistics collection."""

    @pytest.fixture
    def stats(self, tmp_path):
        return RoutingStats(stats_file=tmp_path / "stats.json")

    def test_record_and_summary(self, stats):
        stats.record(RoutingTarget.LOCAL, "translate", success=True)
        stats.record(RoutingTarget.LOCAL, "translate", success=True)
        stats.record(RoutingTarget.CLOUD, "architecture", success=True)

        summary = stats.summary()
        assert summary["total_requests"] == 3
        assert summary["local_requests"] == 2
        assert summary["cloud_requests"] == 1
        assert summary["local_ratio"] == "66.7%"

    def test_persistence(self, tmp_path):
        file = tmp_path / "stats_persist.json"

        s1 = RoutingStats(stats_file=file)
        s1.record(RoutingTarget.LOCAL, "summarize")

        s2 = RoutingStats(stats_file=file)
        s2.record(RoutingTarget.LOCAL, "summarize")

        summary = s2.summary()
        assert summary["rules"]["summarize"]["local_count"] == 2

    def test_failure_tracking(self, stats):
        stats.record(RoutingTarget.LOCAL, "translate", success=False)

        summary = stats.summary()
        assert summary["rules"]["translate"]["failure_count"] == 1
        assert summary["rules"]["translate"]["success_count"] == 0
