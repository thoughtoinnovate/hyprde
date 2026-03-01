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

# Get mode from hyprde.toml
if [ -f "$HOME/.config/hypr/hyprde.toml" ]; then
    # Use python for reliable extraction
    MODE=$(python3 -c "import tomlkit, os; path = os.path.expanduser('~/.config/hypr/hyprde.toml'); data = tomlkit.load(open(path)); print(data.get('wallpapers', {}).get('mode', 'fixed'))" 2>/dev/null)
    [ -z "$MODE" ] && MODE="fixed"
else
    MODE="fixed"
fi

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