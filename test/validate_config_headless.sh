#!/bin/bash

# Configuration
CONFIG_DIR="/tmp/hypr_test"
mkdir -p "$CONFIG_DIR"
export HYPR_CONFIG_DIR="$CONFIG_DIR"

echo "1. Generating configuration from TOML..."
python3 hyprde/configs/hypr/build_config.py

if [ ! -f "$CONFIG_DIR/hyprland.lua" ]; then
    echo "ERROR: Configuration failed to generate."
    exit 1
fi

echo "2. Launching Hyprland in HEADLESS mode for validation..."
# WLR_BACKENDS=headless: Runs without a screen
# WLR_RENDERER=pixman: Uses CPU instead of GPU (essential for Docker)
# -c: specifies the config file
# &> ...: captures all output
WLR_BACKENDS=headless WLR_RENDERER=pixman Hyprland -c "$CONFIG_DIR/hyprland.lua" &> /tmp/hypr_run.log &
HYPR_PID=$!

# Give it time to parse the config
sleep 3

# Kill it
kill $HYPR_PID 2>/dev/null

echo "3. Analyzing logs for errors..."
if grep -Ei "error|invalid field|failed to parse" /tmp/hypr_run.log | grep -v -E "Could not generate config errors|Creating the Error Overlay|Errors from xkbcomp" >/dev/null; then
    echo "--------------------------------------------------"
    echo "CRITICAL: Configuration errors detected!"
    grep -Ei "error|invalid field|failed to parse" /tmp/hypr_run.log | grep -v -E "Could not generate config errors|Creating the Error Overlay|Errors from xkbcomp"
    echo "--------------------------------------------------"
    exit 1
else
    echo "SUCCESS: No configuration errors found by the Hyprland parser."
    exit 0
fi
