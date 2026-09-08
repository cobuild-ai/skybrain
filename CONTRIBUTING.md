# 🤝 Contributing to SkyBrain

Thank you for your interest in contributing to **SkyBrain**! We welcome engineers, researchers, and developers worldwide to help build a universal on-device AI serving engine and multi-lens code review system.

---

## ✍️ Contributor License Agreement (CLA)
By submitting a Pull Request to SkyBrain, you agree to our [Contributor License Agreement (CLA)](CLA.md). All contributions are licensed under the **Apache License 2.0** pursuant to Section 5 of the License.

---

## ⚡ Quick Start for Developers
1. **Clone and Install**:
   ```bash
   git clone https://github.com/cobuild-ai/skybrain.git
   cd skybrain
   uv sync
   ```
2. **Run Tests**:
   ```bash
   pytest tests/
   ```
3. **Run Daemon**:
   ```bash
   uv run skybrain start --foreground
   ```

---

## 📋 PR Submission Checklist
- [ ] Ensure all pytest tests pass locally (`pytest tests/`).
- [ ] Adhere to the Universal `uv tool` Mandate and Docker-free Apple Silicon Metal architecture.
- [ ] Check the CLA affirmation box in your Pull Request description.
- [ ] Follow Conventional Commits format (`feat:`, `fix:`, `docs:`, `test:`).
