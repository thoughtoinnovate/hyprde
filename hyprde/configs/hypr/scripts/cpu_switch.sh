#!/bin/bash
# Function to prompt for password using zenity
prompt_password() {
    zenity --password --title="Authentication Required"
}

# Get the password from the user
PASSWORD=$(prompt_password)

# Check if the user canceled the password prompt
if [ -z "$PASSWORD" ]; then
    echo "Password prompt canceled."
    exit 1
fi
# Check if the correct number of arguments is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <on|off>"
    exit 1
fi

# Get the action (on or off)
action=$1

# Validate the action
if [ "$action" != "on" ] && [ "$action" != "off" ]; then
    echo "Invalid argument: $action. Use 'on' or 'off'."
    exit 1
fi

# List CPU directories and filter them
cpu_dirs=$(ls /sys/devices/system/cpu/ | grep -i "^cpu[0-9]\+$")

# Convert the list to an array
cpu_array=($cpu_dirs)

# Calculate the number of CPUs
num_cpus=${#cpu_array[@]}

if [ "$action" == "off" ]; then
    # Calculate the number of CPUs to turn off (50%)
    num_to_turn_off=$((num_cpus / 2))

    # Turn off 50% of the CPUs
    for ((i=0; i<=num_to_turn_off; i++)); do
        cpu_no=${cpu_array[$i]}
        echo "Setting $cpu_no to idle mode"
        # sudo cpupower -c ${cpu_no:1} idle-set -d 0
        echo "Turning off $cpu_no"
        sh -c "echo 0 > /sys/devices/system/cpu/$cpu_no/online"
    done
else
    # Turn on all CPUs
        echo "Turning on $cpu_no"
        sh -c "echo 1 > /sys/devices/system/cpu/$cpu_no/online"
        echo "Setting $cpu_no to active mode"
        # sudo cpupower -c ${cpu_no:1} idle-set -d 0
    done
fi