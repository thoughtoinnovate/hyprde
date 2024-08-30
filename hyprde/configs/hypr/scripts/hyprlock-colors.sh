#!/bin/bash

hex2dec() {
  hex=$1
  printf "%d %d %d" 0x${hex:0:2} 0x${hex:2:2} 0x${hex:4:2}
}


# Set the wallpaper
wal -i /path/to/your/wallpaper.jpg

# Get the color for the label from the Pywal palette
FG_COLOR=$(grep -w "foreground" ~/.cache/wal/colors.sh | cut -d' ' -f2)
BG_COLOR=$(grep -w "background" ~/.cache/wal/colors.sh | cut -d' ' -f2)
OUTER_COLOR=$(grep -w "color1" ~/.cache/wal/colors.sh | cut -d' ' -f2)

# Example usage
fg_hx_color=`echo $FG_COLOR|awk -F'#' '{print $2}'|sed  "s/'//g"`
bg_hx_color=`echo $BG_COLOR|awk -F'#' '{print $2}'|sed  "s/'//g"`

# Extract individual hex values
fg_colors=$(hex2dec $fg_hx_color)
fg_colors=($fg_colors)

bg_colors=$(hex2dec $bg_hx_color)
bg_colors=($bg_colors)

# Update hyprlock configuration
CONFIG_FILE=~/.config/hypr/hyprlock.conf


# Replace the font color in the configuration file
sed -i "s/fgColor/rgba(${fg_colors[0]},${fg_colors[1]},${fg_colors[2]}, 1.0)/" $CONFIG_FILE

sed -i "s/bgColor/rgba(${bg_colors[0]},${bg_colors[1]},${bg_colors[2]}, 1.0)/" $CONFIG_FILE

# Restart hyprlock to apply changes
killall -e hyprlock
hyprlock &
