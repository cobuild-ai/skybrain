"""Multi-Project Document Intelligence and CAS Synchronization Manager."""

import hashlib
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from skybrain.store.db import KnowledgeDB
from skybrain.store.readers.base import DocumentReader
from skybrain.store.readers.markdown import MarkdownReader
from skybrain.store.readers.text import TextReader
from skybrain.store.readers.pdf import PdfReader
from skybrain.store.lexicon import LexiconHarvester

logger = logging.getLogger(__name__)

HASH_CHUNK_SIZE = 65536
DEFAULT_SEARCH_LIMIT = 10

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".idea",
    ".vscode",
    "build",
    "dist",
    ".gradle",
    ".gemini",
}

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".text", ".log", ".pdf"}


class DocumentManager:
    """Orchestrates multi-project document indexing, CAS deduplication, and search."""

    def __init__(self, db: Optional[KnowledgeDB] = None):
        self.db = db or KnowledgeDB()
        self.readers: List[DocumentReader] = [
            MarkdownReader(),
            TextReader(),
            PdfReader(),
        ]
        self._lexicon_cache: Dict[Optional[str], List[Dict[str, Any]]] = {}

    def clear_lexicon_cache(self, project_id: Optional[str] = None) -> None:
        """Invalidates in-memory lexicon cache."""
        if project_id is not None:
            self._lexicon_cache.pop(project_id, None)
            self._lexicon_cache.pop(None, None)
        else:
            self._lexicon_cache.clear()

    def _get_reader_for_file(self, file_path: Path) -> Optional[DocumentReader]:
        for reader in self.readers:
            if reader.can_read(file_path):
                return reader
        return None

    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        """Calculates SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(HASH_CHUNK_SIZE):
                hasher.update(chunk)
        return hasher.hexdigest()

    def add_project(self, root_path: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Registers a directory or single file as a project and scans all documents with CAS deduplication."""
        target = Path(root_path).resolve()
        if not target.exists():
            raise ValueError(f"Path does not exist: {target}")

        existing = self.db.get_project_by_path(str(target))
        if existing:
            project_id = existing["id"]
            project_name = name or existing["name"]
        else:
            project_name = name or (target.stem if target.is_file() else target.name)
            project_id = project_name.lower().replace(" ", "-")
            self.db.register_project(project_id, project_name, str(target))

        if target.is_file():
            stats = self._scan_and_ingest(project_id, target.parent, single_file=target)
        else:
            stats = self._scan_and_ingest(project_id, target)

        stats["project_id"] = project_id
        stats["project_name"] = project_name
        return stats

    def sync_project(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Performs incremental sync for specified project or all registered projects."""
        projects = [self.db.get_project(project_id)] if project_id else self.db.list_projects()
        results = []

        for p in projects:
            if not p:
                continue
            root = Path(p["root_path"])
            if not root.exists():
                continue
            stats = self._scan_and_ingest(p["id"], root)
            stats["project_id"] = p["id"]
            stats["project_name"] = p["name"]
            results.append(stats)

        return results

    def _scan_and_ingest(
        self,
        project_id: str,
        root: Path,
        single_file: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Scans files in root (or ingests a single file), detects additions/moves/updates, and ingests into CAS store."""
        added_files = 0
        reused_files = 0
        updated_files = 0
        total_chunks = 0

        # Scan filesystem or process single file
        found_absolute_paths = set()
        if single_file:
            files_to_process = [single_file]
        else:
            files_to_process = []
            for current_dir, dirs, files in os.walk(root):
                # Prune ignored directories in-place
                dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
                for file_name in files:
                    fp = Path(current_dir) / file_name
                    if fp.suffix.lower() in SUPPORTED_EXTENSIONS:
                        files_to_process.append(fp)

        for file_path in files_to_process:
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            abs_path_str = str(file_path.resolve())
            found_absolute_paths.add(abs_path_str)

            try:
                stat = file_path.stat()
            except (PermissionError, FileNotFoundError, OSError) as e:
                logger.debug("Failed to stat file %s: %s", file_path, e)
                continue

            mtime = stat.st_mtime
            size_bytes = stat.st_size

            existing_record = self.db.get_project_file(project_id, abs_path_str)

            # Check if file has changed (mtime and size match)
            if existing_record and existing_record["mtime"] == mtime and existing_record["size_bytes"] == size_bytes:
                continue

            # Calculate SHA-256
            try:
                content_hash = self.calculate_file_hash(file_path)
            except (PermissionError, OSError) as e:
                logger.warning("Failed to read file %s for hashing: %s", file_path, e)
                continue

            try:
                relative_path = str(file_path.relative_to(root))
            except ValueError:
                relative_path = file_path.name

            # CAS Deduplication check
            content_already_exists = self.db.has_content(content_hash)

            if content_already_exists:
                # Content already in DB! Just pointer registration (Zero Re-Embedding)
                reused_files += 1
            else:
                # New content - Parse and store
                reader = self._get_reader_for_file(file_path)
                if not reader:
                    continue

                parsed = reader.parse(file_path)
                self.db.store_content(
                    content_hash=content_hash,
                    doc_type=parsed.doc_type,
                    raw_text=parsed.raw_text,
                    metadata=parsed.metadata,
                )

                chunk_dicts = [
                    {"heading": c.heading, "text": c.text}
                    for c in parsed.chunks
                ]
                self.db.store_chunks(project_id, content_hash, chunk_dicts)
                total_chunks += len(chunk_dicts)

                # Harvest domain terms
                harvested_terms = LexiconHarvester.harvest(parsed.raw_text)
                if harvested_terms:
                    self.db.record_lexicon_terms(project_id, harvested_terms)
                    self.clear_lexicon_cache(project_id)

                # Store any extracted visual assets in doc_images
                visual_assets = parsed.metadata.get("visual_assets", [])
                for va in visual_assets:
                    self.db.store_doc_image(
                        image_hash=va["image_hash"],
                        content_hash=content_hash,
                        page_num=va["page_num"],
                        image_index=va["image_index"],
                        image_name=va["image_name"],
                        mime_type=va["mime_type"],
                        size_bytes=va["size_bytes"],
                        storage_path=va["storage_path"],
                        ocr_text=va["ocr_text"],
                        diagram_summary=va["diagram_summary"],
                        vision_model=va["vision_model"],
                        confidence=va["confidence"],
                    )

                if existing_record:
                    updated_files += 1
                else:
                    added_files += 1

            # Unconditionally register/update file pointer in CAS registry
            self.db.register_file(
                project_id=project_id,
                relative_path=relative_path,
                absolute_path=abs_path_str,
                content_hash=content_hash,
                mtime=mtime,
                size_bytes=size_bytes,
            )

        return {
            "scanned_files": len(found_absolute_paths),
            "added_files": added_files,
            "reused_files": reused_files,
            "updated_files": updated_files,
            "new_chunks": total_chunks,
        }

    def search(
        self,
        query: str,
        project_id: Optional[str] = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
        expand_lexicon: bool = True,
    ) -> List[Dict[str, Any]]:
        """Searches documents using FTS5 with optional domain lexicon expansion."""
        search_query = query
        if expand_lexicon:
            if project_id not in self._lexicon_cache:
                self._lexicon_cache[project_id] = self.db.get_lexicon_terms(project_id=project_id)
            harvested = self._lexicon_cache[project_id]
            search_query = LexiconHarvester.expand_query(query, harvested)

        return self.db.search_fts(search_query, project_id=project_id, limit=limit)

    def list_projects(self) -> List[Dict[str, Any]]:
        """Returns all registered projects and file counts."""
        projects = self.db.list_projects()
        summaries = []
        for p in projects:
            files = self.db.list_project_files(p["id"])
            summaries.append({
                "id": p["id"],
                "name": p["name"],
                "root_path": p["root_path"],
                "active_files": len(files),
                "created_at": p["created_at"],
            })
        return summaries

    def reindex_vision(self, target_model: Optional[str] = None) -> Dict[str, Any]:
        """Upgrades visual diagram understanding on preserved images using a specified or newer VLM model.

        Re-analyzes all preserved visual assets with the upgraded model and updates
        the knowledge base without re-scanning or needing original source documents.
        """
        from skybrain.store.vision import VisionRegistry
        analyzer = VisionRegistry.get_analyzer(target_model)
        images_to_process = self.db.list_doc_images_for_upgrade(target_model=target_model)

        upgraded_count = 0
        for img_row in images_to_process:
            storage_p = img_row.get("storage_path")
            if not storage_p or not Path(storage_p).exists():
                continue

            img_bytes = Path(storage_p).read_bytes()
            analysis = analyzer.analyze(
                img_bytes,
                context={"page_num": img_row["page_num"]}
            )
            if analysis and analysis.model_name != "metadata-fallback":
                self.db.update_image_analysis(
                    image_hash=img_row["image_hash"],
                    ocr_text=analysis.ocr_text,
                    diagram_summary=analysis.diagram_summary,
                    vision_model=analysis.model_name,
                    confidence=analysis.confidence,
                )
                upgraded_count += 1

        return {
            "total_candidates": len(images_to_process),
            "upgraded_images": upgraded_count,
            "vision_model": getattr(analyzer, "model_name", target_model or "default"),
        }
