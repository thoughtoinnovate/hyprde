#!/bin/bash

echo "Testing wofi directly..."
echo "DISPLAY: $DISPLAY"
echo "WAYLAND_DISPLAY: $WAYLAND_DISPLAY"

# Try to run wofi with a simple command
echo "Testing wofi --dmenu with echo..."
echo "test" | timeout 5 wofi --dmenu --prompt "Test:" 2>&1 || echo "wofi command failed or timed out"

echo "Test completed"
