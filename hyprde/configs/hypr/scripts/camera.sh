#!/bin/bash

# Function to get TLP status and return JSON for Waybar
get_status() {
  local exists=$(find /dev -name "video*"|wc -l)
  if [ "$exists" -gt 0 ]; then
      echo "{\"text\": \"enabled\", \"tooltip\":\"enabled\",\"class\":\"enbld\",\"percentage\":100}"
  else
      echo "{\"text\": \"disabled\", \"tooltip\":\"disabled\",\"class\":\"disbld\",\"percentage\":0}"
  fi
}

toggle() {
  local status=$(get_status|jq '.text')
  if [ $status = "\"enabled\"" ]; then
    turn_off
  else
    turn_on
  fi

  response=$(get_status)
  status=$(echo $response|jq '.text')
  notify-send -t 700 "Camera: $status"
}

# Function to turn TLP on
turn_on() {
  sudo modprobe uvcvideo
  get_status
}

# Function to turn TLP off
turn_off() {
  sudo modprobe -r uvcvideo
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