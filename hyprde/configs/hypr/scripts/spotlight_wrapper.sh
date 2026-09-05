#!/bin/bash
# Native High-Performance Spotlight Launcher (built with Zig/GTK)
# Toggle: only an existing drun instance is closed here.
# (Never match the dock or power-menu by bare process name.)
if pgrep -f "hyprsearch --instance drun" > /dev/null; then
    pkill -f "hyprsearch --instance drun" || true
    exit 0
fi
exec "$HOME/.config/hypr/scripts/hyprsearch" --instance drun