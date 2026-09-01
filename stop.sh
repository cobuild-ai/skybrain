#!/bin/bash
# 🧠 SkyBrain One-Click Stop Controller
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$PROJECT_DIR/scripts/daemon.sh" stop
