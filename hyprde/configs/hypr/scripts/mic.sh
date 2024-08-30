#!/bin/bash

# Function to get TLP status and return JSON for Waybar
get_status() {
  local exists=$(pactl get-source-mute @DEFAULT_SOURCE@|grep -i yes|awk '{print $2}'|wc -l)
  if [ "$exists" -gt 0 ]; then
      echo "{\"text\": \"disabled\", \"tooltip\":\"disabled\",\"class\":\"disbld\",\"percentage\":0}"
  else
      echo "{\"text\": \"enabled\", \"tooltip\":\"enabled\",\"class\":\"enbld\",\"percentage\":100}"
  fi
}

toggle() {
  pactl set-source-mute @DEFAULT_SOURCE@ toggle
  response=$(get_status)
  status=$(echo $response|jq '.text')
  notify-send -t 700 "Mic: $status"
}

# Function to turn TLP on
turn_on() {
  pactl set-source-mute @DEFAULT_SOURCE@ off
  get_status
}

# Function to turn TLP off
turn_off() {
  pactl set-source-mute @DEFAULT_SOURCE@ on
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