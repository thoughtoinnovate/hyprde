#!/bin/bash
# Pin an app into [launcher.dock] apps= in hyprde.toml.
# Stdlib python3 only (no tomlkit). DOCK_PIN_TOML overrides the target file (tests).
# Usage: dock-pin.sh "App Display Name"
APP_NAME="$1"
TOML="${DOCK_PIN_TOML:-$HOME/.config/hypr/hyprde.toml}"

if [ -z "$APP_NAME" ]; then
    echo "usage: dock-pin.sh \"App Display Name\"" >&2
    exit 2
fi
if [ ! -f "$TOML" ]; then
    echo "dock-pin: not found: $TOML" >&2
    exit 2
fi

python3 - "$APP_NAME" "$TOML" <<'EOF'
import re
import subprocess
import sys

want, path = sys.argv[1], sys.argv[2]

with open(path) as f:
    text = f.read()

lines = text.splitlines(keepends=True)

# Locate [launcher.dock] section bounds.
start = end = None
for i, line in enumerate(lines):
    if re.match(r'\s*\[launcher\.dock\]', line):
        start = i
    elif start is not None and re.match(r'\s*\[[^]]+\]', line):
        end = i
        break
if start is None:
    print("dock-pin: [launcher.dock] section not found", file=sys.stderr)
    sys.exit(2)
if end is None:
    end = len(lines)

# Locate the apps = [ ... ] assignment (may span lines).
ai = aj = None
depth = 0
in_apps = False
for i in range(start, end):
    code = lines[i].split("#", 1)[0]
    if not in_apps:
        if re.search(r'(^|[\s,])apps\s*=\s*\[', code):
            in_apps = True
            ai = i
            depth = code.count("[") - code.count("]")
            if depth <= 0:
                aj = i
                break
    else:
        depth += code.count("[") - code.count("]")
        if depth <= 0:
            aj = i
            break
if ai is None:
    print("dock-pin: apps= not found in [launcher.dock]", file=sys.stderr)
    sys.exit(2)

block = "".join(lines[ai:aj + 1])
existing = re.findall(r'"([^"]*)"', block.split("#", 1)[0] if ai == aj else block)
if any(e.lower() == want.lower() for e in existing):
    print(f"dock-pin: '{want}' already pinned")
    sys.exit(0)

if ai == aj:
    # Single-line: insert before the closing bracket, keep trailing comment.
    line = lines[ai]
    code, sep, comment = line.partition("#")
    close = code.rfind("]")
    inner = code[:close].rstrip()
    needs_comma = bool(re.search(r'"[^"]*"\s*$', inner))
    new_code = f'{inner}{"," if needs_comma else ""} "{want}"]\n'
    lines[ai] = new_code + (sep + comment if sep else "")
else:
    # Multi-line: insert before the closing-bracket line.
    close_line = lines[aj]
    indent = re.match(r'\s*', close_line).group(0) + "    "
    prev = lines[aj - 1].rstrip("\n")
    if not prev.rstrip().endswith(","):
        lines[aj - 1] = prev + ",\n"
    lines.insert(aj, f'{indent}"{want}",\n')

with open(path, "w") as f:
    f.writelines(lines)

print(f"dock-pin: pinned '{want}'")
try:
    subprocess.run(["notify-send", "-t", "2500", "HyprDE Dock", f"Pinned {want}"],
                   capture_output=True, timeout=5)
except Exception:
    pass
EOF
