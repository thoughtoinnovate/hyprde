#!/bin/bash

if pgrep -x wofi; then
    pkill -x wofi
else
    choice=$(echo -e " Lock\n Logout\n Suspend\n Hibernate\n Reboot\n Shutdown" | wofi --dmenu --prompt "Session:")

    case $choice in
        " Lock")
            hyprlock
            ;; 
        " Logout")
            pkill -f dynamic-wallpapers.sh && hyprctl dispatch exit
            ;; 
        " Suspend")
            systemctl suspend
            ;; 
        " Hibernate")
            systemctl hibernate
            ;; 
        " Reboot")
            systemctl reboot
            ;; 
        " Shutdown")
            systemctl poweroff
            ;; 
    esac
fi