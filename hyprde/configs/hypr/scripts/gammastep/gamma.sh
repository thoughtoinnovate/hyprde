#!/bin/bash

# Configuration
TOML_CONFIG="$HOME/.config/hypr/hyprde.toml"
SHADER_FILE="$HOME/.config/hypr/shaders/redglow.frag"

# Load Icons
source "$HOME/.config/hypr/scripts/hyprrocket.icons"

# Helper to save state for persistence
save_state() {
  local mode=$1
  python3 - <<EOF
import tomlkit
import os
path = os.path.expanduser("$TOML_CONFIG")
if os.path.exists(path):
    with open(path, 'r') as f: data = tomlkit.load(f)
    if "nightlight" not in data: data["nightlight"] = tomlkit.table()
    data["nightlight"]["mode"] = "$mode"
    # Sync enabled boolean for backward compatibility
    data["nightlight"]["enabled"] = True if "$mode" != "off" else False
    with open(path, 'w') as f: f.write(tomlkit.dumps(data))
EOF
}

get_config_value() {
    local key=$1
    local default=$2
    python3 -c "import tomlkit, os; path=os.path.expanduser('$TOML_CONFIG'); d=tomlkit.load(open(path)) if os.path.exists(path) else {}; print(d.get('nightlight', {}).get('$key', '$default'))" 2>/dev/null || echo "$default"
}

get_mode() {
    get_config_value "mode" "off"
}

# Generate shader based on config intensity
generate_shader() {
    local blue=$(get_config_value "blue_intensity" "0.60")
    local green=$(get_config_value "green_intensity" "0.85")
    
    mkdir -p "$(dirname "$SHADER_FILE")"
    cat > "$SHADER_FILE" <<EOF
#version 300 es
precision mediump float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

void main() {
    vec4 pix = texture(tex, v_texcoord);
    
    // Intensity values from config: Green: $green, Blue: $blue
    pix.g *= $green;
    pix.b *= $blue;
    
    fragColor = pix;
}
EOF
}

get_gamma_status() {
  local mode=$(get_mode)
  local icon="$GAMMA_ICON_DISABLED"
  local class="disbld"
  local tooltip="RedGlow: OFF"

  case "$mode" in
    on)
      icon="$GAMMA_ICON_ENABLED"
      class="enbld"
      tooltip="RedGlow: Manual ON"
      ;;
    auto)
      icon="$GAMMA_ICON_AUTO"
      class="auto"
      tooltip="RedGlow: Auto Mode"
      ;;
    *)
      icon="$GAMMA_ICON_DISABLED"
      class="disbld"
      tooltip="RedGlow: OFF"
      ;;
  esac

  echo "{\"text\": \"$icon\", \"tooltip\": \"$tooltip\", \"class\": \"$class\"}"
}

# Apply visual effect using Hyprland shaders
apply_effect() {
  local type=$1 # "on", "off", or "auto"
  
  # Ensure gammastep is not running
  pkill gammastep

  if [ "$type" == "off" ]; then
    hyprctl keyword decoration:screen_shader "" > /dev/null
    return
  fi

  # Always regenerate shader before applying to catch config changes
  generate_shader

  if [ -f "$SHADER_FILE" ]; then
      if [ "$type" == "on" ]; then
          hyprctl keyword decoration:screen_shader "$SHADER_FILE" > /dev/null
      elif [ "$type" == "auto" ]; then
          local hour=$(date +%H)
          if [ $hour -ge 18 ] || [ $hour -lt 6 ]; then
              hyprctl keyword decoration:screen_shader "$SHADER_FILE" > /dev/null
          else
              hyprctl keyword decoration:screen_shader "" > /dev/null
          fi
      fi
  fi
}

# Function to turn ON (Manual)
turn_on() {
  apply_effect "on"
  save_state "on"
}

# Function to turn OFF
turn_off() {
  apply_effect "off"
  save_state "off"
}

# Function to turn AUTO
turn_auto() {
  apply_effect "auto"
  save_state "auto"
}

toggle() {
    local mode=$(get_mode)
    if [ "$mode" == "off" ]; then
        turn_on
    elif [ "$mode" == "on" ]; then
        turn_auto
    else
        turn_off
    fi
}

# Check the argument passed to the script
case "$1" in
  status)
    get_gamma_status
    ;;
  toggle)
    toggle
    get_gamma_status
    ;;
  on)
    turn_on
    get_gamma_status
    ;;
  off)
    turn_off
    get_gamma_status
    ;;
  auto)
    turn_auto
    get_gamma_status
    ;;
  generate)
    generate_shader
    ;;
  *)
    echo "{\"text\": \"$GAMMA_ICON_DISABLED\", \"tooltip\": \"Usage: $0 {status|toggle|on|off|auto|generate}\", \"class\": \"disbld\"}"
    exit 1
    ;;
esac
