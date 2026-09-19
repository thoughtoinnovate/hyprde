#!/bin/bash

case $1 in
	--inc)
	brightnessctl set +5%
	;;
	--dec)
	# Floor at 10%: mashing decrease on a dark screen otherwise drives the
	# panel to true black with no visible feedback (reads as dead display).
	max=$(brightnessctl m 2>/dev/null); cur=$(brightnessctl get 2>/dev/null)
	floor=$(( ${max:-7500} * 10 / 100 ))
	if [ -n "$cur" ] && [ "$cur" -le $(( floor + ${max:-7500} * 5 / 100 )) ]; then
		brightnessctl set "$floor"
	else
		brightnessctl set 5%-
	fi
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
