#!/bin/bash

# Load Icons
source "$HOME/.config/hypr/scripts/hyprrocket.icons"

# Get current user for pulseaudio session
REAL_USER=$(whoami)

# Helper to save state for persistence
save_state() {
  local state=$1
  local STATE_FILE="$HOME/.config/hypr/toggles.state"
  mkdir -p "$(dirname "$STATE_FILE")"
  if [ -f "$STATE_FILE" ]; then
    grep -v "^mic=" "$STATE_FILE" > "$STATE_FILE.tmp"
    echo "mic=$state" >> "$STATE_FILE.tmp"
    mv "$STATE_FILE.tmp" "$STATE_FILE"
  else
    echo "mic=$state" > "$STATE_FILE"
  fi
}

# Function to get status and return JSON for Waybar
get_status() {
  local target=$1
  local mute_status=$(pactl get-source-mute @DEFAULT_SOURCE@ 2>/dev/null | grep -i "Mute: yes")
  
  if [ -n "$mute_status" ]; then
      # Muted = Disabled (Safe)
      echo "{\"text\": \"$MIC_ICON_DISABLED\", \"tooltip\":\"Microphone Muted (Safe)\",\"class\":\"disbld\",\"percentage\":0}"
  else
      # Unmuted = Enabled (Active)
      local icon="$MIC_ICON_ENABLED"
      if [ "$target" == "cc" ]; then
          icon="$MIC_ICON_CC_ENABLED"
      fi
      echo "{\"text\": \"$icon\", \"tooltip\":\"Microphone Active (Recording Possible)\",\"class\":\"enbld\",\"percentage\":100}"
  fi
}

toggle() {
  local target=$1
  local mute_status=$(pactl get-source-mute @DEFAULT_SOURCE@ 2>/dev/null | grep -i "Mute: yes")
  
  if [ -z "$mute_status" ]; then
      # Currently ON -> Turn OFF (No password needed for privacy)
      # Frictionless Mute: Try sudo for NOPASSWD or normal pactl
      sudo /usr/bin/pactl set-source-mute @DEFAULT_SOURCE@ on 2>/dev/null || pactl set-source-mute @DEFAULT_SOURCE@ on
      save_state "off"
  else
      # Currently OFF -> Turn ON (Password required for security)
      notify-send -t 3000 "Security Alert" "Microphone activation requested. Please authenticate to enable audio recording."
      # Secure ON: Require PolicyKit authentication
      # Use unique binary path to avoid conflict with screen recording
      if pkexec /usr/local/bin/hyprde-mic-auth; then
          pactl set-source-mute @DEFAULT_SOURCE@ off
          save_state "on"
      fi
  fi
  
  response=$(get_status "$target")
  status=$(echo $response|jq -r '.text')
  notify-send -t 700 "Mic: $status"
}

# Function to turn ON (Unmute) - Secure
turn_on() {
  local target=$1
  notify-send -t 3000 "Security Alert" "Microphone activation requested. Please authenticate to enable audio recording."
  if pkexec /usr/local/bin/hyprde-mic-auth; then
      pactl set-source-mute @DEFAULT_SOURCE@ off
      save_state "on"
  fi
  get_status "$target"
}

# Function to turn OFF (Mute) - Frictionless
turn_off() {
  local target=$1
  sudo /usr/bin/pactl set-source-mute @DEFAULT_SOURCE@ on 2>/dev/null || pactl set-source-mute @DEFAULT_SOURCE@ on
  save_state "off"
  get_status "$target"
}

# Check the argument passed to the script
case "$1" in
  status)
    get_status "$2"
    ;;
  toggle)
    toggle "$2"
    ;;    
  on)
    turn_on "$2"
    ;;
  off)
    turn_off "$2"
    ;;
  *)
    echo "{\"text\": \"Usage: $0 {status|on|off}\", \"class\": \"normal\"}"
    exit 1
    ;;
esac
