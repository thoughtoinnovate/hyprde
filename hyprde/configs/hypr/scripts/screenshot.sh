#!/bin/bash

# Directory to save screenshots
SCREENSHOT_DIR="$HOME/Pictures/Screenshots"

# Create the directory if it doesn't exist
mkdir -p "$SCREENSHOT_DIR"

# Filename with timestamp
FILENAME="$SCREENSHOT_DIR/screenshot-$(date +'%Y-%m-%d-%H%M%S').png"

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