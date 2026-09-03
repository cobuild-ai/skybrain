import json
import logging
import shutil
import urllib.request
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional

from skybrain.core.config import settings

logger = logging.getLogger("skybrain.catalog")

MODEL_PRESETS: Dict[str, Dict[str, Any]] = {
    "qwen3.8": {
        "name": "Qwen 3.8 4B Instruct",
        "filename": "Qwen3.8-4B-Q4_K_M.gguf",
        "url": "https://huggingface.co/empero-ai/Qwen3.8-4B-GGUF/resolve/main/Qwen3.8-4B-Q4_K_M.gguf",
        "description": "Alibaba Qwen 3.8 4B (Thinking Mode, Ultra-Fast M1 Optimized, ~2.65GB)",
        "context_length": 32768,
        "is_vision": False,
        "default": True,
    },
    "qwen3.8-9b": {
        "name": "Qwen 3.8 9B Distill Instruct",
        "filename": "Qwen3.8-9B-Q4_K_M.gguf",
        "url": "https://huggingface.co/empero-ai/Qwen3.8-9B-Distill-GGUF/resolve/main/Qwen3.8-9B-Q4_K_M.gguf",
        "description": "Alibaba Qwen 3.8 9B Distill (Advanced Reasoning & Deep Logic, ~5.51GB)",
        "context_length": 32768,
        "is_vision": False,
        "default": False,
    },
    "gemma-4-e4b": {
        "name": "Gemma 4 E4B Instruct",
        "filename": "gemma-4-E4B-it-Q4_K_M.gguf",
        "url": "https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf",
        "description": "Google Gemma 4 E4B (128k Context, Thinking Mode, Native System Role, ~4.7GB)",
        "context_length": 131072,
        "is_vision": False,
        "default": False,
    },
    "gemma-2-2b": {
        "name": "Gemma 2 2B Instruct",
        "filename": "gemma-2-2b-it.Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf",
        "description": "Google Gemma 2 2B (8k Context, Ultra Light Baseline, ~1.63GB)",
        "context_length": 8192,
        "is_vision": False,
        "default": False,
    }
}

DEFAULT_PRESET_KEY = "qwen3.8"
MIN_VALID_MODEL_SIZE = 100 * 1024 * 1024  # 100MB


class ModelCatalog:
    """Manages AI model presets, storage paths, active model selection, and downloads."""

    def __init__(self, models_dir: Optional[Path] = None, home_dir: Optional[Path] = None):
        self.models_dir = models_dir or settings.models_dir
        self.home_dir = home_dir or settings.home_dir
        self.home_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.home_dir / "state.json"

    def get_active_key(self) -> str:
        """Returns active model key from state.json or falls back to installed/default model."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                key = data.get("active_model")
                if key in MODEL_PRESETS:
                    return key
            except Exception:
                pass
        
        # Check installed models
        for key in [DEFAULT_PRESET_KEY, "gemma-2-2b"]:
            if self.is_installed(key):
                return key

        return DEFAULT_PRESET_KEY

    def set_active_key(self, key: str) -> None:
        """Saves active model key to state.json."""
        if key not in MODEL_PRESETS:
            raise ValueError(f"Unknown preset '{key}'. Available: {list(MODEL_PRESETS.keys())}")
        self.home_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps({"active_model": key}, indent=2), encoding="utf-8")

    def get_model_path(self, key: Optional[str] = None) -> Path:
        """Returns the file path for given or active model key."""
        target_key = key or self.get_active_key()
        preset = MODEL_PRESETS.get(target_key, MODEL_PRESETS[DEFAULT_PRESET_KEY])
        return self.models_dir / preset["filename"]

    def get_mmproj_path(self, key: Optional[str] = None) -> Optional[Path]:
        """Returns the vision mmproj file path if model preset has vision support."""
        target_key = key or self.get_active_key()
        preset = MODEL_PRESETS.get(target_key, MODEL_PRESETS[DEFAULT_PRESET_KEY])
        if preset.get("mmproj_filename"):
            return self.models_dir / preset["mmproj_filename"]
        return None

    def is_installed(self, key: Optional[str] = None) -> bool:
        """Checks if given or active model (and required mmproj) exists and exceeds minimum size."""
        target_key = key or self.get_active_key()
        preset = MODEL_PRESETS.get(target_key, MODEL_PRESETS[DEFAULT_PRESET_KEY])
        path = self.get_model_path(target_key)
        if not path.exists() or path.stat().st_size < MIN_VALID_MODEL_SIZE:
            return False
        if preset.get("mmproj_filename"):
            mm_path = self.get_mmproj_path(target_key)
            if not mm_path or not mm_path.exists() or mm_path.stat().st_size < (50 * 1024 * 1024):
                return False
        return True

    def list_models(self) -> List[Dict[str, Any]]:
        """Returns all presets with current installation and active state."""
        active = self.get_active_key()
        results = []
        for key, p in MODEL_PRESETS.items():
            path = self.models_dir / p["filename"]
            installed = self.is_installed(key)
            size_bytes = path.stat().st_size if path.exists() else 0
            if p.get("mmproj_filename"):
                mm_p = self.models_dir / p["mmproj_filename"]
                if mm_p.exists():
                    size_bytes += mm_p.stat().st_size
            size_mb = (size_bytes / (1024 * 1024)) if size_bytes > 0 else 0.0
            results.append({
                "key": key,
                "name": p["name"],
                "filename": p["filename"],
                "mmproj_filename": p.get("mmproj_filename"),
                "is_vision": p.get("is_vision", False),
                "installed": installed,
                "active": (key == active),
                "size_mb": round(size_mb, 2),
                "context_length": p["context_length"],
                "description": p["description"],
                "url": p["url"]
            })
        return results

    def download(self, key: Optional[str] = None, progress_callback: Optional[Callable[[int, int], None]] = None) -> Path:
        """Downloads model file and vision projector (if applicable) with atomic rename."""
        target_key = key or self.get_active_key()
        preset = MODEL_PRESETS.get(target_key, MODEL_PRESETS[DEFAULT_PRESET_KEY])
        target_path = self.get_model_path(target_key)
        temp_path = target_path.with_suffix(".download.tmp")

        def _download_url(url: str, dest_temp: Path, dest_final: Path, desc: str):
            logger.info(f"🚀 Downloading {desc} from {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "SkyBrain-Daemon/0.1.0"})

            # Build opener with custom proxy if configured
            proxy_handler = settings.get_proxy_handler()
            opener = urllib.request.build_opener(proxy_handler) if proxy_handler else None

            ssl_ctx = settings.get_ssl_context()

            def _open(context):
                if opener:
                    # Install ssl context on HTTPSHandler if custom
                    return opener.open(req)
                return urllib.request.urlopen(req, context=context)

            try:
                response = _open(ssl_ctx)
            except Exception as e:
                # Detect corporate SSL MITM / Certificate Verification failure
                err_str = str(e).lower()
                is_ssl_err = "certificate verify failed" in err_str or "certverificationerror" in err_str or "self-signed" in err_str
                if is_ssl_err:
                    logger.warning(
                        "⚠️ Corporate SSL Inspection / Self-Signed certificate detected (%s). "
                        "Auto-falling back to unverified SSL context for model download...",
                        e,
                    )
                    import ssl
                    insecure_ctx = ssl.create_default_context()
                    insecure_ctx.check_hostname = False
                    insecure_ctx.verify_mode = ssl.CERT_NONE
                    response = urllib.request.urlopen(req, context=insecure_ctx)
                else:
                    raise

            try:
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0
                block_size = 1024 * 1024  # 1MB
                with open(dest_temp, "wb") as f:
                    while True:
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        downloaded += len(chunk)
                        f.write(chunk)
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded, total_size)
            finally:
                response.close()

            shutil.move(dest_temp, dest_final)

        # 1. Download main LLM weights
        _download_url(preset["url"], temp_path, target_path, preset["name"])

        # 2. Download mmproj if vision model
        if preset.get("mmproj_url") and preset.get("mmproj_filename"):
            mm_target = self.get_mmproj_path(target_key)
            if mm_target:
                mm_temp = mm_target.with_suffix(".download.tmp")
                _download_url(preset["mmproj_url"], mm_temp, mm_target, f"{preset['name']} Vision Projector")

        self.set_active_key(target_key)
        logger.info(f"✅ Download complete: {target_path}")
        return target_path

    def ensure_model_ready(self, key: Optional[str] = None, progress_callback: Optional[Callable[[int, int], None]] = None) -> Path:
        """Checks if model is installed; if not, automatically downloads it."""
        target_key = key or self.get_active_key()
        if not self.is_installed(target_key):
            logger.info(f"Model '{target_key}' not found locally. Auto-downloading...")
            return self.download(target_key, progress_callback=progress_callback)
        return self.get_model_path(target_key)


