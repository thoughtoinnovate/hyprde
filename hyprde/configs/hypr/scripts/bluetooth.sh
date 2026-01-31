#!/bin/bash

# Function to get Bluetooth status and return JSON for Waybar
get_status() {
  # Check if bluetooth is powered on using more robust parsing
  local powered=$(bluetoothctl show 2>/dev/null | grep -i "powered:" | grep -ic "yes" || echo "0")
  if [ "$powered" -gt 0 ]; then
      echo "{\"text\": \"enabled\", \"tooltip\":\"enabled\",\"class\":\"enbld\"}"
  else
      echo "{\"text\": \"disabled\", \"tooltip\":\"disabled\",\"class\":\"disbld\"}"
  fi
}

toggle() {
  # Check current power status
  local powered=$(bluetoothctl show 2>/dev/null | grep -i "powered:" | grep -ic "yes" || echo "0")
  if [ "$powered" -gt 0 ]; then
      turn_off
      get_status
  else
      turn_on
      get_status
  fi
}

# Function to turn TLP on
turn_on() {
  bluetoothctl power on
  echo "{\"text\": \"enabled\", \"class\": \"enbld\"}"
}

# Function to turn TLP off
turn_off() {
  bluetoothctl power off
  echo "{\"text\": \"disabled\", \"class\": \"disbld\"}"
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
    echo "{\"text\": \"Usage: $0 {status|on|off}\", \"class\": \"normal\"}"
    exit 1
    ;;
esac