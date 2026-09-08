"""Plain Text Document Reader."""

from pathlib import Path
from typing import List, Dict, Any
from skybrain.store.readers.base import DocumentReader, ParsedDocument, ParsedChunk


class TextReader(DocumentReader):
    """Parses plain text (.txt, .log) files into paragraph chunks."""

    def can_read(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in [".txt", ".text", ".log"]

    def parse(self, file_path: Path) -> ParsedDocument:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        chunks: List[ParsedChunk] = []
        if not paragraphs:
            chunks.append(ParsedChunk(chunk_index=0, heading=file_path.stem, text=text.strip()))
        else:
            # Group small paragraphs into reasonable chunks (~1000 chars)
            current_chunk = []
            current_len = 0

            for p in paragraphs:
                current_chunk.append(p)
                current_len += len(p)
                if current_len >= 1000:
                    chunks.append(
                        ParsedChunk(
                            chunk_index=len(chunks),
                            heading=f"{file_path.stem} (Part {len(chunks) + 1})",
                            text="\n\n".join(current_chunk),
                        )
                    )
                    current_chunk = []
                    current_len = 0

            if current_chunk:
                chunks.append(
                    ParsedChunk(
                        chunk_index=len(chunks),
                        heading=f"{file_path.stem} (Part {len(chunks) + 1})",
                        text="\n\n".join(current_chunk),
                    )
                )

        return ParsedDocument(
            doc_type="txt",
            raw_text=text,
            chunks=chunks,
            metadata={"title": file_path.stem, "total_chunks": len(chunks)},
        )
