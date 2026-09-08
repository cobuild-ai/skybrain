"""Abstract Document Reader Base Class."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class ParsedChunk:
    chunk_index: int
    heading: str
    text: str


@dataclass
class ParsedDocument:
    doc_type: str
    raw_text: str
    chunks: List[ParsedChunk]
    metadata: Dict[str, Any]


class DocumentReader(ABC):
    @abstractmethod
    def can_read(self, file_path: Path) -> bool:
        """Returns True if this reader can parse the specified file."""
        pass

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedDocument:
        """Parses the document into raw text, chunks, and metadata."""
        pass
