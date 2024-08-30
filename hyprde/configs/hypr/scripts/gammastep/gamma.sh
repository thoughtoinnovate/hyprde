#!/bin/bash

# Function to get TLP status and return JSON for Waybar
get_gamma_status() {
  local exists=$(pgrep gammastep|wc -l)
  if [ "$exists" -gt 0 ]; then
      echo "{\"text\": \"enabled\", \"tooltip\":\"enabled\",\"class\":\"enbld\"}"

  else
      echo "{\"text\": \"disabled\", \"tooltip\":\"disabled\",\"class\":\"disbld\"}"
  fi
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
    get_gamma_status
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