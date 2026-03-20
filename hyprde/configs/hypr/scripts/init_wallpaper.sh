#!/bin/bash
# init_wallpaper.sh

STATE_FILE="$HOME/.config/hypr/wallpaper_mode"
LOG_FILE="/tmp/hypr_wallpaper.log"
WALLPAPER_DIR="${1:-$HOME/Pictures/wallpapers/}"
INTERVAL="${2:-60}"

# Function to log
log() {
    echo "$(date +'%Y-%m-%d %H:%M:%S') [INIT] - $1" >> "$LOG_FILE"
}

# Ensure log file exists
touch "$LOG_FILE"

# Get config from hyprde.toml
if [ -f "$HOME/.config/hypr/hyprde.toml" ]; then
    # Use python for reliable extraction
    CONFIG_VALS=$(python3 -c "
import tomlkit, os
path = os.path.expanduser('~/.config/hypr/hyprde.toml')
try:
    with open(path, 'r') as f: data = tomlkit.load(f)
    wp = data.get('wallpapers', {})
    mode = wp.get('mode', 'fixed')
    wp_path = wp.get('path', '~/Pictures/wallpapers/')
    interval = wp.get('interval', 60)
    
    def expand_p(p):
        return os.path.expanduser(str(p).replace('\$HOME', os.path.expanduser('~')).replace('$HOME', os.path.expanduser('~')))
    
    print(f'MODE=\"{mode}\"')
    print(f'WP_PATH=\"{expand_p(wp_path)}\"')
    print(f'INTERVAL_VAL={interval}')
except Exception as e:
    print('MODE=\"fixed\"')
    print('WP_PATH=\"' + os.path.expanduser('~/Pictures/wallpapers/') + '\"')
    print('INTERVAL_VAL=60')
")
    eval "$CONFIG_VALS"
else
    MODE="fixed"
    WP_PATH="$HOME/Pictures/wallpapers/"
    INTERVAL_VAL=60
fi

# Override with arguments if provided
WALLPAPER_DIR="${1:-$WP_PATH}"
INTERVAL="${2:-$INTERVAL_VAL}"

# Sync state file for Waybar and other scripts
echo "$MODE" > "$STATE_FILE"

# Map 'fixed' to 'static' internally if needed
INTERNAL_MODE="$MODE"
[ "$INTERNAL_MODE" == "fixed" ] && INTERNAL_MODE="static"

log "Initializing wallpaper with mode: $MODE (internal: $INTERNAL_MODE)"

if [ "$INTERNAL_MODE" == "dynamic" ]; then
    log "Starting dynamic wallpapers..."
    pkill -f "dynamic-wallpapers.sh"
    sh "$HOME/.config/hypr/scripts/dynamic-wallpapers.sh" "$WALLPAPER_DIR" "$INTERVAL" >> "$LOG_FILE" 2>&1 &
elif [ "$INTERNAL_MODE" == "static" ]; then
    log "Starting static wallpaper..."
    pkill -f "dynamic-wallpapers.sh"
    if [ -f "$HOME/.config/hypr/scripts/fixed-wallpaper.sh" ]; then
        sh "$HOME/.config/hypr/scripts/fixed-wallpaper.sh" >> "$LOG_FILE" 2>&1 &
    else
        log "fixed-wallpaper.sh not found."
    fi
else
    log "Wallpaper management disabled or unknown mode '$MODE'."
fi