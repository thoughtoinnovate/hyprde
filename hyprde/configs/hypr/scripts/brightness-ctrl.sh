#!/bin/bash

case $1 in
	--inc)
	brightnessctl set +5%
	;;
	--dec)
	brightnessctl set 5%-
esac

#send notifications to mako
max_brightness=$(brightnessctl m)
#echo "max: $max_brightness"
current_brightness=$(brightnessctl get)
#echo "curr: $current_brightness"
brightness_percentage=$(((current_brightness * 100 )/ max_brightness))
#echo "percentage: $brightness_percentage"
notify-send --expire-time=200 "Brightness: $brightness_percentage%"
