"""SkyBrain Local Intent Classifier & Shared Brain Cache.

Provides two core v2.0 capabilities:

1. **IntentClassifier** — Rule-based + SkyBrain self-triage classifier
   that determines whether a user request can be handled locally (zero
   cloud tokens) or requires cloud LLM escalation.

2. **ConversationHistory** — FIFO ring buffer persisted to
   ``~/.skybrain/history/`` that enables cross-channel context continuity
   between IDE (Mode A) and Terminal (Mode B) sessions.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Sequence

logger = logging.getLogger("skybrain.gateway")

# ═══════════════════════════════════════════════════════════════
#  Intent Classification
# ═══════════════════════════════════════════════════════════════


class RoutingTarget(str, Enum):
    """Where to route a user request."""

    LOCAL = "local"          # SkyBrain on-device (zero cloud tokens)
    CLOUD = "cloud"          # Cloud LLM (Gemini / Claude)
    UNCERTAIN = "uncertain"  # Needs SkyBrain self-triage or default to cloud


@dataclass(frozen=True)
class ClassificationResult:
    """Result of intent classification."""

    target: RoutingTarget
    reason: str
    confidence: float  # 0.0 – 1.0
    matched_rule: Optional[str] = None


# ── Rule definitions ──────────────────────────────────────────

# Patterns that strongly indicate LOCAL processing capability
_LOCAL_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # Translation tasks
    ("translate", re.compile(
        r"(번역|translate|翻訳|terjemah)", re.IGNORECASE
    ), "Translation tasks are optimally handled by on-device Qwen 3.8"),

    # Log summarization
    ("log_summary", re.compile(
        r"(로그|log|빌드|build|에러|error|traceback|stack\s*trace)", re.IGNORECASE
    ), "Log analysis and summarization runs locally to keep sensitive data on-device"),

    # Simple Q&A / greetings
    ("simple_qa", re.compile(
        r"^(안녕|hello|hi|뭐야|what is|who is|정의|define|설명해|explain)", re.IGNORECASE
    ), "Simple Q&A can be answered by local model"),

    # Boilerplate generation
    ("boilerplate", re.compile(
        r"(보일러플레이트|boilerplate|dto|스키마|schema|초안|draft|독스트링|docstring|주석|comment)", re.IGNORECASE
    ), "Single-file boilerplate and documentation drafts are local-friendly"),

    # Summarization
    ("summarize", re.compile(
        r"(요약|summarize|summary|정리|핵심)", re.IGNORECASE
    ), "Text summarization is a core on-device capability"),

    # Code review (uses ExpertEngine locally)
    ("code_review", re.compile(
        r"(리뷰|review|검토|코드\s*분석|code\s*analysis|린트|lint)", re.IGNORECASE
    ), "Code review uses the local Multi-Lens ExpertEngine"),
]

# Patterns that require CLOUD processing
_CLOUD_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # Multi-file architecture
    ("architecture", re.compile(
        r"(아키텍처|architecture|리팩토링|refactor|모듈\s*분리|multi.?file)", re.IGNORECASE
    ), "Multi-file architecture changes require cloud LLM capabilities"),

    # Git / deployment operations
    ("git_ops", re.compile(
        r"(git\s+(push|pull|merge|rebase|cherry)|pr\s+생성|create\s+pr|deploy|배포)", re.IGNORECASE
    ), "Git operations and deployment require cloud orchestration"),

    # Complex reasoning / planning
    ("complex_reasoning", re.compile(
        r"(설계|design\s+pattern|전략|strategy|분석\s*해\s*줘|analyze.*architecture|시스템)", re.IGNORECASE
    ), "Complex multi-step reasoning benefits from cloud LLM capabilities"),
]


class IntentClassifier:
    """Rule-based intent classifier for SkyBrain Gateway routing.

    Classification pipeline:
      1. Keyword/pattern rules (instant, 0 tokens)
      2. If uncertain → SkyBrain self-triage (optional, ~50 tokens)
      3. If still uncertain → default to cloud

    Usage::

        classifier = IntentClassifier()
        result = classifier.classify("이 로그 요약해줘")
        # ClassificationResult(target=LOCAL, reason="Log analysis...", confidence=0.9)
    """

    def __init__(self, enable_self_triage: bool = False) -> None:
        self._enable_self_triage = enable_self_triage

    def classify(self, prompt: str) -> ClassificationResult:
        """Classify user intent using rule-based pattern matching.

        Returns a ClassificationResult indicating where to route.
        """
        prompt_clean = prompt.strip()

        # Phase 1: Check CLOUD patterns first (they take priority)
        for rule_id, pattern, reason in _CLOUD_PATTERNS:
            if pattern.search(prompt_clean):
                return ClassificationResult(
                    target=RoutingTarget.CLOUD,
                    reason=reason,
                    confidence=0.85,
                    matched_rule=rule_id,
                )

        # Phase 2: Check LOCAL patterns
        for rule_id, pattern, reason in _LOCAL_PATTERNS:
            if pattern.search(prompt_clean):
                return ClassificationResult(
                    target=RoutingTarget.LOCAL,
                    reason=reason,
                    confidence=0.9,
                    matched_rule=rule_id,
                )

        # Phase 3: Heuristics — short prompts tend to be local-friendly
        if len(prompt_clean) < 100:
            return ClassificationResult(
                target=RoutingTarget.LOCAL,
                reason="Short prompt — defaulting to local processing",
                confidence=0.6,
                matched_rule="short_prompt_heuristic",
            )

        # Phase 4: Uncertain — requires self-triage or defaults to cloud
        return ClassificationResult(
            target=RoutingTarget.UNCERTAIN,
            reason="No clear pattern match — escalation may be needed",
            confidence=0.3,
            matched_rule=None,
        )


# ═══════════════════════════════════════════════════════════════
#  Conversation History Ring (Shared Brain Cache)
# ═══════════════════════════════════════════════════════════════

DEFAULT_HISTORY_DIR = Path.home() / ".skybrain" / "history"
DEFAULT_MAX_TURNS = 50


@dataclass
class ConversationTurn:
    """A single turn in the conversation history."""

    role: str           # "user", "assistant", "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    channel: str = "terminal"   # "ide" or "terminal"
    engine: str = "skybrain"    # "skybrain", "gemini", "claude"
    routing_rule: Optional[str] = None


class ConversationHistory:
    """FIFO ring buffer for cross-channel conversation context.

    Persisted to ``~/.skybrain/history/current.jsonl`` as a JSON Lines file.
    Provides shared context between IDE (Antigravity) and Terminal sessions.

    Usage::

        history = ConversationHistory()
        history.add("user", "이 로그 요약해줘", channel="terminal")
        history.add("assistant", "요약 결과입니다...", engine="skybrain")

        # Later, from IDE or Terminal:
        recent = history.get_recent(5)
        context_str = history.to_context_string(max_turns=3)
    """

    def __init__(
        self,
        history_dir: Optional[Path] = None,
        max_turns: int = DEFAULT_MAX_TURNS,
    ) -> None:
        self._dir = history_dir or DEFAULT_HISTORY_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "current.jsonl"
        self._max_turns = max_turns
        self._turns: list[ConversationTurn] = []
        self._load()

    def add(
        self,
        role: str,
        content: str,
        channel: str = "terminal",
        engine: str = "skybrain",
        routing_rule: Optional[str] = None,
    ) -> None:
        """Add a conversation turn and persist to disk."""
        turn = ConversationTurn(
            role=role,
            content=content,
            channel=channel,
            engine=engine,
            routing_rule=routing_rule,
        )
        self._turns.append(turn)

        # FIFO: trim oldest turns if over capacity
        if len(self._turns) > self._max_turns:
            self._turns = self._turns[-self._max_turns:]

        self._save()

    def get_recent(self, n: int = 10) -> list[ConversationTurn]:
        """Return the N most recent conversation turns."""
        return self._turns[-n:]

    def to_context_string(self, max_turns: int = 5) -> str:
        """Generate a context injection string for LLM prompts.

        Formats recent history as a readable summary that can be
        prepended to new prompts to maintain conversation continuity.
        """
        recent = self.get_recent(max_turns)
        if not recent:
            return ""

        lines = ["## Recent Conversation Context"]
        for turn in recent:
            channel_emoji = "📝" if turn.channel == "ide" else "💻"
            engine_emoji = "⚡" if turn.engine == "skybrain" else "👑"
            prefix = f"{channel_emoji}{engine_emoji} [{turn.role}]"
            # Truncate long content for context injection
            content = turn.content[:200] + "..." if len(turn.content) > 200 else turn.content
            lines.append(f"{prefix}: {content}")

        return "\n".join(lines)

    def to_messages(self, max_turns: int = 5) -> list[dict[str, str]]:
        """Convert recent history to OpenAI-style message format."""
        return [
            {"role": t.role, "content": t.content}
            for t in self.get_recent(max_turns)
        ]

    def clear(self) -> None:
        """Clear all conversation history."""
        self._turns.clear()
        if self._file.exists():
            self._file.unlink()

    @property
    def total_turns(self) -> int:
        return len(self._turns)

    def stats(self) -> dict:
        """Return conversation history statistics."""
        if not self._turns:
            return {"total_turns": 0}

        channels = {}
        engines = {}
        for t in self._turns:
            channels[t.channel] = channels.get(t.channel, 0) + 1
            engines[t.engine] = engines.get(t.engine, 0) + 1

        return {
            "total_turns": len(self._turns),
            "channels": channels,
            "engines": engines,
            "oldest_timestamp": self._turns[0].timestamp,
            "newest_timestamp": self._turns[-1].timestamp,
        }

    # ── Private ──────────────────────────────────────────────

    def _load(self) -> None:
        """Load conversation history from JSONL file."""
        if not self._file.exists():
            return

        try:
            lines = self._file.read_text(encoding="utf-8").strip().splitlines()
            for line in lines:
                if not line.strip():
                    continue
                data = json.loads(line)
                self._turns.append(ConversationTurn(
                    role=data["role"],
                    content=data["content"],
                    timestamp=data.get("timestamp", 0),
                    channel=data.get("channel", "terminal"),
                    engine=data.get("engine", "skybrain"),
                    routing_rule=data.get("routing_rule"),
                ))
            # Apply FIFO limit on load
            if len(self._turns) > self._max_turns:
                self._turns = self._turns[-self._max_turns:]
            logger.debug("Loaded %d conversation turns from history", len(self._turns))
        except Exception as exc:
            logger.warning("Failed to load conversation history: %s", exc)
            self._turns = []

    def _save(self) -> None:
        """Persist full conversation history as JSONL."""
        try:
            lines = []
            for turn in self._turns:
                lines.append(json.dumps(asdict(turn), ensure_ascii=False))
            self._file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to save conversation history: %s", exc)


# ═══════════════════════════════════════════════════════════════
#  Routing Statistics Collector
# ═══════════════════════════════════════════════════════════════

DEFAULT_STATS_FILE = Path.home() / ".skybrain" / "routing_stats.json"


class RoutingStats:
    """Collects routing decision statistics for self-improvement.

    Tracks which rules fire, how often, and whether local processing
    was successful. This data can later inform the Self-Triage classifier.
    """

    def __init__(self, stats_file: Optional[Path] = None) -> None:
        self._file = stats_file or DEFAULT_STATS_FILE
        self._data: dict = self._load()

    def record(
        self,
        target: RoutingTarget,
        rule_id: Optional[str],
        success: bool = True,
    ) -> None:
        """Record a routing decision."""
        key = rule_id or "unmatched"
        if key not in self._data:
            self._data[key] = {
                "local_count": 0,
                "cloud_count": 0,
                "success_count": 0,
                "failure_count": 0,
            }

        entry = self._data[key]
        if target == RoutingTarget.LOCAL:
            entry["local_count"] += 1
        else:
            entry["cloud_count"] += 1

        if success:
            entry["success_count"] += 1
        else:
            entry["failure_count"] += 1

        self._save()

    def summary(self) -> dict:
        """Return a summary of routing statistics."""
        total_local = sum(v.get("local_count", 0) for v in self._data.values())
        total_cloud = sum(v.get("cloud_count", 0) for v in self._data.values())
        total = total_local + total_cloud

        return {
            "total_requests": total,
            "local_requests": total_local,
            "cloud_requests": total_cloud,
            "local_ratio": f"{total_local / total:.1%}" if total > 0 else "N/A",
            "rules": self._data,
        }

    def _load(self) -> dict:
        if not self._file.exists():
            return {}
        try:
            return json.loads(self._file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self) -> None:
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Failed to save routing stats: %s", exc)


# ═══════════════════════════════════════════════════════════════
#  Proxy & Circuit Breaker Re-exports
# ═══════════════════════════════════════════════════════════════

from skybrain.gateway.proxy import (
    CloudAPIQuotaError,
    CloudAPIOverloadedError,
    CloudLLMClient,
    SmartRoutingProxy,
)

