#!/bin/bash
CURRENT_LAYOUT=$(hyprctl getoption general:layout -j | jq -r ".str")
if [ "$CURRENT_LAYOUT" == "dwindle" ]; then
    # Dwindle does not support most of these scroll commands.
    # We will map "promote" to swapping the window, or just suppress the error.
    case "$1" in
        promote) hyprctl dispatch swapwindow u ;;
        *) exit 0 ;; # Suppress error for others
    esac
else
    hyprctl dispatch "layoutmsg" "$*"
fi
