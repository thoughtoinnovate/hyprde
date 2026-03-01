#!/bin/bash
# Usage: ./bluetooth_device_toggle.sh [MAC] [Action: connect|disconnect|toggle]

MAC=$1
ACTION=$2

if [ -z "$MAC" ]; then
    exit 1
fi

# Get current status if toggle is requested
if [ "$ACTION" == "toggle" ] || [ -z "$ACTION" ]; then
    IS_CONNECTED=$(bluetoothctl info "$MAC" | grep "Connected: yes")
    if [ -n "$IS_CONNECTED" ]; then
        ACTION="disconnect"
    else
        ACTION="connect"
    fi
fi

if [ "$ACTION" == "connect" ]; then
    notify-send "Bluetooth" "Connecting to device..."
    bluetoothctl connect "$MAC"
elif [ "$ACTION" == "disconnect" ]; then
    notify-send "Bluetooth" "Disconnecting device..."
    bluetoothctl disconnect "$MAC"
fi
