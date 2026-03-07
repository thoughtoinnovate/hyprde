#!/bin/bash

# Check if hyprsearch is already running
if pgrep -x "hyprsearch" > /dev/null; then
    pkill -x "hyprsearch"
    exit 0
fi

# Use hyprsearch in power-menu mode
# The binary is expected to be in ~/.config/hypr/scripts/hyprsearch
# or in the PATH
LAUNCHER="$HOME/.config/hypr/scripts/hyprsearch"
if [ ! -f "$LAUNCHER" ]; then
    LAUNCHER="hyprsearch"
fi

choice=$($LAUNCHER --power-menu)

case $choice in
    "Lock")
        hyprlock
        ;;
    "Logout")
    	pkill -f dynamic-wallpapers.sh
        hyprctl dispatch exit
        ;;
    "Suspend")
        systemctl suspend
        ;;
    "Hibernate")
        systemctl hibernate
        ;;          
    "Reboot")
        systemctl reboot
        ;;  
    "Shutdown")
        systemctl poweroff
        ;;
esac
