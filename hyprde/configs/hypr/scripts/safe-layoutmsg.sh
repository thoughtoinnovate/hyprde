#!/bin/bash
# Safe wrapper for scroll-layout messages (Hyprland 0.55+ Lua dispatch syntax).
# NOTE: layouts are per-workspace since 0.54, so check the ACTIVE WORKSPACE,
# not the global default.
CURRENT_LAYOUT=$(hyprctl activeworkspace -j 2>/dev/null | jq -r ".tiledLayout // empty")
if [ -z "$CURRENT_LAYOUT" ]; then
    CURRENT_LAYOUT=$(hyprctl getoption general:layout -j | jq -r ".str")
fi
if [ "$CURRENT_LAYOUT" == "dwindle" ]; then
    # Dwindle does not support most of these scroll commands.
    # We will map "promote" to swapping the window, or just suppress the error.
    case "$1" in
        promote) hyprctl dispatch 'hl.dispatch("swapwindow", "u")' ;;
        *) exit 0 ;; # Suppress error for others
    esac
else
    hyprctl dispatch "hl.dsp.layout(\"$*\")"
fi
