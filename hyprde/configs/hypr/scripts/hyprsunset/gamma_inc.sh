#!/bin/bash
default_temp=3400
if pgrep hyprsunset >/dev/null; then
    current_temp=$((default_temp + 200))
    if (( current_temp > 4200 )); then
        notify-send -t 700 "Temp can't exceed 4200K."
    else
        pkill hyprsunset
        hyprsunset -O "$current_temp" & 
        notify-send -t 700 "Temp $current_temp K"
    fi
else
    hyprsunset -O "$default_temp" & 
    notify-send -t 700 "RedGlow Started"
fi

