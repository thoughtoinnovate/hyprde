#!/bin/bash

# Persistence script for control center toggles
STATE_FILE="$HOME/.config/hypr/toggles.state"

get_state() {
    local key=$1
    local default=$2
    if [ -f "$STATE_FILE" ]; then
        local value=$(grep "^$key=" "$STATE_FILE" | cut -d'=' -f2)
        if [ -n "$value" ]; then
            echo "$value"
            return
        fi
    fi
    echo "$default"
}

# 1. Microphone
MIC_STATE=$(get_state "mic" "on")
if [ "$MIC_STATE" == "off" ]; then
    ~/.config/hypr/scripts/mic.sh off > /dev/null 2>&1
fi

# 2. Camera
CAM_STATE=$(get_state "camera" "on")
if [ "$CAM_STATE" == "off" ]; then
    ~/.config/hypr/scripts/camera.sh off > /dev/null 2>&1
fi

# 3. Gammastep (Night Light)
GAMMA_STATE=$(get_state "gamma" "off")
if [ "$GAMMA_STATE" == "on" ]; then
    ~/.config/hypr/scripts/gammastep/gamma.sh on > /dev/null 2>&1
fi
