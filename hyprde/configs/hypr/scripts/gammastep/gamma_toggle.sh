#!/bin/bash
if pgrep gammastep >/dev/null; then
    pkill gammastep
    echo "{\"text\": \"disabled\", \"tooltip\":\"disabled\",\"class\":\"disbld\"}"
    notify-send -t 700 "RedGlow Stopped"
else
    gammastep -O 3400 & 
    echo "{\"text\": \"enabled\", \"tooltip\":\"enabled\",\"class\":\"enbld\"}"
    notify-send -t 700 "RedGlow ON"
fi

