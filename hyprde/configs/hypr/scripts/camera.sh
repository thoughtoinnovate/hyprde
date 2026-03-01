#!/bin/bash

# Load Icons
source "$HOME/.config/hypr/scripts/hyprrocket.icons"

# Helper to save state for persistence
save_state() {
  local state=$1
  local STATE_FILE="$HOME/.config/hypr/toggles.state"
  mkdir -p "$(dirname "$STATE_FILE")"
  if [ -f "$STATE_FILE" ]; then
    grep -v "^camera=" "$STATE_FILE" > "$STATE_FILE.tmp"
    echo "camera=$state" >> "$STATE_FILE.tmp"
    mv "$STATE_FILE.tmp" "$STATE_FILE"
  else
    echo "camera=$state" > "$STATE_FILE"
  fi
}

# Function to get status and return JSON for Waybar
get_status() {
  # Check if uvcvideo module is loaded (standard for most webcams)
  if lsmod | grep -q uvcvideo; then
      # Camera is potentially active if driver is loaded
      echo "{\"text\": \"$CAM_ICON_ENABLED\", \"tooltip\":\"Camera Driver Active\",\"class\":\"enbld\",\"percentage\":100}"
  else
      # Module not loaded, camera is physically/driver disabled
      echo "{\"text\": \"$CAM_ICON_DISABLED\", \"tooltip\":\"Camera Driver Disabled\",\"class\":\"disbld\",\"percentage\":0}"
  fi
}

toggle() {
  # If driver is loaded (uvcvideo present), it is ON
  if lsmod | grep -q uvcvideo; then
    # Currently ON -> Turn OFF (Driver Removal)
    # 1. Try clean removal first
    if sudo /usr/bin/modprobe -r uvcvideo 2>/dev/null; then
        save_state "off"
    else
        # 2. Forceful removal if clean removal fails (e.g. module in use)
        notify-send -t 2000 "Camera" "Module in use, attempting forced disable..."
        if sudo /usr/bin/rmmod -f uvcvideo 2>/dev/null; then
            save_state "off"
        else
            notify-send -t 3000 "Camera Error" "Failed to disable camera even with force. Please close apps using the camera."
        fi
    fi
  else
    # Currently OFF -> Turn ON (Driver Load)
    notify-send -t 3000 "Security Alert" "Camera activation requested. Please authenticate to enable video recording."
    if pkexec /usr/sbin/modprobe uvcvideo; then
        save_state "on"
    fi
  fi

  response=$(get_status)
  status=$(echo $response|jq -r '.text')
  notify-send -t 700 "Camera: $status"
}

# Function to turn ON (Driver Load) - Secure
turn_on() {
  notify-send -t 3000 "Security Alert" "Camera activation requested. Please authenticate to enable video recording."
  if pkexec /usr/sbin/modprobe uvcvideo; then
      save_state "on"
  fi
  get_status
}

# Function to turn OFF (Driver Removal) - Frictionless
turn_off() {
  # Try clean removal then force
  sudo /usr/bin/modprobe -r uvcvideo 2>/dev/null || sudo /usr/bin/rmmod -f uvcvideo 2>/dev/null
  save_state "off"
  get_status
}

# Check the argument passed to the script
case "$1" in
  status)
    get_status
    ;;
  toggle)
    toggle
    ;;    
  on)
    turn_on
    ;;
  off)
    turn_off
    ;;
  *)
    echo "{\"text\": \"Usage: $0 {status|on|off}\", \"class\": \"normal\"}"
    exit 1
    ;;
esac
