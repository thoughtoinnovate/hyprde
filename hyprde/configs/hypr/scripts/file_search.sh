#!/bin/bash

# Source common icons
source "$(dirname "$0")/common_icons.sh"

# Check dependencies
if ! command -v fd >/dev/null 2>&1; then
    notify-send "Error" "fd is not installed"
    exit 1
fi

LAUNCHER="$HOME/.config/hypr/scripts/hyprsearch"
if [ ! -f "$LAUNCHER" ]; then
    LAUNCHER="hyprsearch"
fi

# Generate list with symbols
list_with_symbols() {
    fd . $HOME | while read -r file; do
        symbol=$(get_symbol "$file")
        echo "$symbol $file"
    done
}

# Launch hyprsearch in dmenu mode
selected=$(list_with_symbols | $LAUNCHER --dmenu --prompt "Search Files/Dirs:")

if [ -n "$selected" ]; then
    # Remove the symbol from the selected line
    file_path=$(echo "$selected" | cut -d' ' -f2-)
    notify-send "Opening:" "$file_path"
    
    # Get the terminal from hyprde.toml if possible, else fallback
    # We'll use ghostty as default if not found
    terminal="ghostty"
    if [ -f "$HOME/.config/hypr/hyprde.toml" ]; then
        toml_term=$(grep 'terminal =' "$HOME/.config/hypr/hyprde.toml" | cut -d'"' -f2)
        if [ -n "$toml_term" ]; then
            terminal="$toml_term"
        fi
    fi

    # Open all files in Yazi file explorer, highlighted
    "$terminal" -e yazi "$file_path" || notify-send "Error" "Could not open $file_path in Yazi"
fi