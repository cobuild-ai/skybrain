#!/bin/bash
# Install SkyBrain as macOS LaunchAgent background service dynamically

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE="$SCRIPT_DIR/com.skybrain.daemon.plist.template"
PLIST_DEST="$HOME/Library/LaunchAgents/com.skybrain.daemon.plist"
LOG_DIR="$HOME/.skybrain"
LOG_PATH="$LOG_DIR/skybrain.log"

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

# Determine uvicorn path
UVICORN_PATH="$PROJECT_DIR/.venv/bin/uvicorn"
if [ ! -f "$UVICORN_PATH" ]; then
    UVICORN_PATH="$(which uvicorn || echo "/opt/homebrew/bin/uvicorn")"
fi

PATH_ENV="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Render template dynamically without hardcoded user paths
sed \
    -e "s|{{UVICORN_PATH}}|$UVICORN_PATH|g" \
    -e "s|{{WORKING_DIR}}|$PROJECT_DIR|g" \
    -e "s|{{LOG_PATH}}|$LOG_PATH|g" \
    -e "s|{{PATH_ENV}}|$PATH_ENV|g" \
    "$TEMPLATE" > "$PLIST_DEST"

launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "✅ SkyBrain macOS LaunchAgent service dynamically installed and started!"
echo "• Project: $PROJECT_DIR"
echo "• Binary:  $UVICORN_PATH"
echo "• Log:     $LOG_PATH"
echo "• Endpoint: http://127.0.0.1:8000/v1"
