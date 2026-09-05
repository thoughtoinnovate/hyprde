#!/bin/bash
[ -n "${_HYPRDE_PYTHON_BIN:-}" ] || source "${0%/*}/hyprde-python.sh" 2>/dev/null || source "$HOME/.config/hypr/scripts/hyprde-python.sh" 2>/dev/null || true

# Configuration
TOML_CONFIG="$HOME/.config/hypr/hyprde.toml"
GAMMA_LOG="$HOME/.config/hypr/gamma.log"

# Load Icons
if [ -f "$HOME/.config/hypr/scripts/hyprrocket.icons" ]; then
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

save_state() {
  local mode=$1
  local err
  if ! err=$(GAMMA_MODE="$mode" GAMMA_TOML="$TOML_CONFIG" python3 - <<'PYEOF' 2>&1
import os
try:
    import tomlkit
except ImportError:
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
data["nightlight"]["enabled"] = (mode != "off")
with open(path, 'w') as f:
    f.write(tomlkit.dumps(data))
PYEOF
  ); then
      log_msg "failed to persist state '$mode': $err"
      return 1
  fi
  return 0
}

get_mode() {
    local toml_mode=""
    if [ -f "$TOML_CONFIG" ]; then
        toml_mode=$(python3 -c "import tomlkit, sys; doc=tomlkit.parse(open('$TOML_CONFIG').read()); print(doc.get('nightlight', {}).get('mode', ''))" 2>/dev/null)
    fi
    if [ -n "$toml_mode" ]; then
        echo "$toml_mode"
        return
    fi
    # Fallback checking running process
    if pgrep hyprsunset >/dev/null; then
        echo "on"
    else
        echo "off"
    fi
}

get_temperature() {
    local key=$1
    if [ -f "$TOML_CONFIG" ]; then
        python3 -c "import tomlkit, sys; doc=tomlkit.parse(open('$TOML_CONFIG').read()); print(doc.get('nightlight', {}).get('$key', '3400'))" 2>/dev/null || echo "3400"
    else
        echo "3400"
    fi
}

get_gamma_status() {
  local mode=$(get_mode)
  local icon=""
  local class=""
  local tooltip=""

  case "$mode" in
    on)
      icon="$GAMMA_ICON_ENABLED"
      class="active"
      tooltip="Nightlight: ON"
      ;;
    auto)
      icon="$GAMMA_ICON_AUTO"
      class="auto"
      tooltip="Nightlight: Auto Mode"
      ;;
    *)
      icon="$GAMMA_ICON_DISABLED"
      class="disbld"
      tooltip="Nightlight: OFF"
      ;;
  esac

  echo "{\"text\": \"$icon\", \"tooltip\": \"$tooltip\", \"class\": \"$class\"}"
}

apply_effect() {
  local type=$1 # "on", "off", or "auto"

  # Ensure hyprsunset is not running
  pkill hyprsunset 2>/dev/null || true

  if [ "$type" == "off" ]; then
    return 0
  fi

  local temp="3400"
  if [ "$type" == "on" ]; then
      temp=$(get_temperature "temp_night")
  elif [ "$type" == "auto" ]; then
      local hour=$(date +%H)
      hour=$((10#$hour))
      if [ "$hour" -ge 18 ] || [ "$hour" -lt 6 ]; then
          temp=$(get_temperature "temp_night")
      else
          # Day mode
          return 0
      fi
  fi

  hyprsunset -t "$temp" >/dev/null 2>&1 &
  return 0
}

turn_on() {
  if apply_effect "on"; then
      save_state "on"
  else
      return 1
  fi
}

turn_off() {
  if apply_effect "off"; then
      save_state "off"
  else
      return 1
  fi
}

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

case "$1" in
  status)
    get_gamma_status
    ;;
  toggle)
    toggle
    pkill -RTMIN+6 waybar || true
    get_gamma_status
    ;;
  on)
    turn_on
    pkill -RTMIN+6 waybar || true
    get_gamma_status
    ;;
  off)
    turn_off
    pkill -RTMIN+6 waybar || true
    get_gamma_status
    ;;
  auto)
    turn_auto
    pkill -RTMIN+6 waybar || true
    get_gamma_status
    ;;
  *)
    echo "{\"text\": \"$GAMMA_ICON_DISABLED\", \"tooltip\": \"Usage: $0 {status|toggle|on|off|auto}\", \"class\": \"disbld\"}"
    exit 1
    ;;
esac
