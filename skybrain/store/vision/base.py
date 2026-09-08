"""Base interfaces and data structures for modular on-device vision understanding."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class VisionAnalysisResult:
    """Standardized result of visual diagram/image analysis."""
    image_hash: str
    ocr_text: str
    diagram_summary: str
    model_name: str
    confidence: float = 1.0

    def to_markdown(self) -> str:
        """Formats the analysis into an informative markdown chunk annotation."""
        parts = []
        if self.diagram_summary:
            parts.append(f"- **다이어그램/시각 분석**: {self.diagram_summary}")
        if self.ocr_text:
            parts.append(f"- **추출된 텍스트(OCR)**: {self.ocr_text}")
        if self.model_name and self.model_name != "none":
            parts.append(f"- *[분석 모델: {self.model_name}]*")
        return "\n".join(parts)


class BaseVisionAnalyzer(ABC):
    """Abstract contract for modular vision understanding backends."""

    @abstractmethod
    def analyze(self, image_bytes: bytes, context: Optional[Dict[str, Any]] = None) -> Optional[VisionAnalysisResult]:
        """Analyzes an image and extracts structured OCR and diagram understanding.

        Args:
            image_bytes: Raw binary bytes of the image (PNG/JPEG/etc.).
            context: Contextual info such as document title, page number, surrounding text.

        Returns:
            VisionAnalysisResult or None if analysis could not be performed.
        """
        pass
