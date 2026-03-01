#!/bin/bash

read -p "Enter date (YYYY-MM-DD): " date
read -p "Enter time (HH:MM AM/PM): " time
read -p "Enter reminder text: " text

gcalcli add --title="$text" --when="$date $time" --duration=1h
