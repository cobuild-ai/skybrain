"""
SkyBrain Model Context Protocol (MCP) Server.

Standard JSON-RPC 2.0 MCP implementation allowing VS Code, Cursor, Cline,
Roo Code, and Claude Desktop to interact with local SkyBrain (Qwen 3.8 Metal)
and the 2/3 Consensus Multi-Lens ExpertEngine without any external cloud dependencies.
"""

import sys
import json
import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List

from skybrain.expert.engine import ExpertEngine
from skybrain.expert.registry import LensRegistry
from skybrain.review.client import SkyBrainClient
from skybrain.core.config import settings


TOOLS = [
    {
        "name": "skybrain_expert_consensus",
        "description": "Run 2/3 majority consensus multi-lens code evaluation across 6 specialized perspectives (Clean Code, Architecture, Test Rules, Design Patterns, Security, Performance). Returns vetted findings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the source code file to evaluate (absolute or relative)."
                },
                "rounds": {
                    "type": "integer",
                    "description": "Number of evaluation passes per lens (default: 3 for 2/3 majority vote, 5 for high-rigor).",
                    "default": 3
                },
                "lenses": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of lens IDs to run (default: all 6 lenses)."
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "skybrain_query",
        "description": "Query local SkyBrain (Qwen 3.8 on Apple Silicon Metal) for fast zero-cost text inference, translation, or multimodal vision OCR.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Prompt or instruction to execute locally."
                },
                "image_path": {
                    "type": "string",
                    "description": "Optional local image path for multimodal vision/screenshot analysis."
                },
                "system_prompt": {
                    "type": "string",
                    "description": "Optional system prompt."
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "skybrain_translate",
        "description": "Translate text across 12 languages (KO, EN, ID, JA, ZH, ES, FR, DE, VI, TL, TH, MS) using on-device Qwen 3.8.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to translate."
                },
                "target_lang": {
                    "type": "string",
                    "description": "Target language code or name (e.g. 'EN', 'KO', 'ID', 'English')."
                },
                "source_lang": {
                    "type": "string",
                    "description": "Source language (default: auto/KO).",
                    "default": "KO"
                }
            },
            "required": ["text", "target_lang"]
        }
    },
    {
        "name": "skybrain_summarize_logs",
        "description": "Locally filter noise and summarize large build or runtime logs (50+ lines) without sending sensitive tokens to the cloud.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "log_text": {
                    "type": "string",
                    "description": "Raw log text to clean and summarize."
                },
                "focus": {
                    "type": "string",
                    "description": "Specific focus: 'errors', 'performance', 'security', or 'all'.",
                    "default": "errors"
                }
            },
            "required": ["log_text"]
        }
    },
    {
        "name": "skybrain_code_review",
        "description": "Run Multi-Lens static and semantic Pre-Screening Code Review on a Python file (CleanCode, Architecture, Security, Performance, AIConduct). Returns structured candidate findings optimized for Lead LLM (Claude/Gemini) cross-checking and verification.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the Python source code file to review."
                },
                "rounds": {
                    "type": "integer",
                    "description": "Voting rounds per lens (default: 1 for fast, 3 for consensus).",
                    "default": 1
                },
                "verify": {
                    "type": "boolean",
                    "description": "Run Chain-of-Thought verification on findings (default: true).",
                    "default": True
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "skybrain_status",
        "description": "Check SkyBrain daemon health, active model, memory guard level, and Apple Silicon Metal GPU readiness.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "skybrain_doc_search",
        "description": "Search multi-project document knowledge base using SQLite FTS5 (BM25) with project domain lexicon query expansion. Zero-cloud on-device retrieval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query or natural language question."
                },
                "project": {
                    "type": "string",
                    "description": "Optional project ID to filter by (e.g., 'ossproject', 'deartalk'). Omit for cross-project search."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of chunks to return (default: 5).",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "skybrain_doc_import",
        "description": "Index a file or directory as a project in the on-device CAS knowledge base with automatic deduplication and visual diagram intelligence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Local file path (e.g. document.pdf) or directory path to scan and index."
                },
                "name": {
                    "type": "string",
                    "description": "Optional project name (defaults to file or folder name)."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "skybrain_doc_list",
        "description": "List all registered projects, document counts, and indexing statistics in SkyBrain knowledge base.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


class SkyBrainMCPServer:
    """Standard stdio JSON-RPC 2.0 MCP Server."""

    def __init__(self):
        self.settings = settings
        self.client = SkyBrainClient()
        self.engine = ExpertEngine(client=self.client)

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any] | None:
        method = request.get("method")
        msg_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "skybrain",
                        "version": "0.1.0"
                    }
                }
            }

        elif method == "notifications/initialized":
            return None

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": TOOLS
                }
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            try:
                result_text = await self.execute_tool(tool_name, arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result_text
                            }
                        ]
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "isError": True,
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error executing {tool_name}: {str(e)}"
                            }
                        ]
                    }
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

    async def execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        if name == "skybrain_expert_consensus":
            file_path = args["file_path"]
            rounds = args.get("rounds", 3)
            lenses = args.get("lenses")

            # Resolve path
            target_path = Path(file_path).resolve()
            if not target_path.exists():
                return f"Error: File not found: {file_path}"

            report = await self.engine.evaluate_file(
                file_path=target_path,
                lens_ids=lenses,
                num_rounds=rounds
            )

            res = {
                "file": str(target_path),
                "total_evaluations": report.total_evaluations,
                "consensus_items_count": len(report.consensus_items),
                "consensus_items": [
                    {
                        "finding_signature": item.finding_signature,
                        "criterion_id": item.criterion_id,
                        "line_cluster": item.line_cluster,
                        "votes": f"{item.votes_count}/{item.total_rounds}",
                        "ratio": f"{item.consensus_ratio:.1%}",
                        "agreed_message": item.agreed_message,
                        "suggestion": item.agreed_suggestion
                    }
                    for item in report.consensus_items
                ],
                "summary": report.summary()
            }
            return json.dumps(res, indent=2, ensure_ascii=False)

        elif name == "skybrain_query":
            prompt = args["prompt"]
            system_prompt = args.get("system_prompt", "You are SkyBrain, an expert on-device local AI on Apple Silicon.")
            image_path = args.get("image_path")

            if image_path:
                resp = await self.client.query_multimodal(
                    prompt=prompt,
                    image_path=image_path,
                    system_prompt=system_prompt
                )
            else:
                resp = await self.client.query(
                    prompt=prompt,
                    system_prompt=system_prompt
                )
            return resp

        elif name == "skybrain_translate":
            text = args["text"]
            target_lang = args["target_lang"]
            source_lang = args.get("source_lang", "KO")

            prompt = (
                f"You are an expert simultaneous interpreter. "
                f"Translate the following text from {source_lang} to {target_lang}. "
                f"Output ONLY the single-line translated sentence without quotes or notes.\n\n"
                f"Input: \"{text}\""
            )
            return await self.client.query(prompt=prompt)

        elif name == "skybrain_summarize_logs":
            log_text = args["log_text"]
            focus = args.get("focus", "errors")

            prompt = (
                f"Analyze and summarize the following runtime/build log. "
                f"Focus on: {focus}. Filter out noise, highlight root causes, and provide actionable fixes.\n\n"
                f"```\n{log_text}\n```"
            )
            return await self.client.query(prompt=prompt)

        elif name == "skybrain_code_review":
            from skybrain.review.engine import ReviewEngine
            from skybrain.review.lenses.clean_code import CleanCodeLens
            from skybrain.review.lenses.clean_architecture import CleanArchitectureLens
            from skybrain.review.lenses.security import SecurityLens
            from skybrain.review.lenses.performance import PerformanceLens
            from skybrain.review.lenses.ai_conduct import AIConductLens
            from skybrain.review.lenses.resilience import ResilienceLens

            file_path = args["file_path"]
            rounds = args.get("rounds", 1)
            verify = args.get("verify", True)

            target_path = Path(file_path).resolve()
            if not target_path.exists():
                return f"Error: File not found: {file_path}"

            lenses = [
                CleanCodeLens,
                CleanArchitectureLens,
                SecurityLens,
                PerformanceLens,
                AIConductLens,
                ResilienceLens,
            ]
            engine = ReviewEngine(lens_classes=lenses)
            # Run review synchronously in threadpool executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            report = await loop.run_in_executor(
                None,
                lambda: engine.review(
                    file_paths=[target_path],
                    verify=verify,
                    voting_rounds=rounds,
                    use_cache=True,
                )
            )

            res = report.to_lead_llm_payload()
            res["file"] = str(target_path)
            return json.dumps(res, indent=2, ensure_ascii=False)

        elif name == "skybrain_status":
            from skybrain.server.supervisor import DaemonSupervisor
            from skybrain.engine.model_catalog import ModelCatalog, MODEL_PRESETS
            from skybrain.core.monitor import HostMemoryMonitor

            pid = DaemonSupervisor.get_pid()
            catalog = ModelCatalog()
            active_key = catalog.get_active_key()
            mem = HostMemoryMonitor.get_memory_info()

            res = {
                "daemon_running": pid is not None,
                "daemon_pid": pid,
                "active_model_key": active_key,
                "active_model_name": MODEL_PRESETS.get(active_key, {}).get("name", "Unknown"),
                "memory_guard": mem.to_dict(),
            }
            return json.dumps(res, indent=2, ensure_ascii=False)

        elif name == "skybrain_doc_search":
            from skybrain.store.manager import DocumentManager
            from skybrain.server.supervisor import DaemonSupervisor
            from skybrain.engine.model_catalog import ModelCatalog, MODEL_PRESETS

            manager = DocumentManager()
            query = args["query"]
            project = args.get("project")
            limit = args.get("limit", 5)

            # Check daemon & LLM status
            daemon_pid = DaemonSupervisor.get_pid()
            is_daemon_active = daemon_pid is not None
            catalog = ModelCatalog()
            active_key = catalog.get_active_key()
            active_model_name = MODEL_PRESETS.get(active_key, {}).get("name", "Unknown") if is_daemon_active else "None (Pure SQLite FTS5 Engine)"

            results = manager.search(query=query, project_id=project, limit=limit)

            # Annotate results with provenance and diagram flags
            enhanced_results = []
            for r in results:
                chunk_text = r.get("chunk_text", "")
                has_vlm_diagram = "[On-Device Visual Intelligence]" in chunk_text
                r_copy = dict(r)
                r_copy["contains_vlm_diagram"] = has_vlm_diagram
                enhanced_results.append(r_copy)

            engine_metadata = {
                "retrieval_mode": "FTS5_BM25_LEXICAL",
                "llm_enhanced": False,
                "local_daemon_active": is_daemon_active,
                "active_model": active_model_name,
                "confidence_level": "EXACT_SOURCE_RAW",
                "processing_tag": "[💾 Engine: SQLite FTS5 (Pure Raw Text | Zero AI Hallucination)]" if not is_daemon_active else f"[⚡ Engine: SQLite FTS5 + Local Daemon Standby ({active_model_name})]",
                "governance_note": "Truth-First & Zero Fake: Results are exact verbatim chunks extracted from local source files without LLM synthesis.",
            }

            return json.dumps({
                "query": query,
                "project": project or "all",
                "total_results": len(enhanced_results),
                "engine_metadata": engine_metadata,
                "results": enhanced_results,
            }, indent=2, ensure_ascii=False)

        elif name == "skybrain_doc_import":
            from skybrain.store.manager import DocumentManager
            manager = DocumentManager()
            path = args["path"]
            project_name = args.get("name")

            stats = manager.add_project(root_path=path, name=project_name)
            return json.dumps({
                "status": "success",
                "project": stats,
            }, indent=2, ensure_ascii=False)

        elif name == "skybrain_doc_list":
            from skybrain.store.manager import DocumentManager
            manager = DocumentManager()
            projects = manager.list_projects()
            return json.dumps({
                "total_projects": len(projects),
                "projects": projects,
            }, indent=2, ensure_ascii=False)

        else:
            raise ValueError(f"Unknown tool: {name}")

    async def run_stdio(self):
        """Read standard input and write to standard output."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            line = await reader.readline()
            if not line:
                break
            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                request = json.loads(line_str)
                response = await self.handle_request(request)
                if response is not None:
                    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                    sys.stdout.flush()
            except Exception as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()


def main():
    server = SkyBrainMCPServer()
    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()
