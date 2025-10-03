#!/bin/bash

# Debug logging
mkdir -p "$HOME/.cache"
echo "$(date): wofi_launcher.sh started" >> "$HOME/.cache/wofi_launcher.log"

# Check dependencies
if ! command -v wofi >/dev/null 2>&1; then
    echo "$(date): ERROR - wofi not found" >> "$HOME/.cache/wofi_launcher.log"
    notify-send "Error" "wofi is not installed"
    exit 1
fi

# Check for calculator (prefer bc, fallback to awk)
CALCULATOR=""
if command -v bc >/dev/null 2>&1; then
    CALCULATOR="bc"
elif command -v awk >/dev/null 2>&1; then
    CALCULATOR="awk"
else
    notify-send "Error" "No calculator found (bc or awk)"
    exit 1
fi

# Launch wofi in dmenu mode to get user input
echo "$(date): Launching wofi dmenu" >> "$HOME/.cache/wofi_launcher.log"
if ! input=$(wofi --dmenu --prompt "Calc/Run:" --width 400 --lines 1 --conf "$HOME/.config/wofi/config" --style "$HOME/.config/wofi/style.css" 2>"$HOME/.cache/wofi_error.log"); then
    echo "$(date): ERROR - wofi dmenu failed" >> "$HOME/.cache/wofi_launcher.log"
    notify-send "Launcher Error" "Failed to launch wofi input dialog"
    exit 1
fi

echo "$(date): Got input: '$input'" >> "$HOME/.cache/wofi_launcher.log"

# Exit if no input
if [ -z "$input" ]; then
    echo "$(date): No input, exiting" >> "$HOME/.cache/wofi_launcher.log"
    exit 0
fi

# Remove leading/trailing whitespace
input=$(echo "$input" | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')

# Check if input starts with "calc:"
if [[ "$input" =~ ^calc: ]]; then
    # Extract the expression after "calc:"
    calc_input=$(echo "$input" | sed 's/^calc://' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')

    # Check if calc_input looks like a math expression
    is_math_expression() {
        local input="$1"
        local clean_input=$(echo "$input" | tr -d '[:space:]')
        [[ "$clean_input" =~ [0-9] ]] && ([[ "$clean_input" =~ [+*/-] ]] || [[ "$clean_input" =~ [a-zA-Z] ]])
    }

    result=""
    if is_math_expression "$calc_input"; then
        if [ "$CALCULATOR" = "bc" ]; then
            result=$(echo "scale=2; $calc_input" | bc -l 2>/dev/null)
        elif [ "$CALCULATOR" = "awk" ]; then
            result=$(echo "$calc_input" | awk -F'+' '{print $1+$2}' 2>/dev/null || echo "$calc_input" | awk -F'-' '{print $1-$2}' 2>/dev/null || echo "$calc_input" | awk -F'*' '{print $1*$2}' 2>/dev/null || echo "$calc_input" | awk -F'/' '{print $1/$2}' 2>/dev/null || echo "error")
        fi
    fi

    # If valid result, display in wofi and copy to clipboard
    if [[ -n "$result" && "$result" =~ ^[0-9.-]+$ && "$result" != "error" ]]; then
        echo "$(date): Showing calculator result: $result" >> "$HOME/.cache/wofi_launcher.log"
        sleep 2
        echo "$result" | wofi --dmenu --prompt "Calculator" --width 400 --lines 1 --conf "$HOME/.config/wofi/config" --style "$HOME/.config/wofi/style.css" &
        wofi_pid=$!
        sleep 2
        kill $wofi_pid 2>/dev/null
        echo "$result" | wl-copy 2>/dev/null || echo "$result" | xclip -selection clipboard 2>/dev/null || true
    else
        # Invalid calc input, show app launcher
        echo "$(date): Invalid calc input, showing app launcher" >> "$HOME/.cache/wofi_launcher.log"
        wofi --show drun --conf "$HOME/.config/wofi/config" --style "$HOME/.config/wofi/style.css" 2>"$HOME/.cache/wofi_drun_error.log" || echo "$(date): ERROR - wofi drun failed" >> "$HOME/.cache/wofi_launcher.log"
    fi
else
    # Not calc, show application launcher
    echo "$(date): Showing application launcher" >> "$HOME/.cache/wofi_launcher.log"
    if ! wofi --show drun --conf "$HOME/.config/wofi/config" --style "$HOME/.config/wofi/style.css" 2>"$HOME/.cache/wofi_drun_error.log"; then
        echo "$(date): ERROR - wofi drun failed" >> "$HOME/.cache/wofi_launcher.log"
        notify-send "Launcher Error" "Failed to launch application menu"
        exit 1
    fi
fi
