#!/bin/bash
# 🧠 SkyBrain One-Click Auto-Provisioning & Start Launcher
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$PROJECT_DIR/scripts/daemon.sh" start
