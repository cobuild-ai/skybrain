#!/bin/bash
# Install SkyBrain as macOS LaunchAgent background service

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/com.skybrain.daemon.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.skybrain.daemon.plist"

mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST_SRC" "$PLIST_DEST"

launchctl unload "$PLIST_DEST" 2>/dev/null
launchctl load "$PLIST_DEST"

echo "✅ SkyBrain macOS LaunchAgent service installed and started!"
echo "• Log: ~/.skybrain/skybrain.log"
echo "• Endpoint: http://127.0.0.1:8000/v1"
