#!/bin/bash
# shortcuts-help.sh - Display Hyprocket shortcuts with hash-based caching

# Prevent multiple instances using flock for atomic locking
lock_file="/tmp/hyprocket-shortcuts.lock"
exec 200>"$lock_file"
if ! flock -n 200; then
    exit 0
fi
trap "rm -f '$lock_file'" EXIT

# Function to get variable value from config (Lua locals first, legacy $vars after)
get_var_value() {
    local var_name="$1"
    local config_file="$2"
    local lua_name="${var_name#\$}"
    local val=""
    val=$(grep -m1 "^local $lua_name = " "$config_file" 2>/dev/null | cut -d'"' -f2)
    if [ -z "$val" ]; then
        val=$(grep "^${var_name} = " "$config_file" 2>/dev/null | sed "s/${var_name} = //" | sed 's/ #.*$//' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
    fi
    printf '%s' "$val"
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

# Function to format keys with spaces (handles Lua "SUPER + T" and legacy "SUPER, T")
format_keys() {
    local keys="$1"
    if [[ "$keys" == *"+"* ]]; then
        echo "$keys" | sed 's/ *+ */ + /g' | sed 's/^ *//' | sed 's/ *$//'
        return
    fi
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
    if [[ $action =~ killactive ]] || [[ $action =~ window.close ]]; then echo "󰅖 Kill Window"
    elif [[ $action == "fullscreen, 1" ]] || [[ $action =~ window.fullscreen ]]; then echo "󰊓 Toggle Fullscreen"
    elif [[ $action =~ "exec, $terminal_value" ]] || [[ $action =~ "exec_cmd($terminal_value" ]]; then echo " Open Terminal"
    elif [[ $action =~ "exec, $filemanager_value" ]] || [[ $action =~ "exec_cmd($filemanager_value" ]]; then echo "󰉋 Open File Manager"
    elif [[ $action =~ togglefloating ]] || [[ $action =~ window.float ]]; then echo "󰉣 Toggle Floating"
    elif [[ $action =~ "exec, hyprlock" ]] || [[ $action =~ "exec_cmd(hyprlock" ]]; then echo "󰌾 Lock Screen"
    elif [[ $action =~ pseudo ]]; then echo "󰘔 Toggle Pseudo Tiling"
    elif [[ $action =~ togglesplit ]]; then echo "󰘕 Toggle Split Layout"
    elif [[ $action =~ movefocus ]] || [[ $action =~ 'focus({ direction' ]]; then
        # Lua form carries direction = "l|r|u|d"
        if [[ $action =~ '"l"' ]] || [[ $action =~ "movefocus, l" ]]; then echo "󰁍 Move Focus Left"
        elif [[ $action =~ '"r"' ]] || [[ $action =~ "movefocus, r" ]]; then echo "󰁎 Move Focus Right"
        elif [[ $action =~ '"u"' ]] || [[ $action =~ "movefocus, u" ]]; then echo "󰁟 Move Focus Up"
        elif [[ $action =~ '"d"' ]] || [[ $action =~ "movefocus, d" ]]; then echo "󰁆 Move Focus Down"
        else echo "󰌌 Move Focus"
        fi
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
    elif [[ $action =~ "screen-record.sh toggle" ]]; then echo "󰻃 Screen Recording Menu"
    elif [[ $action =~ "layoutmsg, move -col" ]]; then echo "󰁍 Scroll Left"
    elif [[ $action =~ "layoutmsg, move +col" ]]; then echo "󰁎 Scroll Right"
    elif [[ $action =~ "layoutmsg, movewindowto l" ]]; then echo "󰁍 Move Window Left"
    elif [[ $action =~ "layoutmsg, movewindowto r" ]]; then echo "󰁎 Move Window Right"
    elif [[ $action =~ "layoutmsg, swapcol l" ]]; then echo "󰁍 Swap Column Left"
    elif [[ $action =~ "layoutmsg, swapcol r" ]]; then echo "󰁎 Swap Column Right"
    elif [[ $action =~ "layoutmsg, colresize +conf" ]]; then echo "󰘔 Cycle Column Width"
    elif [[ $action =~ "layoutmsg, togglefit" ]]; then echo "󰊓 Toggle Fit/Center"
    elif [[ $action =~ "layoutmsg, promote" ]]; then echo "󰘕 Promote to New Column"
    elif [[ $action =~ "layoutmsg, swaptomaster" ]]; then echo "󰘕 Swap to Master"
    elif [[ $action =~ "layoutmsg, addmaster" ]]; then echo "󰘕 Add Master"
    elif [[ $action =~ "layoutmsg, removemaster" ]]; then echo "󰘕 Remove Master"
    elif [[ $action =~ "safe-layoutmsg.sh promote" ]]; then echo "󰘕 Promote to New Column"
    elif [[ $action =~ "safe-layoutmsg.sh consume_or_expel" ]]; then echo "󰘕 Consume or Expel Column"
    elif [[ $action =~ "safe-layoutmsg.sh consume" ]]; then echo "󰘕 Consume Into Column"
    elif [[ $action =~ "safe-layoutmsg.sh expel" ]]; then echo "󰘕 Expel to Own Column"
    elif [[ $action =~ "safe-layoutmsg.sh colresize" ]]; then echo "󰘔 Cycle Column Width"
    elif [[ $action =~ "safe-layoutmsg.sh togglefit" ]]; then echo "󰊓 Fit Column Into View"
    elif [[ $action =~ "safe-layoutmsg.sh swapcol" ]]; then echo "󰁍 Swap Column"
    elif [[ $action =~ "toggle-split.sh" ]]; then echo "󰘕 Toggle Split"
    elif [[ $action =~ "layout-ctrl.sh" ]]; then echo "󰘕 Toggle Layout (scroll/dwindle)"
    elif [[ $action =~ "power-mode.sh" ]]; then echo "󰚥 Power Mode Cycle"
    elif [[ $action =~ "gpu-run.sh" ]]; then echo "󰢮 Run App on GPU"
    elif [[ $action =~ "window.drag" ]]; then echo "󰉣 Move Window (drag)"
    elif [[ $action =~ "window.resize" ]]; then echo "󰁝 Resize Window"
    elif [[ $action =~ movewindow ]]; then
        if [[ $action =~ '"l"' ]] || [[ $action =~ "movewindow, l" ]]; then echo "󰁍 Move Window Left"
        elif [[ $action =~ '"r"' ]] || [[ $action =~ "movewindow, r" ]]; then echo "󰁎 Move Window Right"
        elif [[ $action =~ '"u"' ]] || [[ $action =~ "movewindow, u" ]]; then echo "󰁟 Move Window Up"
        elif [[ $action =~ '"d"' ]] || [[ $action =~ "movewindow, d" ]]; then echo "󰁆 Move Window Down"
        else echo "󰉣 Move Window"
        fi
    elif [[ $action =~ "wallpaper-ctrl" ]]; then echo "󰸉 Wallpaper Control"
    elif [[ $action =~ "settings_manager" ]]; then echo "󰒓 Settings Manager"
    elif [[ $action =~ "dock-toggle" ]]; then echo "󰏝 Toggle Dock"
    elif [[ $action =~ "spotlight" ]]; then echo "󰀻 Open Application Launcher"
    elif [[ $action =~ wofi ]]; then echo "󰀻 Open Application Launcher"
    elif [[ $action =~ "waybars.sh ctrl-cntr" ]]; then echo "󰀻 Open Control Center"
    elif [[ $action =~ "screenshot.sh area" ]]; then echo "󰄀 Screenshot Area"
    elif [[ $action =~ screenshot.sh ]]; then echo "󰄀 Screenshot"
    elif [[ $action =~ shortcuts-help.sh ]]; then echo "󰋙 Show Shortcuts Help"
    elif [[ $action =~ file_search.sh ]]; then echo "󰈞 File Search"
    elif [[ $action =~ any_finder.sh ]]; then echo "󰈞 Any Finder"
    elif [[ $action =~ session_menu.sh ]]; then echo "󰀻 Session Menu"
    elif [[ $action =~ temperature.sh ]]; then echo "󰔏 Temperature Monitor"
    elif [[ $action =~ gpu_monitor.sh ]]; then echo "󰾲 GPU Monitor"
    elif [[ $action =~ power_usr.sh ]]; then echo "󰚥 Power Management"
    elif [[ $action =~ bluetooth.sh ]]; then echo "󰂯 Bluetooth Control"
    elif [[ $action =~ wifi.sh ]]; then echo "󰖩 WiFi Control"
    elif [[ $action =~ gamma.sh ]]; then echo "󰌶 Eye Comfort Toggle"
    elif [[ $action =~ reminder.sh ]]; then echo "󰄉 Reminder"
    elif [[ $action =~ time_of_day.sh ]]; then echo "󰥔 Time of Day"
    elif [[ $action =~ toggle_calendar.sh ]]; then echo "󰃭 Toggle Calendar"
    elif [[ $action =~ waybars.sh ]]; then echo "󰀻 Control Center"
    elif [[ $action =~ wofi_session.sh ]]; then echo "󰀻 Wofi Session"
    else echo "󰀻 Custom Action"
    fi
}

# Function to parse and format shortcuts (Lua hl.bind first, legacy bind= after)
parse_shortcuts() {

    # Initialize section variables
    local window_management=""
    local focus_movement=""
    local scroll_layout=""
    local workspaces=""
    local media_controls=""
    local apps_tools=""

    # Parse all binds
    while IFS= read -r line; do
        local keys action
        if [[ "$line" == hl.bind* ]]; then
            # Lua: hl.bind("SUPER + T", hl.dsp.exec_cmd("ghostty"))[, flags]
            keys=$(echo "$line" | sed -n 's/^hl\.bind("\([^"]*\)".*/\1/p')
            action=$(echo "$line" | sed -n 's/^hl\.bind("[^"]*", *//p' | sed 's/)[,}]* *$//')
            # Normalize dsp calls to legacy tokens for matching below
            action=$(echo "$action" | sed \
                -e 's/hl\.dsp\.focus({ workspace = /workspace, /' \
                -e 's/hl\.dsp\.window\.move({ workspace = /movetoworkspace, /' \
                -e 's/hl\.dsp\.workspace\.toggle_special/togglespecialworkspace/' \
                -e 's/togglespecialworkspace(/togglespecialworkspace, /' \
                -e 's/hl\.dsp\.focus({ direction = /movefocus, /' \
                -e 's/hl\.dsp\.window\.move({ direction = /movewindow, /' \
                -e 's/hl\.dsp\.layout("/layoutmsg, /' \
                -e 's/[{}"]//g' -e 's/) *$//' -e 's/ *$//')
        else
            keys=$(echo "$line" | awk -F'=' '{print $2}' | awk -F', ' '{print $1 "," $2}' | sed 's/^,//' | sed 's/^ *//')
            action=$(echo "$line" | awk -F', ' '{for(i=3;i<=NF;i++) printf "%s, ", $i; print ""}' | sed 's/, $//')
        fi
        action=$(replace_vars "$action" "$config_file")
        desc=$(get_bind_description "$action" "$config_file")
        formatted_keys=$(format_keys "$(replace_vars "$keys" "$config_file")")
        entry="  $formatted_keys : $desc"

        if [[ $action =~ (layoutmsg|safe-layoutmsg|toggle-split) ]]; then
            scroll_layout+="$entry\n"
        elif [[ $action =~ (killactive|window.close|fullscreen|window.fullscreen|exec.*terminal|exec.*fileManager|exec_cmd\(ghostty|exec_cmd\(thunar|togglefloating|window.float|exec.*hyprlock|pseudo|togglesplit|layout-ctrl) ]]; then
            window_management+="$entry\n"
        elif [[ $action =~ (movefocus|resizeactive|dsp.focus|dsp.window.resize|window.resize|movewindow) ]]; then
            focus_movement+="$entry\n"
        elif [[ $action =~ (workspace|movetoworkspace|togglespecialworkspace|special) ]]; then
            workspaces+="$entry\n"
        elif [[ $action =~ (XF86|brightness|audio|mic|camera) ]]; then
            media_controls+="$entry\n"
        elif [[ $action =~ (wofi|spotlight|waybars|screenshot|shortcuts-help|file_search|any_finder|power-mode|gpu-run|session_menu) ]]; then
            apps_tools+="$entry\n"
        else
            apps_tools+="$entry\n"
        fi
    done < <(rg "^hl\.bind\(|^bind[el]* *=" "$config_file")

    # Output header
    echo "󰋙 HYPROCKET SHORTCUTS HELP"
    echo "──────────────────────"
    echo ""

    # Scroll Layout
    if [ -n "$scroll_layout" ]; then
        echo "󰘕 SCROLL LAYOUT"
        echo "────────────────"
        echo -e "$scroll_layout"
        echo ""
    fi

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

    echo "󰌍 Press ESC to close"
}

# Hash-based caching setup
hash_file="$HOME/.config/hypr/hyprocket-shortcuts-hash.txt"
help_file="$HOME/.config/hypr/hyprocket-shortcuts-help.txt"
mkdir -p "$(dirname "$hash_file")"

# Determine config file: generated Lua first, then legacy hyprlang fallbacks
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
lua_config="$HOME/.config/hypr/hyprland.lua"
dev_config="$script_dir/../hyprland.conf"
generated_config="$HOME/.config/hypr/hyprde.generated.conf"
main_config="$HOME/.config/hypr/hyprland.conf"

# Prefer the live Lua config (all binds); fall back to legacy confs
if [ -f "$lua_config" ]; then
    config_file="$lua_config"
elif [ -f "$generated_config" ]; then
    config_file="$generated_config"
elif [ -f "$dev_config" ]; then
    config_file="$dev_config"
else
    config_file="$main_config"
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
        --prompt "Hyprocket Shortcuts (ESC to close)" \
        --width 800 \
        --height 600 \
        --location center \
        --insensitive \
        --cache-file /dev/null
fi

