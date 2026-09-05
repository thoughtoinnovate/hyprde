#!/bin/bash
# Toggle split that works in both dwindle and scroll layouts
# (Hyprland 0.55+ Lua dispatch syntax).
# NOTE: layouts are per-workspace since 0.54, so check the ACTIVE WORKSPACE,
# not the global default.
CURRENT_LAYOUT=$(hyprctl activeworkspace -j 2>/dev/null | jq -r ".tiledLayout // empty")
if [ -z "$CURRENT_LAYOUT" ]; then
    CURRENT_LAYOUT=$(hyprctl getoption general:layout -j | jq -r ".str")
fi
if [ "$CURRENT_LAYOUT" == "dwindle" ]; then
    hyprctl dispatch 'hl.dsp.layout("togglesplit")'
else
    hyprctl dispatch 'hl.dsp.layout("consume_or_expel prev")'
fi
