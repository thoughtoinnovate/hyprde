#!/bin/bash

# Load Icons
source "$HOME/.config/hypr/scripts/hyprrocket.icons"

# Function to get Bluetooth status and return JSON for Waybar
get_status() {
  # Check if bluetooth is powered on using more robust parsing
  # Powered: yes/no
  local powered=$(bluetoothctl show 2>/dev/null | grep -i "Powered:" | awk '{print $2}')
  
  if [ "$powered" = "yes" ]; then
      echo "{\"text\": \"$BT_ICON_ENABLED\", \"tooltip\":\"Bluetooth: Enabled\",\"class\":\"enbld\"}"
  else
      # Check if it's blocked by rfkill
      local blocked=$(rfkill list bluetooth | grep -i "Soft blocked:" | awk '{print $3}')
      if [ "$blocked" = "yes" ]; then
          echo "{\"text\": \"$BT_ICON_DISABLED\", \"tooltip\":\"Bluetooth: Soft Blocked\",\"class\":\"disbld\"}"
      else
          echo "{\"text\": \"$BT_ICON_DISABLED\", \"tooltip\":\"Bluetooth: Disabled\",\"class\":\"disbld\"}"
      fi
  fi
}

toggle() {
  local powered=$(bluetoothctl show 2>/dev/null | grep -i "Powered:" | awk '{print $2}')
  if [ "$powered" = "yes" ]; then
      turn_off
  else
      turn_on
  fi
}

# Function to turn Bluetooth on
turn_on() {
  rfkill unblock bluetooth
  bluetoothctl power on
  get_status
}

# Function to turn Bluetooth off
turn_off() {
  bluetoothctl power off
  get_status
}

# Check the argument passed to the script
case "$1" in
  status)
    get_status
    ;;   
  on)
    turn_on
    ;;
  off)
    turn_off
    ;;
  toggle)
    toggle
    ;;   
  *)
    echo "{\"text\": \"Usage: $0 {status|on|off|toggle}\", \"class\": \"normal\"}"
    exit 1
    ;;
esac