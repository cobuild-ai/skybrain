import json
import logging
import shutil
import urllib.request
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional

from skybrain.core.config import settings

logger = logging.getLogger("skybrain.catalog")

MODEL_PRESETS: Dict[str, Dict[str, Any]] = {
    "gemma-4-e4b": {
        "name": "Gemma 4 E4B Instruct",
        "filename": "gemma-4-E4B-it-Q4_K_M.gguf",
        "url": "https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf",
        "description": "Google Gemma 4 E4B (128k Context, Thinking Mode, Native System Role, ~4.7GB)",
        "context_length": 131072,
        "default": True,
    },
    "gemma-2-2b": {
        "name": "Gemma 2 2B Instruct",
        "filename": "gemma-2-2b-it.Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf",
        "description": "Google Gemma 2 2B (8k Context, Ultra Light Baseline, ~1.63GB)",
        "context_length": 8192,
        "default": False,
    }
}

DEFAULT_PRESET_KEY = "gemma-4-e4b"
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

    def is_installed(self, key: Optional[str] = None) -> bool:
        """Checks if given or active model exists and exceeds minimum size."""
        path = self.get_model_path(key)
        if not path.exists():
            return False
        return path.stat().st_size >= MIN_VALID_MODEL_SIZE

    def list_models(self) -> List[Dict[str, Any]]:
        """Returns all presets with current installation and active state."""
        active = self.get_active_key()
        results = []
        for key, p in MODEL_PRESETS.items():
            path = self.models_dir / p["filename"]
            installed = path.exists() and path.stat().st_size >= MIN_VALID_MODEL_SIZE
            size_mb = (path.stat().st_size / (1024 * 1024)) if path.exists() else 0.0
            results.append({
                "key": key,
                "name": p["name"],
                "filename": p["filename"],
                "installed": installed,
                "active": (key == active),
                "size_mb": round(size_mb, 2),
                "context_length": p["context_length"],
                "description": p["description"],
                "url": p["url"]
            })
        return results

    def download(self, key: Optional[str] = None, progress_callback: Optional[Callable[[int, int], None]] = None) -> Path:
        """Downloads model file with atomic rename."""
        target_key = key or self.get_active_key()
        preset = MODEL_PRESETS.get(target_key, MODEL_PRESETS[DEFAULT_PRESET_KEY])
        target_path = self.get_model_path(target_key)
        temp_path = target_path.with_suffix(".download.tmp")

        logger.info(f"🚀 Downloading {preset['name']} from {preset['url']}")
        req = urllib.request.Request(preset["url"], headers={"User-Agent": "SkyBrain-Daemon/0.1.0"})

        with urllib.request.urlopen(req) as response:
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            block_size = 1024 * 1024  # 1MB

            with open(temp_path, "wb") as f:
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    f.write(chunk)
                    if progress_callback and total_size > 0:
                        progress_callback(downloaded, total_size)

        shutil.move(temp_path, target_path)
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

