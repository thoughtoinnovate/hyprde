#!/bin/bash
# Toggle preview mode between secure (metadata) and rendered (image)
# Creates a state file that preview scripts check

STATE_FILE="/tmp/hyprde-preview-mode.$$"

if [[ "$1" == "toggle" ]]; then
    # Toggle mode
    if [[ -f "$STATE_FILE" ]]; then
        rm -f "$STATE_FILE"
    else
        echo "render" > "$STATE_FILE"
    fi
    echo "Mode: $([[ -f "$STATE_FILE" ]] && echo 'Render' || echo 'Metadata')"
elif [[ "$1" == "get" ]]; then
    # Get current mode
    if [[ -f "$STATE_FILE" ]]; then
        cat "$STATE_FILE"
    else
        echo "metadata"
    fi
elif [[ "$1" == "reset" ]]; then
    # Reset to metadata mode
    rm -f "$STATE_FILE"
fi
