#!/bin/bash

# Function to get TLP status and return JSON for Waybar
get_tlp_status() {
  local status=$(tlp-stat -s | grep 'Mode' | awk '{print $3}')
  local class="normal"
  local text="Mode: High Performance"

  if [ "$status" == "battery" ]; then
    class="green"
    text="Mode: Power Saver"
  fi

  echo "{\"text\": \"$text\", \"class\": \"$class\"}"
}

# Function to turn TLP on
turn_tlp_on() {
  sudo tlp bat
  echo "{\"text\": \"TLP turned on\", \"class\": \"normal\"}"
}

# Function to turn TLP off
turn_tlp_off() {
  sudo tlp ac
  echo "{\"text\": \"TLP turned off\", \"class\": \"normal\"}"
}

# Check the argument passed to the script
case "$1" in
  status)
    get_tlp_status
    ;;
  on)
    turn_tlp_on
    ;;
  off)
    turn_tlp_off
    ;;
  *)
    echo "{\"text\": \"Usage: $0 {status|on|off}\", \"class\": \"normal\"}"
    exit 1
    ;;
esac