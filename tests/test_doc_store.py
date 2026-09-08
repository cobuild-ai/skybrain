"""Comprehensive Unit & Integration Tests for SkyBrain Multi-Project Document Store."""

import json
import pytest
from pathlib import Path
from skybrain.store.db import KnowledgeDB
from skybrain.store.manager import DocumentManager
from skybrain.store.readers.markdown import MarkdownReader
from skybrain.store.readers.text import TextReader
from skybrain.store.lexicon import LexiconHarvester
from skybrain.mcp.server import SkyBrainMCPServer


@pytest.fixture
def temp_db(tmp_path: Path):
    db_file = tmp_path / "test_knowledge.db"
    db = KnowledgeDB(db_path=db_file)
    yield db
    db.close()


@pytest.fixture
def doc_manager(tmp_path: Path):
    db_file = tmp_path / "test_knowledge.db"
    db = KnowledgeDB(db_path=db_file)
    manager = DocumentManager(db=db)
    yield manager
    db.close()


def test_db_initialization(temp_db: KnowledgeDB):
    """Verifies that KnowledgeDB initializes tables and FTS5 in WAL mode."""
    cursor = temp_db.conn.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    assert mode.lower() == "wal"

    cursor = temp_db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name;"
    )
    table_names = [row[0] for row in cursor.fetchall()]
    assert "projects" in table_names
    assert "project_files" in table_names
    assert "doc_contents" in table_names
    assert "doc_chunks" in table_names
    assert "doc_chunks_fts" in table_names
    assert "project_lexicon" in table_names


def test_markdown_reader_hierarchical_chunking(tmp_path: Path):
    """Verifies MarkdownReader parses YAML frontmatter and hierarchical headings."""
    md_file = tmp_path / "sample.md"
    md_content = """---
title: "Project Governance Guide"
tags: ["governance", "standards"]
---
# Welcome to OSSProject
This is the root introduction.

## Architecture
Overview of the core architecture.

### 3-Tier Pipeline
Gate 1, Gate 2, and Gate 3 workflow.
"""
    md_file.write_text(md_content, encoding="utf-8")

    reader = MarkdownReader()
    assert reader.can_read(md_file) is True

    parsed = reader.parse(md_file)
    assert parsed.doc_type == "md"
    assert parsed.metadata["title"] == "Project Governance Guide"
    assert "governance" in parsed.metadata["tags"]
    assert len(parsed.chunks) >= 3

    # Check hierarchical heading format
    headings = [c.heading for c in parsed.chunks]
    assert any("Welcome to OSSProject" in h for h in headings)
    assert any("Architecture" in h for h in headings)
    assert any("3-Tier Pipeline" in h for h in headings)


def test_text_reader(tmp_path: Path):
    """Verifies TextReader parses plain text documents into paragraph chunks."""
    txt_file = tmp_path / "readme.txt"
    txt_content = "Paragraph 1: Initial setup.\n\nParagraph 2: Second step configuration."
    txt_file.write_text(txt_content, encoding="utf-8")

    reader = TextReader()
    assert reader.can_read(txt_file) is True

    parsed = reader.parse(txt_file)
    assert parsed.doc_type == "txt"
    assert len(parsed.chunks) >= 1
    assert "Initial setup" in parsed.raw_text


def test_lexicon_harvest_and_expansion():
    """Verifies LexiconHarvester extracts project terms and expands queries."""
    sample_text = """
    We follow the 3-Tier Pipeline standard with Gate 1, Gate 2, and Gate 3.
    Enforce Zero-Fake Protocol and PAD for on-device SLM models.
    Run `make stage-pr` before deployment.
    """
    harvested = LexiconHarvester.harvest(sample_text)
    assert "3-Tier" in harvested
    assert "Zero-Fake" in harvested
    assert "PAD" in harvested

    mock_lexicon = [{"term": "3-Tier"}, {"term": "Gate 1"}, {"term": "PAD"}]
    expanded = LexiconHarvester.expand_query("How does 3-tier work?", mock_lexicon)
    assert "3-Tier" in expanded


def test_cas_deduplication_and_pointer_reuse(doc_manager: DocumentManager, tmp_path: Path):
    """Verifies that identical files across directories are deduplicated with zero re-indexing."""
    proj_dir = tmp_path / "my_project"
    proj_dir.mkdir()

    file_a = proj_dir / "doc_a.md"
    file_b = proj_dir / "doc_b.md"  # exact same content as file_a
    content = "# Standard Workflow\n\nThis is a reusable standard guide."
    file_a.write_text(content, encoding="utf-8")
    file_b.write_text(content, encoding="utf-8")

    stats = doc_manager.add_project(str(proj_dir), name="MyProject")
    assert stats["scanned_files"] == 2
    assert stats["added_files"] == 1
    assert stats["reused_files"] == 1  # file_b reused content from file_a!

    # Verify doc_contents table only has 1 physical row
    cursor = doc_manager.db.conn.execute("SELECT COUNT(*) FROM doc_contents")
    assert cursor.fetchone()[0] == 1

    # Verify project_files has 2 logical rows
    cursor = doc_manager.db.conn.execute("SELECT COUNT(*) FROM project_files")
    assert cursor.fetchone()[0] == 2


def test_subfolder_and_parent_folder_indexing(doc_manager: DocumentManager, tmp_path: Path):
    """Verifies indexing a subfolder first, then indexing the parent folder reuses existing files."""
    parent_dir = tmp_path / "root_repo"
    sub_dir = parent_dir / "sub_module"
    sub_dir.mkdir(parents=True)

    file_in_sub = sub_dir / "sub_doc.md"
    file_in_sub.write_text("# Sub Module Doc\n\nContent inside sub module.", encoding="utf-8")

    file_in_parent = parent_dir / "parent_doc.md"
    file_in_parent.write_text("# Parent Doc\n\nContent in parent directory.", encoding="utf-8")

    # 1. Add subfolder first
    sub_stats = doc_manager.add_project(str(sub_dir), name="SubModule")
    assert sub_stats["added_files"] == 1
    assert sub_stats["reused_files"] == 0

    # 2. Add parent folder
    parent_stats = doc_manager.add_project(str(parent_dir), name="ParentRepo")
    assert parent_stats["scanned_files"] == 2
    # sub_doc.md content hash already exists in DB!
    assert parent_stats["reused_files"] == 1
    assert parent_stats["added_files"] == 1


def test_fts5_search_and_project_filtering(doc_manager: DocumentManager, tmp_path: Path):
    """Verifies FTS5 BM25 search across projects and project-specific filtering."""
    proj1_dir = tmp_path / "proj1"
    proj1_dir.mkdir()
    (proj1_dir / "guide.md").write_text(
        "# Deployment Protocol\n\nMust pass 3-Tier gate reviews and secret audit.",
        encoding="utf-8",
    )

    proj2_dir = tmp_path / "proj2"
    proj2_dir.mkdir()
    (proj2_dir / "readme.md").write_text(
        "# Frontend Guidelines\n\nUse React and CSS modules.",
        encoding="utf-8",
    )

    doc_manager.add_project(str(proj1_dir), name="ProjectAlpha")
    doc_manager.add_project(str(proj2_dir), name="ProjectBeta")

    # Cross-project search
    results = doc_manager.search("audit")
    assert len(results) >= 1
    assert results[0]["project_id"] == "projectalpha"

    # Scoped project search
    results_filtered = doc_manager.search("audit", project_id="projectbeta")
    assert len(results_filtered) == 0

    results_matched = doc_manager.search("React", project_id="projectbeta")
    assert len(results_matched) >= 1
    assert results_matched[0]["project_id"] == "projectbeta"


@pytest.mark.asyncio
async def test_mcp_doc_tools_integration(tmp_path: Path):
    """Verifies that MCP server responds to skybrain_doc_list and skybrain_doc_import."""
    server = SkyBrainMCPServer()

    # 1. Call skybrain_doc_list
    list_req = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {
            "name": "skybrain_doc_list",
            "arguments": {}
        }
    }
    resp = await server.handle_request(list_req)
    assert resp is not None
    assert "result" in resp
    content = resp["result"]["content"][0]["text"]
    assert "total_projects" in content

    # 2. Call skybrain_doc_import on a sample directory
    sample_dir = tmp_path / "mcp_sample_project"
    sample_dir.mkdir()
    (sample_dir / "spec.md").write_text("# MCP Integration Spec\n\nHigh performance local RAG.", encoding="utf-8")

    import_req = {
        "jsonrpc": "2.0",
        "id": "2",
        "method": "tools/call",
        "params": {
            "name": "skybrain_doc_import",
            "arguments": {
                "path": str(sample_dir),
                "name": "MCPSample"
            }
        }
    }
    import_resp = await server.handle_request(import_req)
    assert import_resp is not None
    import_content = import_resp["result"]["content"][0]["text"]
    assert "success" in import_content

    # 3. Call skybrain_doc_search and verify engine_metadata & transparency
    search_req = {
        "jsonrpc": "2.0",
        "id": "3",
        "method": "tools/call",
        "params": {
            "name": "skybrain_doc_search",
            "arguments": {
                "query": "RAG",
                "project": "mcpsample"
            }
        }
    }
    search_resp = await server.handle_request(search_req)
    assert search_resp is not None
    assert "result" in search_resp
    search_json = json.loads(search_resp["result"]["content"][0]["text"])
    assert "engine_metadata" in search_json
    assert "retrieval_mode" in search_json["engine_metadata"]
    assert "llm_enhanced" in search_json["engine_metadata"]
    assert "confidence_level" in search_json["engine_metadata"]
    assert len(search_json["results"]) >= 1
    assert "contains_vlm_diagram" in search_json["results"][0]


def test_single_file_import(temp_db: KnowledgeDB, tmp_path: Path):
    """Verifies that DocumentManager.add_project supports importing a single file directly."""
    single_doc = tmp_path / "standalone_spec.md"
    single_doc.write_text("# Standalone Specification\n\nDirect file import without folder wrapping.", encoding="utf-8")

    manager = DocumentManager(db=temp_db)
    stats = manager.add_project(str(single_doc), name="SingleDocProject")

    assert stats["project_id"] == "singledocproject"
    assert stats["scanned_files"] == 1
    assert stats["added_files"] == 1

    # Search for content from the single file
    results = manager.search("Standalone", project_id="singledocproject")
    assert len(results) >= 1
    assert "standalone_spec.md" in results[0]["relative_path"]


def test_pdf_reader_visual_intelligence(tmp_path: Path):
    """Verifies that PdfReader instantiates with visual intelligence configuration and parses safely."""
    from skybrain.store.readers.pdf import PdfReader

    # Test initialization with min_image_bytes
    reader = PdfReader(min_image_bytes=1024, assets_dir=tmp_path / "assets")
    assert reader.min_image_bytes == 1024
    assert reader.can_read(Path("test.pdf")) is True
    assert reader.can_read(Path("test.txt")) is False


def test_modular_vision_registry_and_upgrade(temp_db: KnowledgeDB, tmp_path: Path):
    """Verifies VisionRegistry modularity, asset preservation, and reindex_vision lifecycle."""
    from skybrain.store.vision import VisionRegistry, BaseVisionAnalyzer, VisionAnalysisResult

    # 1. Verify registry list
    available = VisionRegistry.list_available()
    assert "default" in available

    # 2. Register mock upgraded vision analyzer
    class MockUpgradedVision(BaseVisionAnalyzer):
        model_name = "qwen3-vl-upgraded"

        def analyze(self, image_bytes, context=None):
            return VisionAnalysisResult(
                image_hash="imghash123",
                ocr_text="Gate 1 -> Gate 2 -> Gate 3",
                diagram_summary="3-Tier Release Pipeline Flowchart",
                model_name=self.model_name,
                confidence=0.99,
            )

    VisionRegistry.register("mock_upgraded", MockUpgradedVision)

    # 3. Simulate stored visual asset in temp_db
    test_img = tmp_path / "test_asset.png"
    test_img.write_bytes(b"fake_png_data_1234567890")

    temp_db.register_project("proj1", "Proj1", str(tmp_path))
    temp_db.store_content("contenthash1", "pdf", "raw text", {})
    temp_db.store_doc_image(
        image_hash="imghash123",
        content_hash="contenthash1",
        page_num=1,
        image_index=1,
        image_name="pipeline.png",
        mime_type="image/png",
        size_bytes=len(test_img.read_bytes()),
        storage_path=str(test_img),
        vision_model=None,  # Not analyzed yet
    )

    manager = DocumentManager(db=temp_db)
    reindex_res = manager.reindex_vision(target_model="mock_upgraded")

    assert reindex_res["total_candidates"] == 1
    assert reindex_res["upgraded_images"] == 1
    assert reindex_res["vision_model"] == "qwen3-vl-upgraded"

    # Verify updated record in db
    imgs = temp_db.get_doc_images("contenthash1")
    assert len(imgs) == 1
    assert imgs[0]["diagram_summary"] == "3-Tier Release Pipeline Flowchart"
    assert imgs[0]["ocr_text"] == "Gate 1 -> Gate 2 -> Gate 3"
    assert imgs[0]["vision_model"] == "qwen3-vl-upgraded"



