import json
import logging
import os
from pathlib import Path
import ssl
import threading
from typing import Optional, List, Union
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
    n_gpu_layers: Union[int, str] = Field(
        default="auto",
        description="GPU offload layers: 'auto' (hardware auto-tuning), -1 (full GPU), 0 (CPU only), or specific layer count"
    )
    n_ctx: int = 16384
    n_threads: int = 8

    def get_resolved_gpu_layers(self, model_key: str = "default") -> int:
        """Returns integer layer count, resolving 'auto' via HardwareAutoTuner."""
        if str(self.n_gpu_layers).lower() == "auto":
            from skybrain.core.hardware import HardwareAutoTuner
            return HardwareAutoTuner.resolve_gpu_layers(model_key=model_key)
        try:
            return int(self.n_gpu_layers)
        except (ValueError, TypeError):
            return ALL_GPU_LAYERS

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
                "host", "port", "n_gpu_layers", "n_ctx", "n_threads", "auto_download"
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
