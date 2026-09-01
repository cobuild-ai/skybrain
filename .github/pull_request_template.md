## 📝 Summary of Changes
Please include a concise summary of the changes, motivation, and link related issues.
- **Related Issue:** Closes #

---

## 🏷️ Type of Change
- [ ] 🐛 Bug fix (non-breaking fix for a defect)
- [ ] ✨ New feature / enhancement (non-breaking addition)
- [ ] ⚡ Performance / Metal GPU memory optimization
- [ ] 🤖 Model integration (Gemma, Qwen, Llama, etc.)
- [ ] 📖 Journal indexer / backup enhancement
- [ ] 🧪 Testing / CI & automation scripts
- [ ] 📝 Documentation update (READMEs / docs)

---

## 💻 Components & Modules Affected
- [ ] Core Engine & Model Catalog (`skybrain/engine/`)
- [ ] OpenAI Compatible REST API Server (`skybrain/server/`)
- [ ] Supervisor & Daemon Lifecycle (`skybrain/server/supervisor.py`, `scripts/`)
- [ ] Journal Indexer & Markdown Parser (`skybrain/journal/`)
- [ ] CLI Interface (`skybrain/cli/`)
- [ ] CI/CD & Test Automation (`tests/`, `.github/workflows/`)

---

## 🧪 Verification & Testing Performed
Please check what tests you ran before submitting this PR:
- [ ] **Secret & Privacy Audit**: `make audit-secrets` passed with 0 leaks.
- [ ] **Pytest Unit Tests**: `pytest` passed 100% locally.
- [ ] **Daemon Runtime Healthcheck**: Verified `skybrain start` and `/v1/models` response.
- [ ] **Clean Code & Lint**: Zero lingering temporary files or untracked cache.

---

## 📋 Contributor Checklist
- [ ] My code adheres to the project's **Docker-Free & Apple Silicon Native** architecture principles.
- [ ] I have updated relevant documentation if this PR introduces public-facing changes.
- [ ] My commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (e.g. `feat: ...`, `fix: ...`).
