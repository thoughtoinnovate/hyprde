#!/usr/bin/env python3
import sys
import re
import os
import subprocess

LUA_CONF = os.path.expanduser("~/.config/hypr/hyprland.lua")
if not os.path.exists(LUA_CONF):
    LUA_CONF = os.path.expanduser("~/.config/hypr/hyprland.conf")

with open(LUA_CONF, "r", encoding="utf-8") as f:
    lines = f.readlines()

categories = {
    "scroll_layout": [],
    "window_management": [],
    "focus_movement": [],
    "workspaces": [],
    "media_controls": [],
    "apps_tools": []
}

def get_desc(action):
    action = action.lower()
    if "killactive" in action or "window.close" in action: return "󰅖 Kill Window"
    if "fullscreen" in action: return "󰊓 Toggle Fullscreen"
    if "ghostty" in action or "kitty" in action: return " Open Terminal"
    if "thunar" in action or "dolphin" in action: return "󰉋 Open File Manager"
    if "togglefloating" in action or "window.float" in action: return "󰉣 Toggle Floating"
    if "hyprlock" in action: return "󰌾 Lock Screen"
    if "pseudo" in action: return "󰘔 Toggle Pseudo Tiling"
    if "togglesplit" in action: return "󰘕 Toggle Split Layout"
    if "movefocus" in action or "focus({ direction" in action:
        if "l" in action or "left" in action: return "󰁍 Move Focus Left"
        if "r" in action or "right" in action: return "󰁎 Move Focus Right"
        if "u" in action or "up" in action: return "󰁟 Move Focus Up"
        if "d" in action or "down" in action: return "󰁆 Move Focus Down"
        return "󰌌 Move Focus"
    if "resizeactive, 0 -10" in action: return "󰁝 Resize Window Up"
    if "resizeactive, 0 10" in action: return "󰁅 Resize Window Down"
    if "resizeactive, -10 0" in action: return "󰁜 Resize Window Left"
    if "resizeactive, 10 0" in action: return "󰁞 Resize Window Right"
    if "workspace, " in action or "focus({ workspace" in action: return "󰪱 Switch Workspace"
    if "movetoworkspace, " in action or "window.move({ workspace" in action: return "󰪱 Move to Workspace"
    if "specialworkspace" in action: return "󰪱 Toggle Special Workspace"
    if "audio" in action or "volume" in action: return "󰕾 Audio Control"
    if "brightness" in action: return "󰃠 Brightness Control"
    if "mic" in action: return "󰍬 Mic Control"
    if "camera" in action: return "󰄀 Camera Control"
    if "playerctl" in action: return "󰎆 Media Playback"
    if "settings_manager" in action: return "󰒓 Settings Manager"
    if "dock-toggle" in action: return "󰏝 Toggle Dock"
    if "hyprsearch" in action or "wofi" in action: return "󰀻 Application Launcher"
    if "screenshot" in action: return "󰄀 Screenshot"
    if "shortcuts-help" in action: return "󰋙 Show Shortcuts Help"
    if "file_search" in action: return "󰈞 File Search"
    if "session_menu" in action: return "󰀻 Session Menu"
    if "temperature" in action: return "󰔏 Temperature Monitor"
    if "gpu" in action: return "󰾲 GPU Monitor"
    if "power" in action: return "󰚥 Power Management"
    if "bluetooth" in action: return "󰂯 Bluetooth Control"
    if "wifi" in action: return "󰖩 WiFi Control"
    if "gamma" in action: return "󰌶 Eye Comfort Toggle"
    if "waybars" in action: return "󰀻 Status Bar / Control Center"
    return "󰀻 Custom Action"

bind_pattern = re.compile(r'^hl\.bind\("([^"]+)",\s*(.+)\)')
for line in lines:
    m = bind_pattern.search(line)
    if not m:
        continue
    keys = m.group(1).upper()
    keys = keys.replace("SHIFT", "⇧").replace("CTRL", "⌃").replace("ALT", "⌥").replace("SUPER", "⌘")
    action = m.group(2)
    desc = get_desc(action)
    entry = f"  {keys} : {desc}"
    
    if "layout" in action or "split" in action: categories["scroll_layout"].append(entry)
    elif "close" in action or "fullscreen" in action or "exec" in action and ("ghostty" in action or "thunar" in action) or "float" in action or "hyprlock" in action: categories["window_management"].append(entry)
    elif "focus" in action or "resize" in action or "movewindow" in action: categories["focus_movement"].append(entry)
    elif "workspace" in action: categories["workspaces"].append(entry)
    elif "audio" in action or "brightness" in action or "mic" in action or "camera" in action: categories["media_controls"].append(entry)
    else: categories["apps_tools"].append(entry)

out = ["󰋙 HYPROCKET SHORTCUTS HELP\n──────────────────────\n"]
if categories["scroll_layout"]: out.extend(["󰘕 SCROLL LAYOUT\n────────────────", *categories["scroll_layout"], ""])
if categories["window_management"]: out.extend(["󰖯 WINDOW MANAGEMENT\n───────────────────", *categories["window_management"], ""])
if categories["focus_movement"]: out.extend(["󰌌 FOCUS & MOVEMENT\n──────────────────", *categories["focus_movement"], ""])
if categories["workspaces"]: out.extend(["󰪱 WORKSPACES\n─────────────", *categories["workspaces"], ""])
if categories["media_controls"]: out.extend(["󰕾 MEDIA CONTROLS\n─────────────────", *categories["media_controls"], ""])
if categories["apps_tools"]: out.extend(["󰀻 APPLICATIONS & TOOLS\n───────────────────────", *categories["apps_tools"], ""])
out.append("󰌍 Press ESC to close")

text = "\n".join(out)
if "--text" in sys.argv:
    print(text)
else:
    process = subprocess.Popen(["wofi", "--dmenu", "--prompt", "Hyprocket Shortcuts (ESC to close)", "--width", "800", "--height", "600", "--location", "center", "--insensitive", "--cache-file", "/dev/null"], stdin=subprocess.PIPE)
    process.communicate(input=text.encode())
