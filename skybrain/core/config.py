import json
import logging
import os
from pathlib import Path
import ssl
import threading
from typing import Optional, List
import urllib.request
from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger("skybrain.core.config")

# Hardware constant: offload all layers to Apple Silicon Metal GPU
ALL_GPU_LAYERS: int = -1

_no_proxy_lock = threading.Lock()


class SkyBrainSettings(BaseSettings):
    app_name: str = "SkyBrain"
    version: str = "0.2.0"
    
    # Storage & Cache
    home_dir: Path = Field(default_factory=lambda: Path.home() / ".skybrain")
    models_dir: Path = Field(default_factory=lambda: Path.home() / ".skybrain" / "models")
    
    # Server Defaults
    host: str = "127.0.0.1"
    port: int = 8000
    
    # Hardware & Performance
    n_gpu_layers: int = ALL_GPU_LAYERS  # Offload all layers to Apple Silicon Metal GPU
    n_ctx: int = 16384
    n_threads: int = 8

    # Auto-Provisioning
    auto_download: bool = True

    # ── SSL/TLS & Network (Corporate Environment Support) ────
    ssl_verify: bool = Field(
        default=True,
        description=(
            "Verify SSL certificates for external HTTPS connections "
            "(e.g., HuggingFace model downloads). "
            "Set to False in corporate environments where CA bundles "
            "cannot be configured. "
            "Environment variable: SKYBRAIN_SSL_VERIFY"
        ),
    )
    ca_bundle: Optional[str] = Field(
        default=None,
        description=(
            "Path to a custom CA certificate bundle (.pem / .crt) for "
            "corporate SSL-inspecting proxies. "
            "Environment variable: SKYBRAIN_CA_BUNDLE"
        ),
    )
    http_proxy: Optional[str] = Field(
        default=None,
        description=(
            "HTTP proxy URL for external connections. "
            "Environment variable: SKYBRAIN_HTTP_PROXY"
        ),
    )
    https_proxy: Optional[str] = Field(
        default=None,
        description=(
            "HTTPS proxy URL for external connections. "
            "Environment variable: SKYBRAIN_HTTPS_PROXY"
        ),
    )

    # ── Cloud LLM Gateway Settings (Local Routing Proxy) ────
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API Key. Environment variable: GEMINI_API_KEY or SKYBRAIN_GEMINI_API_KEY"
    )
    gemini_endpoint: str = Field(
        default="https://generativelanguage.googleapis.com",
        description="Base URL for Google Gemini API. Can be overridden for private/corporate gateways."
    )
    gemini_model: str = Field(
        default="gemini-3.6-flash",
        description="Gemini model name. Environment variable: GEMINI_MODEL or SKYBRAIN_GEMINI_MODEL"
    )

    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API Key. Environment variable: OPENAI_API_KEY or SKYBRAIN_OPENAI_API_KEY"
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI base URL. Environment variable: OPENAI_BASE_URL or SKYBRAIN_OPENAI_BASE_URL"
    )

    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic Claude API Key. Environment variable: ANTHROPIC_API_KEY or SKYBRAIN_ANTHROPIC_API_KEY"
    )

    # ── Universal Custom AI API Address ──────────────────────────
    custom_api_url: Optional[str] = Field(
        default=None,
        description="Custom AI server/proxy address. Environment variable: CUSTOM_API_URL or SKYBRAIN_CUSTOM_API_URL"
    )
    custom_api_key: Optional[str] = Field(
        default=None,
        description="Optional API key / Bearer token for the custom AI address."
    )
    custom_api_model: str = Field(
        default="custom-model",
        description="Model identifier to send to the custom AI server."
    )

    model_config = {"env_prefix": "SKYBRAIN_", "extra": "ignore"}

    def model_post_init(self, __context):
        """Orchestrates directory creation and persistent user config loading."""
        self._create_directories()
        self._load_user_config()

    def _create_directories(self) -> None:
        """Ensures home and model storage directories exist."""
        self.home_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def _load_user_config(self) -> None:
        """Safely reads and merges persistent user config from ~/.skybrain/config.json."""
        config_file = self.home_dir / "config.json"
        if not config_file.exists():
            return

        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            overridable_keys = {
                "gemini_endpoint", "gemini_model", "openai_base_url",
                "custom_api_url", "custom_api_key", "custom_api_model"
            }
            for k, v in data.items():
                if hasattr(self, k) and (getattr(self, k) is None or k in overridable_keys):
                    setattr(self, k, v)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load user config file %s: %s", config_file, exc)

    @staticmethod
    def _resolve_env_fallback(primary: Optional[str], env_vars: List[str]) -> Optional[str]:
        """Helper to resolve a configuration value with priority over fallback environment variables."""
        if primary:
            return primary
        for var in env_vars:
            val = os.environ.get(var)
            if val:
                return val
        return None

    def get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Build an ssl.SSLContext for external HTTPS connections.

        Handles corporate proxy CA bundles, environment variable fallbacks,
        and the ssl_verify toggle.
        """
        if not self.ssl_verify:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx

        ca_env_priority = [
            "SKYBRAIN_CA_BUNDLE",
            "REQUESTS_CA_BUNDLE",
            "SSL_CERT_FILE",
            "CURL_CA_BUNDLE",
        ]
        ca_path = self._resolve_env_fallback(self.ca_bundle, ca_env_priority)

        if ca_path:
            resolved = Path(ca_path).resolve()
            if resolved.is_file():
                return ssl.create_default_context(cafile=str(resolved))
            logger.warning("Configured CA bundle not found or not a file: %s", ca_path)

        return None

    def get_proxy_handler(self) -> Optional[urllib.request.ProxyHandler]:
        """Build a urllib ProxyHandler for corporate proxy environments."""
        http_proxy = self._resolve_env_fallback(self.http_proxy, ["HTTP_PROXY", "http_proxy"])
        https_proxy = self._resolve_env_fallback(self.https_proxy, ["HTTPS_PROXY", "https_proxy"])

        proxies = {}
        if http_proxy:
            proxies["http"] = http_proxy
        if https_proxy:
            proxies["https"] = https_proxy

        return urllib.request.ProxyHandler(proxies) if proxies else None

    def ensure_localhost_no_proxy(self) -> None:
        """Thread-safely ensures localhost/127.0.0.1 is excluded from proxy settings."""
        with _no_proxy_lock:
            no_proxy = os.environ.get("NO_PROXY", os.environ.get("no_proxy", ""))
            localhost_entries = {"localhost", "127.0.0.1", "::1"}

            existing = {e.strip() for e in no_proxy.split(",") if e.strip()}
            missing = localhost_entries - existing

            if missing:
                updated = ",".join(sorted(existing | localhost_entries))
                os.environ["NO_PROXY"] = updated
                os.environ["no_proxy"] = updated


settings = SkyBrainSettings()
settings.ensure_localhost_no_proxy()
