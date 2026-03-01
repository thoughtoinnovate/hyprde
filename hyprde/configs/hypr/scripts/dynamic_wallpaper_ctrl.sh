#!/bin/bash

# Path to the dynamic-wallpapers.sh script
SCRIPT_NAME="dynamic-wallpapers.sh"
FULL_SCRIPT_PATH="$HOME/.config/hypr/scripts/dynamic-wallpapers.sh"
WALLPAPER_DIR="$HOME/Pictures/wallpapers/"
INTERVAL=60

is_running() {
    pgrep -f "$SCRIPT_NAME" > /dev/null
}

case "$1" in
    toggle)
        if is_running; then
            pkill -f "$SCRIPT_NAME"
            notify-send "Dynamic Wallpaper" "Disabled"
        else
            sh "$FULL_SCRIPT_PATH" "$WALLPAPER_DIR" "$INTERVAL" &
            notify-send "Dynamic Wallpaper" "Enabled"
        fi
        ;;
    status)
        if is_running; then
            echo '{"text": "Enabled", "class": "enbld", "alt": "on", "tooltip": "Dynamic Wallpaper: Enabled"}'
        else
            echo '{"text": "Disabled", "class": "disbld", "alt": "off", "tooltip": "Dynamic Wallpaper: Disabled"}'
        fi
        ;;
    *)
        echo "Usage: $0 {toggle|status}"
        exit 1
        ;;
esac
