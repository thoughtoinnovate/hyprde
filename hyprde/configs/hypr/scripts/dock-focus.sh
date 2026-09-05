#!/bin/bash
APP_NAME="$1"
APP_ID="$2"

# Get all running window classes from hyprland
CLASSES=$(hyprctl clients -j | jq -r '.[].class')

# Try to match by Exact ID (e.g., google-chrome matches google-chrome.desktop)
MATCH=$(echo "$CLASSES" | grep -i -m 1 "^${APP_ID}$")

# If no exact match, try partial match on ID or Name
if [ -z "$MATCH" ]; then
    MATCH=$(echo "$CLASSES" | grep -i -m 1 "${APP_ID}")
fi
if [ -z "$MATCH" ]; then
    MATCH=$(echo "$CLASSES" | grep -i -m 1 "${APP_NAME}")
fi

if [ -n "$MATCH" ]; then
    # Focus the matched application
    hyprctl dispatch "hl.dsp.focuswindow(\"class:$MATCH\")" >/dev/null 2>&1
    exit 0
else
    # Not running
    exit 1
fi
