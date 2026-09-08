"""SkyBrain LLM HTTP Client — Infrastructure Layer.

Thin, zero-dependency client for the local OpenAI-compatible API.
Handles connection errors, auto-healing (daemon restart), and retries.

Clients
-------
SkyBrainClient   — local on-device daemon (Qwen 3.8 Metal, default)
ClaudeLLMClient  — Anthropic Claude API (claude-sonnet-4-5, etc.)

Factory
-------
create_review_client() — auto-selects the best available client:
    ANTHROPIC_API_KEY set  →  ClaudeLLMClient
    (no key)               →  SkyBrainClient (local fallback)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger("skybrain.review.client")

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 3.0
REQUEST_TIMEOUT_SECONDS = 240.0

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-5"


@runtime_checkable
class LLMClient(Protocol):
    """Model-agnostic inference client interface.

    Allows seamless swapping between on-device SLM (SkyBrain Qwen 3.8)
    and commercial cloud LLMs (Gemini, Claude, GPT-4o) without touching
    the core ExpertEngine or ExpertLens specifications.
    """

    def query(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Send chat messages and return assistant text."""
        ...


class SkyBrainClient:
    """HTTP client for the local SkyBrain OpenAI-compatible API (Qwen 3.8).

    Responsibilities (Single Responsibility):
      - Send chat completion requests to the local daemon
      - Auto-heal by restarting daemon on connection failure
      - Retry with exponential backoff

    Implements LLMClient protocol.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
        auto_heal: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._auto_heal = auto_heal
        self._endpoint = f"{self._base_url}/v1/chat/completions"

    def query(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Send a chat completion request and return the assistant's content.

        Raises RuntimeError if all retries are exhausted.
        """
        payload = {
            "model": "default",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")

        last_error: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                return self._send_request(data)
            except (urllib.error.URLError, ConnectionError, OSError) as exc:
                last_error = exc
                logger.warning(
                    "SkyBrain connection failed (attempt %d/%d): %s",
                    attempt,
                    MAX_RETRIES + 1,
                    exc,
                )
                if self._auto_heal and attempt == 1:
                    self._try_auto_heal()
                if attempt <= MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS * attempt)

        raise RuntimeError(
            f"SkyBrain unreachable after {MAX_RETRIES + 1} attempts: {last_error}"
        )

    def health_check(self) -> bool:
        """Returns True if the daemon is responsive."""
        try:
            req = urllib.request.Request(
                f"{self._base_url}/healthz",
                headers={"User-Agent": "SkyBrain-ReviewEngine/1.0"},
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    # ── Private ──────────────────────────────────────────────

    def _send_request(self, data: bytes) -> str:
        """Execute a single HTTP POST and extract the content string."""
        req = urllib.request.Request(
            self._endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "SkyBrain-ReviewEngine/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        choices = body.get("choices", [])
        if not choices:
            raise RuntimeError("Empty choices in SkyBrain response")
        return choices[0].get("message", {}).get("content", "")

    @staticmethod
    def _try_auto_heal() -> None:
        """Attempt to start the SkyBrain daemon if it is not running.

        Resolution order for the ``skybrain`` CLI binary:
          1. ``shutil.which("skybrain")`` — global PATH (uv tool install)
          2. ``~/.local/bin/skybrain`` — uv tool default install location
        """
        import shutil

        skybrain_bin = shutil.which("skybrain")
        if skybrain_bin is None:
            # Fallback: uv tool default install location
            fallback = Path.home() / ".local" / "bin" / "skybrain"
            if fallback.exists():
                skybrain_bin = str(fallback)

        if skybrain_bin is None:
            logger.warning(
                "⚠️ Auto-heal skipped: 'skybrain' CLI not found in PATH. "
                "Install with: uv tool install skybrain"
            )
            return

        logger.info("🔄 Auto-healing: starting SkyBrain daemon via %s", skybrain_bin)
        try:
            subprocess.run(
                [skybrain_bin, "start"],
                capture_output=True,
                timeout=15,
                check=False,
            )
            time.sleep(3.0)  # Give the daemon time to initialize
            logger.info("✅ SkyBrain daemon auto-started.")
        except Exception as exc:
            logger.warning("⚠️ Auto-heal failed: %s", exc)


# ═══════════════════════════════════════════════════════════════
#  Claude LLM Client (Anthropic API — 1st-class LLMClient impl)
# ═══════════════════════════════════════════════════════════════


class ClaudeLLMClient:
    """Anthropic Claude API client implementing the LLMClient protocol.

    Drop-in replacement for SkyBrainClient: same ``query()`` interface,
    no extra dependencies (uses stdlib ``urllib`` only).

    Usage::

        # Explicit key
        client = ClaudeLLMClient(api_key="sk-ant-...")
        result = client.query(messages=[{"role": "user", "content": "hi"}])

        # Auto-detect from environment
        client = ClaudeLLMClient()   # reads ANTHROPIC_API_KEY or SKYBRAIN_ANTHROPIC_API_KEY

    Env vars (in priority order):
        ANTHROPIC_API_KEY
        SKYBRAIN_ANTHROPIC_API_KEY

    Model override::
        SKYBRAIN_CLAUDE_MODEL=claude-opus-4-5  (default: claude-sonnet-4-5)

    Message format translation:
        OpenAI-style ``{"role": "system", "content": "..."}``
        → Anthropic ``system`` top-level field + filtered ``messages`` list.
        This ensures the caller (ReviewLens, ExpertEngine, ChainOfVerifier)
        never needs to know which backend is in use.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        resolved_key = (
            api_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("SKYBRAIN_ANTHROPIC_API_KEY")
        )
        if not resolved_key:
            raise ValueError(
                "ClaudeLLMClient requires an Anthropic API key. "
                "Set ANTHROPIC_API_KEY environment variable or pass api_key=."
            )
        self._api_key = resolved_key
        self._model = (
            model
            or os.environ.get("SKYBRAIN_CLAUDE_MODEL")
            or DEFAULT_CLAUDE_MODEL
        )
        self._timeout = timeout

    def query(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Send messages to the Anthropic Claude API and return assistant text.

        Translates OpenAI-style messages (including ``role: system``) to the
        Anthropic ``/v1/messages`` format transparently.

        Raises:
            RuntimeError: On HTTP error, quota exceeded, or unexpected response.
        """
        system_parts: list[str] = []
        anthropic_messages: list[dict] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                # Accumulate system instructions into the top-level system field
                system_parts.append(content)
            elif role in ("user", "assistant"):
                anthropic_messages.append({"role": role, "content": content})

        # Anthropic requires at least one user message
        if not anthropic_messages:
            anthropic_messages.append({"role": "user", "content": ""})

        payload: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anthropic_messages,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "Content-Type": "application/json",
            "User-Agent": "SkyBrain-ReviewEngine/1.0",
        }

        req = urllib.request.Request(
            ANTHROPIC_API_URL,
            data=data,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.read().decode("utf-8")
            except Exception:
                pass
            status = exc.code
            if status == 429:
                raise RuntimeError(
                    f"Claude API quota exceeded (429). Retry after back-off. Detail: {error_body}"
                ) from exc
            if status in (529, 503, 502):
                raise RuntimeError(
                    f"Claude API overloaded ({status}). Detail: {error_body}"
                ) from exc
            raise RuntimeError(
                f"Claude API HTTP error ({status}): {error_body}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Claude API connection error: {exc}") from exc

        # Parse Anthropic response format:
        # {"content": [{"type": "text", "text": "..."}], ...}
        try:
            content_blocks = body.get("content", [])
            text_blocks = [b["text"] for b in content_blocks if b.get("type") == "text"]
            if not text_blocks:
                raise KeyError("no text content block")
            return "".join(text_blocks)
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Unexpected Claude API response structure: {body}"
            ) from exc


# ═══════════════════════════════════════════════════════════════
#  Auto-selecting factory
# ═══════════════════════════════════════════════════════════════


def create_review_client() -> LLMClient:
    """Auto-select the best available LLM client for review/expert pipelines.

    Priority order:
      1. ``ANTHROPIC_API_KEY`` / ``SKYBRAIN_ANTHROPIC_API_KEY`` → ClaudeLLMClient
      2. Fallback → SkyBrainClient (local on-device Qwen 3.8)

    Usage::

        from skybrain.review.client import create_review_client
        client = create_review_client()
        engine = ReviewEngine(client=client)

    This means:
      - ``ANTHROPIC_API_KEY`` set  →  all review/expert/verification calls use Claude
      - No key set                 →  uses local SkyBrain daemon (zero cloud tokens)
    """
    anthropic_key = (
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("SKYBRAIN_ANTHROPIC_API_KEY")
    )
    if anthropic_key:
        model = os.environ.get("SKYBRAIN_CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL)
        logger.info(
            "☁️ [create_review_client] Claude API detected (model: %s). "
            "Using ClaudeLLMClient for review pipeline.",
            model,
        )
        return ClaudeLLMClient(api_key=anthropic_key, model=model)

    logger.info(
        "⚡ [create_review_client] No cloud API key found. "
        "Using local SkyBrain daemon (on-device Qwen 3.8)."
    )
    return SkyBrainClient()
