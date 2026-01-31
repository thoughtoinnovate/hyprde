#!/bin/bash

CURRENT_LAYOUT=$(hyprctl getoption general:layout -j | jq -r '.str')

if [ "$CURRENT_LAYOUT" == "dwindle" ]; then
    hyprctl keyword general:layout scrolling
    notify-send -t 1000 "Layout Switched" "Scrolling (PaperWM style)"
else
    hyprctl keyword general:layout dwindle
    notify-send -t 1000 "Layout Switched" "Dwindle (Standard)"
fi
