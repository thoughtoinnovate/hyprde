#!/bin/bash

# Load Icons (best-effort: keep script functional without them)
if [ -f "$HOME/.config/hypr/scripts/hyprrocket.icons" ]; then
    # shellcheck disable=SC1091
    source "$HOME/.config/hypr/scripts/hyprrocket.icons"
fi
# Fallbacks match waybar config format-icons (saver/high)
: "${POWER_ICON_SAVER:=󰈐}"
: "${POWER_ICON_HIGH:=󰓅}"

# Detect whether TLP is currently in power-saver (battery) mode.
# Supports old + new `tlp-stat -s` output:
#   old: "Mode = BAT|AC", "Power profile = ..."
#   new (TLP 1.10+): "TLP profile = balanced/BAT", "Power source = battery"
# Returns 0 (true) for saver, 1 for high-performance.
is_saver_mode() {
  local tlp_out="$1"
  local haystack
  haystack=$(printf '%s' "$tlp_out" | tr '[:upper:]' '[:lower:]')

  # Explicit battery indicators (checked first)
  if printf '%s' "$haystack" | grep -qiE "tlp profile[^\\n]*bat|power profile[^\\n]*bat|mode[[:space:]]*=[[:space:]]*bat|power source[^\\n]*batter|power-saver|power saver|[^a-z]sav[^a-z]|/bat([^a-z]|$)"; then
    return 0
  fi
  # Explicit AC / high-performance indicators
  if printf '%s' "$haystack" | grep -qiE "tlp profile[^\\n]*/ac|power profile[^\\n]*/ac|mode[[:space:]]*=[[:space:]]*ac|power source[^\\n]*ac|[^a-z]performance([^a-z]|$)"; then
    return 1
  fi
  # Fallback: any bare BAT token (e.g. "balanced/BAT (manual)") means saver
  if printf '%s' "$haystack" | grep -q "bat"; then
    return 0
  fi
  return 1
}

# Function to get TLP status reliably for Waybar
get_tlp_status() {
  local tlp_out=""
  if command -v tlp-stat >/dev/null 2>&1; then
    tlp_out=$(tlp-stat -s 2>/dev/null)
  fi

  local class="normal"
  local text="$POWER_ICON_HIGH"
  local alt="high"
  local tooltip="High Performance (AC)"
  local percentage=100

  if is_saver_mode "$tlp_out"; then
    class="green"
    text="$POWER_ICON_SAVER"
    alt="saver"
    tooltip="Power Saver (Battery)"
    percentage=0
  fi

  # text carries the icon glyph directly (works on all Waybar versions);
  # alt + percentage keep {icon}/format-icons object + array lookups working;
  # tooltip carries the human-readable mode name.
  echo "{\"text\": \"$text\", \"alt\": \"$alt\", \"tooltip\": \"$tooltip\", \"class\": \"$class\", \"percentage\": $percentage}"
}

# Toggle TLP modes
toggle_tlp() {
  local tlp_out=""
  if command -v tlp-stat >/dev/null 2>&1; then
    tlp_out=$(tlp-stat -s 2>/dev/null)
  fi

  if is_saver_mode "$tlp_out"; then
    # Currently in battery/saver mode -> Switch to AC mode
    sudo tlp ac > /dev/null 2>&1
    notify-send -t 1500 "Power Mode" "High Performance (AC)"
  else
    # Currently in AC/Performance mode -> Switch to BAT mode
    sudo tlp bat > /dev/null 2>&1
    notify-send -t 1500 "Power Mode" "Power Saver (Battery)"
  fi
  get_tlp_status
}

# Check the argument passed to the script
case "$1" in
  status)
    get_tlp_status
    ;;
  toggle)
    toggle_tlp
    ;;
  on)
    sudo tlp bat > /dev/null 2>&1
    get_tlp_status
    ;;
  off)
    sudo tlp ac > /dev/null 2>&1
    get_tlp_status
    ;;
  *)
    echo "{\"text\": \"Usage: $0 {status|toggle|on|off}\", \"class\": \"normal\"}"
    exit 1
    ;;
esac
