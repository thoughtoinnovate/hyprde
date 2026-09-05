#!/bin/bash
[ -n "${_HYPRDE_PYTHON_BIN:-}" ] || source "${0%/*}/hyprde-python.sh" 2>/dev/null || source "$HOME/.config/hypr/scripts/hyprde-python.sh" 2>/dev/null || true

# Configuration file path
TOML_CONFIG="$HOME/.config/hypr/hyprde.toml"

if [ ! -f "$TOML_CONFIG" ]; then
    # Fallback to hardcoded if TOML is missing
    hour=$(date +%H)
    if [ "$hour" -ge 6 ] && [ "$hour" -lt 12 ]; then echo "morning"
    elif [ "$hour" -ge 12 ] && [ "$hour" -lt 18 ]; then echo "noon"
    else echo "evening"; fi
    exit 0
fi

# Use python to parse TOML and determine time of day based on user schedule
# Three slots: morning (6AM-12PM), noon (12PM-6PM), evening (6PM-6AM)
python3 -c "
import tomlkit, os, datetime
path = os.path.expanduser('~/.config/hypr/hyprde.toml')

def convert_to_minutes(t_str):
    try:
        t = datetime.datetime.strptime(t_str.strip(), '%I:%M %p')
        return t.hour * 60 + t.minute
    except:
        return 0

with open(path, 'r') as f: data = tomlkit.load(f)
wp = data.get('wallpapers', {})
sched = wp.get('schedule', {})

m_start = convert_to_minutes(sched.get('morning_start', '6:00 AM'))
n_start = convert_to_minutes(sched.get('noon_start', '12:00 PM'))
e_start = convert_to_minutes(sched.get('evening_start', '6:00 PM'))

now = datetime.datetime.now()
curr = now.hour * 60 + now.minute

if m_start <= curr < n_start:
    print('morning')
elif n_start <= curr < e_start:
    print('noon')
else:
    print('evening')
"
