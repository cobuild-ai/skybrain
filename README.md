# 🧠 SkyBrain: Universal On-Device AI Engine & Multi-Lens Reviewer

<div align="center">

<p align="center">
  <b>English</b> |
  <a href="README.ko.md">한국어</a> |
  <a href="README.id.md">Bahasa Indonesia</a>
</p>

[![Platform: Apple Silicon](https://img.shields.io/badge/Platform-macOS%20Apple%20Silicon%20(Metal)-black?logo=apple&logoColor=white)](#-key-platform-features)
[![Inference: Metal GPU](https://img.shields.io/badge/Inference-Apple%20Metal%20GPU%20(Zero--Docker)-blueviolet)](#-zero-docker-native-metal-gpu-acceleration)
[![API: OpenAI Compatible](https://img.shields.io/badge/API-OpenAI%20v1%20Compatible-412991?logo=openai&logoColor=white)](#-openai-compatible-local-rest-api)
[![Package: uv tool](https://img.shields.io/badge/Package-uv%20tool%20(Rust)-FF4088?logo=python&logoColor=white)](#-quick-start)
[![Review: 5--Lens Engine](https://img.shields.io/badge/Code%20Review-5--Lens%20Multi--Pass-success)](#-5-lens-multi-pass-code-review-engine)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**SkyBrain** is an enterprise-grade, Docker-free, pure-native on-device AI serving daemon and developer productivity platform designed specifically for Apple Silicon (M1/M2/M3/M4) Macs.

It provides zero-latency SLM/LLM local serving (Qwen, Gemma, Llama) with Apple Metal GPU acceleration, a robust local routing proxy with automatic cloud-to-local circuit breaker failover, and a state-of-the-art **5-Lens Multi-Pass Code Review Engine** producing standalone interactive HTML dashboards.

[Key Features](#-key-platform-features) • [Review Demo & Samples](#-5-lens-review-in-action) • [How It Works](#-how-it-works) • [Architecture](ARCHITECTURE.md) • [Quick Start](#-quick-start) • [Repository Structure](#-repository-structure) • [Governance](GEMINI.md)

</div>


---

## 💡 Why SkyBrain? (5 Key Architectural Advantages)

> **"Unleash the full power of your Mac's dormant Metal GPU for maximum developer velocity—with zero cloud token bills and absolute data privacy."**

| Key Advantage | Architectural Detail & Mechanism | Business & Engineering Impact |
| :--- | :--- | :--- |
| 💰 **85%+ Cloud Token Savings** | Offloads repetitive bulk tasks (multi-language translations, boilerplate schemas, unit tests, 50+ line build log summaries) directly to local SLMs (Qwen 3.8 / Gemma) | Drastically reduces operational API costs for premium cloud LLMs (Claude Sonnet, Gemini 1.5 Pro) |
| 🔒 **100% Air-Gapped Data Privacy** | Zero outbound network transmission. Proprietary source code, system logs, environment secrets, and intellectual property never leave your local machine | Complies with strict enterprise security and data privacy mandates with complete peace of mind |
| ⚡ **Zero-Docker Pure Metal Speed** | Bypasses slow Docker virtualization layers; runs directly on macOS, linking unified RAM directly to Apple Silicon (M1–M4) Metal GPU cores (`-DGGML_METAL=on`) | Zero-copy memory architecture and ultra-low latency token streaming right out of the box |
| 🛡️ **Host RAM Protection & Self-Healing** | Pre-flight memory guard intercepts intensive inference when free RAM drops below 2.5 GB; auto-healing supervisor revives downed daemons in under 500ms via 150ms heartbeat pings | Eliminates macOS OOM freezes and provides an unyielding, resilient local circuit breaker |
| 🔍 **5-Lens Quality Guard & Zero-Fake** | Analyzes code across Clean Code, Clean Architecture, Security, Performance, plus our specialized `AI Conduct` lens that flags **fake hardcoded mocks, hallucinated APIs, and silent exception swallowing** | Catches subtle AI-generated anti-patterns before they reach production, guaranteeing code integrity |

---

## 📊 Release Status

| Component | Version | Architecture | Status | Primary Highlights |
| :--- | :---: | :---: | :---: | :--- |
| 🧠 **SkyBrain Core & Daemon** | `v0.2.0` | **macOS Apple Silicon (Metal)** | **Production Stable** | Docker-Free Native Metal GPU, 150ms Auto-Healing Supervisor, Pre-flight Host Memory Guard, Zero-Drop Circuit Breaker |
| 🔍 **Multi-Lens Review Engine** | `v0.2.0` | **5-Lens Strategy Pattern** | **Production Stable** | 5 Lenses (`CleanCode`, `Architecture`, `Security`, `Performance`, `AIConduct`), Chain-of-Verification, Interactive Glassmorphism HTML Dashboard |
| 🔌 **SkyBrain MCP Server** | `v0.2.0` | **Model Context Protocol** | **Production Stable** | Universal IDE integration (Cursor, VS Code, Antigravity, Claude Desktop) |

---

## 🌟 Key Platform Features

### ⚡ Zero-Docker, Native Metal GPU Acceleration
- **Pure Native Speed:** Runs directly on macOS without virtualization overhead or Docker daemon bloat.
- **Unified Memory Utilization:** Fully utilizes Apple Silicon Unified Memory architecture with zero memory copy penalties (`-DGGML_METAL=on`).
- **Hot-Swappable SLMs:** Seamless switching between Qwen 2.5 (3.8B/7B), Google Gemma (2B/4B E4B), and custom GGUF models.

### 🌐 OpenAI-Compatible Local REST API
- **Drop-In Compatibility:** Serves `/v1/chat/completions` and `/v1/models` on `http://127.0.0.1:8000`.
- **Universal SDK Support:** Compatible with OpenAI Python/Node SDKs, LangChain, LiteLLM, and LlamaIndex.
- **Corporate Proxy & SSL Self-Healing:** Native support for corporate MITM SSL inspection bundles (`SKYBRAIN_CA_BUNDLE`) and proxy exclusion (`NO_PROXY`).

### 🛡️ Pre-flight Host Memory Guard & Auto-Healing
- **Host Memory Protection (`SystemGuard`):** Continuously measures available RAM via native `sysctl` + `vm_stat`. Prevents macOS freezes by intercepting heavy inference when free memory falls below 2.5 GB.
- **Sub-150ms Auto-Healing:** High-speed heartbeat ping before every request; if the daemon crashed or stopped, it revives in the background automatically in under 500ms.
- **Atomic Process Cleaner:** Eliminates orphaned and zombie processes cleanly using atomic `SIGTERM` ➔ `SIGKILL` sequencing.

### 🔍 5-Lens Multi-Pass Code Review Engine
- **Blind Multi-Perspective Analysis:** Reviews source code across 5 independent architectural disciplines:
  1. 🧹 **Clean Code Lens:** Robert C. Martin principles, Single Responsibility (SRP), DRY, expressive naming.
  2. 🏛️ **Clean Architecture Lens:** Uncle Bob dependency rule, boundary isolation, Contract Facade pattern.
  3. 🛡️ **Security Lens:** OWASP Top 10, path traversal, injection vectors, unhandled exception leaks.
  4. ⚡ **Performance Lens:** Resource lifecycles (sockets/SSL), blocking I/O on hot paths, complexity.
  5. 🤖 **AI Conduct Lens (New):** Detects subtle AI-generated anti-patterns: fake mock hardcoding, hallucinated APIs, silent exception swallowing (`except Exception: pass`), and unfinished stubs.
- **Chain-of-Verification (CoVe):** Every detected finding is cross-verified by an independent on-device verification pass to eliminate false positives.
- **Tier-1 Content Hash Disk Cache:** Instant sub-second results for unchanged files using SHA-256 caching.

### 🎯 Lead-LLM Cross-Check Structured Data Payload
- **Optimized for Lead LLMs (Cloud AI):** Instead of heavy browser HTML reports, SkyBrain outputs structured JSON (`to_lead_llm_payload()`) containing candidate findings (`PRE-XX`), rule justifications, 2/3 consensus rates, and tailored cross-check prompts for immediate verification by Cloud Gemini/Claude.
- **85%+ Token Overhead Reduction:** Replaces 25KB+ HTML boilerplate with compact <3KB JSON payloads, preventing context saturation in orchestrator agents.
- **Code Health Score (0–100):** Algorithmic penalty-weighted score assessing overall codebase health.

### 📚 Multi-Project Document Intelligence & Materialized Cache Hub
- **100% On-Device Sovereign RAG:** Air-gapped indexing and retrieval across Markdown, TXT, and PDF documents with zero external network transmission.
- **Content-Addressed Storage (CAS Deduplication):** Separates physical content (SHA-256) from logical paths. Renaming/moving files incurs 0s re-embedding cost, and parent folder imports reuse existing sub-project files with 0% disk waste.
- **Hybrid Lexical & Domain Expansion:** High-speed SQLite FTS5 (BM25) search coupled with automated project domain lexicon harvesting (`3-Tier`, `Gate 1/2/3`, `PAD`, `Zero-Fake`).
- **Read-Only Source Principle:** Never touches or mutates original repository documents; maintains an isolated materialized cache in `~/.skybrain/knowledge.db` (WAL mode).

---

## 🎭 5-Lens Review in Action

| Lens | Detected Anti-Pattern | Severity | AI-Driven Fix & Suggestion |
| :--- | :--- | :---: | :--- |
| 🤖 **AI Conduct** | Fake hardcoded mock return `return {"status": "ok"}` | 🚨 **CRITICAL** | Implement actual database query or raise explicit `NotImplementedError`. |
| 🛡️ **Security** | `except Exception: pass` silently swallowing errors | 🔴 **HIGH** | Catch specific `(json.JSONDecodeError, OSError)` and log with `logger.warning()`. |
| 🏛️ **Architecture** | Inner layer directly importing concrete models (`DIP violation`) | 🔴 **HIGH** | Apply **Contract Facade Pattern** in `base.py` and re-export abstractions. |
| ⚡ **Performance** | `ssl.SSLContext` created repeatedly without resource reuse | 🟡 **MEDIUM** | Cache or wrap context creation in a lifecycle-managed helper. |
| 🧹 **Clean Code** | Magic number `-1` used for offloading all GPU layers | 🟡 **MEDIUM** | Declare explicit module constant `ALL_GPU_LAYERS = -1`. |

---

## 🔄 How It Works

```mermaid
sequenceDiagram
    autonumber
    actor Dev as 👨‍💻 Developer / Lead Agent (Cloud LLM)
    participant CLI as 🖥️ SkyBrain CLI (`uv tool`) / MCP
    participant Guard as 🧠 4-Tier Hardware Diagnostic Guard
    participant Super as 🩺 Supervisor (Auto-Heal)
    participant Engine as 🔍 ReviewEngine (5 Lenses)
    participant Daemon as ⚡ On-Device Daemon (Metal SLM)
    participant Lead as 👑 Lead LLM (Gemini/Claude)

    Dev->>CLI: skybrain review ./src --json
    CLI->>Guard: Evaluate macOS Unified Memory & Metal acceleration
    Guard-->>CLI: Memory Safe (6.5 GB available / OPTIMAL)
    CLI->>Super: check_health_fast()
    alt Daemon Down
        Super->>Super: Auto-heal daemon in background
    end
    CLI->>Engine: Run 5-Lens Multi-Pass Review
    loop For Each Lens (CleanCode, Architecture, Security, Performance, AIConduct)
        Engine->>Daemon: Query system prompt + code slice
        Daemon-->>Engine: Structured JSON findings
        Engine->>Daemon: Chain-of-Verification (Fact-check findings)
        Daemon-->>Engine: Verified findings
    end
    Engine->>CLI: Return to_lead_llm_payload() compact JSON
    CLI->>Lead: Forward PRE-XX candidate findings & verification prompt
    Lead-->>Dev: Mutual fact-checking against active code & final action
```

---

## 📦 Quick Start

### 1. One-Touch Global CLI Installation (`uv tool` - Recommended)
SkyBrain enforces the **Universal `uv tool` Standard** for isolated, reproducible, zero-friction developer experience:

```bash
# Global CLI installation (Isolated environment with Metal acceleration)
CMAKE_ARGS="-DGGML_METAL=on" uv tool install git+https://github.com/cobuild-ai/skybrain.git

# Or Local Developer Editable Installation (Live source reflection)
git clone https://github.com/cobuild-ai/skybrain.git
cd skybrain
CMAKE_ARGS="-DGGML_METAL=on" uv tool install --editable .
```

### 2. Zero-Config One-Touch Setup Script (`setup.sh`)
```bash
./setup.sh
```
`setup.sh` automatically performs 4-tier hardware assessment, compiles Metal bindings, runs 94 unit tests, registers the `skybrain` global CLI, and generates `.vscode/mcp.json` for IDE integration.

### 3. Common CLI Operations
```bash
# Start background on-device daemon (Auto-downloads default SLM if missing)
skybrain start

# Check real-time status & host memory guard
skybrain status

# Check model catalog with real-time 4-tier suitability (🟢/⚠️/🛑) and recommended GPU layers
skybrain model list

# Execute 5-Lens Multi-Pass Code Review on a file or directory (supports -j for Lead LLM JSON)
skybrain review ./skybrain/core/config.py -j

# Direct on-device SLM query with zero cloud token cost ($0 Token)
skybrain query "Explain Clean Architecture Dependency Inversion Principle"

# Index a directory into multi-project knowledge base with CAS deduplication
skybrain doc add ./00-governance --name "OSS-Governance"

# Search knowledge base with SQLite FTS5 & domain lexicon expansion
skybrain doc search "3-Tier Pipeline" --project oss-governance

# List all registered projects and active file statistics
skybrain doc list

# Incremental sync for changed/modified files
skybrain doc sync

# Stop background daemon
skybrain stop
```

---

## 💻 Model Context Protocol (MCP) Integration

SkyBrain provides a first-class, standard Model Context Protocol (MCP) server (`skybrain-mcp`), allowing **Antigravity IDE, Anthropic Claude CLI (Claude Code), Cursor, and VS Code** to seamlessly leverage local Apple Silicon Metal SLM intelligence as high-speed worker tools:

### 🚀 1-Command Setup

```bash
# Register SkyBrain in Anthropic Claude CLI (Claude Code)
claude mcp add skybrain -- uv tool run skybrain-mcp

# Or check all available MCP tools directly from CLI
skybrain mcp tools
skybrain mcp setup
```

### 🛠️ Available MCP Tools

| MCP Tool | Description | Target Use Case |
| :--- | :--- | :--- |
| 🔍 `skybrain_code_review` | Multi-Lens semantic review (`CleanCode`, `Architecture`, `Security`, `Performance`, `AIConduct`) | Automatic PR & file audits in IDE |
| ⚖️ `skybrain_expert_consensus` | 2/3 majority consensus multi-pass evaluation across 6 specialized perspectives | High-rigor consensus verification |
| ⚡ `skybrain_query` | Direct local SLM query with zero cloud token cost (supports multimodal vision) | Quick on-device code generation |
| 🌐 `skybrain_translate` | Offline multi-lingual translation across 12 languages | Translation & docs synchronization |
| 📜 `skybrain_summarize_logs` | High-throughput noise filtering and root-cause analysis for 50+ line logs | Zero-leak build log debugging |
| 🩺 `skybrain_status` | Real-time daemon status, active model, and host memory guard level | Hardware and daemon readiness |
| 📚 `skybrain_doc_search` | Multi-project SQLite FTS5 (BM25) search with project domain lexicon expansion | Instant zero-cloud project context retrieval |
| 📥 `skybrain_doc_import` | Index a local directory into CAS knowledge base with zero-waste deduplication | Multi-project document registration |
| 📋 `skybrain_doc_list` | List registered projects, document counts, and indexing status | Knowledge hub overview |

### ⚙️ IDE Configuration (`mcp_config.json` / `settings.json`)

```json
{
  "mcpServers": {
    "skybrain": {
      "command": "uv",
      "args": ["tool", "run", "skybrain-mcp"]
    }
  }
}
```

---

## 📁 Repository Structure

```
skybrain/
├── pyproject.toml              # Modern Python project configuration (uv & PEP 621)
├── setup.sh                    # Automated one-touch setup and MCP configuration script
├── ARCHITECTURE.md             # In-depth system architecture & circuit breaker diagrams
├── GEMINI.md                   # Truth-First & enterprise governance guidelines
│
├── skybrain/
│   ├── cli/                    # Typer-based CLI commands (start, stop, status, review, ask)
│   │   └── main.py
│   ├── core/                   # Core settings & host hardware guards
│   │   ├── config.py           # Pydantic BaseSettings, SSL bundles & proxy configuration
│   │   └── monitor.py          # Native sysctl/vm_stat memory monitor & SystemGuard
│   ├── engine/                 # Apple Silicon Metal SLM inference engine
│   │   └── model_catalog.py    # llama-cpp-python bindings, GGUF catalog & auto-downloader
│   ├── gateway/                # Local Routing Proxy & Circuit Breaker
│   │   └── proxy.py            # HTTP 429/503 cloud-to-local zero-drop failover client
│   ├── server/                 # FastAPI background daemon & supervisor
│   │   ├── app.py              # OpenAI-compatible /v1 endpoints & memory telemetry
│   │   └── supervisor.py       # Atomic process killer & sub-150ms auto-healing supervisor
│   ├── review/                 # 5-Lens Multi-Pass Code Review Platform
│   │   ├── models.py           # Pure domain models (Severity, Category, Finding, Report)
│   │   ├── engine.py           # Multi-pass orchestrator with Rich Progress tracking
│   │   ├── verification.py     # Chain-of-Verification (CoVe) fact-checker
│   │   ├── html_report.py      # Standalone interactive glassmorphism HTML generator
│   │   └── lenses/             # Strategy Pattern review lenses
│   │       ├── base.py         # Contract Facade re-exporting abstractions
│   │       ├── clean_code.py   # Robert C. Martin clean code principles
│   │       ├── clean_architecture.py # Dependency Inversion & layer boundary rules
│   │       ├── security.py     # OWASP, path traversal & exception leakage rules
│   │       ├── performance.py  # Resource lifecycle, memory leaks & blocking I/O
│   │       └── ai_conduct.py   # AI anti-patterns: fake hardcoding, hallucination & stubs
│   └── mcp/                    # Model Context Protocol server for IDEs
│
└── tests/                      # 111 comprehensive pytest test suites (100% passing)
```

---

## 🔒 Privacy, Truth-First & Governance Principles

1. **Truth-First Protocol (Zero Fake Policy):**
   - No mock responses, fake status strings, or regex hacks pretending to be AI intelligence. All insights originate from real, verified local SLM inference.
2. **100% On-Device Privacy:**
   - Zero telemetry, zero keystroke recording, and zero cloud dependencies for local operations. All code reviewed remains strictly inside your Apple Silicon Mac's unified memory.
3. **Universal `uv tool` Mandate:**
   - No legacy global `pip install` or brittle virtual environment path dependencies. All Python CLI tools are strictly managed through isolated, high-speed `uv tool` environments.

---

## 📄 License & Maintainers

- **License:** Apache License 2.0
- **Organization:** [cobuild-ai](https://github.com/cobuild-ai)
- **Maintainer:** `smilelife` (<mysmilelife@gmail.com>)
- **Public Support:** <deartalkai.dev@gmail.com>
