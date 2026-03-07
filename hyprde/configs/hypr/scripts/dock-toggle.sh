#!/bin/bash
if pgrep -x "hyprsearch" | xargs -I{} ps -p {} -o args= | grep -q -- "--dock"; then
    pkill -f "hyprsearch --dock"
else
    "$HOME/.config/hypr/scripts/hyprsearch" --dock &
fi
