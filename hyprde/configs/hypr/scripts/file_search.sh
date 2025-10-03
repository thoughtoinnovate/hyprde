#!/bin/bash

# Check dependencies
if ! command -v fd >/dev/null 2>&1; then
    notify-send "Error" "fd is not installed"
    exit 1
fi

if ! command -v wofi >/dev/null 2>&1; then
    notify-send "Error" "wofi is not installed"
    exit 1
fi

# Function to map file extension to Nerd Font symbol
get_symbol_from_ext() {
    local file="$1"
    local ext="${file##*.}"
    case "$ext" in
        pdf) echo "" ;;  # nf-fa-file_pdf_o
        sh|bash) echo "" ;;  # nf-oct-terminal
        txt|md) echo "" ;;  # nf-fa-file_text_o
        jpg|jpeg|png|gif|bmp|raw|cr2|nef) echo "" ;;  # nf-fa-file_image_o
        mp4|avi|mkv|mov) echo "" ;;  # nf-fa-file_video_o
        mp3|wav|flac|ogg) echo "" ;;  # nf-fa-file_audio_o
        zip|tar|gz|bz2|xz|7z) echo "" ;;  # nf-fa-file_archive_o
        html|htm) echo "" ;;  # nf-fa-globe
        css) echo "" ;;  # nf-fa-css3
        json|xml) echo "" ;;  # nf-fa-file_code_o
        py) echo "" ;;  # nf-dev-python
        js) echo "" ;;  # nf-dev-javascript
        java) echo -e "\ue256" ;;  # nf-dev-java
        scala) echo -e "\ue68e" ;;  # nf-dev-scala
        rs) echo -e "\ue68b" ;;  # nf-dev-rust
        go) echo -e "\udb81\udfd3" ;;  # nf-dev-go
        c|cpp|h) echo -e "\ue771" ;;  # nf-fa-code
        *) echo "" ;;  # nf-fa-file_o
    esac
}

# Generate list with symbols
list_with_symbols() {
    fd . $HOME --type f | while read -r file; do
        symbol=$(get_symbol_from_ext "$file")
        echo "$symbol $file"
    done
}

# Launch wofi with fd output including symbols
selected=$(list_with_symbols | wofi --dmenu --prompt "Search Files:" --conf "$HOME/.config/wofi/config" --style "$HOME/.config/wofi/style.css")

if [ -n "$selected" ]; then
    # Remove the symbol from the selected line
    file_path=$(echo "$selected" | cut -d' ' -f2-)
    notify-send "Opening:" "$file_path"
    # Get the default terminal from Hyprland config
    terminal=$(grep '^\$terminal' "$HOME/.config/hypr/hyprland.conf" | cut -d'=' -f2 | tr -d ' ')
    # Open all files in Yazi file explorer, highlighted
    $terminal -e yazi "$file_path" || notify-send "Error" "Could not open $file_path in Yazi"
fi