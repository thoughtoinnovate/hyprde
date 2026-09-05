#!/bin/bash
[ -n "${_HYPRDE_PYTHON_BIN:-}" ] || source "${0%/*}/hyprde-python.sh" 2>/dev/null || source "$HOME/.config/hypr/scripts/hyprde-python.sh" 2>/dev/null || true

# Persistence script for control center toggles
STATE_FILE="$HOME/.config/hypr/toggles.state"

get_state() {
    local key=$1
    local default=$2
    if [ -f "$STATE_FILE" ]; then
        local value=$(grep "^$key=" "$STATE_FILE" | cut -d'=' -f2)
        if [ -n "$value" ]; then
            echo "$value"
            return
        fi
    fi
    echo "$default"
}

# 1. Microphone
MIC_STATE=$(get_state "mic" "on")
if [ "$MIC_STATE" == "off" ]; then
    ~/.config/hypr/scripts/mic.sh off > /dev/null 2>&1
fi

# 2. Camera
CAM_STATE=$(get_state "camera" "on")
if [ "$CAM_STATE" == "off" ]; then
    ~/.config/hypr/scripts/camera.sh off > /dev/null 2>&1
fi

# 3. Gammastep (Night Light) — single source of truth: TOML nightlight.mode
# (gamma.sh save_state writes TOML; legacy toggles.state key kept as fallback)
get_nightlight_mode() {
    local toml="$HOME/.config/hypr/hyprde.toml"
    local mode=""
    if [ -f "$toml" ]; then
        mode=$(GAMMA_TOML="$toml" python3 - <<'PYEOF' 2>/dev/null
import os
try:
    import tomlkit
except ImportError:
    raise SystemExit(1)
path = os.path.expanduser(os.environ.get("GAMMA_TOML", ""))
with open(path, 'r') as f:
    data = tomlkit.load(f)
print(data.get("nightlight", {}).get("mode", ""))
PYEOF
)
    fi
    if [ -z "$mode" ]; then
        mode=$(get_state "gamma" "off")
    fi
    echo "$mode"
}
GAMMA_STATE=$(get_nightlight_mode)
if [ "$GAMMA_STATE" == "on" ] || [ "$GAMMA_STATE" == "auto" ]; then
    ~/.config/hypr/scripts/hyprsunset/gamma.sh "$GAMMA_STATE" > /dev/null 2>&1
fi
