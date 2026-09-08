"""Markdown and Journal Document Reader."""

import re
from pathlib import Path
from typing import List, Dict, Any
from skybrain.store.readers.base import DocumentReader, ParsedDocument, ParsedChunk


class MarkdownReader(DocumentReader):
    """Parses Markdown (.md, .markdown) files into hierarchical chunks."""

    def can_read(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in [".md", ".markdown"]

    def parse(self, file_path: Path) -> ParsedDocument:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        metadata: Dict[str, Any] = {
            "title": file_path.stem,
            "headings": [],
            "tags": [],
        }

        # Extract YAML Frontmatter if present
        body = text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1]
                body = parts[2]
                for line in fm_text.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k = k.strip().lower()
                        v = v.strip().strip("'\"[]")
                        if k == "tags":
                            metadata["tags"] = [t.strip().strip("'\"[] ") for t in v.split(",") if t.strip().strip("'\"[] ")]
                        elif k in ["title", "subject", "date"]:
                            metadata[k] = v

        # Chunking by Headings (#, ##, ###)
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        matches = list(heading_pattern.finditer(body))

        chunks: List[ParsedChunk] = []

        if not matches:
            # Single chunk for documents without headings
            chunks.append(ParsedChunk(chunk_index=0, heading=metadata.get("title", ""), text=body.strip()))
        else:
            # Content before the first heading
            first_start = matches[0].start()
            if first_start > 0 and body[:first_start].strip():
                chunks.append(
                    ParsedChunk(
                        chunk_index=0,
                        heading=metadata.get("title", "Introduction"),
                        text=body[:first_start].strip(),
                    )
                )

            current_hierarchy = []
            for i, m in enumerate(matches):
                level = len(m.group(1))
                h_text = m.group(2).strip()
                metadata["headings"].append(h_text)

                # Maintain hierarchy stack
                while len(current_hierarchy) >= level:
                    current_hierarchy.pop()
                current_hierarchy.append(h_text)
                heading_hierarchy = " > ".join(current_hierarchy)

                start = m.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
                section_text = body[start:end].strip()

                chunk_text = f"## {h_text}\n\n{section_text}" if section_text else f"## {h_text}"
                chunks.append(
                    ParsedChunk(
                        chunk_index=len(chunks),
                        heading=heading_hierarchy,
                        text=chunk_text,
                    )
                )

        return ParsedDocument(
            doc_type="md",
            raw_text=text,
            chunks=chunks,
            metadata=metadata,
        )
