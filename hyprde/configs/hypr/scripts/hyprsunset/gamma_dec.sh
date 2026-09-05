#!/bin/bash
default_temp=3400
if pgrep hyprsunset >/dev/null; then
    current_temp=$((default_temp - 200))
    if (( current_temp < 1000 )); then
        notify-send -t 700 "Temp can't be below 1000K."
    else
        pkill hyprsunset
        hyprsunset -O "$current_temp" & 
        notify-send -t 700 "Temp $current_temp K"
    fi
else
    hyprsunset -O "$default_temp" & 
    notify-send -t 700 "RedGlow Started"
fi
default_temp=3400


