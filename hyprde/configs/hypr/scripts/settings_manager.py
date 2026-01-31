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

def get_hyprpm_status():
    """
    Parses 'hyprpm list' to get installed plugins and their status.
    Returns a dict: {plugin_name: bool_enabled}
    """
    try:
        # hyprpm list returns text output, let's parse it
        # Output format example:
        # Plugin name
        #   enabled: true
        #   ...
        result = subprocess.run(["hyprpm", "list"], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        
        plugins = {}
        current_plugin = None
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            if line.startswith("Plugin"): 
                # "Plugin some-name" or just "some-name"?
                # It usually prints just the name on a line, or "Repository ..."
                # Let's use a simpler heuristic or JSON if available (no json flag for hyprpm yet)
                pass
            
            # Simple heuristic: Lines starting with "→" or "Repository" are headers.
            # Actual plugin names are usually indented or just listed.
            # Let's try to find "enabled: true/false" and associate with previous line?
            # Actually, hyprpm list output is a bit verbose.
            # Let's use 'hyprpm list' just to verify what we have.
            pass

        # Alternate approach: We can't easily parse human output reliably without seeing it.
        # But we can assume if the user asks to enable/disable, we just run the command.
        # For the menu, we might need to rely on what we stored in TOML as the "source of truth" 
        # for what SHOULD be enabled, or just list generic options if we can't parse.
        
        # Let's try to get a list of plugins from the official repo if we can't parse local.
        # 'hyprpm update' usually lists them.
        return {} 
    except Exception:
        return {}

def run_hyprpm(cmd, args=[]):
    command = ["hyprpm", cmd] + args
    try:
        # Run in terminal because it might ask for sudo or show progress
        # We want to wait for it.
        # Construct a command that pauses only on error?
        # For better UX, let's just run it. If it fails, the user sees the output in the terminal window.
        
        full_cmd = " ".join(command)
        # Use a wrapper to capture exit code
        # We use a trick: run command; echo $? > /tmp/exitcode; read...
        
        # Actually, python's subprocess.run won't easily get the exit code of the *inner* shell command 
        # if we wrap it in a terminal emulator that detaches or returns immediately.
        # But 'ghostty -e' usually waits? No, often it returns.
        
        # Let's try running it directly with subprocess if it's not an interactive command?
        # 'hyprpm' might ask for sudo. So we DO need a terminal.
        
        # Alternative: checking if the command succeeded is hard with 'ghostty -e'.
        # Let's assume for now we just run it. 
        # But to be smarter, we can try to run 'update' if the user reports issues or we can 
        # just execute a chained command: "hyprpm enable X || (echo 'Failed...'; read)"
        
        subprocess.run(["ghostty", "-e", "bash", "-c", f"{full_cmd} || (echo ''; echo 'Command failed. Press Enter...'; read)"])
        return True
    except Exception as e:
        subprocess.run(["notify-send", "HyprPM Error", str(e)])
        return False

# ... inside main ...
# I will just update the logic flow in the main function instead of changing run_hyprpm's return signature heavily since we can't capture it easily from ghostty.
# Actually, I can just instruct the user.

# Wait, the user wants "how to fix this".
# The fix is running the installer. 
# But making the script smart is good too.

# Let's modify the 'run_hyprpm' to be simple for now as per previous instruction.
# But wait, I can't easily detect failure inside ghostty from python.
# I will stick to the previous plan: update the logic in main to be more helpful?
# No, the most robust fix is just telling the user to run the installer.

# However, the user asked "how to fix this" referring to the dependencies.
# I already answered that by updating config.yml and install.sh.

# But for the "missing?" error, it happens because 'update' wasn't run successfully.
# So I will add an explicit check: if enabling fails (which the user sees in the terminal),
# they will likely try "Update Plugins" from the menu.

# I will update 'run_hyprpm' to chained command logic so the window stays open on error, 
# which gives feedback. I already did that in the previous 'new_string' logic above? 
# No, the previous logic was: "; echo 'Press Enter to close...'; read"
# I will change it to only pause on error or always pause? 
# Always pausing is annoying for "enable" if it's fast. 
# Let's pause only on error?
# "cmd || (echo fail; read)"

# Let's refine run_hyprpm.


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
        "monitors": "",
        "plugins": ""
    }

    # Special Actions (Main Menu)
    display_list.append("  Configure Keybindings")
    menu_map["  Configure Keybindings"] = "SUBMENU_BINDS"
    
    display_list.append("  Manage Plugins")
    menu_map["  Manage Plugins"] = "SUBMENU_PLUGINS"
    
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

import urllib.request
import time
import json
from pathlib import Path

def get_available_plugins():
    """Returns a list of known official plugins, using a 24-hour cache."""
    fallback_list = [
        "hyprbars",
        "hyprexpo",
        "hyprtrails",
        "borders-plus-plus",
        "csgo-vulkan-fix",
        "hyprwinwrap",
        "hyprscrolling",
        "hyprfocus",
        "xtra-dispatchers"
    ]
    
    cache_dir = Path(os.path.expanduser("~/.cache/hypr"))
    cache_file = cache_dir / "plugin_cache.json"
    
    # Try to read cache
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                cached = json.load(f)
                # Check if cache is less than 24 hours old (86400 seconds)
                if time.time() - cached.get("timestamp", 0) < 86400:
                    return cached.get("plugins", fallback_list)
        except Exception:
            pass # invalid cache, ignore

    # Fetch from upstream
    url = "https://raw.githubusercontent.com/hyprwm/hyprland-plugins/main/hyprpm.toml"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            data = tomllib.load(response)
            # The top-level keys that are NOT 'repository' are the plugin names
            plugins = [k for k in data.keys() if k != "repository"]
            
            if plugins:
                # Save to cache
                cache_dir.mkdir(parents=True, exist_ok=True)
                with open(cache_file, "w") as f:
                    json.dump({"timestamp": time.time(), "plugins": plugins}, f)
                return plugins
    except Exception as e:
        # Silently fail to fallback
        pass
        
    return fallback_list

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
        "monitors": "",
        "plugins": ""
    }

    # Special Actions (Main Menu)
    display_list.append("  Configure Keybindings")
    menu_map["  Configure Keybindings"] = "SUBMENU_BINDS"
    
    display_list.append("  Manage Plugins")
    menu_map["  Manage Plugins"] = "SUBMENU_PLUGINS"
    
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

    # Handle Submenu: Plugins
    if menu_map.get(choice) == "SUBMENU_PLUGINS":
        pm_opts = [
            "1. Initialize/Add Official Repo (hyprland-plugins)",
            "2. Update Plugins (hyprpm update)",
            "3. Enable/Disable Plugin >"
        ]
        
        pm_choice = wofi_menu(pm_opts, "Plugin Manager")
        if not pm_choice: return
        
        if pm_choice.startswith("1."):
            run_hyprpm("add", ["https://github.com/hyprwm/hyprland-plugins"])
            # Update config to reflect we managed it
            if "plugins" in data:
                data["plugins"]["manage_official"] = True
                save_config(data)
                
        elif pm_choice.startswith("2."):
            run_hyprpm("update")
            
        elif pm_choice.startswith("3."):
            # Enable/Disable Submenu
            available = get_available_plugins()
            enabled_list = data.get("plugins", {}).get("enabled", [])
            
            plugin_display = []
            for p in available:
                status = "ON" if p in enabled_list else "OFF"
                icon = "" if p in enabled_list else ""
                plugin_display.append(f"{icon}  {p} [{status}]")
            
            # Allow manual entry too
            plugin_display.append("➕  Manual Entry...")
            
            p_choice = wofi_menu(plugin_display, "Toggle Plugins")
            if not p_choice: return
            
            target_plugin = None
            if "Manual Entry" in p_choice:
                target_plugin = wofi_input("Enter Plugin Name:")
            else:
                # Parse name from string "  hyprbars [ON]"
                parts = p_choice.split()
                if len(parts) >= 2:
                    target_plugin = parts[1]
            
            if target_plugin:
                # Toggle logic
                if target_plugin in enabled_list:
                    # Disable
                    if run_hyprpm("disable", [target_plugin]):
                        enabled_list.remove(target_plugin)
                        subprocess.run(["hyprctl", "reload"])
                        subprocess.run(["notify-send", "Plugin Manager", f"Disabled {target_plugin}"])
                else:
                    # Enable
                    if run_hyprpm("enable", [target_plugin]):
                        enabled_list.append(target_plugin)
                        subprocess.run(["hyprctl", "reload"])
                        subprocess.run(["notify-send", "Plugin Manager", f"Enabled {target_plugin}"])
                
                # Save config
                if "plugins" not in data: data["plugins"] = {}
                data["plugins"]["enabled"] = enabled_list
                save_config(data)

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
