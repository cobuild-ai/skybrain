"""Tests for skybrain.gateway.proxy — Local AI Gateway and Circuit Breaker Failover."""

import pytest
from unittest.mock import patch, MagicMock

from skybrain.gateway.proxy import (
    CloudAPIOverloadedError,
    CloudAPIQuotaError,
    CloudLLMClient,
    SmartRoutingProxy,
)
from skybrain.gateway import IntentClassifier, ConversationHistory, RoutingStats


class TestCloudLLMClient:
    """Test suite for cloud LLM API error handling and provider detection."""

    def test_has_credentials_false_when_unset(self, monkeypatch):
        from skybrain.core.config import settings
        monkeypatch.setattr(settings, "gemini_api_key", None)
        monkeypatch.setattr(settings, "openai_api_key", None)
        monkeypatch.setattr(settings, "anthropic_api_key", None)
        monkeypatch.setattr(settings, "custom_api_url", None)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("CUSTOM_API_URL", raising=False)
        client = CloudLLMClient()
        assert not client.has_cloud_credentials()

    def test_has_credentials_true_when_set(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        client = CloudLLMClient()
        assert client.has_cloud_credentials()

    def test_gemini_429_quota_exceeded_raises_specific_error(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        client = CloudLLMClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Resource has been exhausted (e.g. check quota)."

        with patch("httpx.Client.post", return_value=mock_resp):
            with pytest.raises(CloudAPIQuotaError) as exc_info:
                client.generate(messages=[{"role": "user", "content": "hello"}])
            assert "429 Quota Exceeded" in str(exc_info.value)

    def test_gemini_503_overloaded_raises_specific_error(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        client = CloudLLMClient()

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "The model is overloaded. Please try again later."

        with patch("httpx.Client.post", return_value=mock_resp):
            with pytest.raises(CloudAPIOverloadedError) as exc_info:
                client.generate(messages=[{"role": "user", "content": "hello"}])
            assert "503 Overloaded" in str(exc_info.value)

    def test_custom_api_address_calling(self, monkeypatch):
        """Verifies that arbitrary custom AI server addresses (e.g. internal company proxy) work seamlessly."""
        monkeypatch.setenv("CUSTOM_API_URL", "http://internal-ai.corp:8000/v1")
        monkeypatch.setenv("CUSTOM_API_KEY", "corp-token-123")
        monkeypatch.setenv("CUSTOM_API_MODEL", "qwen-72b-corp")

        client = CloudLLMClient()
        assert client.has_cloud_credentials()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "사내 커스텀 AI 모델의 응답입니다."}}]
        }

        with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
            text, provider = client.generate(messages=[{"role": "user", "content": "hello"}])
            assert text == "사내 커스텀 AI 모델의 응답입니다."
            assert "Custom API" in provider

            # Verify normalized endpoint URL and auth header
            call_args = mock_post.call_args
            assert call_args[0][0] == "http://internal-ai.corp:8000/v1/chat/completions"
            assert call_args[1]["headers"]["Authorization"] == "Bearer corp-token-123"
            assert call_args[1]["json"]["model"] == "qwen-72b-corp"


class TestSmartRoutingProxy:
    """Test suite for intelligent routing and zero-downtime circuit breaker."""

    @pytest.fixture
    def proxy(self, tmp_path):
        history = ConversationHistory(history_dir=tmp_path / "history")
        stats = RoutingStats(stats_file=tmp_path / "stats.json")
        return SmartRoutingProxy(history=history, stats=stats)

    def test_local_query_bypasses_cloud_completely(self, proxy):
        """Simple tasks (e.g. translation) must execute locally without cloud overhead."""
        called_local = False

        def mock_local_executor(messages, system_prompt, temperature, max_tokens):
            nonlocal called_local
            called_local = True
            return "번역 결과입니다."

        result = proxy.route_and_generate(
            prompt="이 텍스트를 영어로 번역해줘",
            local_fallback_executor=mock_local_executor,
        )

        assert called_local
        assert not result["is_failover"]
        assert "SkyBrain" in result["engine"]
        assert result["content"] == "번역 결과입니다."

    def test_circuit_breaker_failover_on_429_quota_exceeded(self, proxy, monkeypatch):
        """When Cloud API returns 429 Quota Exceeded, auto-failover to local SkyBrain."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        # Mock CloudLLMClient.generate to raise CloudAPIQuotaError
        def mock_generate(*args, **kwargs):
            raise CloudAPIQuotaError("Gemini 429 Quota Exceeded")

        proxy.cloud_client.generate = mock_generate

        called_fallback = False

        def mock_local_executor(messages, system_prompt, temperature, max_tokens):
            nonlocal called_fallback
            called_fallback = True
            return "로컬 SkyBrain에서 복구하여 답변을 완성했습니다."

        result = proxy.route_and_generate(
            prompt="아키텍처 설계 전략을 분석해줘",  # Complex prompt -> targets CLOUD
            local_fallback_executor=mock_local_executor,
        )

        assert called_fallback
        assert result["is_failover"]
        assert "Circuit Breaker Failover" in result["engine"]
        assert "429 Quota Exceeded" in result["failover_reason"]
        assert result["content"] == "로컬 SkyBrain에서 복구하여 답변을 완성했습니다."

    def test_circuit_breaker_failover_on_503_overloaded(self, proxy, monkeypatch):
        """When Cloud API returns 503 Overloaded, auto-failover to local SkyBrain."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        def mock_generate(*args, **kwargs):
            raise CloudAPIOverloadedError("Gemini 503 Model Overloaded")

        proxy.cloud_client.generate = mock_generate

        called_fallback = False

        def mock_local_executor(messages, system_prompt, temperature, max_tokens):
            nonlocal called_fallback
            called_fallback = True
            return "오버로드 발생으로 로컬에서 복구 처리 완료했습니다."

        result = proxy.route_and_generate(
            prompt="시스템 아키텍처 리팩토링 방안 제시해줘",
            local_fallback_executor=mock_local_executor,
        )

        assert called_fallback
        assert result["is_failover"]
        assert "Circuit Breaker Failover" in result["engine"]
        assert "503 Model Overloaded" in result["failover_reason"]

    def test_no_cloud_keys_graceful_local_fallback(self, proxy, monkeypatch):
        """When no cloud keys exist, executes locally without crashing."""
        from skybrain.core.config import settings
        monkeypatch.setattr(settings, "gemini_api_key", None)
        monkeypatch.setattr(settings, "openai_api_key", None)
        monkeypatch.setattr(settings, "anthropic_api_key", None)
        monkeypatch.setattr(settings, "custom_api_url", None)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("CUSTOM_API_URL", raising=False)

        def mock_local_executor(messages, system_prompt, temperature, max_tokens):
            return "로컬 답변입니다."

        result = proxy.route_and_generate(
            prompt="복잡한 아키텍처 분석",
            local_fallback_executor=mock_local_executor,
        )

        assert result["is_failover"]
        assert result["content"] == "로컬 답변입니다."


class TestServerAutoRoutingEndpoint:
    """Test suite for server /v1/models and model=auto chat completions."""

    def test_models_list_contains_auto(self):
        from fastapi.testclient import TestClient
        from skybrain.server.app import app

        client = TestClient(app)
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        ids = [m["id"] for m in data["data"]]
        assert "auto" in ids

    def test_chat_completions_model_auto_routing(self):
        from fastapi.testclient import TestClient
        from skybrain.server.app import app

        client = TestClient(app)

        with patch("skybrain.gateway.proxy.SmartRoutingProxy.route_and_generate") as mock_route:
            mock_route.return_value = {
                "content": "안녕하세요! 무엇을 도와드릴까요?",
                "engine": "SkyBrain (Qwen 3.8 Metal)",
                "is_failover": False,
                "routing_target": "local",
                "rule_matched": "simple_qa",
                "reason": "Simple Q&A can be answered by local model",
            }

            resp = client.post(
                "/v1/chat/completions",
                json={
                    "model": "auto",
                    "messages": [{"role": "user", "content": "안녕하세요"}],
                }
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["choices"][0]["message"]["content"] == "안녕하세요! 무엇을 도와드릴까요?"
            assert resp.headers.get("x-processing-engine") == "SkyBrain (Qwen 3.8 Metal)"
            assert data["skybrain_routing"]["rule"] == "simple_qa"
