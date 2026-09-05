#!/bin/bash
[ -n "${_HYPRDE_PYTHON_BIN:-}" ] || source "${0%/*}/hyprde-python.sh" 2>/dev/null || source "$HOME/.config/hypr/scripts/hyprde-python.sh" 2>/dev/null || true
# Fixed wallpaper mode - simple static display
# No rotation, no time-based changes - just a single static wallpaper

# Configuration file path
TOML_CONFIG="$HOME/.config/hypr/hyprde.toml"
LOG_FILE="/tmp/hypr_wallpaper.log"

log() {
    echo "$(date +'%Y-%m-%d %H:%M:%S') [FIXED] - $1" >> "$LOG_FILE"
}

wait_for_hyprpaper_ipc() {
    # Newer hyprpaper builds (Hyprland 0.55+) dropped listloaded/preload;
    # don't burn 10 attempts when the command doesn't exist.
    if hyprctl hyprpaper listloaded 2>&1 | grep -qi "invalid hyprpaper request"; then
        return 0
    fi
    local max_attempts=10
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if hyprctl hyprpaper listloaded &>/dev/null; then
            return 0
        fi
        sleep 0.1
        ((attempt++))
    done
    return 1
}

if [ ! -f "$TOML_CONFIG" ]; then
    log "Error: Config not found at $TOML_CONFIG"
    exit 1
fi

# Extract values directly from TOML using python/tomlkit
read_toml() {
    python3 -c "
import tomlkit, os
path = os.path.expanduser('~/.config/hypr/hyprde.toml')
with open(path, 'r') as f: data = tomlkit.load(f)
wp = data.get('wallpapers', {})
fixed = wp.get('fixed', {})
def expand_path(p):
    if not p: return ''
    # Replace \$HOME or $HOME with actual home dir
    p = p.replace('\$HOME', os.path.expanduser('~')).replace('$HOME', os.path.expanduser('~'))
    return os.path.expanduser(p)
print(f\"WALLPAPER_TYPE='{fixed.get('type', 'image')}'\")
print(f\"WALLPAPER_IMAGE='{expand_path(fixed.get('image', ''))}'\")
print(f\"WALLPAPER_DIRECTORY='{expand_path(fixed.get('directory', ''))}'\")
"
}

# Source the values
eval $(read_toml)

# Validate configuration
if [ -z "$WALLPAPER_TYPE" ]; then
    log "Error: WALLPAPER_TYPE not set in config"
    exit 1
fi

# Function to apply wallpaper
apply_wallpaper() {
    local wp="$1"
    
    wait_for_hyprpaper_ipc
    
    log "Applying wallpaper: $wp"
    
    # Preload the wallpaper first to ensure it's available in hyprpaper.
    # Skipped on builds where preload was removed (hyprpaper.conf already
    # carries preload entries, and `wallpaper` works without it).
    preload_out=$(hyprctl hyprpaper preload "$wp" 2>&1)
    if ! printf '%s' "$preload_out" | grep -qi "invalid hyprpaper request"; then
        [ -n "$preload_out" ] && log "preload: $preload_out"
    fi
    
    # Try to get monitors
    local monitors=$(hyprctl monitors -j | python3 -c "import sys, json; print(' '.join([m['name'] for m in json.load(sys.stdin)]))" 2>/dev/null)
    [ -z "$monitors" ] && monitors=$(hyprctl monitors | grep "Monitor" | cut -d " " -f 2)

    if [ -z "$monitors" ]; then
        log "No monitors detected, applying to all (,)"
        hyprctl hyprpaper wallpaper ",$wp" >> "$LOG_FILE" 2>&1
    else
        for monitor in $monitors; do
            log "Applying to monitor $monitor"
            hyprctl hyprpaper wallpaper "$monitor,$wp" >> "$LOG_FILE" 2>&1
        done
    fi
}

# Handle single image mode
if [ "$WALLPAPER_TYPE" = "image" ]; then
    if [ -z "$WALLPAPER_IMAGE" ] || [ ! -f "$WALLPAPER_IMAGE" ]; then
        log "Error: Valid wallpaper image not found: $WALLPAPER_IMAGE"
        exit 1
    fi
    apply_wallpaper "$WALLPAPER_IMAGE"
    exit 0
fi

# Handle directory mode
if [ "$WALLPAPER_TYPE" = "directory" ]; then
    if [ -z "$WALLPAPER_DIRECTORY" ] || [ ! -d "$WALLPAPER_DIRECTORY" ]; then
        log "Error: Valid wallpaper directory not found: $WALLPAPER_DIRECTORY"
        exit 1
    fi
    
    wallpaper=$(find "$WALLPAPER_DIRECTORY" -type f \( -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" -o -name "*.webp" -o -name "*.bmp" \) 2>/dev/null | shuf -n 1)
    
    if [ -n "$wallpaper" ]; then
        apply_wallpaper "$wallpaper"
    else
        log "No images found in $WALLPAPER_DIRECTORY"
    fi
    exit 0
fi
