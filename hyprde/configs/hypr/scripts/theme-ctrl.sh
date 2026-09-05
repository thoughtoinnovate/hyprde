#!/bin/bash
[ -n "${_HYPRDE_PYTHON_BIN:-}" ] || source "${0%/*}/hyprde-python.sh" 2>/dev/null || source "$HOME/.config/hypr/scripts/hyprde-python.sh" 2>/dev/null || true

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
    # Active border follows the accent: first gradient stop re-derived,
    # remainder of the user's gradient preserved (custom second stops and
    # angles survive theme toggles).
    local accent_rgb=$(python3 -c "import tomlkit, os, re; path=os.path.expanduser('~/.config/hypr/hyprde.toml'); d=tomlkit.load(open(path)) if os.path.exists(path) else {}; a=d.get('theme', {}).get('accent', '#007aff'); m=re.match(r'#([0-9a-fA-F]{6})', a); print(m.group(1).lower() if m else ''.join('%02x' % max(0, min(255, int(x))) for x in re.match(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', a).groups()) if re.match(r'rgba?\(', a) else '007aff')" 2>/dev/null || echo "007aff")
    local cur_border=$(python3 -c "import tomlkit, os; path=os.path.expanduser('~/.config/hypr/hyprde.toml'); d=tomlkit.load(open(path)) if os.path.exists(path) else {}; print(d.get('general', {}).get('col_active_border', ''))" 2>/dev/null || echo "")
    local border_rest="${cur_border#* }"
    [ "$border_rest" = "$cur_border" ] && border_rest=""
    local active_border="rgba(${accent_rgb}ee)${border_rest:+ $border_rest}"
    local inactive_border="rgba(595959aa)"

    if [[ "$new_theme" == *"light"* ]]; then
        theme_name="Light Mode"
        gsettings set org.gnome.desktop.interface color-scheme 'prefer-light'
        gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita'
        active_border="rgba(${accent_rgb}ee) rgba(003366ee) 45deg"
        inactive_border="rgba(00000044)"
    else
        gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
        gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita-dark'
    fi

    # Update symlink
    ln -sf "$new_theme" "$CURRENT_SYMLINK"

    # Fan out the accent color to all components (theme vars, wofi, Mako).
    local accent_hex=$(python3 -c "import tomlkit, os; path=os.path.expanduser('~/.config/hypr/hyprde.toml'); d=tomlkit.load(open(path)) if os.path.exists(path) else {}; print(d.get('theme', {}).get('accent', '#007aff'))" 2>/dev/null || echo "#007aff")
    sh "$HOME/.config/hypr/scripts/apply-accent.sh" "$accent_hex" 2>/dev/null || true

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

    # 2. Hyprland colors apply via the Lua rebuild + reload below.
    # NOTE: `hyprctl keyword general:col.*` is a silent no-op on Hyprland
    # 0.55+ ("keyword can't work with non-legacy parsers"), and gradients
    # via `hyprctl eval` are rejected in 0.55.4 — so no fast path here.

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

    # 4. Generate Lua config and reload
    python3 "$HOME/.config/hypr/build_config.py" > /dev/null 2>&1
    hyprctl reload
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
    pkill -RTMIN+5 waybar || true
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
