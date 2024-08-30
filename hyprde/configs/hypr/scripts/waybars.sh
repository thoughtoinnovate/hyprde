#!/bin/bash

if [ "$1" = "ctrl-cntr" ]; then
    exists=$(ps aux|grep /control-center|awk '{print $2}'|wc -l)
    echo "Exists: $exists"
    if [ "$exists" -gt 1 ]; then
        echo "Control Center already open."
        ps aux|grep /control-center|awk '{print $2}'|xargs kill -9
    else
        waybar -c $HOME/.config/waybar/control-center/config -s $HOME/.config/waybar/control-center/style.css
    fi
else
    # Add any other actions you want to perform when $1 is not "ctrl-cntr"
    echo "Invalid argument. Please provide 'ctrl-cntr' as an argument."
fi