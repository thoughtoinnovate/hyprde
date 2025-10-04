#!/bin/bash
# shortcuts-help.sh - Display Hyprland shortcuts with hash-based caching

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

# Function to format keys with spaces
format_keys() {
    local keys="$1"
    # Trim leading/trailing spaces
    keys=$(echo "$keys" | sed 's/^ *//' | sed 's/ *$//')
    # Trim leading ", "
    keys=$(echo "$keys" | sed 's/^, //')
    # Replace , with +
    keys=$(echo "$keys" | sed 's/,/ + /g')
    # Normalize spaces
    echo "$keys" | sed 's/ \+/ /g'
}

# Function to get description for a bind action
get_bind_description() {
    local action="$1"
    local config_file="$2"
    action="${action//\$HOME/$HOME}"
    action=$(replace_vars "$action" "$config_file")
    local terminal_value=$(get_var_value '$terminal' "$config_file")
    local filemanager_value=$(get_var_value '$fileManager' "$config_file")
    if [[ $action =~ killactive ]]; then echo "󰅖 Kill Window"
    elif [[ $action == "fullscreen, 1" ]]; then echo "󰊓 Toggle Fullscreen"
    elif [[ $action =~ "exec, $terminal_value" ]]; then echo " Open Terminal"
    elif [[ $action =~ "exec, $filemanager_value" ]]; then echo "󰉋 Open File Manager"
    elif [[ $action =~ togglefloating ]]; then echo "󰉣 Toggle Floating"
    elif [[ $action =~ "exec, hyprlock" ]]; then echo "󰌾 Lock Screen"
    elif [[ $action =~ pseudo ]]; then echo "󰘔 Toggle Pseudo Tiling"
    elif [[ $action =~ togglesplit ]]; then echo "󰘕 Toggle Split Layout"
    elif [[ $action =~ "movefocus, l" ]]; then echo "󰁍 Move Focus Left"
    elif [[ $action =~ "movefocus, r" ]]; then echo "󰁎 Move Focus Right"
    elif [[ $action =~ "movefocus, u" ]]; then echo "󰁟 Move Focus Up"
    elif [[ $action =~ "movefocus, d" ]]; then echo "󰁆 Move Focus Down"
    elif [[ $action =~ "resizeactive, 0 -10" ]]; then echo "󰁝 Resize Window Up"
    elif [[ $action =~ "resizeactive, 0 10" ]]; then echo "󰁅 Resize Window Down"
    elif [[ $action =~ "resizeactive, -10 0" ]]; then echo "󰁜 Resize Window Left"
    elif [[ $action =~ "resizeactive, 10 0" ]]; then echo "󰁞 Resize Window Right"
    elif [[ $action == "workspace, 1" ]]; then echo "󰪱 Switch to Workspace 1"
    elif [[ $action == "workspace, 2" ]]; then echo "󰪱 Switch to Workspace 2"
    elif [[ $action == "workspace, 3" ]]; then echo "󰪱 Switch to Workspace 3"
    elif [[ $action == "workspace, 4" ]]; then echo "󰪱 Switch to Workspace 4"
    elif [[ $action == "workspace, 5" ]]; then echo "󰪱 Switch to Workspace 5"
    elif [[ $action == "workspace, 6" ]]; then echo "󰪱 Switch to Workspace 6"
    elif [[ $action == "workspace, 7" ]]; then echo "󰪱 Switch to Workspace 7"
    elif [[ $action == "workspace, 8" ]]; then echo "󰪱 Switch to Workspace 8"
    elif [[ $action == "workspace, 9" ]]; then echo "󰪱 Switch to Workspace 9"
    elif [[ $action == "workspace, 10" ]]; then echo "󰪱 Switch to Workspace 10"
    elif [[ $action == "movetoworkspace, 1" ]]; then echo "󰪱 Move Window to Workspace 1"
    elif [[ $action == "movetoworkspace, 2" ]]; then echo "󰪱 Move Window to Workspace 2"
    elif [[ $action == "movetoworkspace, 3" ]]; then echo "󰪱 Move Window to Workspace 3"
    elif [[ $action == "movetoworkspace, 4" ]]; then echo "󰪱 Move Window to Workspace 4"
    elif [[ $action == "movetoworkspace, 5" ]]; then echo "󰪱 Move Window to Workspace 5"
    elif [[ $action == "movetoworkspace, 6" ]]; then echo "󰪱 Move Window to Workspace 6"
    elif [[ $action == "movetoworkspace, 7" ]]; then echo "󰪱 Move Window to Workspace 7"
    elif [[ $action == "movetoworkspace, 8" ]]; then echo "󰪱 Move Window to Workspace 8"
    elif [[ $action == "movetoworkspace, 9" ]]; then echo "󰪱 Move Window to Workspace 9"
    elif [[ $action == "movetoworkspace, 10" ]]; then echo "󰪱 Move Window to Workspace 10"
    elif [[ $action =~ "togglespecialworkspace, magic" ]]; then echo "󰪱 Toggle Special Workspace"
    elif [[ $action =~ "movetoworkspace, special:magic" ]]; then echo "󰪱 Move Window to Special Workspace"
    elif [[ $action =~ "workspace, e+1" ]]; then echo "󰪱 Next Workspace"
    elif [[ $action =~ "workspace, e-1" ]]; then echo "󰪱 Previous Workspace"
    elif [[ $action =~ "brightness-ctrl.sh --inc" ]]; then echo "󰃠 Brightness Up"
    elif [[ $action =~ "brightness-ctrl.sh --dec" ]]; then echo "󰃟 Brightness Down"
    elif [[ $action =~ "audio-ctrl.sh --inc" ]]; then echo "󰕾 Volume Up"
    elif [[ $action =~ "audio-ctrl.sh --dec" ]]; then echo "󰕿 Volume Down"
    elif [[ $action =~ "audio-ctrl.sh --mute" ]]; then echo "󰝟 Mute Audio"
    elif [[ $action =~ "mic.sh toggle" ]]; then echo "󰍬 Toggle Microphone"
    elif [[ $action =~ "camera.sh toggle" ]]; then echo "󰄀 Toggle Camera"
    elif [[ $action =~ wofi ]]; then echo "󰀻 Open Application Launcher"
    elif [[ $action =~ "waybars.sh ctrl-cntr" ]]; then echo "󰀻 Open Control Center"
    elif [[ $action =~ "screenshot.sh area" ]]; then echo "󰄀 Screenshot Area"
    elif [[ $action =~ screenshot.sh ]]; then echo "󰄀 Screenshot"
    elif [[ $action =~ shortcuts-help.sh ]]; then echo "󰋙 Show Shortcuts Help"
    elif [[ $action =~ file_search.sh ]]; then echo "󰈞 File Search"
    else echo "󰀻 Custom Action"
    fi
}

# Function to parse and format shortcuts from hyprland.conf
parse_shortcuts() {

    # Initialize section variables
    local window_management=""
    local focus_movement=""
    local workspaces=""
    local media_controls=""
    local apps_tools=""

    # Parse all binds
    while IFS= read -r line; do
        keys=$(echo "$line" | awk -F'=' '{print $2}' | awk -F', ' '{print $1 "," $2}' | sed 's/^,//' | sed 's/^ *//')
        action=$(echo "$line" | awk -F', ' '{for(i=3;i<=NF;i++) printf "%s, ", $i; print ""}' | sed 's/, $//')
        action=$(replace_vars "$action" "$config_file")
        desc=$(get_bind_description "$action" "$config_file")
        formatted_keys=$(format_keys "$(replace_vars "$keys" "$config_file")")
        entry="  $formatted_keys : $desc"

        if [[ $action =~ (killactive|fullscreen|exec.*terminal|exec.*fileManager|togglefloating|exec.*hyprlock|pseudo|togglesplit) ]]; then
            window_management+="$entry\n"
        elif [[ $action =~ (movefocus|resizeactive) ]]; then
            focus_movement+="$entry\n"
        elif [[ $action =~ (workspace|movetoworkspace|togglespecialworkspace) ]]; then
            workspaces+="$entry\n"
        elif [[ $action =~ (XF86|brightness|audio|mic|camera) ]]; then
            media_controls+="$entry\n"
        elif [[ $action =~ (wofi|waybars|screenshot|shortcuts-help|file_search) ]]; then
            apps_tools+="$entry\n"
        else
            apps_tools+="$entry\n"
        fi
    done < <(grep "^bind[el]* *=" "$config_file")

    # Output header
    echo "󰋙 HYPR SHORTCUTS HELP"
    echo "──────────────────────"
    echo ""

    # Window Management
    if [ -n "$window_management" ]; then
        echo "󰖯 WINDOW MANAGEMENT"
        echo "───────────────────"
        echo -e "$window_management"
        echo ""
    fi

    # Focus & Movement
    if [ -n "$focus_movement" ]; then
        echo "󰌌 FOCUS & MOVEMENT"
        echo "──────────────────"
        echo -e "$focus_movement"
        echo ""
    fi

    # Workspaces
    if [ -n "$workspaces" ]; then
        echo "󰪱 WORKSPACES"
        echo "─────────────"
        echo -e "$workspaces"
        echo ""
    fi

    # Media Controls
    if [ -n "$media_controls" ]; then
        echo "󰕾 MEDIA CONTROLS"
        echo "─────────────────"
        echo -e "$media_controls"
        echo ""
    fi

    # Applications & Tools
    if [ -n "$apps_tools" ]; then
        echo "󰀻 APPLICATIONS & TOOLS"
        echo "───────────────────────"
        echo -e "$apps_tools"
        echo ""
    fi

    # Focus & Movement
    if [ -n "$focus_movement" ]; then
        echo "󰌌 FOCUS & MOVEMENT"
        echo "──────────────────"
        echo -e "$focus_movement" | while IFS= read -r line; do
            if [ -n "$line" ]; then
                key=$(echo "$line" | cut -d':' -f1)
                desc=$(echo "$line" | cut -d':' -f2-)
                printf "  %-25s : %s\n" "$key" "$desc"
            fi
        done
        echo ""
    fi

    # Workspaces
    if [ -n "$workspaces" ]; then
        echo "󰪱 WORKSPACES"
        echo "─────────────"
        echo -e "$workspaces" | while IFS= read -r line; do
            if [ -n "$line" ]; then
                key=$(echo "$line" | cut -d':' -f1)
                desc=$(echo "$line" | cut -d':' -f2-)
                printf "  %-25s : %s\n" "$key" "$desc"
            fi
        done
        echo ""
    fi

    # Media Controls
    if [ -n "$media_controls" ]; then
        echo "󰕾 MEDIA CONTROLS"
        echo "─────────────────"
        echo -e "$media_controls" | while IFS= read -r line; do
            if [ -n "$line" ]; then
                key=$(echo "$line" | cut -d':' -f1)
                desc=$(echo "$line" | cut -d':' -f2-)
                printf "  %-25s : %s\n" "$key" "$desc"
            fi
        done
        echo ""
    fi

    # Applications & Tools
    if [ -n "$apps_tools" ]; then
        echo "󰀻 APPLICATIONS & TOOLS"
        echo "───────────────────────"
        echo -e "$apps_tools" | while IFS= read -r line; do
            if [ -n "$line" ]; then
                key=$(echo "$line" | cut -d':' -f1)
                desc=$(echo "$line" | cut -d':' -f2-)
                printf "  %-25s : %s\n" "$key" "$desc"
            fi
        done
        echo ""
    fi

    echo "󰌍 Press ESC to close"
}

# Hash-based caching setup
hash_file="$HOME/.config/hypr/shortcuts-hash.txt"
help_file="$HOME/.config/hypr/shortcuts-help.txt"
mkdir -p "$(dirname "$hash_file")"

# Determine config file (moved from parse_shortcuts)
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dev_config="$script_dir/../hyprland.conf"
config_file="$HOME/.config/hypr/hyprland.conf"
if [ -f "$dev_config" ]; then
    config_file="$dev_config"
fi

# Compute current hash
if command -v sha256sum >/dev/null 2>&1; then
    config_hash=$(sha256sum "$config_file" 2>/dev/null | awk '{print $1}')
else
    # Fallback to no caching if sha256sum not available
    config_hash=""
fi

# Check cache
stored_hash=""
if [ -f "$hash_file" ] && [ -n "$config_hash" ]; then
    read -r stored_hash < "$hash_file"
fi

full_output=""
if [ "$stored_hash" != "$config_hash" ] || [ ! -f "$help_file" ] || [ -z "$config_hash" ]; then
    # Recompute
    full_output=$(parse_shortcuts)
    if [ -n "$config_hash" ]; then
        echo "$config_hash" > "$hash_file"
        echo "$full_output" > "$help_file"
    fi
else
    # Load from cache
    full_output=$(cat "$help_file")
fi

# Display
if [ -t 0 ] || [ "$1" = "--text" ]; then
    echo "$full_output"
else
    echo "$full_output" | wofi --dmenu \
        --prompt "Hypr Shortcuts (ESC to close)" \
        --width 800 \
        --height 600 \
        --location center \
        --insensitive \
        --cache-file /dev/null
fi

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