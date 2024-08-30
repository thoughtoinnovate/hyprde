#!/bin/bash

# Function to get TLP status and return JSON for Waybar
get_status() {
  local exists=$(nmcli radio|awk '{print $2}'|grep -i 'enabled' |wc -l)
  if [ "$exists" -gt 0 ]; then
      echo "{\"text\": \"enabled\", \"tooltip\":\"enabled\",\"class\":\"enbld\"}"

  else
      echo "{\"text\": \"disabled\", \"tooltip\":\"disabled\",\"class\":\"disbld\"}"
  fi
}

toggle() {
  local exists=$(nmcli radio|awk '{print $2}'|grep -i 'enabled' |wc -l)
  if [ "$exists" -gt 0 ]; then
      turn_off
      get_status
  else
    turn_on
    get_status
  fi
}

# Function to turn TLP on
turn_on() {
  nmcli radio wifi on
  echo "{\"text\": \"enabled\", \"class\": \"enbld\"}"
}

# Function to turn TLP off
turn_off() {
  nmcli radio wifi off
  echo "{\"text\": \"disabled\", \"class\": \"disbld\"}"
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