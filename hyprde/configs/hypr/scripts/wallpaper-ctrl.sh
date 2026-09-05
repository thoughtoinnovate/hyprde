#!/bin/bash
[ -n "${_HYPRDE_PYTHON_BIN:-}" ] || source "${0%/*}/hyprde-python.sh" 2>/dev/null || source "$HOME/.config/hypr/scripts/hyprde-python.sh" 2>/dev/null || true

# State management
STATE_FILE="$HOME/.config/hypr/wallpaper_mode"
LOG_FILE="/tmp/hypr_wallpaper.log"

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
    print(f'WALLPAPER_DIR=\"{expand_p(wp_path)}\"')
    print(f'INTERVAL={interval}')
except Exception as e:
    print('MODE=\"fixed\"')
    print('WALLPAPER_DIR=\"' + os.path.expanduser('~/Pictures/wallpapers/') + '\"')
    print('INTERVAL=60')
")
    eval "$CONFIG_VALS"
else
    MODE="fixed"
    WALLPAPER_DIR="$HOME/Pictures/wallpapers/"
    INTERVAL=60
fi

# Load Icons
source "$HOME/.config/hypr/scripts/hyprrocket.icons"

log() {
    echo "$(date +'%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Ensure state file exists
if [ ! -f "$STATE_FILE" ]; then
    if pgrep -f "dynamic-wallpapers.sh" > /dev/null; then
        echo "dynamic" > "$STATE_FILE"
    else
        echo "static" > "$STATE_FILE"
    fi
fi

# Function to get dynamic wallpaper status and return JSON for Waybar
get_status() {
  MODE=$(cat "$STATE_FILE" 2>/dev/null || echo "fixed")
  
  if [ "$MODE" == "dynamic" ]; then
      echo "{\"text\": \"$WALLPAPER_ICON\", \"tooltip\":\"Wallpaper: Dynamic (Timed)\",\"class\":\"enbld\"}"
  else
      # Try to get the current wallpaper path for the tooltip
      WP_PATH=$(grep -A 5 "\[wallpapers.fixed\]" "$HOME/.config/hypr/hyprde.toml" | grep "image =" | head -1 | cut -d'"' -f2 2>/dev/null)
      WP_NAME=$(basename "$WP_PATH")
      [ -z "$WP_NAME" ] && WP_NAME="None"
      echo "{\"text\": \"$WALLPAPER_ICON\", \"tooltip\":\"Wallpaper: Static\nFile: $WP_NAME\nPath: $WP_PATH\",\"class\":\"disbld\"}"
  fi
}

# Function to update hyprde.toml mode and sync state
update_config_mode() {
    local new_mode=$1
    if [ -f "$HOME/.config/hypr/hyprde.toml" ]; then
        # Use python with tomlkit for robust TOML update
        python3 -c "
import sys, os, tomlkit
path = os.path.expanduser('~/.config/hypr/hyprde.toml')
new_mode = sys.argv[1]
with open(path, 'r') as f: data = tomlkit.load(f)
if 'wallpapers' in data:
    data['wallpapers']['mode'] = new_mode
    # Ensure enable_dynamic is true if mode is dynamic
    if new_mode == 'dynamic':
        data['wallpapers']['enable_dynamic'] = True
with open(path, 'w') as f: f.write(tomlkit.dumps(data))
" "$new_mode"
        
        # Update state file
        echo "$new_mode" > "$STATE_FILE"
        
        # Regenerate generated configs
        if ! python3 "$HOME/.config/hypr/build_config.py" >> "$LOG_FILE" 2>&1; then
            log "ERROR: build_config.py failed"
            notify-send "Wallpaper Error" "Failed to regenerate configuration"
        fi
    fi
}

toggle() {
  # MODE is already set from TOML at top of script
  if [ "$MODE" == "dynamic" ]; then
      # Switch to Fixed (Static)
      pkill -f "dynamic-wallpapers.sh"
      update_config_mode "fixed"
      
      # Try to apply fixed wallpaper
      sh "$HOME/.config/hypr/scripts/fixed-wallpaper.sh" >> "$LOG_FILE" 2>&1 &
      
      notify-send -t 1000 "Wallpaper" "Switched to Static Mode"
      log "User toggled to FIXED"
  else
      # Switch to Dynamic
      update_config_mode "dynamic"
      sh "$HOME/.config/hypr/scripts/dynamic-wallpapers.sh" "$WALLPAPER_DIR" "$INTERVAL" >> "$LOG_FILE" 2>&1 &
      
      notify-send -t 1000 "Wallpaper" "Switched to Dynamic Mode"
      log "User toggled to DYNAMIC"
  fi
}

configure_time_slots() {
    # Get current directory settings from TOML
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
    
    cur_morning=$(echo "$dirs" | cut -d'|' -f1)
    cur_noon=$(echo "$dirs" | cut -d'|' -f2)
    cur_evening=$(echo "$dirs" | cut -d'|' -f3)
    
    while true; do
        # Define options with current values
        OPTIONS="󰖨  Set Morning Folder (current: $cur_morning)\n󰖧  Set Noon Folder (current: $cur_noon)\n󰖔  Set Evening Folder (current: $cur_evening)\n---\n󰅙  Back"
        
        CHOICE=$(echo -e "$OPTIONS" | wofi --dmenu --prompt "Configure Time Slots")
        
        if [[ -z "$CHOICE" ]] || [[ "$CHOICE" == *"Back"* ]]; then
            return
        fi
        
        # Determine which slot to configure
        slot=""
        current_val=""
        if [[ "$CHOICE" == *"Morning"* ]]; then
            slot="morning"
            current_val="$cur_morning"
        elif [[ "$CHOICE" == *"Noon"* ]]; then
            slot="noon"
            current_val="$cur_noon"
        elif [[ "$CHOICE" == *"Evening"* ]]; then
            slot="evening"
            current_val="$cur_evening"
        fi
        
        if [ -n "$slot" ]; then
            # Use zenity to pick folder
            FOLDER=$(zenity --file-selection --directory --title="Select $slot Wallpaper Folder" --filename="$HOME/Pictures/wallpapers/")
            
            if [ -n "$FOLDER" ]; then
                # Get just the folder name (relative to wallpapers base or absolute)
                FOLDER_NAME=$(basename "$FOLDER")
                
                # Update TOML
                if [ -f "$HOME/.config/hypr/hyprde.toml" ]; then
                    python3 -c "
import sys, os, tomlkit
path = os.path.expanduser('~/.config/hypr/hyprde.toml')
slot = sys.argv[1]
folder = sys.argv[2]
with open(path, 'r') as f: data = tomlkit.load(f)
if 'wallpapers' in data:
    if 'directories' not in data['wallpapers']:
        data['wallpapers']['directories'] = {}
    data['wallpapers']['directories'][slot] = folder
with open(path, 'w') as f: f.write(tomlkit.dumps(data))
" "$slot" "$FOLDER_NAME"
                    
                    # Update current values for display
                    case $slot in
                        morning) cur_morning="$FOLDER_NAME" ;;
                        noon) cur_noon="$FOLDER_NAME" ;;
                        evening) cur_evening="$FOLDER_NAME" ;;
                    esac
                    
                    # Regenerate config
                    python3 "$HOME/.config/hypr/build_config.py" >> "$LOG_FILE" 2>&1
                    
                    # Restart dynamic wallpaper service if running
                    if pgrep -f "dynamic-wallpapers.sh" > /dev/null; then
                        pkill -f "dynamic-wallpapers.sh"
                        WALLPAPER_PATH=$(grep -A 5 "\[wallpapers\]" "$HOME/.config/hypr/hyprde.toml" | grep "path =" | head -1 | cut -d'"' -f2)
                        [ -z "$WALLPAPER_PATH" ] && WALLPAPER_PATH="$HOME/Pictures/wallpapers/"
                        sh "$HOME/.config/hypr/scripts/dynamic-wallpapers.sh" "$WALLPAPER_PATH" "60" "time" >> "$LOG_FILE" 2>&1 &
                    fi
                    
                    notify-send "Wallpaper" "$slot folder set to: $FOLDER_NAME"
                fi
            fi
        fi
    done
}

menu() {
    # Get current info for display
    CUR_MODE=$(python3 -c "import os, tomlkit; path = os.path.expanduser('~/.config/hypr/hyprde.toml'); data = tomlkit.load(open(path, 'r')); print(data.get('wallpapers', {}).get('mode', 'fixed'))")
    CUR_SPLASH=$(python3 -c "import os, tomlkit; path = os.path.expanduser('~/.config/hypr/hyprde.toml'); data = tomlkit.load(open(path, 'r')); print(data.get('wallpapers', {}).get('splash', False))")
    CUR_WP=$(python3 -c "import os, tomlkit; path = os.path.expanduser('~/.config/hypr/hyprde.toml'); data = tomlkit.load(open(path, 'r')); print(os.path.basename(data.get('wallpapers', {}).get('fixed', {}).get('image', 'None')))")

    # Define options
    SPLASH_ICON=$([[ "$CUR_SPLASH" == "True" ]] && echo "󰄬" || echo "󰄱")
    OPTIONS="Static Mode (Select Image)\nDynamic Mode (Time-based)\nDynamic Mode (Simple Rotation)\n---\n$SPLASH_ICON  Toggle Splash Text (Watermark)\n󰍜  Configure Time Slots\n---\nCurrent: $CUR_MODE ($CUR_WP)"
    
    CHOICE=$(echo -e "$OPTIONS" | wofi --dmenu --prompt "Wallpaper Management")
    
    if [[ "$CHOICE" == *"Toggle Splash Text"* ]]; then
        python3 -c "
import os, tomlkit
path = os.path.expanduser('~/.config/hypr/hyprde.toml')
with open(path, 'r') as f: data = tomlkit.load(f)
if 'wallpapers' in data:
    current = data['wallpapers'].get('splash', False)
    data['wallpapers']['splash'] = not current
with open(path, 'w') as f: f.write(tomlkit.dumps(data))
"
        python3 "$HOME/.config/hypr/build_config.py"
        # Notify and re-run menu to show updated state
        notify-send "Wallpaper" "Splash text $( [[ "$CUR_SPLASH" == "True" ]] && echo "disabled" || echo "enabled" )"
        exec "$0" menu
        return
    fi
    
    if [[ "$CHOICE" == *"Configure Time Slots"* ]]; then
        configure_time_slots
        return
    fi
    
    if [[ "$CHOICE" == *"Static"* ]]; then
        # Use zenity to pick file
        FILE=$(zenity --file-selection --title="Select Wallpaper" --file-filter="*.jpg *.png *.jpeg *.webp")
        if [ -n "$FILE" ]; then
             # Update TOML for persistence
             if [ -f "$HOME/.config/hypr/hyprde.toml" ]; then
                 python3 -c "
import sys, os, tomlkit
path = os.path.expanduser('~/.config/hypr/hyprde.toml')
new_image = sys.argv[1]
with open(path, 'r') as f: data = tomlkit.load(f)
if 'wallpapers' in data:
    data['wallpapers']['mode'] = 'fixed'
    if 'fixed' not in data['wallpapers']:
        data['wallpapers']['fixed'] = {}
    data['wallpapers']['fixed']['type'] = 'image'
    data['wallpapers']['fixed']['image'] = new_image
with open(path, 'w') as f: f.write(tomlkit.dumps(data))
" "$FILE"
                 echo "fixed" > "$STATE_FILE"
                 python3 "$HOME/.config/hypr/build_config.py" >> "$LOG_FILE" 2>&1
             fi
             
             # Set mode to static
             pkill -f "dynamic-wallpapers.sh"
             sh "$HOME/.config/hypr/scripts/fixed-wallpaper.sh" >> "$LOG_FILE" 2>&1 &
             
             # Ask to update lockscreen too
             if zenity --question --text="Would you like to use this image for your lockscreen as well?" --title="Sync Lockscreen"; then
                 python3 -c "
import sys, os, tomlkit
path = os.path.expanduser('~/.config/hypr/hyprde.toml')
new_image = sys.argv[1]
with open(path, 'r') as f: data = tomlkit.load(f)
if 'lockscreen' in data:
    data['lockscreen']['background'] = new_image
with open(path, 'w') as f: f.write(tomlkit.dumps(data))
" "$FILE"
                 python3 "$HOME/.config/hypr/build_config.py" >> "$LOG_FILE" 2>&1
             fi
             
             notify-send "Wallpaper" "Static mode set: $(basename "$FILE")"
        fi
        
    elif [[ "$CHOICE" == *"Time-based"* ]]; then
        # Pick directory
        DIR=$(zenity --file-selection --directory --title="Select Base Directory (containing sunrise/sunset)")
        if [ -n "$DIR" ]; then 
            # Update TOML
            if [ -f "$HOME/.config/hypr/hyprde.toml" ]; then
                 python3 -c "
import sys, os, tomlkit
path = os.path.expanduser('~/.config/hypr/hyprde.toml')
new_dir = sys.argv[1]
with open(path, 'r') as f: data = tomlkit.load(f)
if 'wallpapers' in data:
    data['wallpapers']['mode'] = 'dynamic'
    data['wallpapers']['path'] = new_dir
    data['wallpapers']['enable_dynamic'] = True
with open(path, 'w') as f: f.write(tomlkit.dumps(data))
" "$DIR"
                 echo "dynamic" > "$STATE_FILE"
                 python3 "$HOME/.config/hypr/build_config.py" >> "$LOG_FILE" 2>&1
            fi
            
            # Kill old, Start new
            pkill -f "dynamic-wallpapers.sh"
            sh "$HOME/.config/hypr/scripts/dynamic-wallpapers.sh" "$DIR" "60" "time" >> "$LOG_FILE" 2>&1 &
            notify-send "Wallpaper" "Dynamic (Time) mode enabled"
        fi
        
    elif [[ "$CHOICE" == *"Rotation"* ]]; then
        # Pick directory
        DIR=$(zenity --file-selection --directory --title="Select Wallpaper Directory")
        if [ -n "$DIR" ]; then
            # Update TOML
            if [ -f "$HOME/.config/hypr/hyprde.toml" ]; then
                 python3 -c "
import sys, os, tomlkit
path = os.path.expanduser('~/.config/hypr/hyprde.toml')
new_dir = sys.argv[1]
with open(path, 'r') as f: data = tomlkit.load(f)
if 'wallpapers' in data:
    data['wallpapers']['mode'] = 'dynamic'
    data['wallpapers']['path'] = new_dir
    data['wallpapers']['enable_dynamic'] = True
with open(path, 'w') as f: f.write(tomlkit.dumps(data))
" "$DIR"
                 echo "dynamic" > "$STATE_FILE"
                 python3 "$HOME/.config/hypr/build_config.py" >> "$LOG_FILE" 2>&1
            fi
            
            pkill -f "dynamic-wallpapers.sh"
            sh "$HOME/.config/hypr/scripts/dynamic-wallpapers.sh" "$DIR" "60" "simple" >> "$LOG_FILE" 2>&1 &
            notify-send "Wallpaper" "Dynamic (Rotation) mode enabled"
        fi
    fi
}

case "$1" in
  status)
    get_status
    ;;
  toggle)
    toggle
    ;;
  menu)
    menu
    ;;
  *)
    echo "Usage: $0 {status|toggle|menu}"
    exit 1
    ;;
esac
