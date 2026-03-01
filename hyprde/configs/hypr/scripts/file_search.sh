#!/bin/bash

# Source common icons
source "$(dirname "$0")/common_icons.sh"

# Check dependencies
if ! command -v fd >/dev/null 2>&1; then
    notify-send "Error" "fd is not installed"
    exit 1
fi

if ! command -v wofi >/dev/null 2>&1; then
    notify-send "Error" "wofi is not installed"
    exit 1
fi

# Generate list with symbols
list_with_symbols() {
    fd . $HOME | while read -r file; do
        symbol=$(get_symbol "$file")
        echo "$symbol $file"
    done
}

# Launch wofi with fd output including symbols
selected=$(list_with_symbols | wofi --dmenu --prompt "Search Files/Dirs:" --conf "$HOME/.config/wofi/config" --style "$HOME/.config/wofi/style.css")

if [ -n "$selected" ]; then
    # Remove the symbol from the selected line
    file_path=$(echo "$selected" | cut -d' ' -f2-)
    notify-send "Opening:" "$file_path"
    # Get the default terminal from Hyprland config
    terminal=$(rg '^\$terminal' "$HOME/.config/hypr/hyprland.conf" | cut -d'=' -f2 | tr -d ' ')
    # Open all files in Yazi file explorer, highlighted
    "$terminal" -e yazi "$file_path" || notify-send "Error" "Could not open $file_path in Yazi"
fi