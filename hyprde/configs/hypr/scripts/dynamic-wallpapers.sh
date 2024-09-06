#!/bin/bash

script_dir=$(dirname "$0")
WALLPAPER_DIR=$1
INTERVAL=$2  # Change wallpaper every 5 minutes (300 seconds)

toggleNightLight(){
    
    isOn=$($HOME/.config/hypr/scripts/gammastep/gamma.sh status|jq '.text')
    
    if [ "$isOn" = "\"disabled\"" ]; then
        sh $HOME/.config/hypr/scripts/gammastep/gamma_toggle.sh
    fi

}

wallpaper_dir(){
   
timeOfDay=$($script_dir/time_of_day.sh)

case $timeOfDay in
    morning)
        echo "$WALLPAPER_DIR/sunrise"
        ;;
    afternoon)
       echo "$WALLPAPER_DIR/sunrise"
        ;;
    evening)
        echo "$WALLPAPER_DIR/sunset"
        ;;
    night)
        echo "$WALLPAPER_DIR/sunset"
        ;;
esac

}

while true; do
    #Unload all
    hyprctl hyprpaper unload all
    # Select a random wallpaper
    wall_dir=$(wallpaper_dir)
    wallpaper=$(find "$wall_dir" -type f | shuf -n 1)
    # Preload the new wallpaper
    hyprctl hyprpaper preload "$wallpaper"

    # Set the new wallpaper for all monitors
    for monitor in $(hyprctl monitors | grep "Monitor" | cut -d " " -f 2); do
        hyprctl hyprpaper wallpaper "$monitor,$wallpaper"
    done
    # Wait for the specified interval
    sleep "$INTERVAL"
done
