# 📋 Changelog
All notable changes to the **SkyBrain** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2026-09-03

### 🚀 Added
- **5-Lens Multi-Pass Code Review Platform**:
  - Implemented Strategy Pattern review engine with 5 independent specialized lenses:
    - 🧹 `CleanCodeLens`: Robert C. Martin clean code, SRP, DRY, expressive naming.
    - 🏛️ `CleanArchitectureLens`: Dependency Inversion Principle, layer boundary isolation.
    - 🛡️ `SecurityLens`: OWASP Top 10, path traversal, exception leakage prevention.
    - ⚡ `PerformanceLens`: Resource lifecycle, blocking I/O, algorithmic complexity.
    - 🤖 `AIConductLens`: Detects AI anti-patterns (fake mock hardcoding, phantom API hallucinations, silent exception swallowing `except Exception: pass`, and incomplete TODO stubs).
  - Added Chain-of-Verification (CoVe) on-device fact-checker to eliminate false positives.
  - Added Tier-1 Content Hash Disk Cache (`~/.skybrain/cache/`) for sub-second repeat reviews.
- **Standalone Interactive HTML Dashboard**:
  - Implemented self-contained glassmorphism HTML report generator (`skybrain/review/html_report.py`).
  - Added Code Health Score (0–100) with weighted defect severity penalties.
  - Added multi-dimensional real-time filtering by lens, severity, and text search query.
  - Added one-click code suggestion clipboard copying.
  - Added live multilingual i18n switcher (`English`, `한국어`, `Bahasa Indonesia`).
- **Pre-flight Host Memory Guard & Stability Architecture**:
  - Implemented macOS native `sysctl` + `vm_stat` memory monitor (`HostMemoryMonitor`).
  - Added `SystemGuard` pre-flight evaluator preventing macOS freezes by intercepting inference when RAM < 2.5 GB.
  - Added `BackgroundMemoryWatcher` background thread (15s interval) and `/v1/system/memory` telemetry.
- **150ms Auto-Healing Daemon Supervisor**:
  - Implemented `check_health_fast()` with 150ms heartbeat ping and sub-500ms background revival.
  - Added `kill_stale_daemon_processes()` atomic 2-stage process killer (`SIGTERM` ➔ `SIGKILL`).
- **Local Routing Proxy & Circuit Breaker**:
  - Implemented zero-drop failover from cloud LLMs (Gemini, Claude, OpenAI) to local SLM on HTTP 429/503.
- **Tri-lingual Documentation Standard**:
  - Published comprehensive 3-language documentation (`README.md`, `README.ko.md`, `README.id.md`) adhering to OSS enterprise governance.

### 🛠️ Changed
- Refactored `skybrain.review.lenses.base` into a **Contract Facade** re-exporting domain abstractions, decoupling concrete lenses from inner models.
- Refactored `skybrain.core.config` for strict Single Responsibility, thread-safe proxy settings, and environment fallback helpers.
- Standardized CLI terminal messages with universal English phrasing and intuitive emojis.
- Expanded automated unit test suite to 111 comprehensive tests (100% passing).

---

## [0.1.0] - 2026-08-25
- Initial release of SkyBrain daemon.
- Docker-free Apple Silicon Metal GPU acceleration via `llama-cpp-python`.
- OpenAI-compatible `/v1/chat/completions` and `/v1/models` endpoints.
- Auto-download catalog for Gemma and Qwen SLMs.
- Initial MCP server integration for VS Code and Cursor.
