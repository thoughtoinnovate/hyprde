#!/bin/bash

# Function to close specific waybar instance
close_bar() {
    local config_pattern=$1
    local pid=$(pgrep -f "waybar -c .*/$config_pattern")
    if [ -n "$pid" ]; then
        kill $pid
        return 0 # Closed successfully
    fi
    return 1 # Was not open
}

if [ "$1" = "ctrl-cntr" ]; then
    # Close others
    close_bar "system-metrics/config"
    close_bar "waybar_bt_gen.json"
    
    # Toggle Control Center
    if ! close_bar "control-center/config"; then
        echo "Opening Control Center"
        waybar -c ~/.config/waybar/control-center/config -s ~/.config/waybar/control-center/style.css &
    fi

elif [ "$1" = "sys-metrics" ]; then
    # Close others
    close_bar "control-center/config"
    close_bar "waybar_bt_gen.json"
    
    # Toggle System Metrics
    if ! close_bar "system-metrics/config"; then
        echo "Opening System Metrics"
        waybar -c ~/.config/waybar/system-metrics/config -s ~/.config/waybar/system-metrics/style.css &
    fi

elif [ "$1" = "bluetooth" ]; then
    # Close others
    close_bar "control-center/config"
    close_bar "system-metrics/config"
    
    # Toggle Bluetooth Center
    if ! close_bar "waybar_bt_gen.json"; then
        echo "Opening Bluetooth Center"
        # Generate the dynamic config
        python3 ~/.config/hypr/scripts/bluetooth_widget_gen.py
        waybar -c /tmp/waybar_bt_gen.json -s ~/.config/waybar/bluetooth-center/style.css &
    fi
elif [ "$1" = "toggle-main" ]; then
    # Hard toggle for the main waybar to avoid overlay/mode issues
    if pgrep -x waybar > /dev/null; then
        pkill -x waybar
    else
        waybar &
    fi
    exit 0
elif [ "$1" = "close-all" ]; then
    close_bar "control-center/config"
    close_bar "waybar_bt_gen.json"
    pkill wofi || true
    pkill -f "python3.*spotlight.py" || true
    pkill -x "hyprsearch" || true
    pkill -f "any_finder.sh" || true
    # Close any floating terminal launchers by class
    hyprctl dispatch 'hl.dsp.closewindow("class:com.fzf.launcher")' > /dev/null 2>&1 || true
    hyprctl dispatch 'hl.dsp.closewindow("class:fzf-launcher")' > /dev/null 2>&1 || true
    exit 0
else
    echo "Invalid argument. Please provide 'ctrl-cntr', 'sys-metrics', 'bluetooth', or 'close-all'."
fi
