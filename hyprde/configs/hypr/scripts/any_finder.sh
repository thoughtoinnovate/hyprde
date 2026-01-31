#!/bin/bash

# Check if running in terminal, if not, launch in terminal
if ! tty -s; then
    terminal=$(rg '^\$terminal' "$HOME/.config/hypr/hyprland.conf" | cut -d'=' -f2 | tr -d ' ')

    case "$terminal" in
        *ghostty*) exec ghostty --class=com.fzf.launcher -e "$0" ;;
        *kitty*) exec kitty --class fzf-launcher "$0" ;;
        *foot*) exec foot --app-id=fzf-launcher "$0" ;;
        *alacritty*) exec alacritty --class fzf-launcher -e "$0" ;;
        *) exec "$terminal" -e "$0" ;;
    esac
    exit
fi

# Source common icons
source "$(dirname "$0")/common_icons.sh"

# Cross-platform notification
notify() {
    if command -v notify-send >/dev/null 2>&1; then
        notify-send "$1" "$2"
    elif [[ "$(uname)" == "Darwin" ]]; then
        osascript -e "display notification \"$2\" with title \"$1\""
    else
        echo "$1: $2" >&2
    fi
}

# Check dependencies
for cmd in fd fzf rg; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        notify "Error" "$cmd is not installed"
        exit 1
    fi
done

# Get script directory for preview (before changing directory)
script_dir="$(cd "$(dirname "$0")" && pwd)"

# Always start from HOME
cd "$HOME" || exit 1

# Get the default terminal from Hyprland config
terminal=$(rg '^\$terminal' "$HOME/.config/hypr/hyprland.conf" 2>/dev/null | cut -d'=' -f2 | tr -d ' ')
terminal="${terminal:-ghostty}"

# Launch fzf - scanning only HOME folder
selected=$(fd . "$HOME" --type f --type d 2>/dev/null | while IFS= read -r file; do
    icon=$(get_symbol "$file")
    printf "%s\t%s\n" "$icon" "$file"
done | fzf --ansi \
    --delimiter '\t' \
    --with-nth 1,2 \
    --prompt "Search Files/Dirs: " \
    --height=100% \
    --layout=reverse \
    --border \
    --preview "$script_dir/sandbox-preview.sh {2}" \
    --preview-window=right:60%:wrap \
    --bind 'focus:refresh-preview' \
    --bind 'ctrl-/:toggle-preview' \
    --bind 'ctrl-u:preview-page-up' \
    --bind 'ctrl-d:preview-page-down' \
    --bind 'ctrl-o:execute-silent(if [[ "$OSTYPE" == "darwin"* ]]; then open -R {2}; else xdg-open "$(dirname {2})"; fi)' \
    --header 'CTRL-O (open in explorer) | CTRL-/ (toggle preview) | CTRL-U/D (scroll)')

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
            nohup "$terminal" -e yazi "$file_path" >/dev/null 2>&1 &
            ;;
    esac

    sleep 0.2
fi

