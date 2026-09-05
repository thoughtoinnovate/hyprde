#!/bin/bash
[ -n "${_HYPRDE_PYTHON_BIN:-}" ] || source "${0%/*}/hyprde-python.sh" 2>/dev/null || source "$HOME/.config/hypr/scripts/hyprde-python.sh" 2>/dev/null || true

# Configuration
TOML_CONFIG="$HOME/.config/hypr/hyprde.toml"
SHADER_FILE="$HOME/.config/hypr/shaders/redglow.frag"
GAMMA_LOG="$HOME/.config/hypr/gamma.log"

# Load Icons (best-effort: keep script functional without them)
if [ -f "$HOME/.config/hypr/scripts/hyprrocket.icons" ]; then
    # shellcheck disable=SC1091
    source "$HOME/.config/hypr/scripts/hyprrocket.icons"
fi
: "${GAMMA_ICON_DISABLED:=󰛨}"
: "${GAMMA_ICON_ENABLED:=󰌵}"
: "${GAMMA_ICON_AUTO:=󰌶}"

log_msg() {
  local msg=$1
  mkdir -p "$(dirname "$GAMMA_LOG")" 2>/dev/null || true
  echo "$(date '+%F %T') gamma.sh $msg" >> "$GAMMA_LOG" 2>/dev/null || true
}

notify_gamma() {
  local summary=$1
  local body=${2:-""}
  if command -v notify-send >/dev/null 2>&1; then
      notify-send -t 4000 "$summary" "$body" 2>/dev/null || true
  fi
}

# Helper to save state for persistence (quoted heredoc + env, atomic write)
save_state() {
  local mode=$1
  local err
  if ! err=$(GAMMA_MODE="$mode" GAMMA_TOML="$TOML_CONFIG" python3 - <<'PYEOF' 2>&1
import os
try:
    import tomlkit
except ImportError:
    print("tomlkit not installed; cannot persist nightlight mode", flush=True)
    raise SystemExit(3)
path = os.path.expanduser(os.environ.get("GAMMA_TOML", ""))
mode = os.environ.get("GAMMA_MODE", "off")
if not path or not os.path.exists(path):
    raise SystemExit(0)
with open(path, 'r') as f:
    data = tomlkit.load(f)
if "nightlight" not in data:
    data["nightlight"] = tomlkit.table()
data["nightlight"]["mode"] = mode
# Sync enabled boolean for backward compatibility
data["nightlight"]["enabled"] = True if mode != "off" else False
tmp = path + ".tmp"
with open(tmp, 'w') as f:
    f.write(tomlkit.dumps(data))
os.replace(tmp, path)
PYEOF
); then
      log_msg "save_state($mode) failed: $err"
      # Do not notify on missing-toml (first-run); do notify on real errors.
      if [ -f "$TOML_CONFIG" ]; then
          notify_gamma "RedGlow" "Applied, but could not persist mode: $err"
      fi
      return 1
  fi
  return 0
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

# Set the screen shader via Hyprland 0.55+ runtime eval.
# NOTE: `hyprctl keyword decoration:screen_shader` is a silent no-op on
# Lua-backed configs ("keyword can't work with non-legacy parsers", yet
# still exits 0) — so we use `hyprctl eval 'hl.config({...})'` instead.
set_shader() {
  local target=$1
  local escaped=${target//\\/\\\\}
  escaped=${escaped//\"/\\\"}
  local out
  if ! out=$(hyprctl eval "hl.config({ decoration = { screen_shader = \"$escaped\" } })" 2>&1); then
      echo "$out"
      return 1
  fi
  if ! printf '%s' "$out" | grep -q '^ok'; then
      echo "$out"
      return 1
  fi
  return 0
}

# Apply visual effect using Hyprland shaders.
# Returns 0 on success, non-zero when hyprctl or shader generation fails.
# State is saved by callers only on success.
apply_effect() {
  local type=$1 # "on", "off", or "auto"

  # Ensure gammastep is not running
  pkill gammastep 2>/dev/null || true

  if [ "$type" == "off" ]; then
    local err
    if ! err=$(set_shader ""); then
        log_msg "hyprctl off failed: $err"
        notify_gamma "RedGlow" "Failed to disable shader: $err"
        echo "$err" >&2
        return 1
    fi
    return 0
  fi

  # Always regenerate shader before applying to catch config changes
  if ! generate_shader; then
      log_msg "shader generation failed"
      notify_gamma "RedGlow" "Failed to generate shader at $SHADER_FILE"
      return 1
  fi

  if [ ! -f "$SHADER_FILE" ]; then
      log_msg "shader file missing after generate: $SHADER_FILE"
      notify_gamma "RedGlow" "Shader file missing: $SHADER_FILE"
      return 1
  fi

  local target=""
  if [ "$type" == "on" ]; then
      target="$SHADER_FILE"
  elif [ "$type" == "auto" ]; then
      local hour
      hour=$(date +%H)
      # Force base-10 to avoid octal pitfalls (e.g. 08/09)
      hour=$((10#$hour))
      if [ "$hour" -ge 18 ] || [ "$hour" -lt 6 ]; then
          target="$SHADER_FILE"
      else
          target=""
      fi
  fi

  local err
  if ! err=$(set_shader "$target"); then
      log_msg "hyprctl apply failed (type=$type target=$target): $err"
      notify_gamma "RedGlow" "Failed to apply shader: $err"
      echo "$err" >&2
      return 1
  fi
  return 0
}

# Function to turn ON (Manual)
turn_on() {
  if apply_effect "on"; then
      save_state "on"
  else
      return 1
  fi
}

# Function to turn OFF
turn_off() {
  if apply_effect "off"; then
      save_state "off"
  else
      return 1
  fi
}

# Function to turn AUTO
turn_auto() {
  if apply_effect "auto"; then
      save_state "auto"
  else
      return 1
  fi
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
