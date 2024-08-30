#!/bin/bash

max_value() {
    local max="$1"  # Initialize max with the first argument
    for value in "$@"; do
        # Use awk to compare floating-point numbers
        max=$(awk -v a="$max" -v b="$value" 'BEGIN { print (a > b) ? a : b }')
    done
    echo "$max"
}

get_class() {
    local value="$1"

    # Check if the value is a valid number (integer or decimal)
    if ! [[ "$value" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
        echo "Invalid input"
        return 1
    fi

    # Use awk for floating-point comparison
    if awk "BEGIN { exit !($value > 70) }"; then
        echo "critical"
    elif awk "BEGIN { exit !($value > 55) }"; then
        echo "warning"
    else
        echo "normal"
    fi
}

# Function to get CPU temperature
get_cpu_temp() {
    cpu_temp=$(sensors | grep 'CPU' | awk -F'+' '{print $2}' | tr -d '°C')
    echo "$cpu_temp"
}

# Function to get GPU temperature 
get_gpu_temp() {
    gpu_temp=$(sensors | grep 'GPU' | awk -F'+' '{print $2}' | tr -d '°C')
    echo "$gpu_temp"
}

# Function to get ambient temperature
get_ambient_temp() {
    ambient_temp=$(sensors | grep 'Ambient' | awk -F'+' '{print $2}' | tr -d '°C')
    echo "$ambient_temp"
}

# Function to get SODIMM temperature
get_sodimm_temp() {
    sodimm_temp=$(sensors | grep 'SODIMM' | awk -F'+' '{print $2}' | tr -d '°C')
    echo "$sodimm_temp"
}

# Check the argument
case "$1" in
    "CPU")
        cpu_temperature=$(get_cpu_temp)
        echo "{\"text\": \"CPU: $cpu_temperature\", \"tooltip\": \"CPU temperature\", \"percentage\": $cpu_temperature}"
        ;;
    "GPU")
        gpu_temperature=$(get_gpu_temp)
        echo "{\"text\": \"GPU\": $gpu_temperature\", \"tooltip\": \"GPU temperature\", \"percentage\": $gpu_temperature}"
        ;;
    "ambient")
        ambient_temperature=$(get_ambient_temp)
        echo "{\"text\": \"Ambient\": $ambient_temperature\", \"tooltip\": \"Ambient temperature\", \"percentage\": $ambient_temperature}"
        ;;
    "SODIMM")
        sodimm_temperature=$(get_sodimm_temp)
        echo "{\"text\": \"SODIMM\": $sodimm_temperature\", \"tooltip\": \"SODIMM temperature\", \"percentage\": $sodimm_temperature}"
        ;;
    "all")
        cpu_temperature=$(get_cpu_temp)
        gpu_temperature=$(get_gpu_temp)
        ambient_temperature=$(get_ambient_temp)
        sodimm_temperature=$(get_sodimm_temp)
        
         temperatures=("$cpu_temperature" "$gpu_temperature" "$ambient_temperature" "$sodimm_temperature" "$mac_temperature")

        # Calculate the maximum temperature
        max_temperature=$(max_value "${temperatures[@]}")
        max_temperature=$(echo "$max_temperature" | xargs)
      
        class=$(get_class $max_temperature)

        # Create a JSON object with all temperatures
        echo "{\"text\": \"$max_temperature\", \"tooltip\": \"CPU: $cpu_temperature | GPU: $gpu_temperature | Ambient: $ambient_temperature | RAM: $sodimm_temperature\", \"percentage\": $max_temperature,\"class\":\"$class\"}"
        ;;
    *)
        echo "Usage: $0 {CPU|GPU|ambient|SODIMM|all}"
        exit 1
        ;;
esac
