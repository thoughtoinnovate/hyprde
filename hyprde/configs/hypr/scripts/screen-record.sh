#!/bin/bash

# Load Icons
source "$HOME/.config/hypr/scripts/hyprrocket.icons"

# Configuration
SAVE_DIR="$HOME/Videos/Recordings"
mkdir -p "$SAVE_DIR"

# Function to get status for Waybar
get_status() {
  if pgrep -f "gpu-screen-recorder" > /dev/null; then
    # Recording icon (Solid Red Circle)
    echo "{\"text\": \"$RECORD_ICON_ACTIVE\", \"tooltip\": \"Recording in Progress... Click to Stop\", \"class\": \"recording\", \"percentage\": 100}"
  elif [ "$1" == "main" ]; then
    # Return empty to hide it in Main Waybar
    echo "{}"
  else
    # Show idle icon in Control Center
    echo "{\"text\": \"$RECORD_ICON_IDLE\", \"tooltip\": \"Screen Recorder\", \"class\": \"idle\", \"percentage\": 0}"
  fi
}

# Function to stop recording
stop_recording() {
  pkill -SIGINT -f gpu-screen-recorder
  # Wait for it to finish saving
  sleep 2
  notify-send "Screen Recording" "Recording stopped and saved to $SAVE_DIR"
}

# Function to start recording
start_recording() {
  # 0. Secure On: Ask for authentication
  notify-send -t 3000 "Security Alert" "Screen recording requested. Please authenticate to start recording."
  # Use unique binary path to avoid conflict with microphone
  if ! pkexec /usr/local/bin/hyprde-screen-auth; then
    notify-send "Screen Recording" "Authentication failed. Recording cancelled."
    exit 1
  fi

  # 1. Select recording mode
  mode=$(echo -e "󰍹 Record Full Screen\n󰒚 Record Selection\n󰖯 Record Window" | wofi --dmenu --prompt "Recording Mode" --width 400 --height 250)
  
  if [ -z "$mode" ]; then
    exit 0
  fi

  # 2. Select resolution (Only for full screen)
  res_args=""
  res_choice="Native"
  if [[ "$mode" == *"Full Screen"* ]]; then
    res_choice=$(echo -e "Native\n1920x1080 (1080p)\n1280x720 (720p)" | wofi --dmenu --prompt "Select Resolution" --width 400 --height 250)
    if [ -z "$res_choice" ]; then exit 0; fi
    
    if [[ "$res_choice" == *"1920x1080"* ]]; then
      res_args="-s 1920x1080"
    elif [[ "$res_choice" == *"1280x720"* ]]; then
      res_args="-s 1280x720"
    fi
  fi

  # 3. Select audio
  audio_choice=$(echo -e "󰖁 No Audio\n󰓃 System Audio Only\n󰍬 System Audio + Mic" | wofi --dmenu --prompt "Select Audio" --width 400 --height 250)
  
  if [ -z "$audio_choice" ]; then
    exit 0
  fi

  audio_args=""
  if [[ "$audio_choice" == *"System Audio Only"* ]]; then
    audio_args="-a default_output"
  elif [[ "$audio_choice" == *"System Audio + Mic"* ]]; then
    audio_args="-a default_output -a default_input"
  fi

  filename="recording_$(date +%Y%m%d_%H%M%S)"
  filepath="$SAVE_DIR/$filename.mp4"

  # 4. Determine window/area arguments
  case "$mode" in
    *"Record Full Screen"*)
      args="-w screen"
      ;;
    *"Record Selection"*)
      # Use slurp for reliable area selection
      geometry=$(slurp)
      if [ -z "$geometry" ]; then exit 0; fi
      # Slurp output is X,Y WxH. gpu-screen-recorder -region expects WxH+X+Y
      # We need to transform "X,Y WxH" to "WxH+X+Y"
      # Slurp output example: "10,20 100x200"
      formatted_geom=$(echo "$geometry" | sed 's/\([0-9]*\),\([0-9]*\) \([0-9]*x[0-9]*\)/\3+\1+\2/')
      args="-w region -region $formatted_geom"
      ;;
    *"Record Window"*)
      # For window, portal is still the cleanest way to pick a specific window handle
      args="-w portal"
      ;;
    *)
      exit 1
      ;;
  esac

  # 5. Start recording
  notify-send "Screen Recording" "Starting recording: $mode ($res_choice, $audio_choice)"
  gpu-screen-recorder $args $res_args $audio_args -f 60 -fallback-cpu-encoding yes -o "$filepath" > /tmp/gsr.log 2>&1 &
}

# Toggle logic
toggle() {
  if pgrep -f "gpu-screen-recorder" > /dev/null; then
    stop_recording
  else
    start_recording
  fi
}

case "$1" in
  status)
    get_status "$2"
    ;;
  toggle)
    toggle
    ;;
  stop)
    stop_recording
    ;;
  *)
    echo "Usage: $0 {status|toggle|stop}"
    exit 1
    ;;
esac
