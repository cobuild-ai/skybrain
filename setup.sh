#!/usr/bin/env bash
# 🧠 SkyBrain Universal One-Touch Setup Script
# Configures local environment, Metal GPU acceleration, and VS Code / Cursor / Cline MCP integration.

set -euo pipefail

# ANSI Colors
CYAN='\033[1;36m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${CYAN}═══════════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}🧠 SkyBrain: One-Touch Setup & Editor Integration${RESET}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${RESET}\n"

# 1. Check Python Version
echo -e "🔍 Step 1: Checking Python environment..."
PYTHON_BIN=""
for cmd in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
        VER=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON_BIN="$cmd"
            echo -e "  ${GREEN}✔ Found compatible Python:${RESET} $cmd ($VER)"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo -e "  ${RED}❌ Python 3.10+ is required. Please install Python 3.11 or higher.${RESET}"
    exit 1
fi

# 2. Setup Virtual Environment
echo -e "\n📦 Step 2: Provisioning local virtual environment (.venv)..."
if [ ! -d ".venv" ]; then
    "$PYTHON_BIN" -m venv .venv
    echo -e "  ${GREEN}✔ Created .venv${RESET}"
else
    echo -e "  ${YELLOW}ℹ Existing .venv detected${RESET}"
fi

VENV_PYTHON=".venv/bin/python"
VENV_PIP=".venv/bin/pip"

# 2.5 Ensure Localhost NO_PROXY
export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,::1}"
export no_proxy="${no_proxy:-localhost,127.0.0.1,::1}"

# 3. Install Package & Dependencies (with Corporate SSL Auto-Healing)
echo -e "\n⚙️ Step 3: Installing dependencies and editable skybrain package..."

# Detect Corporate CA bundle from environment if present
CA_ARGS=()
if [ -n "${SKYBRAIN_CA_BUNDLE:-}" ] && [ -f "${SKYBRAIN_CA_BUNDLE}" ]; then
    CA_ARGS=(--cert "${SKYBRAIN_CA_BUNDLE}")
elif [ -n "${SSL_CERT_FILE:-}" ] && [ -f "${SSL_CERT_FILE}" ]; then
    CA_ARGS=(--cert "${SSL_CERT_FILE}")
elif [ -n "${REQUESTS_CA_BUNDLE:-}" ] && [ -f "${REQUESTS_CA_BUNDLE}" ]; then
    CA_ARGS=(--cert "${REQUESTS_CA_BUNDLE}")
fi

install_deps() {
    "$VENV_PIP" install --upgrade pip "${CA_ARGS[@]}" --quiet
    "$VENV_PIP" install -e ".[dev]" "${CA_ARGS[@]}" --quiet
}

if ! install_deps; then
    echo -e "  ${YELLOW}⚠️ Standard SSL install failed. Attempting Corporate Proxy / Trusted-Host fallback...${RESET}"
    TRUSTED_HOSTS=(--trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org)
    "$VENV_PIP" install --upgrade pip "${TRUSTED_HOSTS[@]}" --quiet
    "$VENV_PIP" install -e ".[dev]" "${TRUSTED_HOSTS[@]}" --quiet
    echo -e "  ${GREEN}✔ Dependencies installed successfully via Corporate SSL Fallback.${RESET}"
else
    echo -e "  ${GREEN}✔ Dependencies installed successfully.${RESET}"
fi

# 4. Detect Apple Silicon Metal GPU
echo -e "\n🍏 Step 4: Inspecting Apple Silicon Metal acceleration..."
ARCH=$(uname -m)
OS=$(uname -s)
if [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
    echo -e "  ${GREEN}✔ Apple Silicon ($ARCH) detected: Metal acceleration active.${RESET}"
else
    echo -e "  ${YELLOW}ℹ Running on $OS ($ARCH): CPU fallback mode will be used.${RESET}"
fi

# 5. Run Verification Tests
echo -e "\n🧪 Step 5: Running comprehensive unit test suite..."
"$VENV_PYTHON" -m pytest tests/ -q
echo -e "  ${GREEN}✔ All unit tests passed 100%!${RESET}"

# 6. Generate VS Code / Cursor / Cline MCP Configuration
echo -e "\n🔌 Step 6: Configuring Editor MCP (Model Context Protocol)..."
mkdir -p .vscode

ABS_PATH=$(pwd)
cat <<EOF > .vscode/mcp.json
{
  "mcpServers": {
    "skybrain": {
      "command": "${ABS_PATH}/.venv/bin/python",
      "args": ["-m", "skybrain.mcp"]
    }
  }
}
EOF
echo -e "  ${GREEN}✔ Generated .vscode/mcp.json (VS Code / Cursor / Claude Desktop ready)${RESET}"

# 7. Global CLI Provisioning via uv tool (Project Mandatory Standard)
if command -v uv >/dev/null 2>&1; then
    echo -e "\n🌐 Step 7: Registering global 'skybrain' CLI via uv tool..."
    CMAKE_ARGS="-DGGML_METAL=on" uv tool install --editable . --force --quiet
    echo -e "  ${GREEN}✔ Global 'skybrain' command is active on \$PATH via uv tool!${RESET}"
else
    echo -e "\n💡 Step 7: 'uv' is recommended for ultra-fast isolated CLI execution."
    echo -e "   Install uv with: ${CYAN}brew install uv${RESET} or ${CYAN}curl -LsSf https://astral.sh/uv/install.sh | sh${RESET}"
fi


# 8. Summary & Quickstart Guide
echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}🎉 SkyBrain is completely installed and ready to serve!${RESET}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${RESET}\n"
echo -e "${BOLD}🚀 Quickstart Commands:${RESET}"
echo -e "  1. Start daemon in background:"
echo -e "     ${CYAN}skybrain start${RESET}  (or: ${CYAN}.venv/bin/skybrain start${RESET})"
echo -e "  2. Run 2/3 Consensus Multi-Lens Code Review:"
echo -e "     ${CYAN}.venv/bin/python scripts/skybrain_expert.py --target <FILE_PATH> --rounds 3${RESET}"
echo -e "  3. Start MCP Server for VS Code / Cline:"
echo -e "     ${CYAN}skybrain mcp${RESET}   (or: ${CYAN}.venv/bin/skybrain mcp${RESET})"
echo -e "  4. Check daemon status:"
echo -e "     ${CYAN}skybrain status${RESET}\n"

