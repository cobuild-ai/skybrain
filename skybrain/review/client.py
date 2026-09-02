"""SkyBrain LLM HTTP Client — Infrastructure Layer.

Thin, zero-dependency client for the local OpenAI-compatible API.
Handles connection errors, auto-healing (daemon restart), and retries.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
import urllib.error
import urllib.request
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger("skybrain.review.client")

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 3.0
REQUEST_TIMEOUT_SECONDS = 120.0


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
        """Attempt to start the SkyBrain daemon if it is not running."""
        logger.info("🔄 Auto-healing: attempting to start SkyBrain daemon...")
        try:
            subprocess.run(
                ["01-production/skybrain/.venv/bin/skybrain", "start"],
                capture_output=True,
                timeout=15,
                check=False,
            )
            time.sleep(3.0)  # Give the daemon time to initialize
            logger.info("✅ SkyBrain daemon auto-started.")
        except Exception as exc:
            logger.warning("⚠️ Auto-heal failed: %s", exc)
