#!/bin/bash
# Native High-Performance Spotlight Launcher (built with Zig/GTK)
# Kill any existing instance before launching to prevent zombies
pkill -x "hyprsearch" || true
exec "$HOME/.config/hypr/scripts/hyprsearch" --instance drun