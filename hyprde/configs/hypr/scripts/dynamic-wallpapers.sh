#!/bin/bash

script_dir=$(dirname "$0")
WALLPAPER_DIR=${1:-"$HOME/Pictures/wallpapers/"}
INTERVAL=${2:-60}  # Change wallpaper every 60 seconds by default
MODE=${3:-"time"} # 'time' or 'simple'
LOG_FILE="/tmp/hypr_wallpaper.log"

log() {
    echo "$(date +'%Y-%m-%d %H:%M:%S') [DYNAMIC] - $1" >> "$LOG_FILE"
}

toggleNightLight(){
    isOn=$($HOME/.config/hypr/scripts/gammastep/gamma.sh status|jq '.text' 2>/dev/null)
    if [ "$isOn" = "\"disabled\"" ]; then
        sh $HOME/.config/hypr/scripts/gammastep/gamma_toggle.sh
    fi
}

wallpaper_dir(){
    if [ "$MODE" == "simple" ]; then
        echo "$WALLPAPER_DIR"
        return
    fi
   
    # Get directory names from TOML config
    # Defaults: morning, noon, evening
    dirs=$(python3 -c "
import os, tomlkit
path = os.path.expanduser('~/.config/hypr/hyprde.toml')
try:
    with open(path, 'r') as f: data = tomlkit.load(f)
    wp = data.get('wallpapers', {})
    directories = wp.get('directories', {})
    print(f\"{directories.get('morning', 'morning')}|{directories.get('noon', 'noon')}|{directories.get('evening', 'evening')}\")
except:
    print('morning|noon|evening')
" 2>/dev/null)
    
    morning_dir=$(echo "$dirs" | cut -d'|' -f1)
    noon_dir=$(echo "$dirs" | cut -d'|' -f2)
    evening_dir=$(echo "$dirs" | cut -d'|' -f3)
    
    timeOfDay=$($script_dir/time_of_day.sh)
    case $timeOfDay in
        morning)
            echo "$WALLPAPER_DIR/$morning_dir"
            ;;
        noon)
            echo "$WALLPAPER_DIR/$noon_dir"
            ;;
        evening)
            echo "$WALLPAPER_DIR/$evening_dir"
            ;;
        *)
            echo "$WALLPAPER_DIR"
            ;;
    esac
}

while true; do
    # Select a random wallpaper
    wall_dir=$(wallpaper_dir)
    wallpaper=$(find "$wall_dir" -type f \( -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" -o -name "*.webp" -o -name "*.bmp" \) 2>/dev/null | shuf -n 1)
    
    # Validate that we found a wallpaper
    if [ -z "$wallpaper" ] || [ ! -f "$wallpaper" ]; then
        log "Warning: No wallpapers found in $wall_dir"
        sleep "$INTERVAL"
        continue
    fi
    
    log "Applying dynamic wallpaper: $wallpaper"

    # Preload the wallpaper first to ensure it's available in hyprpaper
    hyprctl hyprpaper preload "$wallpaper" >> "$LOG_FILE" 2>&1

    # Get monitor list
    monitors=$(hyprctl monitors -j | python3 -c "import sys, json; print(' '.join([m['name'] for m in json.load(sys.stdin)]))" 2>/dev/null)
    [ -z "$monitors" ] && monitors=$(hyprctl monitors | grep "Monitor" | cut -d " " -f 2)

    if [ -z "$monitors" ]; then
        hyprctl hyprpaper wallpaper ",$wallpaper" >> "$LOG_FILE" 2>&1
    else
        for monitor in $monitors; do
            hyprctl hyprpaper wallpaper "$monitor,$wallpaper" >> "$LOG_FILE" 2>&1
        done
    fi

    toggleNightLight
    sleep "$INTERVAL"
done