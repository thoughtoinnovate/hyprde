#!/bin/bash

case $1 in
	--inc)
	brightnessctl set +5%
	;;
	--dec)
	brightnessctl set 5%-
esac

# Send notifications to mako
max_brightness=$(brightnessctl m)
current_brightness=$(brightnessctl get)

# Validate to prevent division by zero
if [ -z "$max_brightness" ] || [ "$max_brightness" -eq 0 ]; then
    echo "Warning: Could not determine max brightness" >&2
    brightness_percentage=0
else
    brightness_percentage=$(((current_brightness * 100) / max_brightness))
fi

notify-send --expire-time=200 "Brightness: $brightness_percentage%"
