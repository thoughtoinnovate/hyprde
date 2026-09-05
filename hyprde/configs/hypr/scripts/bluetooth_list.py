#!/usr/bin/env python3
import json
import subprocess
import os
import re


def theme_color(name, fallback):
    """Read an accent-tracking color from the active theme CSS.

    Keeps small status tints in the same family as the system accent
    without depending on tomlkit/gi (this script must stay stdlib-only).
    """
    for css in (
        os.path.expanduser("~/.config/hypr/themes/current.css"),
        os.path.expanduser("~/.config/hypr/themes/dark.css"),
    ):
        try:
            with open(css) as f:
                content = f.read()
        except OSError:
            continue
        m = re.search(r"@define-color\s+" + re.escape(name) + r"\s+([^;]+);",
                      content)
        if m:
            val = m.group(1).strip()
            mh = re.match(r'#([0-9a-fA-F]{6})', val)
            if mh:
                return "#" + mh.group(1).lower()
    return fallback


ACCENT = theme_color("theme_active_bg", "#33ccff")

def main():
    script_path = os.path.expanduser("~/.config/hypr/scripts/bluetooth_info.py")
    if not os.path.exists(script_path):
        script_path = os.path.join(os.path.dirname(__file__), "bluetooth_info.py")
    
    try:
        result = subprocess.run([script_path], capture_output=True, text=True)
        data = json.loads(result.stdout)
        devices = data.get("devices", [])
        powered = data.get("powered", False)
    except:
        devices = []
        powered = False

    output_lines = []
    
    if not powered:
        output_lines.append("<span color='#ed333b'>󰂲 Bluetooth is Powered Off</span>")
    elif not devices:
        output_lines.append("<span color='#666666'>No paired devices found</span>")
    else:
        connected = [d for d in devices if d['connected']]
        paired = [d for d in devices if not d['connected']]
        
        if connected:
            output_lines.append(f"<span size='small' color='{ACCENT}'><b>CONNECTED</b></span>")
            for d in connected:
                name = d['name'][:16]
                icon = d['icon']
                signal = f"<span color='{ACCENT}'>{d['signal_icon']}</span>"
                battery = f"<span color='{ACCENT}'>{d['battery_icon']}</span> {d['battery']}%" if d['battery'] else ""
                # White and Bold for connected
                output_lines.append(f"{icon}  <b><span color='#ffffff'>{name:18}</span></b>  {signal:2}  {battery:8}  <span color='#00ff99'>󰄬</span>")
        
        if paired:
            if connected: output_lines.append("") # Spacer
            output_lines.append("<span size='small' color='#595959'><b>PAIRED</b></span>")
            for d in paired:
                name = d['name'][:16]
                icon = d['icon']
                output_lines.append(f"<span color='#595959'>{icon}  {name:18}  {'':2}  {'':8}  </span>")

    print(json.dumps({
        "text": "\n".join(output_lines),
        "tooltip": "Bluetooth Connections"
    }))

if __name__ == "__main__":
    main()
