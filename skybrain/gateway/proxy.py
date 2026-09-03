"""SkyBrain Local AI Gateway & Circuit Breaker Proxy.

Provides zero-downtime resilience by intercepting LLM requests,
routing local-friendly tasks to on-device SkyBrain (Qwen 3.8 Metal),
attempting Cloud LLMs for complex tasks, and automatically failing over
to SkyBrain if Cloud APIs experience Quota Exceeded (429) or Overloaded (503).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from skybrain.gateway import (
    ClassificationResult,
    ConversationHistory,
    IntentClassifier,
    RoutingStats,
    RoutingTarget,
)

logger = logging.getLogger("skybrain.gateway.proxy")


class CloudAPIQuotaError(Exception):
    """Raised when Cloud API returns HTTP 429 or Quota Exceeded."""
    pass


class CloudAPIOverloadedError(Exception):
    """Raised when Cloud API returns HTTP 503 or Model Overloaded."""
    pass


class CloudLLMClient:
    """Lightweight client for external Cloud LLMs (Gemini, OpenAI, Claude).

    Zero extra dependencies; uses standard httpx.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def has_cloud_credentials(self) -> bool:
        """Returns True if custom API URL is provided or any provider API key is set."""
        from skybrain.core.config import settings
        return bool(
            settings.custom_api_url
            or os.environ.get("CUSTOM_API_URL")
            or settings.gemini_api_key
            or os.environ.get("GEMINI_API_KEY")
            or settings.openai_api_key
            or os.environ.get("OPENAI_API_KEY")
            or settings.anthropic_api_key
            or os.environ.get("ANTHROPIC_API_KEY")
        )

    def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Tuple[str, str]:
        """Sends chat messages to custom API or available cloud provider.

        Returns:
            Tuple of (response_text, provider_name)
        Raises:
            CloudAPIQuotaError: On 429 / Quota limits
            CloudAPIOverloadedError: On 503 / Server overload
            RuntimeError: On generic cloud failure
        """
        from skybrain.core.config import settings

        custom_url = settings.custom_api_url or os.environ.get("CUSTOM_API_URL")
        gemini_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        openai_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY")
        anthropic_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")

        if custom_url:
            return self._call_custom_api(custom_url, messages, system_prompt, temperature, max_tokens)
        elif gemini_key:
            return self._call_gemini(gemini_key, messages, system_prompt, temperature, max_tokens)
        elif openai_key:
            return self._call_openai(openai_key, messages, system_prompt, temperature, max_tokens)
        elif anthropic_key:
            return self._call_anthropic(anthropic_key, messages, system_prompt, temperature, max_tokens)
        else:
            raise RuntimeError("No custom API URL or cloud API key found (CUSTOM_API_URL, GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY).")

    def _call_custom_api(
        self,
        api_url: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> Tuple[str, str]:
        """Calls any custom OpenAI-compatible server or proxy address.

        Supports:
          - Full endpoint: http://my-host:port/v1/chat/completions
          - Base URL: http://my-host:port/v1
          - Root URL: http://my-host:port
        """
        from skybrain.core.config import settings

        clean_url = api_url.strip().rstrip("/")
        if not clean_url.endswith("/chat/completions"):
            if clean_url.endswith("/v1"):
                endpoint = f"{clean_url}/chat/completions"
            else:
                endpoint = f"{clean_url}/v1/chat/completions"
        else:
            endpoint = clean_url

        key = (
            settings.custom_api_key
            or os.environ.get("CUSTOM_API_KEY")
            or settings.openai_api_key
            or os.environ.get("OPENAI_API_KEY")
        )
        model_name = (
            os.environ.get("CUSTOM_API_MODEL")
            or settings.custom_api_model
            or "default"
        )

        full_msgs = []
        if system_prompt:
            full_msgs.append({"role": "system", "content": system_prompt})
        full_msgs.extend(messages)

        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"

        payload = {
            "model": model_name,
            "messages": full_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(endpoint, headers=headers, json=payload)
        except Exception as exc:
            raise RuntimeError(f"Custom API connection error ({endpoint}): {exc}") from exc

        if resp.status_code == 429:
            raise CloudAPIQuotaError(f"Custom API 429 Quota Exceeded ({endpoint}): {resp.text}")
        elif resp.status_code in (503, 502):
            raise CloudAPIOverloadedError(f"Custom API {resp.status_code} Overloaded ({endpoint}): {resp.text}")
        elif resp.status_code != 200:
            raise RuntimeError(f"Custom API error ({resp.status_code} from {endpoint}): {resp.text}")

        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
            return content, f"Custom API ({clean_url})"
        except (KeyError, IndexError) as exc:
            # Some non-standard proxies might return directly or in different key
            if "content" in data:
                return data["content"], f"Custom API ({clean_url})"
            raise RuntimeError(f"Unexpected custom API response format: {data}") from exc

    def _call_gemini(
        self,
        api_key: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> Tuple[str, str]:
        """Calls Google Gemini API."""
        from skybrain.core.config import settings

        model_name = os.environ.get("GEMINI_MODEL") or os.environ.get("SKYBRAIN_GEMINI_MODEL") or settings.gemini_model
        endpoint = (
            os.environ.get("GEMINI_ENDPOINT")
            or os.environ.get("SKYBRAIN_GEMINI_ENDPOINT")
            or settings.gemini_endpoint
        ).rstrip("/")

        url = f"{endpoint}/v1beta/models/{model_name}:generateContent?key={api_key}"

        contents = []
        for m in messages:
            role = "user" if m.get("role") in ("user", "system") else "model"
            contents.append({
                "role": role,
                "parts": [{"text": m.get("content", "")}]
            })

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload)
        except Exception as exc:
            raise RuntimeError(f"Gemini connection error: {exc}") from exc

        if resp.status_code == 429:
            raise CloudAPIQuotaError(f"Gemini API 429 Quota Exceeded: {resp.text}")
        elif resp.status_code in (503, 502):
            raise CloudAPIOverloadedError(f"Gemini API {resp.status_code} Overloaded: {resp.text}")
        elif resp.status_code != 200:
            err_text = resp.text.lower()
            if "quota" in err_text or "rate limit" in err_text:
                raise CloudAPIQuotaError(f"Gemini Quota Error ({resp.status_code}): {resp.text}")
            if "overloaded" in err_text or "capacity" in err_text:
                raise CloudAPIOverloadedError(f"Gemini Overload Error ({resp.status_code}): {resp.text}")
            raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")

        data = resp.json()
        try:
            candidate = data["candidates"][0]
            text = candidate["content"]["parts"][0]["text"]
            return text, f"Cloud Gemini ({model_name})"
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected Gemini response structure: {data}") from exc

    def _call_openai(
        self,
        api_key: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> Tuple[str, str]:
        """Calls OpenAI or OpenAI-compatible API."""
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model_name = os.environ.get("SKYBRAIN_OPENAI_MODEL", "gpt-4o-mini")
        url = f"{base_url}/chat/completions"

        full_msgs = []
        if system_prompt:
            full_msgs.append({"role": "system", "content": system_prompt})
        full_msgs.extend(messages)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "messages": full_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
        except Exception as exc:
            raise RuntimeError(f"OpenAI connection error: {exc}") from exc

        if resp.status_code == 429:
            raise CloudAPIQuotaError(f"OpenAI API 429 Rate Limit / Quota Exceeded: {resp.text}")
        elif resp.status_code in (503, 502):
            raise CloudAPIOverloadedError(f"OpenAI API {resp.status_code} Overloaded: {resp.text}")
        elif resp.status_code != 200:
            raise RuntimeError(f"OpenAI API error ({resp.status_code}): {resp.text}")

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content, f"Cloud OpenAI ({model_name})"

    def _call_anthropic(
        self,
        api_key: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> Tuple[str, str]:
        """Calls Anthropic Claude API."""
        model_name = os.environ.get("SKYBRAIN_CLAUDE_MODEL", "claude-3-5-haiku-20241022")
        url = "https://api.anthropic.com/v1/messages"

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": [m for m in messages if m.get("role") in ("user", "assistant")],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
        except Exception as exc:
            raise RuntimeError(f"Anthropic connection error: {exc}") from exc

        if resp.status_code == 429:
            raise CloudAPIQuotaError(f"Claude API 429 Rate Limit / Quota Exceeded: {resp.text}")
        elif resp.status_code in (503, 502):
            raise CloudAPIOverloadedError(f"Claude API {resp.status_code} Overloaded: {resp.text}")
        elif resp.status_code != 200:
            raise RuntimeError(f"Claude API error ({resp.status_code}): {resp.text}")

        data = resp.json()
        text = data["content"][0]["text"]
        return text, f"Cloud Claude ({model_name})"


class SmartRoutingProxy:
    """Intelligent Routing Proxy with Circuit Breaker and Local Fallback.

    Orchestrates the entire query lifecycle:
      1. Classify prompt intent (Local vs Cloud).
      2. If Local: Execute directly on on-device SkyBrain ($0 tokens).
      3. If Cloud: Attempt Cloud API (Gemini/OpenAI/Claude).
      4. If Cloud fails with 429/503/timeout:
         Trigger Circuit Breaker ➔ Automatically failover to Local SkyBrain.
    """

    def __init__(
        self,
        classifier: Optional[IntentClassifier] = None,
        history: Optional[ConversationHistory] = None,
        stats: Optional[RoutingStats] = None,
        cloud_client: Optional[CloudLLMClient] = None,
    ) -> None:
        self.classifier = classifier or IntentClassifier()
        self.history = history or ConversationHistory()
        self.stats = stats or RoutingStats()
        self.cloud_client = cloud_client or CloudLLMClient()

    def route_and_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        force_cloud: bool = False,
        include_context: bool = True,
        local_fallback_executor: Optional[Any] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """Executes query with intelligent routing and auto-failover.

        Returns dict with:
          - content: generated assistant message
          - engine: string describing engine used
          - is_failover: boolean indicating whether fallback occurred
          - routing_target: original target (local/cloud)
          - rule_matched: matched classification rule
          - reason: routing decision explanation
        """
        classification = self.classifier.classify(prompt)
        target = RoutingTarget.CLOUD if force_cloud else classification.target

        context_prefix = ""
        if include_context and self.history.total_turns > 0:
            context_prefix = self.history.to_context_string(max_turns=3)

        # Build message history for execution
        messages: List[Dict[str, str]] = []
        if context_prefix:
            messages.append({"role": "system", "content": context_prefix})
        messages.append({"role": "user", "content": prompt})

        # Record user turn in shared history
        self.history.add(
            role="user",
            content=prompt,
            channel="proxy",
            routing_rule=classification.matched_rule,
        )

        response_content: Optional[str] = None
        engine_tag = "SkyBrain (Qwen 3.8 Metal)"
        is_failover = False
        failover_reason = None

        # ── Pre-flight Memory Guard ─────────────────────────
        from skybrain.core.monitor import SystemGuard
        mem_eval = SystemGuard.evaluate(has_cloud_fallback=self.cloud_client.has_cloud_credentials())
        if target == RoutingTarget.LOCAL and mem_eval.fallback_to_cloud:
            logger.warning("🚨 [Memory Guard] Local RAM critical (%.1f GB). Offloading to Cloud LLM.", mem_eval.available_gb)
            target = RoutingTarget.CLOUD
            is_failover = True
            failover_reason = f"Memory Critical Guard: {mem_eval.available_gb:.1f} GB available"
        elif target == RoutingTarget.LOCAL and not mem_eval.allowed:
            logger.error("🛑 [Memory Guard] Local RAM critical (%.1f GB) & no cloud fallback. Blocking execution.", mem_eval.available_gb)
            response_content = mem_eval.message
            engine_tag = "SystemGuard (Memory Protection Block)"

        # ── Route Execution ───────────────────────────────────

        if target == RoutingTarget.CLOUD:
            if self.cloud_client.has_cloud_credentials():
                try:
                    logger.info("☁️ Routing to Cloud LLM (%s)...", classification.reason)
                    response_content, engine_tag = self.cloud_client.generate(
                        messages=messages,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                except (CloudAPIQuotaError, CloudAPIOverloadedError) as cloud_err:
                    is_failover = True
                    failover_reason = str(cloud_err)
                    logger.warning(
                        "🚨 Circuit Breaker: Cloud API failed with quota/overload (%s). "
                        "Failing over to Local SkyBrain Qwen 3.8 immediately!",
                        cloud_err,
                    )
                except Exception as exc:
                    is_failover = True
                    failover_reason = str(exc)
                    logger.warning(
                        "⚠️ Circuit Breaker: Cloud API unexpected failure (%s). "
                        "Failing over to Local SkyBrain Qwen 3.8...",
                        exc,
                    )
            else:
                logger.info("ℹ️ No cloud API key configured. Executing locally on SkyBrain.")
                is_failover = True
                failover_reason = "No cloud API key configured"

        # If Local route OR Cloud failover triggered
        if response_content is None:
            from skybrain.engine.model_catalog import ModelCatalog, MODEL_PRESETS
            active_key = ModelCatalog().get_active_key()
            active_model_info = MODEL_PRESETS.get(active_key, {})
            model_disp_name = active_model_info.get("name", active_key)

            if is_failover:
                engine_tag = f"Local SkyBrain (Circuit Breaker Failover ➔ {model_disp_name} on Metal GPU)"
            else:
                engine_tag = f"Local SkyBrain ({model_disp_name} on Metal GPU)"

            # Execute via local fallback
            if local_fallback_executor:
                response_content = local_fallback_executor(
                    messages=messages,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            else:
                from skybrain.server.app import get_llm
                llm = get_llm()
                combined = f"{system_prompt or ''}\n\n[User]\n{prompt}"
                resp = llm.create_chat_completion(
                    messages=[{"role": "user", "content": combined}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                response_content = resp["choices"][0]["message"]["content"]

        # Record assistant turn in shared history
        self.history.add(
            role="assistant",
            content=response_content or "",
            channel="proxy",
            engine="skybrain" if ("SkyBrain" in engine_tag or "Local" in engine_tag) else "cloud",
            routing_rule=classification.matched_rule,
        )

        # Record statistics
        self.stats.record(
            target=target,
            rule_id=classification.matched_rule,
            success=True,
        )

        return {
            "content": response_content,
            "engine": engine_tag,
            "is_failover": is_failover,
            "failover_reason": failover_reason,
            "routing_target": target.value,
            "rule_matched": classification.matched_rule,
            "reason": classification.reason,
        }
