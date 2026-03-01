#!/bin/bash
default_temp=3400
if pgrep gammastep >/dev/null; then
    current_temp=$((default_temp + 200))
    if (( current_temp > 4200 )); then
        notify-send -t 700 "Temp can't exceed 4200K."
    else
        pkill gammastep
        gammastep -O "$current_temp" & 
        notify-send -t 700 "Temp $current_temp K"
    fi
else
    gammastep -O "$default_temp" & 
    notify-send -t 700 "RedGlow Started"
fi

