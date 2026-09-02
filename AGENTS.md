# 🏛️ SkyBrain Universal Agent Collaboration Protocol (AGENTS.md)

This document standardizes how AI agents (Antigravity, Cursor, Cline, Roo Code, GitHub Copilot, Claude) interact with SkyBrain.

---

## ⚡ 1. The SkyBrain Assistant Role

SkyBrain runs on macOS Apple Silicon Metal as an ultra-fast on-device neural serving engine.
The primary Cloud LLM (Gemini / Claude / GPT-4) acts as the **Lead Supervisor**, while SkyBrain acts as the **Local Sub-Worker ($0 Cloud Token)**.

---

## 🛠️ 2. Editor Integration Quick Reference

### For VS Code / Cline / Roo Code / Cursor
SkyBrain bundles a standard Model Context Protocol (MCP) server.

1. Run `./setup.sh` in the repository root.
2. In VS Code or Cline, register the MCP server:
```json
{
  "mcpServers": {
    "skybrain": {
      "command": "/path/to/skybrain/.venv/bin/python",
      "args": ["-m", "skybrain.mcp"]
    }
  }
}
```
3. Available MCP Tools:
   - `skybrain_expert_consensus`: Evaluates files with 6 expert lenses and 2/3 majority consensus.
   - `skybrain_query`: Direct zero-latency Qwen 3.8 local inference.
   - `skybrain_translate`: Fast simultaneous interpreter across 12 languages.
   - `skybrain_summarize_logs`: Clean runtime error diagnosis.

---

## 🧪 3. Verification Commands
```bash
# Start background serving daemon
.venv/bin/skybrain start

# Run 2/3 consensus code audit
.venv/bin/python scripts/skybrain_expert.py --target <FILE> --rounds 3

# Run all 56 unit tests
.venv/bin/python -m pytest tests/ -v
```
