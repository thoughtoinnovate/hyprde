#!/bin/bash

# Load Icons
source "$HOME/.config/hypr/scripts/hyprrocket.icons"

# Function to get TLP status and return JSON for Waybar
get_status() {
  local status=$(nmcli radio wifi)
  if [[ "$status" == "enabled" ]]; then
      echo "{\"text\": \"$WIFI_ICON_ENABLED\", \"tooltip\":\"WiFi: enabled\",\"class\":\"enbld\"}"
  else
      echo "{\"text\": \"$WIFI_ICON_DISABLED\", \"tooltip\":\"WiFi: disabled\",\"class\":\"disbld\"}"
  fi
}

toggle() {
  local status=$(nmcli radio wifi)
  if [[ "$status" == "enabled" ]]; then
      turn_off
    pkill -RTMIN+3 waybar || true
      get_status
  else
    turn_on
    pkill -RTMIN+3 waybar || true
    get_status
  fi
}

# Function to turn TLP on
turn_on() {
  nmcli radio wifi on
}

# Function to turn TLP off
turn_off() {
  nmcli radio wifi off
}

# Check the argument passed to the script
case "$1" in
  status)
    get_status
    ;;
  toggle)
    toggle
    pkill -RTMIN+3 waybar || true
    ;;    
  on)
    turn_on
    pkill -RTMIN+3 waybar || true
    ;;
  off)
    turn_off
    pkill -RTMIN+3 waybar || true
    ;;
  *)
    echo "{\"text\": \"Usage: $0 {status|on|off}\", \"class\": \"normal\"}"
    exit 1
    ;;
esac