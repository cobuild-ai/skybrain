"""PDF Document Reader with Visual Intelligence Hooks."""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from skybrain.store.readers.base import DocumentReader, ParsedDocument, ParsedChunk

logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader as PyPdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False


import hashlib
from skybrain.core.config import settings
from skybrain.store.vision import VisionRegistry, BaseVisionAnalyzer


class PdfReader(DocumentReader):
    """Parses PDF files into page-level chunks with modular on-device visual diagram intelligence."""

    def __init__(
        self,
        vision_analyzer: Optional[BaseVisionAnalyzer] = None,
        min_image_bytes: int = 2048,
        assets_dir: Optional[Path] = None,
    ):
        self.vision_analyzer = vision_analyzer or VisionRegistry.get_analyzer()
        self.min_image_bytes = min_image_bytes
        self.assets_dir = assets_dir or (settings.home_dir / "assets")
        self.assets_dir.mkdir(parents=True, exist_ok=True)

    def can_read(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def parse(self, file_path: Path) -> ParsedDocument:
        if not PYPDF_AVAILABLE:
            raise ImportError(
                "pypdf package is required to parse PDF documents. "
                "Install it via `uv add pypdf` or `pip install pypdf`."
            )

        reader = PyPdfReader(str(file_path))
        chunks: List[ParsedChunk] = []
        raw_texts: List[str] = []
        extracted_visual_assets: List[Dict[str, Any]] = []

        total_pages = len(reader.pages)
        total_images = 0

        for page_num, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            
            # Check for meaningful images in page
            meaningful_images = []
            try:
                for img in page.images:
                    if len(img.data) >= self.min_image_bytes:
                        meaningful_images.append(img)
            except Exception as e:
                logger.debug("Error inspecting images on page %d: %s", page_num, e)

            images_in_page = len(meaningful_images)
            total_images += images_in_page

            heading = f"{file_path.stem} - Page {page_num}/{total_pages}"
            
            visual_context = ""
            if images_in_page > 0:
                # Page contains images: preserve asset and run modular vision analysis
                vlm_descriptions = []
                for idx, img in enumerate(meaningful_images[:3], start=1):
                    img_hash = hashlib.sha256(img.data).hexdigest()
                    storage_file = self.assets_dir / f"{img_hash}.png"
                    try:
                        if not storage_file.exists():
                            storage_file.write_bytes(img.data)
                    except Exception as e:
                        logger.debug("Failed to cache image asset %s: %s", img_hash, e)

                    # Execute modular vision understanding
                    analysis = self.vision_analyzer.analyze(
                        img.data,
                        context={"title": file_path.stem, "page_num": page_num}
                    )

                    if analysis:
                        vlm_descriptions.append(f"### 🖼️ {img.name}\n{analysis.to_markdown()}")
                        extracted_visual_assets.append({
                            "image_hash": img_hash,
                            "page_num": page_num,
                            "image_index": idx,
                            "image_name": img.name,
                            "mime_type": "image/png",
                            "size_bytes": len(img.data),
                            "storage_path": str(storage_file),
                            "ocr_text": analysis.ocr_text,
                            "diagram_summary": analysis.diagram_summary,
                            "vision_model": analysis.model_name,
                            "confidence": analysis.confidence,
                        })

                if vlm_descriptions:
                    joined_desc = "\n\n".join(vlm_descriptions)
                    visual_context = (
                        f"\n\n> [!TIP]\n"
                        f"> **[🤖 On-Device Visual Intelligence (VLM Diagram Analysis)]**:\n"
                        f"> Page {page_num} contains {images_in_page} visual diagram(s)/image(s).\n\n"
                        f"{joined_desc}"
                    )
                else:
                    img_names_str = ", ".join(img.name for img in meaningful_images)
                    visual_context = (
                        f"\n\n> [!NOTE]\n"
                        f"> **[On-Device Visual Intelligence]**: Page {page_num} contains {images_in_page} visual diagram(s)/image(s) ({img_names_str})."
                    )

            chunk_content = f"## {heading}\n\n{page_text.strip()}{visual_context}"
            raw_texts.append(page_text)
            chunks.append(
                ParsedChunk(
                    chunk_index=page_num - 1,
                    heading=heading,
                    text=chunk_content,
                )
            )

        full_raw_text = "\n\n".join(raw_texts)
        metadata: Dict[str, Any] = {
            "title": file_path.stem,
            "total_pages": total_pages,
            "total_images": total_images,
            "visual_assets": extracted_visual_assets,
        }

        return ParsedDocument(
            doc_type="pdf",
            raw_text=full_raw_text,
            chunks=chunks,
            metadata=metadata,
        )
