#!/bin/bash
# 🧠 SkyBrain Universal Zero-Config Background Daemon Controller
# Supports seamless execution for Continuum, MySkyNet, DearTalk, and scripts.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

VENV_DIR="$PROJECT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

# Auto-provision virtual environment if missing
if [ ! -f "$VENV_PYTHON" ]; then
    echo "⚡ Initializing SkyBrain virtual environment..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install -q -U pip
    "$VENV_DIR/bin/pip" install -q -e .
fi

ACTION="${1:-start}"

case "$ACTION" in
    start)
        echo "🚀 Starting SkyBrain Daemon (Zero-Config Auto-Provisioning)..."
        "$VENV_PYTHON" -m skybrain.cli.main start --auto-download
        ;;
    stop)
        echo "🛑 Stopping SkyBrain Daemon..."
        "$VENV_PYTHON" -m skybrain.cli.main stop
        ;;
    restart)
        echo "🔄 Restarting SkyBrain Daemon..."
        "$VENV_PYTHON" -m skybrain.cli.main stop
        sleep 1
        "$VENV_PYTHON" -m skybrain.cli.main start --auto-download
        ;;
    status)
        "$VENV_PYTHON" -m skybrain.cli.main status
        ;;
    logs)
        LOG_FILE="$HOME/.skybrain/skybrain.log"
        if [ -f "$LOG_FILE" ]; then
            tail -n 50 -f "$LOG_FILE"
        else
            echo "No log file found at $LOG_FILE"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac


