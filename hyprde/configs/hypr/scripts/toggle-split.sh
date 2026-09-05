#!/bin/bash
CURRENT_LAYOUT=$(hyprctl getoption general:layout -j | jq -r ".str")
if [ "$CURRENT_LAYOUT" == "dwindle" ]; then
    hyprctl dispatch "togglesplit"
else
    hyprctl dispatch "layoutmsg" "consume_or_expel prev"
fi
