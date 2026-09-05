#!/bin/bash
[ -n "${_HYPRDE_PYTHON_BIN:-}" ] || source "${0%/*}/hyprde-python.sh" 2>/dev/null || source "$HOME/.config/hypr/scripts/hyprde-python.sh" 2>/dev/null || true

CURRENT_LAYOUT=$(hyprctl getoption general:layout -j | jq -r '.str')

TARGET="dwindle"
if [ "$CURRENT_LAYOUT" == "dwindle" ]; then
    TARGET="scroll"
fi

# Persist in TOML: global default AND per-workspace rules.
# (Layouts are per-workspace since Hyprland 0.54: existing workspaces keep
# their layout across reloads, so the default alone cannot migrate them.
# NOTE: the scrolling layout's rule name is "scrolling", not "scroll".)
TARGET="$TARGET" python3 -c "
import tomlkit, os
target = os.environ['TARGET']
rule_layout = 'scrolling' if target == 'scroll' else target
path = os.path.expanduser('~/.config/hypr/hyprde.toml')
with open(path, 'r') as f: data = tomlkit.load(f)
if 'general' not in data: data['general'] = tomlkit.table()
data['general']['layout'] = target
if 'rules' not in data: data['rules'] = tomlkit.table()
rules = data['rules']
rules['workspace'] = [f'{i}, layout = \"{rule_layout}\"' for i in range(1, 11)]
with open(path, 'w') as f: f.write(tomlkit.dumps(data))
"

# Regenerate Lua config and reload
python3 "$HOME/.config/hypr/build_config.py" > /dev/null 2>&1
hyprctl reload
notify-send -t 1000 "Layout Switched" "$TARGET (workspaces 1-10 migrated)"
