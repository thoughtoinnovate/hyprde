#!/bin/bash
# shortcuts-help.sh - Display Hyprland shortcuts in realtime

# Function to get variable value from config
get_var_value() {
    local var_name="$1"
    local config_file="$2"
    grep "^${var_name} = " "$config_file" | sed "s/${var_name} = //" | sed 's/ #.*$//' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//'
}

# Function to replace variables in shortcut string
replace_vars() {
    local shortcut="$1"
    local configfile="$2"

    # Replace main variables
    local mainmod_value=$(get_var_value '$mainMod' "$configfile")
    local terminal_value=$(get_var_value '$terminal' "$configfile")
    local filemanager_value=$(get_var_value '$fileManager' "$configfile")
    local launcher_value=$(get_var_value '$launcher' "$configfile")

    shortcut="${shortcut//\$mainMod/$mainmod_value}"
    shortcut="${shortcut//\$terminal/$terminal_value}"
    shortcut="${shortcut//\$fileManager/$filemanager_value}"
    shortcut="${shortcut//\$launcher/$launcher_value}"

    echo "$shortcut"
}

# Function to parse and format shortcuts from hyprland.conf
parse_shortcuts() {
    # Check for development config first (relative path)
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local dev_config="$script_dir/../hyprland.conf"
    local config_file="$HOME/.config/hypr/hyprland.conf"

    if [ -f "$dev_config" ]; then
        config_file="$dev_config"
    fi

    echo "=== HYPR SHORTCUTS HELP ==="
    echo ""

    # Window Management
    echo "WINDOW MANAGEMENT:"

    # Terminal
    terminal_bind=$(grep "^bind.*exec.*terminal" "$config_file")
    if [ -n "$terminal_bind" ]; then
        formatted=$(echo "$terminal_bind" | sed 's/.*bind.*= //' | sed 's/, exec,/, /' | sed 's/\$terminal/Terminal/')
        replace_vars "$formatted" "$config_file"
    fi

    # Kill window
    kill_bind=$(grep "^bind.*killactive" "$config_file")
    if [ -n "$kill_bind" ]; then
        formatted=$(echo "$kill_bind" | sed 's/.*bind.*= //' | sed 's/, killactive,/ Kill Window/')
        replace_vars "$formatted" "$config_file"
    fi

    while IFS= read -r line; do
        if [ -n "$line" ]; then
            formatted=$(echo "$line" | sed 's/.*bind.*= //' | sed 's/, fullscreen,1,/ Fullscreen/')
            replace_vars "$formatted" "$config_file"
        fi
    done < <(grep "^bind.*fullscreen" "$config_file")

    while IFS= read -r line; do
        if [ -n "$line" ]; then
            formatted=$(echo "$line" | sed 's/.*bind.*= //' | sed 's/, exec,/, /' | sed 's/\$fileManager/File Manager/')
            replace_vars "$formatted" "$config_file"
        fi
    done < <(grep "^bind.*exec.*fileManager" "$config_file")

    while IFS= read -r line; do
        if [ -n "$line" ]; then
            formatted=$(echo "$line" | sed 's/.*bind.*= //' | sed 's/, togglefloating,/ Toggle Floating/')
            replace_vars "$formatted" "$config_file"
        fi
    done < <(grep "^bind.*togglefloating" "$config_file")

    while IFS= read -r line; do
        if [ -n "$line" ]; then
            formatted=$(echo "$line" | sed 's/.*bind.*= //' | sed 's/, exec,/, /' | sed 's/hyprlock/Lock Screen/')
            replace_vars "$formatted" "$config_file"
        fi
    done < <(grep "^bind.*exec.*hyprlock" "$config_file")

    while IFS= read -r line; do
        if [ -n "$line" ]; then
            formatted=$(echo "$line" | sed 's/.*bind.*= //' | sed 's/, pseudo, # dwindle/ Toggle Pseudo Tiling/')
            replace_vars "$formatted" "$config_file"
        fi
    done < <(grep "^bind.*pseudo" "$config_file")

    while IFS= read -r line; do
        if [ -n "$line" ]; then
            formatted=$(echo "$line" | sed 's/.*bind.*= //' | sed 's/, togglesplit, # dwindle/ Toggle Split Layout/')
            replace_vars "$formatted" "$config_file"
        fi
    done < <(grep "^bind.*togglesplit" "$config_file")

    echo ""

    # Focus & Movement
    echo "FOCUS & MOVEMENT:"
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            formatted=$(echo "$line" | sed 's/.*bind.*= //' | sed 's/, movefocus, l/ Move Focus Left/' | sed 's/, movefocus, r/ Move Focus Right/' | sed 's/, movefocus, u/ Move Focus Up/' | sed 's/, movefocus, d/ Move Focus Down/')
            replace_vars "$formatted" "$config_file"
        fi
    done < <(grep "^bind.*movefocus" "$config_file")

    # Resize windows
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            formatted=$(echo "$line" | sed 's/.*bind.*= //' | sed 's/, resizeactive, 0 -10/ Resize Window Up/' | sed 's/, resizeactive, 0 10/ Resize Window Down/' | sed 's/, resizeactive, -10 0/ Resize Window Left/' | sed 's/, resizeactive, 10 0/ Resize Window Right/')
            replace_vars "$formatted" "$config_file"
        fi
    done < <(grep "^binde.*resizeactive" "$config_file")
    echo ""

    # Workspaces
    echo "WORKSPACES:"
    # Simple workspace switching (1-9, 0)
    for i in {1..9}; do
        echo "SUPER, $i Switch to Workspace $i"
    done
    echo "SUPER, 0 Switch to Workspace 10"

    # Move windows to workspaces
    for i in {1..9}; do
        echo "SUPER SHIFT, $i Move Window to Workspace $i"
    done
    echo "SUPER SHIFT, 0 Move Window to Workspace 10"

    # Special workspace
    echo "SUPER, S Toggle Special Workspace"
    echo "SUPER SHIFT, S Move Window to Special Workspace"

    # Workspace navigation
    echo "SUPER, TAB Next Workspace"
    echo "SUPER, mouse scroll Scroll Through Workspaces"
    echo ""

    # Media Controls
    echo "MEDIA CONTROLS:"
    # Brightness keys
    echo "Brightness Up Key: Brightness Up"
    echo "Brightness Down Key: Brightness Down"

    # Volume keys
    echo "Volume Up Key: Volume Up"
    echo "Volume Down Key: Volume Down"
    echo "Mute Key: Mute Audio"

    while IFS= read -r line; do
        if [ -n "$line" ]; then
            formatted=$(echo "$line" | sed 's/.*bind.*= //' | sed 's/, exec,.*mic.sh toggle/ Toggle Microphone/')
            replace_vars "$formatted" "$config_file"
        fi
    done < <(grep "mic.sh" "$config_file")

    while IFS= read -r line; do
        if [ -n "$line" ]; then
            formatted=$(echo "$line" | sed 's/.*bind.*= //' | sed 's/, exec,.*camera.sh toggle/ Toggle Camera/')
            replace_vars "$formatted" "$config_file"
        fi
    done < <(grep "camera.sh" "$config_file")
    echo ""

    # Applications
    echo "APPLICATIONS & TOOLS:"
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            formatted=$(echo "$line" | sed 's/.*bindr.*= //' | sed 's/, exec,.*wofi_launcher.sh/ Open Application Launcher/' | sed 's/,$//')
            replace_vars "$formatted" "$config_file"
        fi
    done < <(grep "wofi_launcher" "$config_file")

    while IFS= read -r line; do
        if [ -n "$line" ]; then
            formatted=$(echo "$line" | sed 's/.*bind.*= //' | sed 's/, exec,.*waybars.sh ctrl-cntr/ Control Center/')
            replace_vars "$formatted" "$config_file"
        fi
    done < <(grep "waybars.sh" "$config_file")

    echo "SUPER, Print Screenshot Area"
    echo "Print Screenshot"

    while IFS= read -r line; do
        if [ -n "$line" ]; then
            formatted=$(echo "$line" | sed 's/.*bind.*= //' | sed 's/, exec,.*shortcuts-help.sh/ Show Shortcuts Help/')
            replace_vars "$formatted" "$config_file"
        fi
    done < <(grep "shortcuts-help.sh" "$config_file")
    echo ""

    echo "Press ESC or click outside to close"
}

# Display shortcuts using wofi
if [ -t 0 ] || [ "$1" = "--text" ]; then
    # Running interactively or forced text mode, just show output
    parse_shortcuts
else
    # Running in GUI environment, use wofi
    parse_shortcuts | wofi --dmenu \
        --prompt "Hypr Shortcuts (ESC to close)" \
        --width 800 \
        --height 600 \
        --location center \
        --insensitive \
        --cache-file /dev/null
fi