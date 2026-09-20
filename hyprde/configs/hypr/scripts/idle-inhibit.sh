#!/bin/bash
# Idle inhibit toggle for video watching / presentations.
#
# Watching a video generates no keyboard/mouse input, so hypridle's dim,
# lock and screen-off timers keep firing (dim lock screen reads as a dead
# black screen with "dead keys"). This toggle stops hypridle entirely while
# engaged; suspend via power button / lid still works (logind, not hypridle).
# State persists in toggles.state; re-apply after reboot by re-toggling.
#
# Usage: idle-inhibit.sh [toggle|on|off|status]
# Bind suggestion: $mainMod, I, exec, ~/.config/hypr/scripts/idle-inhibit.sh toggle

STATE_FILE="$HOME/.config/hypr/toggles.state"

get_state() {
    grep "^idle_inhibit=" "$STATE_FILE" 2>/dev/null | cut -d= -f2 | tail -1
}

save_state() {
    local state="$1"
    mkdir -p "$(dirname "$STATE_FILE")"
    if [ -f "$STATE_FILE" ]; then
        grep -v "^idle_inhibit=" "$STATE_FILE" > "$STATE_FILE.tmp" 2>/dev/null || true
        echo "idle_inhibit=$state" >> "$STATE_FILE.tmp"
        mv "$STATE_FILE.tmp" "$STATE_FILE"
    else
        echo "idle_inhibit=$state" > "$STATE_FILE"
    fi
}

is_inhibited() { [ "$(get_state)" = "on" ]; }

do_on() {
    pkill -x hypridle 2>/dev/null || true
    save_state on
    notify-send -t 2500 "HyprDE Idle" "Idle timers OFF — video mode (dim/lock/screen-off paused)" 2>/dev/null || true
}

do_off() {
    save_state off
    if ! pgrep -x hypridle >/dev/null 2>&1; then
        hypridle >/dev/null 2>&1 &
    fi
    # Give hypridle a moment to start and fire any pending idle timeouts 
    # (since consumed keybinds sometimes don't reset the compositor's idle clock)
    sleep 0.5
    
    # Refresh the display in case we engage while dimmed, or if hypridle just blanked it.
    if hyprctl monitors -j | grep -q '"dpmsStatus": false'; then
        hyprctl dispatch 'hl.dsp.dpms({ power = true })' >/dev/null 2>&1 || true
    fi
    brightnessctl -r >/dev/null 2>&1 || true
    notify-send -t 2500 "HyprDE Idle" "Idle timers ON — dim/lock/screen-off resumed" 2>/dev/null || true
}

case "${1:-toggle}" in
    on) do_on ;;
    off) do_off ;;
    status)
        if is_inhibited; then
            echo '{"text": "Inhibit ON", "tooltip": "Idle timers paused (video mode)", "class": "enbld"}'
        else
            echo '{"text": "Inhibit OFF", "tooltip": "Idle timers active", "class": "disbld"}'
        fi
        ;;
    toggle|*)
        if is_inhibited; then do_off; else do_on; fi
        ;;
esac
