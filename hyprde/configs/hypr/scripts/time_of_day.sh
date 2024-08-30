#!/bin/bash

# Get the current hour
hour=$(date +%H)

# Determine the time of day
if [ "$hour" -ge 6 ] && [ "$hour" -lt 12 ]; then
    time_of_day="morning"
elif [ "$hour" -ge 13 ] && [ "$hour" -lt 18 ]; then
    time_of_day="afternoon"
elif [ "$hour" -ge 18 ] && [ "$hour" -lt 22 ]; then
    time_of_day="evening"
else
    time_of_day="night"
fi

# Output the time of day
echo "$time_of_day"