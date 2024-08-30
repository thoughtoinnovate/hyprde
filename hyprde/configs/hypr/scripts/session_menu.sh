#!/bin/bash

choice=$(echo -e "Lock\nLogout\nSuspend\nHibernate\nReboot\nShutdown" | wofi --dmenu)

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
