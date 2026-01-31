#!/bin/bash

# Directory to save screenshots
SCREENSHOT_DIR="$HOME/Pictures/Screenshots"

# Create the directory if it doesn't exist
mkdir -p "$SCREENSHOT_DIR"

# Filename with timestamp
FILENAME="$SCREENSHOT_DIR/screenshot-$(date +'%Y-%m-%d-%H%M%S').png"

# Validate input argument
if [ -n "$1" ] && [ "$1" != "area" ]; then
    echo "Usage: $0 [area]" >&2
    echo "  (no argument) - screenshot entire screen" >&2
    echo "  area          - screenshot selected area" >&2
    exit 1
fi

# Check if the user wants to select an area
if [ "$1" == "area" ]; then
    grim -g "$(slurp)" "$FILENAME"
else
    grim "$FILENAME"
fi

# Notify the user
if [ "$?" == "0" ]; then
notify-send "Screenshot saved to $FILENAME"
fi