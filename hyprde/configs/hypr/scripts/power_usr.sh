#!/bin/bash

# Function to get TLP status reliably for Waybar
get_tlp_status() {
  # Use tlp-stat -s to get the current power profile
  # This is the most reliable way on TLP 1.7+
  local profile_info=$(tlp-stat -s | grep "Power profile")
  
  local class="normal"
  local text="High Performance"
  local alt="high"

  # Check if the profile contains BAT (Battery) or SAV (Power Saver)
  if [[ "$profile_info" == *"BAT"* ]] || [[ "$profile_info" == *"SAV"* ]]; then
    class="green"
    text="Power Saver"
    alt="saver"
  fi

  echo "{\"text\": \"$text\", \"class\": \"$class\", \"alt\": \"$alt\"}"
}

# Toggle TLP modes
toggle_tlp() {
  # Get current profile
  local profile_info=$(tlp-stat -s | grep "Power profile")
  
  if [[ "$profile_info" == *"BAT"* ]] || [[ "$profile_info" == *"SAV"* ]]; then
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