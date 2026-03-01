#!/bin/bash

# Configuration directories
THEMES_DIR="$HOME/.config/hypr/themes"
CURRENT_SYMLINK="$THEMES_DIR/current.css"
MAKO_CONFIG="$HOME/.config/mako/config"

# Load Icons
source "$HOME/.config/hypr/scripts/hyprrocket.icons"

get_status() {
    # Read mode from TOML
    local mode=$(python3 -c "import tomlkit, os; path=os.path.expanduser('~/.config/hypr/hyprde.toml'); d=tomlkit.load(open(path)) if os.path.exists(path) else {}; print(d.get('theme', {}).get('mode', 'dark'))" 2>/dev/null || echo "dark")
    
    local theme="dark"
    if [ -L "$CURRENT_SYMLINK" ]; then
        local target=$(readlink "$CURRENT_SYMLINK")
        if [[ "$target" == *"light"* ]]; then
            theme="light"
        fi
    fi
    
    local icon="$THEME_ICON_MANUAL"
    local class="disbld"
    local tooltip="Theme: Dark Mode"

    if [ "$mode" == "auto" ]; then
        icon="$THEME_ICON_AUTO"
        class="auto-theme"
        tooltip="Theme: Auto ($theme)"
    elif [ "$theme" == "light" ]; then
        class="enbld"
        tooltip="Theme: Light Mode"
    fi

    echo "{\"text\": \"$icon\", \"tooltip\": \"$tooltip\", \"class\": \"$class\"}"
}

set_theme() {
    local new_theme="$1" # e.g., "dark.css" or "light.css"
    local mode="${2:-$1}" # optional mode: "dark", "light", or "auto"
    
    # Clean up mode string for TOML (remove .css if present)
    local clean_mode=$(echo "$mode" | sed 's/\.css//')
    
    local theme_name="Dark Mode"
    local active_border="rgba(33ccffee) rgba(00ff99ee) 45deg"
    local inactive_border="rgba(595959aa)"

    if [[ "$new_theme" == *"light"* ]]; then
        theme_name="Light Mode"
        gsettings set org.gnome.desktop.interface color-scheme 'prefer-light'
        gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita'
        active_border="rgba(0066ccee) rgba(003366ee) 45deg"
        inactive_border="rgba(00000044)"
    else
        gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
        gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita-dark'
    fi

    # Update symlink
    ln -sf "$new_theme" "$CURRENT_SYMLINK"

    # 1. Update Mako config IMMEDIATELY for responsiveness
    local MAKO_DIR="$HOME/.config/mako"
    if [ -d "$MAKO_DIR" ]; then
        if [[ "$new_theme" == *"light"* ]]; then
            ln -sf "$MAKO_DIR/config.light" "$MAKO_DIR/config"
        else
            ln -sf "$MAKO_DIR/config.dark" "$MAKO_DIR/config"
        fi
        
        # Robust restart for systemd-managed Mako
        if systemctl --user is-active --quiet mako; then
            systemctl --user restart mako
        else
            pkill -9 mako 2>/dev/null
            sleep 0.2
            mako --config "$MAKO_DIR/config" > /dev/null 2>&1 &
        fi
        
        # Send confirmation notification
        sleep 0.5
        notify-send -t 2000 "System Theme" "Switched to $theme_name"
    fi

    # 2. Apply Hyprland colors
    hyprctl keyword general:col.active_border "$active_border"
    hyprctl keyword general:col.inactive_border "$inactive_border"

    # 3. Persist choices in hyprde.toml
    python3 - <<EOF
import tomlkit
import os
path = os.path.expanduser("~/.config/hypr/hyprde.toml")
if os.path.exists(path):
    with open(path, 'r') as f: data = tomlkit.load(f)
    if "general" not in data: data["general"] = tomlkit.table()
    data["general"]["col_active_border"] = "$active_border"
    data["general"]["col_inactive_border"] = "$inactive_border"
    if "theme" not in data: data["theme"] = tomlkit.table()
    data["theme"]["mode"] = "$clean_mode"
    with open(path, 'w') as f: f.write(tomlkit.dumps(data))
EOF

    # 4. Generate dynamic config and reload Waybar
    python3 "$HOME/.config/hypr/build_config.py" > /dev/null 2>&1
    pkill -USR2 waybar
}

toggle() {
    local mode=$(python3 -c "import tomlkit, os; path=os.path.expanduser('~/.config/hypr/hyprde.toml'); d=tomlkit.load(open(path)) if os.path.exists(path) else {}; print(d.get('theme', {}).get('mode', 'dark'))" 2>/dev/null || echo "dark")

    if [ "$mode" == "light" ]; then
        set_theme "dark.css" "dark"
    elif [ "$mode" == "dark" ]; then
        # Switch to Auto (use current time to pick the actual css)
        local hour=$(date +%H)
        if [ "$hour" -ge 6 ] && [ "$hour" -lt 18 ]; then
            set_theme "light.css" "auto"
        else
            set_theme "dark.css" "auto"
        fi
    else
        # Currently Auto -> Switch to Light
        set_theme "light.css" "light"
    fi
    
    get_status
}

case "$1" in
    status)
        get_status
        ;;
    toggle)
        toggle
        ;;
    dark)
        set_theme "dark.css" "dark"
        get_status
        ;;
    light)
        set_theme "light.css" "light"
        get_status
        ;;
    auto)
        # Force re-evaluate auto based on time
        local hour=$(date +%H)
        if [ "$hour" -ge 6 ] && [ "$hour" -lt 18 ]; then
            set_theme "light.css" "auto"
        else
            set_theme "dark.css" "auto"
        fi
        get_status
        ;;
    sync)
        # Special command for Rocket: only change if mode is "auto"
        local mode=$(python3 -c "import tomlkit, os; path=os.path.expanduser('~/.config/hypr/hyprde.toml'); d=tomlkit.load(open(path)) if os.path.exists(path) else {}; print(d.get('theme', {}).get('mode', 'dark'))" 2>/dev/null || echo "dark")
        if [ "$mode" == "auto" ]; then
            if [ "$2" == "dark" ]; then set_theme "dark.css" "auto"; else set_theme "light.css" "auto"; fi
        fi
        ;;
    *)
        echo "{\"text\": \"$THEME_ICON_MANUAL\", \"tooltip\": \"Usage: $0 {status|toggle|dark|light|auto|sync}\", \"class\": \"disbld\"}"
        exit 1
        ;;
esac
