#!/bin/bash

# Check dependencies
if ! command -v rg >/dev/null 2>&1; then
    notify-send "Error" "ripgrep (rg) is not installed"
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    notify-send "Error" "jq is not installed"
    exit 1
fi

if ! command -v wofi >/dev/null 2>&1; then
    notify-send "Error" "wofi is not installed"
    exit 1
fi

# Function to map file/directory to Nerd Font symbol
get_symbol() {
    local file="$1"
    if [ -d "$file" ]; then
        echo ""  # nf-fa-folder
    else
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
    fi
}

search_json() {
    local search_term="$1"
    local search_dir="${2:-$HOME}"
    
    if [ -z "$search_term" ]; then
        echo "Usage: search_json <search_term> [directory]"
        return 1
    fi
    
    if [ ! -d "$search_dir" ]; then
        echo "Error: Directory '$search_dir' does not exist"
        return 1
    fi
    
    local results="["
    local first=true
    
    # Use \rg or full path to bypass aliases
    while IFS= read -r file; do
        if [ "$first" = true ]; then
            first=false
        else
            results+=","
        fi
        file_escaped="${file//\\/\\\\}"
        file_escaped="${file_escaped//\"/\\\"}"
        results+=" { \"filePath\":\"$file_escaped\", \"totalMatches\":1 }"
    done < <(\rg --files "$search_dir" 2>/dev/null | \rg "$search_term")
    
    while IFS=: read -r file count; do
        if [ -n "$file" ] && [ -n "$count" ]; then
            if [ "$first" = true ]; then
                first=false
            else
                results+=","
            fi
            file_escaped="${file//\\/\\\\}"
            file_escaped="${file_escaped//\"/\\\"}"
            results+=" { \"filePath\":\"$file_escaped\", \"totalMatches\":$count }"
        fi
    done < <(\rg -c "$search_term" "$search_dir" 2>/dev/null)
    
    results+=" ]"
    echo "$results"
}

# Get the default terminal from Hyprland config
terminal=$(rg '^\$terminal' "$HOME/.config/hypr/hyprland.conf" | cut -d'=' -f2 | tr -d ' ')

# Get query
query=$(wofi --dmenu --prompt "Search query:" --conf "$HOME/.config/wofi/config" --style "$HOME/.config/wofi/style.css")
if [ -z "$query" ]; then
    exit 0
fi

# Get JSON results
json=$(search_json "$query" "$HOME")

# Parse JSON, add icons, and display in wofi
selected=$(echo "$json" | jq -r '.[] | "\(.totalMatches) \(.filePath)"' | while read -r line; do
    matches=$(echo "$line" | cut -d' ' -f1)
    file=$(echo "$line" | cut -d' ' -f2-)
    icon=$(get_symbol "$file")
    echo "$icon $matches $file"
done | sort -k2 -n -r -u | wofi --dmenu --prompt "Select file:" --conf "$HOME/.config/wofi/config" --style "$HOME/.config/wofi/style.css")

if [ -n "$selected" ]; then
    # Extract file path (skip icon and matches)
    file_path=$(echo "$selected" | cut -d' ' -f3-)
    notify-send "Opening:" "$file_path"
    # Open in Yazi
    $terminal -e yazi "$file_path" || notify-send "Error" "Could not open $file_path in Yazi"
fi