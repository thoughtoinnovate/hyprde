#!/bin/bash

# Check if running in terminal, if not, launch in terminal
if ! tty -s; then
    terminal=$(rg '^\$terminal' "$HOME/.config/hypr/hyprland.conf" | cut -d'=' -f2 | tr -d ' ')
    
    case "$terminal" in
        *ghostty*) exec ghostty --class=com.fzf.launcher -e "$0" ;;
        *kitty*) exec kitty --class fzf-launcher "$0" ;;
        *foot*) exec foot --app-id=fzf-launcher "$0" ;;
        *alacritty*) exec alacritty --class fzf-launcher -e "$0" ;;
        *) exec $terminal -e "$0" ;;
    esac
    exit
fi

# Check dependencies
if ! command -v fd >/dev/null 2>&1; then
    notify-send "Error" "fd is not installed"
    exit 1
fi

if ! command -v fzf >/dev/null 2>&1; then
    notify-send "Error" "fzf is not installed"
    exit 1
fi

if ! command -v rg >/dev/null 2>&1; then
    notify-send "Error" "ripgrep (rg) is not installed"
    exit 1
fi

# Get the default terminal from Hyprland config
terminal=$(rg '^\$terminal' "$HOME/.config/hypr/hyprland.conf" | cut -d'=' -f2 | tr -d ' ')

# Launch fzf - scanning only HOME folder (fd already limits to HOME)
selected=$(fd . "$HOME" --type f --type d 2>/dev/null | while IFS= read -r file; do
    # Determine icon based on file type
    if [ -d "$file" ]; then
        icon=""
    else
        case "${file##*.}" in
            pdf) icon="" ;;
            sh|bash) icon="" ;;
            txt|md) icon="" ;;
            jpg|jpeg|png|gif|bmp|raw|cr2|nef) icon="" ;;
            mp4|avi|mkv|mov) icon="" ;;
            mp3|wav|flac|ogg) icon="" ;;
            zip|tar|gz|bz2|xz|7z) icon="" ;;
            html|htm) icon="" ;;
            css) icon="" ;;
            json|xml) icon="" ;;
            py) icon="" ;;
            js) icon="" ;;
            java) icon="" ;;
            scala) icon="" ;;
            rs) icon="" ;;
            go) icon="" ;;
            c|cpp|h) icon="" ;;
            *) icon="" ;;
        esac
    fi
    printf "%s %s\n" "$icon" "$file"
done | fzf --ansi \
    --prompt "Search Files/Dirs: " \
    --height=100% \
    --layout=reverse \
    --border \
    --preview 'file=$(echo {} | cut -d" " -f2-);
        if [ -d "$file" ]; then 
            ls -lah --color=always "$file" 2>/dev/null; 
        elif [ -f "$file" ] && command -v bat >/dev/null 2>&1; then
            if [ -n "{q}" ]; then
                bat --style=numbers --color=always --line-range :500 "$file" | \
                rg --colors "match:bg:yellow" --colors "match:fg:black" --colors "match:style:bold" \
                   --ignore-case --passthru "{q}";
            else
                bat --style=numbers --color=always --line-range :500 "$file";
            fi
        elif [ -f "$file" ]; then 
            if [ -n "{q}" ]; then
                cat "$file" | rg --colors "match:bg:yellow" --colors "match:fg:black" --colors "match:style:bold" \
                   --ignore-case --passthru "{q}";
            else
                cat "$file";
            fi
        fi' \
    --preview-window=right:60%:wrap \
    --bind 'ctrl-/:toggle-preview' \
    --bind 'ctrl-u:preview-page-up' \
    --bind 'ctrl-d:preview-page-down' \
    --header 'CTRL-/ (toggle preview) | CTRL-U/D (scroll) | ESC (cancel)')

# Only open if user pressed Enter (not ESC)
if [ -n "$selected" ]; then
    file_path=$(echo "$selected" | cut -d' ' -f2-)
    
    # Launch Yazi in a NEW separate terminal window
    case "$terminal" in
        *ghostty*) 
            nohup ghostty -e yazi "$file_path" >/dev/null 2>&1 &
            ;;
        *kitty*) 
            nohup kitty -e yazi "$file_path" >/dev/null 2>&1 &
            ;;
        *foot*) 
            nohup foot yazi "$file_path" >/dev/null 2>&1 &
            ;;
        *alacritty*) 
            nohup alacritty -e yazi "$file_path" >/dev/null 2>&1 &
            ;;
        *) 
            nohup $terminal -e yazi "$file_path" >/dev/null 2>&1 &
            ;;
    esac
    
    sleep 0.2
fi

