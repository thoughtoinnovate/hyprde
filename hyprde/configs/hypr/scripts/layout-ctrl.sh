#!/bin/bash
[ -n "${_HYPRDE_PYTHON_BIN:-}" ] || source "${0%/*}/hyprde-python.sh" 2>/dev/null || source "$HOME/.config/hypr/scripts/hyprde-python.sh" 2>/dev/null || true

CURRENT_LAYOUT=$(hyprctl getoption general:layout -j | jq -r '.str')

TARGET="dwindle"
if [ "$CURRENT_LAYOUT" == "dwindle" ]; then
    TARGET="scroll"
fi

# Persist in TOML
python3 -c "
import tomlkit, os
path = os.path.expanduser('~/.config/hypr/hyprde.toml')
with open(path, 'r') as f: data = tomlkit.load(f)
if 'general' not in data: data['general'] = tomlkit.table()
data['general']['layout'] = '$TARGET'
with open(path, 'w') as f: f.write(tomlkit.dumps(data))
"

# Regenerate Lua config and reload
python3 "$HOME/.config/hypr/build_config.py" > /dev/null 2>&1
hyprctl reload
notify-send -t 1000 "Layout Switched" "$TARGET (Standard)"
