from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class SkyBrainSettings(BaseSettings):
    app_name: str = "SkyBrain"
    version: str = "0.1.0"
    
    # Storage & Cache
    home_dir: Path = Field(default_factory=lambda: Path.home() / ".skybrain")
    models_dir: Path = Field(default_factory=lambda: Path.home() / ".skybrain" / "models")
    
    # Server Defaults
    host: str = "127.0.0.1"
    port: int = 8000
    
    # Hardware & Performance
    n_gpu_layers: int = -1  # Offload all layers to Apple Silicon Metal GPU
    n_ctx: int = 4096
    n_threads: int = 8

    # Auto-Provisioning
    auto_download: bool = True


    def model_post_init(self, __context):
        self.home_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)


settings = SkyBrainSettings()
