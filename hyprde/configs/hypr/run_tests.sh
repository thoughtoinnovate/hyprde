#!/bin/bash
echo "Running Hyprland Config Builder Tests..."
python3 -m unittest discover -s "$(dirname "$0")/tests" -p "test_*.py"
