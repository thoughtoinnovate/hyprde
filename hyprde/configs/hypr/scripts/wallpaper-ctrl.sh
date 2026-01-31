#!/bin/bash

# Function to get dynamic wallpaper status and return JSON for Waybar
get_status() {
  if pgrep -f "dynamic-wallpapers.sh" > /dev/null; then
      echo "{\"text\": \"on\", \"tooltip\":\"Dynamic Wallpaper: Enabled\",\"class\":\"enbld\"}"
  else
      echo "{\"text\": \"off\", \"tooltip\":\"Dynamic Wallpaper: Disabled\",\"class\":\"disbld\"}"
  fi
}

toggle() {
  if pgrep -f "dynamic-wallpapers.sh" > /dev/null; then
      pkill -f "dynamic-wallpapers.sh"
      notify-send -t 1000 "Dynamic Wallpaper" "Disabled"
  else
      sh "$HOME/.config/hypr/scripts/dynamic-wallpapers.sh" &
      notify-send -t 1000 "Dynamic Wallpaper" "Enabled"
  fi
}

case "$1" in
  status)
    get_status
    ;;
  toggle)
    toggle
    ;;
  *)
    echo "Usage: $0 {status|toggle}"
    exit 1
    ;;
esac
