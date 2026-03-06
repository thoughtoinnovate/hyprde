#!/bin/bash
# Kill any existing instance before launching to prevent zombies
pkill -f "python3.*spotlight.py" || true
exec python3 "$HOME/.config/hypr/scripts/spotlight.py"
