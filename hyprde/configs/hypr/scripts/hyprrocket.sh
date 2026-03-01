#!/bin/bash

# HyprRocket: Generic Event Dispatcher
# Usage: hyprrocket.sh --trigger <event_name>

EVENT_NAME=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --trigger) EVENT_NAME="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$EVENT_NAME" ]; then
    echo "Error: No trigger specified."
    exit 1
fi

# Configuration path
TOML_CONFIG="$HOME/.config/hypr/hyprde.toml"
SCRIPTS_DIR="$HOME/.config/hypr/scripts"

# Use python to safely parse TOML and handle logic
python3 - <<EOF
import tomlkit
import os
import subprocess
import json

def run_command(cmd):
    # Expand path if it's one of our internal scripts
    if cmd.startswith("theme-ctrl.sh") or cmd.startswith("gamma.sh") or \
       cmd.startswith("mic.sh") or cmd.startswith("camera.sh") or \
       cmd.startswith("wallpaper-ctrl.sh"):
        cmd = os.path.join("$SCRIPTS_DIR", cmd)
    elif cmd.startswith("gammastep/"):
        cmd = os.path.join("$SCRIPTS_DIR", cmd)
    
    # Handle $HOME expansion
    cmd = cmd.replace("\$HOME", os.path.expanduser("~"))
    
    subprocess.run(cmd, shell=True)

def is_fullscreen():
    try:
        output = subprocess.check_output(["hyprctl", "activewindow", "-j"], text=True)
        data = json.loads(output)
        return data.get("fullscreen", False)
    except:
        return False

path = os.path.expanduser("$TOML_CONFIG")
if not os.path.exists(path):
    exit(0)

with open(path, 'r') as f:
    data = tomlkit.load(f)

rocket = data.get("hyprrocket", {})
events = rocket.get("events", {})

if "$EVENT_NAME" in events:
    event_data = events["$EVENT_NAME"]
    
    # Check conditions
    condition = event_data.get("condition", "")
    if condition == "not_fullscreen" and is_fullscreen():
        subprocess.run(["notify-send", "-t", "3000", "HyprRocket", "Trigger '$EVENT_NAME' postponed: Fullscreen app detected."])
        exit(0)
    
    # Run actions
    actions = event_data.get("actions", [])
    for action in actions:
        run_command(action)
    
    # Optional notification
    if rocket.get("notify", True):
        subprocess.run(["notify-send", "-t", "2000", "HyprRocket", f"Event '$EVENT_NAME' executed."])

EOF
