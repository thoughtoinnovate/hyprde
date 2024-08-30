#!/bin/bash

case $1 in
	--inc)
	wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+
	;;
	--dec)
	wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-
	;;
	--mute)
	wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle
esac

#send notifications to mako
if wpctl get-volume @DEFAULT_AUDIO_SINK@|grep -i -c "MUTED"; then
    audio_percentage="Muted!"
else
audio_percentage=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ | awk -F': ' '{print $2 * 100}')%
fi
notify-send -u critical --expire-time=200 "Volume: $audio_percentage"
