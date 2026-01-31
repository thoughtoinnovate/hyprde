#!/usr/bin/env python3
import os
import tomllib
import subprocess
import sys
import json

CONFIG_FILE = os.path.expanduser("~/.config/hypr/hyprde.toml")
BUILD_SCRIPT = os.path.expanduser("~/.config/hypr/build_config.py")

def wofi_menu(options, prompt="Select an option:"):
    """Displays a list of options in Wofi and returns the selected one."""
    options_str = "\n".join(options)
    try:
        result = subprocess.run(
            ["wofi", "--dmenu", "--prompt", prompt, "--conf", os.path.expanduser("~/.config/wofi/config"), "--style", os.path.expanduser("~/.config/wofi/style.css")],
            input=options_str,
            text=True,
            capture_output=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def wofi_input(prompt, default_val=""):
    """Opens Wofi to accept text input."""
    # Note: Wofi doesn't have a native 'input box' mode in dmenu,
    # but we can simulate it or just use the dmenu filter as input if we treat it right.
    # A common trick is to run wofi with no input lines and just capture what the user types (if they hit enter).
    # However, wofi dmenu filters.
    # A better way for input is using a simple zenity or just relying on the user typing in the box and hitting enter if we pass a dummy list.
    
    # Let's try passing the default value as the only option, but the user can type something else.
    # Ideally, for text input, 'zenity --entry' is standard and installed in your packge list.
    try:
        result = subprocess.run(
            ["zenity", "--entry", "--title", "HyprDE Settings", "--text", prompt, "--entry-text", str(default_val)],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def load_config():
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)

def save_config(data):
    """
    A simple TOML serializer since Python stdlib is read-only for TOML.
    We handle the specific types used in hyprde.toml.
    """
    lines = []
    
    def format_val(val):
        if isinstance(val, bool):
            return str(val).lower()
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, list):
            # Formats list of strings ["a", "b"]
            items = ", ".join([f'"{x}"' if isinstance(x, str) else str(x) for x in val])
            return f"[{items}]"
        return f'"{val}"'

    for section, content in data.items():
        lines.append(f"[{section}]")
        for key, val in content.items():
            # Handle nested dicts (like input.touchpad)
            if isinstance(val, dict):
                 lines.append(f"[{section}.{key}]")
                 for k, v in val.items():
                     lines.append(f'{k} = {format_val(v)}')
                 # We don't support deeper nesting for now in this simple writer
            else:
                lines.append(f"{key} = {format_val(val)}")
        lines.append("") # Empty line between sections

    with open(CONFIG_FILE, "w") as f:
        f.write("\n".join(lines))

def check_conflicts(data):
    """Analyzes keybindings for duplicates."""
    if "binds" not in data:
        return "No binds section found."
    
    binds = data["binds"]
    mapped = {} # "MOD+KEY" -> [Actions]
    
    # Sections to check
    sections = ["normal", "release", "mouse", "repeat", "locked"]
    
    for sec in sections:
        if sec not in binds: continue
        for item in binds[sec].get("list", []):
            # item format: "MOD, KEY, dispatcher, arg"
            parts = [p.strip() for p in item.split(",")]
            if len(parts) < 2: continue
            
            key_combo = f"{parts[0]} + {parts[1]}"
            action = ", ".join(parts[2:])
            
            if key_combo in mapped:
                mapped[key_combo].append(f"[{sec}] {action}")
            else:
                mapped[key_combo] = [f"[{sec}] {action}"]
    
    conflicts = []
    for k, v in mapped.items():
        if len(v) > 1:
            conflicts.append(f"CONFLICT: {k}\n" + "\n".join([f"  - {x}" for x in v]))
            
    if not conflicts:
        return "No conflicts found."
    return "\n\n".join(conflicts)

def main():
    data = load_config()
    
    # Flatten the menu for main sections
    # structure: "Section > Key : CurrentValue"
    menu_map = {}
    display_list = []
    
    # Icons for sections
    icons = {
        "wallpapers": "󰸉",
        "idle": "󰒲",
        "nightlight": "",
        "general": "",
        "decoration": "",
        "animations": "",
        "input": "",
        "misc": "",
        "binds": "",
        "programs": "",
        "monitors": ""
    }

    # Special Actions (Main Menu)
    display_list.append("  Configure Keybindings")
    menu_map["  Configure Keybindings"] = "SUBMENU_BINDS"
    
    # Helper to traverse and build menu
    # We focus on the most editable sections
    editable_sections = ["wallpapers", "idle", "nightlight", "general", "decoration", "animations", "input", "misc"]
    
    for section in editable_sections:
        if section not in data: continue
        
        sect_icon = icons.get(section, "")
        for key, val in data[section].items():
            if isinstance(val, dict):
                # Nested (e.g., input.touchpad)
                for subk, subv in val.items():
                    display = f"{sect_icon}  {section}.{key} > {subk} : {subv}"
                    menu_map[display] = (section, key, subk, subv)
                    display_list.append(display)
            else:
                display = f"{sect_icon}  {section} > {key} : {val}"
                menu_map[display] = (section, key, None, val)
                display_list.append(display)

    display_list.sort()
    choice = wofi_menu(display_list, "HyprDE Settings")
    
    if not choice:
        return

    # Handle Submenu: Keybindings
    if menu_map.get(choice) == "SUBMENU_BINDS":
        binds_menu_map = {}
        binds_display_list = []
        
        # Conflict Checker Option
        binds_display_list.append("  CHECK BINDING CONFLICTS")
        binds_menu_map["  CHECK BINDING CONFLICTS"] = "CONFLICTS"
        
        # Populate Binds
        section = "binds"
        sect_icon = icons.get(section, "")
        if section in data:
            for sub_sec in ["normal", "release", "repeat", "locked"]:
                if sub_sec in data["binds"]:
                    idx = 0
                    for b in data["binds"][sub_sec].get("list", []):
                        display = f"{sect_icon}  {sub_sec} > #{idx} : {b}"
                        binds_menu_map[display] = (section, sub_sec, idx, b)
                        binds_display_list.append(display)
                        idx += 1
        
        # Show Submenu
        binds_choice = wofi_menu(binds_display_list, "Keybindings")
        if not binds_choice: return
        
        if binds_menu_map.get(binds_choice) == "CONFLICTS":
            report = check_conflicts(data)
            subprocess.run(["zenity", "--info", "--title", "Conflict Report", "--text", report, "--no-wrap"])
            return
            
        # Select Binding to Edit
        if binds_choice not in binds_menu_map: return
        
        sec, key, subk, current_val = binds_menu_map[binds_choice]
        
        # Edit Binding Logic
        new_val = wofi_input(f"Edit Binding {key} #{subk}", current_val)
        if new_val and new_val != current_val:
            data[sec][key]["list"][subk] = new_val
            save_config(data)
            subprocess.run(["python3", BUILD_SCRIPT])
            subprocess.run(["notify-send", "Settings Saved", "Keybinding updated. Reloading Hyprland..."])
            subprocess.run(["hyprctl", "reload"])
        return

    # Main Menu Selection Logic
    if choice not in menu_map:
        return 
        
    sec, key, subk, current_val = menu_map[choice]
    
    # Edit Logic
    new_val = None
    
    if isinstance(current_val, bool):
        # Toggle for booleans
        toggle_opts = [f"true ({'Current' if current_val else 'Switch'})", f"false ({'Current' if not current_val else 'Switch'})" ]
        sel = wofi_menu(toggle_opts, f"Set {key}")
        if sel:
            new_val = True if "true" in sel else False
            
    else:
        # Text input for others
        prompt = f"Edit {key}"
        if subk: prompt += f".{subk}"
        user_input = wofi_input(prompt, current_val)
        if user_input is not None:
            # Try to convert to number if it looks like one
            if user_input.lower() == "true": new_val = True
            elif user_input.lower() == "false": new_val = False
            elif user_input.isdigit(): new_val = int(user_input)
            else:
                try:
                    new_val = float(user_input)
                except ValueError:
                    new_val = user_input

    # Save and Apply
    if new_val is not None and new_val != current_val:
        if subk:
            data[sec][key][subk] = new_val
        else:
            data[sec][key] = new_val
            
        save_config(data)
        
        # Run Build
        subprocess.run(["python3", BUILD_SCRIPT])
        
        # Reload Hyprland (or specific services)
        # reload dynamic wallpapers if that was changed
        if sec == "wallpapers":
             subprocess.run(["bash", os.path.expanduser("~/.config/hypr/scripts/wallpaper-ctrl.sh"), "toggle"])
        
        subprocess.run(["notify-send", "Settings Saved", f"{key} updated to {new_val}"])

if __name__ == "__main__":
    main()
