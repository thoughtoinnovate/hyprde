#!/bin/bash

# Detect the configured terminal: hyprland.lua (Lua mode) -> hyprde.toml
# -> $TERMINAL env -> ghostty fallback. Works in Lua and legacy hyprlang setups.
detect_terminal() {
    local t=""
    if [ -f "$HOME/.config/hypr/hyprland.lua" ]; then
        t=$(grep -m1 'local terminal' "$HOME/.config/hypr/hyprland.lua" 2>/dev/null | cut -d'"' -f2)
    fi
    if [ -z "$t" ] && [ -f "$HOME/.config/hypr/hyprde.toml" ]; then
        t=$(grep -m1 'terminal =' "$HOME/.config/hypr/hyprde.toml" 2>/dev/null | cut -d'"' -f2)
    fi
    if [ -z "$t" ] && [ -f "$HOME/.config/hypr/hyprde.generated.conf" ]; then
        t=$(rg '^\$terminal' "$HOME/.config/hypr/hyprde.generated.conf" 2>/dev/null | cut -d'=' -f2 | tr -d ' ')
    fi
    if [ -z "$t" ]; then
        t=$(rg '^\$terminal' "$HOME/.config/hypr/hyprland.conf" 2>/dev/null | cut -d'=' -f2 | tr -d ' ')
    fi
    printf '%s' "${t:-${TERMINAL:-ghostty}}"
}

# Check if running in terminal, if not, launch in terminal
if ! tty -s; then
    terminal=$(detect_terminal)

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
toggle_script="$script_dir/preview-toggle.sh"

# Always start from HOME
cd "$HOME" || exit 1

# Get the default terminal (same Lua-aware detection as above)
terminal=$(detect_terminal)

# Function to get current preview mode
get_preview_mode() {
    "$toggle_script" get 2>/dev/null || echo "metadata"
}

# Launch fzf - scanning only HOME folder
selected=$(fd . --type f --type d --max-depth 3 2>/dev/null | fzf --ansi \
    --prompt "Search Files/Dirs: " \
    --height=100% \
    --layout=reverse \
    --border \
    --preview "$script_dir/preview-wrapper.sh {}" \
    --preview-window=right:60%:wrap \
    --bind 'ctrl-/:toggle-preview' \
    --bind 'ctrl-u:up' \
    --bind 'ctrl-d:down' \
    --bind 'ctrl-o:execute-silent(if [[ "$OSTYPE" == "darwin"* ]]; then open -R {}; else xdg-open "$(dirname {})"; fi)' \
    --bind 'ctrl-e:execute-silent(if file -b --mime-type {} | grep -q "^image/"; then if command -v feh >/dev/null 2>&1; then if command -v firejail >/dev/null 2>&1; then firejail --quiet --noprofile --private-tmp --net=none --seccomp --caps.drop=all feh {} 2>/dev/null; else feh {}; fi; elif command -v sxiv >/dev/null 2>&1; then if command -v firejail >/dev/null 2>&1; then firejail --quiet --noprofile --private-tmp --net=none --seccomp --caps.drop=all sxiv {} 2>/dev/null; else sxiv {}; fi; else xdg-open {}; fi; fi)' \
    --bind 'ctrl-s:execute-silent(touch /tmp/hyprde-preview-secure)+preview(true)' \
    --bind 'ctrl-p:execute-silent(rm -f /tmp/hyprde-preview-secure)+preview(true)' \
    --header 'ENTER (Yazi) | CTRL-E (viewer) | CTRL-P (show image) | CTRL-S (metadata only) | CTRL-O (folder)')

# Only open if user pressed Enter (not ESC)
if [ -n "$selected" ]; then
    file_path=$(echo "$selected")

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

