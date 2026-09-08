"""Vision Analyzer Registry for pluggable and modular VLM backends."""

import logging
from typing import Dict, Type, Optional

from skybrain.store.vision.base import BaseVisionAnalyzer
from skybrain.store.vision.local_vlm import LocalVLMAnalyzer

logger = logging.getLogger(__name__)


class VisionRegistry:
    """Registry allowing modular registration and upgrading of Vision Understanding models."""

    _analyzers: Dict[str, Type[BaseVisionAnalyzer]] = {
        "default": LocalVLMAnalyzer,
        "local_vlm": LocalVLMAnalyzer,
    }

    @classmethod
    def register(cls, name: str, analyzer_cls: Type[BaseVisionAnalyzer]) -> None:
        """Registers a new vision analyzer backend."""
        cls._analyzers[name.lower()] = analyzer_cls
        logger.info("Registered vision analyzer backend: %s", name)

    @classmethod
    def get_analyzer(cls, name: Optional[str] = None) -> BaseVisionAnalyzer:
        """Instantiates and returns the requested vision analyzer backend."""
        key = (name or "default").lower()
        analyzer_cls = cls._analyzers.get(key, LocalVLMAnalyzer)
        return analyzer_cls()

    @classmethod
    def list_available(cls) -> list[str]:
        """Lists all registered vision analyzer backend names."""
        return list(cls._analyzers.keys())
