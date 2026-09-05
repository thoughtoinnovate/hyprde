#!/bin/bash

# Toggle: only an existing power-menu instance closes here.
# (Never match the dock or other hyprsearch instances by bare process name.)
if pgrep -f "hyprsearch --power-menu" > /dev/null; then
    pkill -f "hyprsearch --power-menu"
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
        hyprctl dispatch 'hl.dsp.exit()'
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
    "Power Balanced")
        "$HOME/.config/hypr/scripts/power-mode.sh" balanced
        ;;
    "Power High")
        "$HOME/.config/hypr/scripts/power-mode.sh" high
        ;;
    "Power Auto")
        "$HOME/.config/hypr/scripts/power-mode.sh" auto
        ;;
    "Power Saver")
        "$HOME/.config/hypr/scripts/power-mode.sh" saver
        ;;
esac
