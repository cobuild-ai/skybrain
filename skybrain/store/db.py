"""SQLite CAS (Content-Addressed Storage) and FTS5 Knowledge Database."""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- 1. 프로젝트 정의 테이블
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. 프로젝트 소속 파일 메타데이터 (논리적 경로)
CREATE TABLE IF NOT EXISTS project_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    absolute_path TEXT NOT NULL,
    content_hash TEXT NOT NULL REFERENCES doc_contents(content_hash),
    mtime REAL NOT NULL,
    size_bytes INTEGER NOT NULL,
    status TEXT DEFAULT 'ACTIVE',
    last_synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, absolute_path)
);
CREATE INDEX IF NOT EXISTS idx_files_project ON project_files(project_id);
CREATE INDEX IF NOT EXISTS idx_files_hash ON project_files(content_hash);

-- 3. 콘텐츠 주소 지정 본문 캐시 (CAS Deduplication)
CREATE TABLE IF NOT EXISTS doc_contents (
    content_hash TEXT PRIMARY KEY,
    doc_type TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    metadata_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 4. 본문 청크 (Chunking by Section)
CREATE TABLE IF NOT EXISTS doc_chunks (
    chunk_id TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL REFERENCES doc_contents(content_hash) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    heading_hierarchy TEXT,
    chunk_text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_hash ON doc_chunks(content_hash);

-- 5. FTS5 전문 검색 가상 테이블 (BM25 Lexical Search)
CREATE VIRTUAL TABLE IF NOT EXISTS doc_chunks_fts USING fts5(
    chunk_id UNINDEXED,
    project_id,
    heading_hierarchy,
    chunk_text,
    tokenize = 'porter unicode61'
);

-- 6. 프로젝트 고유 도메인 어휘집 (Lexicon Harvesting & Query Expansion)
CREATE TABLE IF NOT EXISTS project_lexicon (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    term TEXT NOT NULL,
    frequency INTEGER DEFAULT 1,
    category TEXT DEFAULT 'KEYWORD',
    UNIQUE(project_id, term)
);
CREATE INDEX IF NOT EXISTS idx_lexicon_term ON project_lexicon(term);

-- 7. 시각 자산 및 다이어그램 영구 보존 (Visual Asset Intelligence & Multi-Model Upgrade)
CREATE TABLE IF NOT EXISTS doc_images (
    image_hash TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL REFERENCES doc_contents(content_hash) ON DELETE CASCADE,
    page_num INTEGER NOT NULL,
    image_index INTEGER NOT NULL,
    image_name TEXT,
    mime_type TEXT,
    size_bytes INTEGER NOT NULL,
    storage_path TEXT,
    ocr_text TEXT,
    diagram_summary TEXT,
    vision_model TEXT,
    confidence REAL DEFAULT 1.0,
    analyzed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_images_content ON doc_images(content_hash);
CREATE INDEX IF NOT EXISTS idx_images_model ON doc_images(vision_model);
"""


class KnowledgeDB:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            skybrain_dir = Path.home() / ".skybrain"
            skybrain_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = skybrain_dir / "knowledge.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Initializes database schema and WAL mode."""
        with self.conn:
            self.conn.executescript(SCHEMA_SQL)
            self.conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_project_files_unique ON project_files(project_id, absolute_path);"
            )

    def register_project(self, project_id: str, name: str, root_path: str) -> None:
        """Registers or updates a project definition."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO projects (id, name, root_path)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    root_path = excluded.root_path
                """,
                (project_id, name, str(Path(root_path).resolve())),
            )

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_project_by_path(self, root_path: str) -> Optional[Dict[str, Any]]:
        resolved = str(Path(root_path).resolve())
        cursor = self.conn.execute("SELECT * FROM projects WHERE root_path = ?", (resolved,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_projects(self) -> List[Dict[str, Any]]:
        cursor = self.conn.execute("SELECT * FROM projects ORDER BY name ASC")
        return [dict(row) for row in cursor.fetchall()]

    def has_content(self, content_hash: str) -> bool:
        """Checks if content is already stored in CAS cache."""
        cursor = self.conn.execute(
            "SELECT 1 FROM doc_contents WHERE content_hash = ?", (content_hash,)
        )
        return cursor.fetchone() is not None

    def store_content(
        self,
        content_hash: str,
        doc_type: str,
        raw_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Stores document content in CAS cache."""
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        with self.conn:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO doc_contents (content_hash, doc_type, raw_text, metadata_json)
                VALUES (?, ?, ?, ?)
                """,
                (content_hash, doc_type, raw_text, metadata_json),
            )

    def store_chunks(
        self,
        project_id: str,
        content_hash: str,
        chunks: List[Dict[str, Any]],
    ) -> None:
        """Stores parsed chunks in doc_chunks and doc_chunks_fts."""
        with self.conn:
            for idx, chunk in enumerate(chunks):
                chunk_id = f"{content_hash}_{idx}"
                heading = chunk.get("heading", "")
                text = chunk.get("text", "")

                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO doc_chunks (chunk_id, content_hash, chunk_index, heading_hierarchy, chunk_text)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (chunk_id, content_hash, idx, heading, text),
                )
                self.conn.execute(
                    """
                    INSERT INTO doc_chunks_fts (chunk_id, project_id, heading_hierarchy, chunk_text)
                    VALUES (?, ?, ?, ?)
                    """,
                    (chunk_id, project_id, heading, text),
                )

    def register_file(
        self,
        project_id: str,
        relative_path: str,
        absolute_path: str,
        content_hash: str,
        mtime: float,
        size_bytes: int,
    ) -> None:
        """Registers a project file mapping to CAS content hash."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO project_files (project_id, relative_path, absolute_path, content_hash, mtime, size_bytes, status, last_synced_at)
                VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', CURRENT_TIMESTAMP)
                ON CONFLICT(project_id, absolute_path) DO UPDATE SET
                    relative_path = excluded.relative_path,
                    content_hash = excluded.content_hash,
                    mtime = excluded.mtime,
                    size_bytes = excluded.size_bytes,
                    status = 'ACTIVE',
                    last_synced_at = CURRENT_TIMESTAMP
                """,
                (project_id, relative_path, absolute_path, content_hash, mtime, size_bytes),
            )

    def get_project_file(self, project_id: str, absolute_path: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.execute(
            "SELECT * FROM project_files WHERE project_id = ? AND absolute_path = ?",
            (project_id, absolute_path),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_file_by_path(self, absolute_path: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.execute(
            "SELECT * FROM project_files WHERE absolute_path = ?", (absolute_path,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_project_files(self, project_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.execute(
            "SELECT * FROM project_files WHERE project_id = ? AND status = 'ACTIVE'",
            (project_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def search_fts(
        self,
        query: str,
        project_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        # Sanitize tokens for flexible BM25 matching
        tokens = [t.strip().replace('"', '""') for t in query.split() if t.strip()]
        if not tokens:
            return []

        if len(tokens) == 1:
            formatted_query = f'"{tokens[0]}"'
        else:
            clean_full = query.replace('"', '""')
            token_or = " OR ".join(f'"{t}"' for t in tokens)
            formatted_query = f'"{clean_full}" OR ({token_or})'

        sql = """
            SELECT DISTINCT
                c.chunk_id,
                pf.project_id,
                c.heading_hierarchy,
                c.chunk_text,
                pf.relative_path,
                pf.absolute_path,
                bm25(doc_chunks_fts) as rank
            FROM doc_chunks_fts f
            JOIN doc_chunks c ON f.chunk_id = c.chunk_id
            JOIN project_files pf ON c.content_hash = pf.content_hash
            WHERE doc_chunks_fts MATCH ?
        """
        params: List[Any] = [formatted_query]

        if project_id:
            sql += " AND pf.project_id = ?"
            params.append(project_id)

        sql += " ORDER BY rank ASC LIMIT ?"
        params.append(limit)

        try:
            cursor = self.conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            tokens = query.split()
            fts_tokens = " OR ".join(f'"{t}"' for t in tokens if t)
            if not fts_tokens:
                return []
            params[0] = fts_tokens
            cursor = self.conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def store_doc_image(
        self,
        image_hash: str,
        content_hash: str,
        page_num: int,
        image_index: int,
        image_name: str,
        mime_type: str,
        size_bytes: int,
        storage_path: Optional[str] = None,
        ocr_text: Optional[str] = None,
        diagram_summary: Optional[str] = None,
        vision_model: Optional[str] = None,
        confidence: float = 1.0,
    ) -> None:
        """Stores or updates a visual asset record linked to document content."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO doc_images (
                    image_hash, content_hash, page_num, image_index, image_name,
                    mime_type, size_bytes, storage_path, ocr_text, diagram_summary,
                    vision_model, confidence, analyzed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(image_hash) DO UPDATE SET
                    page_num = excluded.page_num,
                    storage_path = COALESCE(excluded.storage_path, doc_images.storage_path),
                    ocr_text = COALESCE(excluded.ocr_text, doc_images.ocr_text),
                    diagram_summary = COALESCE(excluded.diagram_summary, doc_images.diagram_summary),
                    vision_model = COALESCE(excluded.vision_model, doc_images.vision_model),
                    confidence = excluded.confidence,
                    analyzed_at = CURRENT_TIMESTAMP
                """,
                (
                    image_hash, content_hash, page_num, image_index, image_name,
                    mime_type, size_bytes, storage_path, ocr_text, diagram_summary,
                    vision_model, confidence
                ),
            )

    def update_image_analysis(
        self,
        image_hash: str,
        ocr_text: Optional[str],
        diagram_summary: Optional[str],
        vision_model: str,
        confidence: float = 1.0,
    ) -> None:
        """Updates analysis result (OCR and diagram understanding) for an existing image."""
        with self.conn:
            self.conn.execute(
                """
                UPDATE doc_images
                SET ocr_text = ?,
                    diagram_summary = ?,
                    vision_model = ?,
                    confidence = ?,
                    analyzed_at = CURRENT_TIMESTAMP
                WHERE image_hash = ?
                """,
                (ocr_text, diagram_summary, vision_model, confidence, image_hash),
            )

    def get_doc_images(self, content_hash: str) -> List[Dict[str, Any]]:
        """Retrieves all visual assets for a given document content hash."""
        cursor = self.conn.execute(
            "SELECT * FROM doc_images WHERE content_hash = ? ORDER BY page_num, image_index",
            (content_hash,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_doc_images_for_upgrade(self, target_model: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists images that lack analysis or were analyzed with an older/different model."""
        if target_model:
            cursor = self.conn.execute(
                "SELECT * FROM doc_images WHERE vision_model IS NULL OR vision_model != ?",
                (target_model,)
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM doc_images WHERE vision_model IS NULL"
            )
        return [dict(row) for row in cursor.fetchall()]

    def record_lexicon_terms(self, project_id: str, terms: Dict[str, int], category: str = "KEYWORD") -> None:
        """Records harvested domain terms for query expansion."""
        with self.conn:
            for term, count in terms.items():
                self.conn.execute(
                    """
                    INSERT INTO project_lexicon (project_id, term, frequency, category)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(project_id, term) DO UPDATE SET
                        frequency = frequency + excluded.frequency
                    """,
                    (project_id, term, count, category),
                )

    def get_lexicon_terms(self, project_id: Optional[str] = None, min_frequency: int = 1) -> List[Dict[str, Any]]:
        """Retrieves harvested domain terms."""
        if project_id:
            cursor = self.conn.execute(
                "SELECT * FROM project_lexicon WHERE project_id = ? AND frequency >= ? ORDER BY frequency DESC",
                (project_id, min_frequency),
            )
        else:
            cursor = self.conn.execute(
                "SELECT term, category, SUM(frequency) as frequency FROM project_lexicon WHERE frequency >= ? GROUP BY term ORDER BY frequency DESC",
                (min_frequency,),
            )
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        self.conn.close()
