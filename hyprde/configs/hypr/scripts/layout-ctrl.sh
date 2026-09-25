#!/bin/bash
[ -n "${_HYPRDE_PYTHON_BIN:-}" ] || source "${0%/*}/hyprde-python.sh" 2>/dev/null || source "$HOME/.config/hypr/scripts/hyprde-python.sh" 2>/dev/null || true
PYTHON="${_HYPRDE_PYTHON_BIN:-python3}"

exec "$PYTHON" - << 'EOF'
import os
import re
import sys
import json
import subprocess
import tomlkit

# 1. Determine current layout: active workspace -> general:layout -> hyprde.toml
cur = None
try:
    p = subprocess.run(["hyprctl", "activeworkspace", "-j"], capture_output=True, text=True, timeout=2)
    if p.returncode == 0:
        d = json.loads(p.stdout)
        cur = d.get("tiledLayout")
except Exception:
    pass

if not cur:
    try:
        p = subprocess.run(["hyprctl", "getoption", "general:layout", "-j"], capture_output=True, text=True, timeout=2)
        if p.returncode == 0:
            d = json.loads(p.stdout)
            cur = d.get("str")
    except Exception:
        pass

path = os.path.expanduser("~/.config/hypr/hyprde.toml")
if not os.path.exists(path):
    alt = os.path.join(os.path.dirname(__file__), "../hyprde.toml")
    if os.path.exists(alt):
        path = alt

data = {}
try:
    with open(path, "r") as f:
        data = tomlkit.load(f)
except Exception as e:
    print(f"Error loading TOML: {e}", file=sys.stderr)

if not cur:
    cur = data.get("general", {}).get("layout")

# 2. Cycle: dwindle -> master -> scroll -> dwindle
if cur == "dwindle":
    target = "master"
elif cur == "master":
    target = "scroll"
elif cur in ("scroll", "scrolling"):
    target = "dwindle"
else:
    target = "master"

rule_layout = "scrolling" if target == "scroll" else target

# 3. Live migration via Hyprland repl for instant visual feedback
try:
    subprocess.run([
        "hyprctl", "repl",
        f"for i=1,10 do hl.workspace_rule({{ workspace = tostring(i), layout = '{rule_layout}' }}) end; return true"
    ], capture_output=True, timeout=2)
except Exception:
    pass

# 4. Persist in TOML
try:
    if "general" not in data:
        data["general"] = tomlkit.table()
    data["general"]["layout"] = target

    if "rules" not in data:
        data["rules"] = tomlkit.table()
    rules = data["rules"]

    existing = list(rules.get("workspace", []))
    new_rules = []
    layout_nums = set()
    for r in existing:
        m = re.match(r"^(\d+)\s*,\s*layout\s*=", r)
        if m:
            num = int(m.group(1))
            layout_nums.add(num)
            new_rules.append(f'{num}, layout = "{rule_layout}"')
        else:
            new_rules.append(r)

    for i in range(1, 11):
        if i not in layout_nums:
            new_rules.append(f'{i}, layout = "{rule_layout}"')

    rules["workspace"] = new_rules

    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(tomlkit.dumps(data))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)
except Exception as e:
    print(f"Error updating TOML: {e}", file=sys.stderr)

# 5. Regenerate Lua config and reload
build_script = os.path.expanduser("~/.config/hypr/build_config.py")
if not os.path.exists(build_script):
    build_script = os.path.join(os.path.dirname(__file__), "../build_config.py")
if os.path.exists(build_script):
    subprocess.run([sys.executable, build_script], capture_output=True, timeout=10)

subprocess.run(["hyprctl", "reload"], capture_output=True, timeout=5)

# 6. Notification
target_cap = target.capitalize()
subprocess.run([
    "notify-send", "-t", "1500", "Layout Switched",
    f"{target_cap} (workspaces 1-10 migrated)"
], capture_output=True, timeout=3)
EOF
