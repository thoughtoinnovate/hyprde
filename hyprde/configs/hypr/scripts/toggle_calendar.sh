#!/bin/bash

if pgrep zenity; then
    pkill zenity
else
    zenity --calendar --title='Calendar'
fi
