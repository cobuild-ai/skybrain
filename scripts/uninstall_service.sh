#!/bin/bash
# Uninstall SkyBrain macOS LaunchAgent service

PLIST_DEST="$HOME/Library/LaunchAgents/com.skybrain.daemon.plist"

if [ -f "$PLIST_DEST" ]; then
    launchctl unload "$PLIST_DEST" 2>/dev/null
    rm "$PLIST_DEST"
    echo "🛑 SkyBrain LaunchAgent service uninstalled."
else
    echo "ℹ️ No LaunchAgent service found."
fi
