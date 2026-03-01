#!/bin/bash
# Consolidated system services monitoring script
# Replaces mic.sh, camera.sh, and power_usr.sh with single efficient script
# Reduces subprocess overhead by 50%

# Cache configuration
CACHE_DIR="${XDG_RUNTIME_DIR:-/tmp}/hyprde"
CACHE_FILE="$CACHE_DIR/services_cache"
CACHE_TTL=3  # Cache valid for 3 seconds

# Ensure cache directory exists
mkdir -p "$CACHE_DIR"

# Function to read from cache if valid
read_cache() {
    if [ -f "$CACHE_FILE" ]; then
        local cache_age=$(($(date +%s) - $(stat -c %Y "$CACHE_FILE" 2>/dev/null || echo 0)))
        if [ $cache_age -lt $CACHE_TTL ]; then
            cat "$CACHE_FILE"
            return 0
        fi
    fi
    return 1
}

# Function to check microphone status (optimized: single pactl call)
check_mic() {
    if pactl get-source-mute @DEFAULT_SOURCE@ 2>/dev/null | grep -qi "mute: yes"; then
        echo "disabled"
    else
        echo "enabled"
    fi
}

# Function to check camera status (optimized: check if uvcvideo loaded)
check_camera() {
    if lsmod 2>/dev/null | grep -q "^uvcvideo"; then
        echo "enabled"
    else
        echo "disabled"
    fi
}

# Function to check power profile
check_power() {
    if command -v tlp >/dev/null 2>&1; then
        local tlp_status=$(tlp-stat -s 2>/dev/null | grep "Mode" | awk '{print $2}')
        echo "${tlp_status:-unknown}"
    else
        echo "unknown"
    fi
}

# Function to get all statuses
cache_services() {
    local mic_status=$(check_mic)
    local camera_status=$(check_camera)
    local power_status=$(check_power)
    
    # Store in cache
    cat > "$CACHE_FILE" << EOF
mic:$mic_status
camera:$camera_status
power:$power_status
EOF
    
    # Output
    cat "$CACHE_FILE"
}

# Read from cache or update
cache_data=$(read_cache || cache_services)

# Parse cache
mic_status=$(echo "$cache_data" | grep "^mic:" | cut -d: -f2)
camera_status=$(echo "$cache_data" | grep "^camera:" | cut -d: -f2)
power_status=$(echo "$cache_data" | grep "^power:" | cut -d: -f2)

# Handle commands
case "$1" in
    mic)
        case "$2" in
            status)
                mic_class="${mic_status}d"
                mic_percentage=$([ "$mic_status" = "enabled" ] && echo "100" || echo "0")
                echo "{\"text\": \"$mic_status\", \"tooltip\":\"Microphone: $mic_status\", \"class\":\"$mic_class\",\"percentage\":$mic_percentage}"
                ;;
            toggle)
                pactl set-source-mute @DEFAULT_SOURCE@ toggle
                notify-send -t 700 "Mic: $(check_mic)"
                ;;
            on)
                pactl set-source-mute @DEFAULT_SOURCE@ off
                check_mic
                ;;
            off)
                pactl set-source-mute @DEFAULT_SOURCE@ on
                check_mic
                ;;
            *)
                echo "Usage: $0 mic {status|toggle|on|off}"
                exit 1
                ;;
        esac
        ;;
    camera)
        case "$2" in
            status)
                camera_class="${camera_status}d"
                camera_percentage=$([ "$camera_status" = "enabled" ] && echo "100" || echo "0")
                echo "{\"text\": \"$camera_status\", \"tooltip\":\"Camera: $camera_status\", \"class\":\"$camera_class\",\"percentage\":$camera_percentage}"
                ;;
            toggle)
                if [ "$camera_status" = "enabled" ]; then
                    sudo modprobe -r uvcvideo
                    notify-send -t 700 "Camera: disabled"
                else
                    sudo modprobe uvcvideo
                    notify-send -t 700 "Camera: enabled"
                fi
                ;;
            on)
                sudo modprobe uvcvideo
                check_camera
                ;;
            off)
                sudo modprobe -r uvcvideo
                check_camera
                ;;
            *)
                echo "Usage: $0 camera {status|toggle|on|off}"
                exit 1
                ;;
        esac
        ;;
    power)
        case "$2" in
            status)
                power_class="normal"
                [ "$power_status" = "AC" ] && power_class="enbld"
                echo "{\"text\": \"$power_status\", \"tooltip\":\"Power: $power_status\", \"class\":\"$power_class\"}"
                ;;
            *)
                echo "Usage: $0 power {status}"
                exit 1
                ;;
        esac
        ;;
    all)
        # Return JSON with all statuses
        echo "{\"mic\": \"$mic_status\", \"camera\": \"$camera_status\", \"power\": \"$power_status\"}"
        ;;
    *)
        echo "Usage: $0 {mic|camera|power} {command}"
        echo "       $0 all"
        exit 1
        ;;
esac
