"""Local On-Device VLM (Qwen/Gemma Vision) Analyzer on Apple Silicon Metal."""

import base64
import hashlib
import logging
from typing import Optional, Dict, Any

from skybrain.store.vision.base import BaseVisionAnalyzer, VisionAnalysisResult
from skybrain.review.client import SkyBrainClient

logger = logging.getLogger(__name__)


class LocalVLMAnalyzer(BaseVisionAnalyzer):
    """Executes on-device visual analysis using local SkyBrain VLM."""

    def __init__(self, client: Optional[SkyBrainClient] = None, model_name: str = "skybrain-vlm-local"):
        self.client = client or SkyBrainClient(auto_heal=False)
        self.model_name = model_name

    def analyze(self, image_bytes: bytes, context: Optional[Dict[str, Any]] = None) -> Optional[VisionAnalysisResult]:
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        context = context or {}
        page_num = context.get("page_num", 1)
        doc_title = context.get("title", "문서")

        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            f"당신은 온디바이스 시각 다이어그램 분석 전문가입니다. "
            f"이 이미지는 '{doc_title}' 문서의 {page_num}페이지에 수록된 다이어그램, 아키텍처 순서도, 차트 또는 스크린샷입니다.\n\n"
            f"검색 인덱싱을 위해 다음 두 가지를 한국어로 명확히 작성해 주세요:\n"
            f"1. [다이어그램 구조 및 흐름 요약]: 어떤 컴포넌트들이 어떻게 연결되어 동작하는지\n"
            f"2. [이미지 내 주요 텍스트]: 이미지 안에 적힌 키워드 및 식별자 목록\n"
            f"간결하고 명확하게 작성해 주세요."
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}},
                ],
            }
        ]

        try:
            response_text = self.client.query(messages=messages, temperature=0.1, max_tokens=600)
            if response_text and response_text.strip():
                raw = response_text.strip()
                # Parse summary vs text if structured, otherwise assign whole output
                summary = raw
                ocr = ""
                if "[이미지 내 주요 텍스트]" in raw:
                    parts = raw.split("[이미지 내 주요 텍스트]")
                    summary = parts[0].replace("[다이어그램 구조 및 흐름 요약]:", "").strip()
                    ocr = parts[1].strip()

                return VisionAnalysisResult(
                    image_hash=image_hash,
                    ocr_text=ocr,
                    diagram_summary=summary,
                    model_name=self.model_name,
                    confidence=0.95,
                )
        except Exception as e:
            logger.debug("Local VLM inference skipped: %s", e)

        # Graceful fallback result preserving image presence
        return VisionAnalysisResult(
            image_hash=image_hash,
            ocr_text="",
            diagram_summary=f"다이어그램/이미지 자산 보존됨 ({len(image_bytes):,} bytes)",
            model_name="metadata-fallback",
            confidence=0.5,
        )
