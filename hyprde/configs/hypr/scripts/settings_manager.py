#!/usr/bin/env python3
import subprocess
import os
import json
import sys
import re
import tomlkit

# Paths
# Try to find config relative to script for dev/repo usage, fallback to ~/.config/hypr
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(SCRIPT_DIR, "wallpaper-ctrl.sh")):
    CONFIG_DIR = os.path.dirname(SCRIPT_DIR) # go up from scripts/ to hypr/
else:
    CONFIG_DIR = os.path.expanduser("~/.config/hypr")
    
TOML_CONFIG = os.path.join(CONFIG_DIR, "hyprde.toml")
BUILD_SCRIPT = os.path.join(CONFIG_DIR, "build_config.py")

# Base path for other configs
# If we are in hyprde/hypr/scripts, configs are in hyprde/
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))

def get_path(rel_path, fallback_path):
    # Check in repo first
    repo_p = os.path.join(REPO_ROOT, "hyprde/configs", rel_path)
    if os.path.exists(repo_p): return repo_p
    return os.path.expanduser(fallback_path)

WAYBAR_MAIN_CONFIG = get_path("waybar/config", "~/.config/waybar/config")
WAYBAR_CC_CONFIG = get_path("waybar/control-center/config", "~/.config/waybar/control-center/config")
WAYBAR_METRICS_CONFIG = get_path("waybar/system-metrics/config", "~/.config/waybar/system-metrics/config")

WAYBAR_MAIN_STYLE = get_path("waybar/style.css", "~/.config/waybar/style.css")
WAYBAR_CC_STYLE = get_path("waybar/control-center/style.css", "~/.config/waybar/control-center/style.css")
WAYBAR_METRICS_STYLE = get_path("waybar/system-metrics/style.css", "~/.config/waybar/system-metrics/style.css")
WAYBAR_BT_STYLE = get_path("waybar/bluetooth-center/style.css", "~/.config/waybar/bluetooth-center/style.css")
WOFI_STYLE = get_path("wofi/style.css", "~/.config/wofi/style.css")

def wofi_menu(options, prompt="Select"):
    cmd = [
        "wofi", "--dmenu", "--prompt", prompt, 
        "--conf", os.path.expanduser("~/.config/wofi/config"), 
        "--style", os.path.expanduser("~/.config/wofi/style.css"),
        "--font", "JetBrainsMono Nerd Font 13",
        "--width", "800",
        "--height", "450"
    ]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, _ = process.communicate(input="\n".join(options))
    return stdout.strip()

def wofi_input(prompt, placeholder=""):
    """Uses Zenity for text input to provide a proper pre-filled text box."""
    cmd = [
        "zenity", "--entry", 
        "--title=HyprDE Settings", 
        f"--text={prompt}", 
        f"--entry-text={placeholder}",
        "--width=500"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        # Fallback to wofi if zenity is missing
        cmd = ["wofi", "--dmenu", "--prompt", prompt, "--font", "JetBrainsMono Nerd Font 13"]
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, _ = process.communicate(input=placeholder)
        return stdout.strip()
    return None

def load_config():
    try:
        with open(TOML_CONFIG, 'r') as f: return tomlkit.load(f)
    except: return tomlkit.parse("")

def save_config(data):
    with open(TOML_CONFIG, 'w') as f: f.write(tomlkit.dumps(data))

def update_component_css_variable(var_name, value):
    tag_map = {
        "--main-font-size": "SETTINGS_MAIN_FONT_SIZE",
        "--panel-font-size": "SETTINGS_PANEL_FONT_SIZE",
        "--icon-spacing": "SETTINGS_ICON_SPACING",
        "--bar-opacity": "SETTINGS_BAR_OPACITY",
        "--wofi-opacity": "SETTINGS_WOFI_OPACITY"
    }
    target_tag = tag_map.get(var_name)
    if not target_tag: return False
    paths = [WAYBAR_MAIN_STYLE, WAYBAR_CC_STYLE, WAYBAR_METRICS_STYLE, WAYBAR_BT_STYLE, WOFI_STYLE]
    success = False
    for style_path in paths:
        if not os.path.exists(style_path): continue
        try:
            with open(style_path, 'r') as f: lines = f.readlines()
            new_lines = []
            for line in lines:
                if target_tag in line:
                    indent = line[:line.find(line.strip())]
                    if "font-size" in line: new_lines.append(f"{indent}font-size: {value}; /* {target_tag} */\n")
                    elif "margin" in line: new_lines.append(f"{indent}margin: 0px {value} 0px {value}; /* {target_tag} */\n")
                    elif "background-color" in line and "alpha(" in line:
                        new_line = re.sub(r'alpha\(([^,]+),\s*([^)]+)\)', f'alpha(\\1, {value})', line)
                        new_lines.append(new_line)
                    else: new_lines.append(line)
                else: new_lines.append(line)
            with open(style_path, 'w') as f: f.writelines(new_lines)
            success = True
        except: pass
    if success: subprocess.run(["pkill", "-USR2", "waybar"])
    return success

def get_module_icon(config, module_name):
    fallbacks = {
        "cpu": "", "memory": "", "battery": "🔋", "pulseaudio": "󰕾", 
        "network": "󰤨", "backlight": "󰃠", "clock": "󰥔", "tray": "󰬬",
        "custom/ps_toggle": "󰈐", "custom/metrics": "", "custom/ctrl": "󰍜",
        "custom/mic": "󰍬", "custom/camera": "󰕧", "custom/wallpaper": "󰸉",
        "hyprland/workspaces": "󰄵", "hyprland/window": "󰖲"
    }
    mod_cfg = config.get(module_name, {})
    if not isinstance(mod_cfg, dict): return fallbacks.get(module_name, "󰄱")
    icons = mod_cfg.get("format-icons")
    if isinstance(icons, list) and len(icons) > 0: return icons[0]
    elif isinstance(icons, dict): 
        d = icons.get("default")
        return d[0] if isinstance(d, list) and d else fallbacks.get(module_name, "󰄱")
    return fallbacks.get(module_name, "󰄱")

def handle_monitors_submenu():
    data = load_config()
    rules = data.get("monitors", {}).get("rules", [])
    
    options = ["󰐕  Add New Monitor Rule"]
    for idx, rule in enumerate(rules):
        options.append(f"󰍹  Rule {idx+1}: {rule}")
    options.append("󰅙  Back")
    
    choice = wofi_menu(options, "Monitor Layout")
    if not choice or "Back" in choice: return False
    
    if "Add New" in choice:
        new_rule = wofi_input("Define New Monitor (Name, Res, Pos, Scale):", ", highres, auto, 1.0")
        if new_rule:
            rules.append(new_rule)
            data.setdefault("monitors", {})["rules"] = rules
            save_config(data)
            subprocess.run(["python3", BUILD_SCRIPT])
            subprocess.run(["hyprctl", "reload"])
            return True
    elif "Rule" in choice:
        try:
            match = re.search(r'Rule (\d+):', choice)
            if not match: return True
            idx = int(match.group(1)) - 1
            current_rule = rules[idx]
            
            sub_opts = ["󰏫  Edit Configuration", "󰆴  Remove Rule", "󰅙  Cancel"]
            sub_choice = wofi_menu(sub_opts, f"Monitor Rule {idx+1}")
            
            if "Edit" in sub_choice:
                new_val = wofi_input("Modify Monitor Rule:", current_rule)
                if new_val: rules[idx] = new_val
            elif "Remove" in sub_choice:
                rules.pop(idx)
            else: return True
            
            data["monitors"]["rules"] = rules
            save_config(data)
            subprocess.run(["python3", BUILD_SCRIPT])
            subprocess.run(["hyprctl", "reload"])
        except Exception as e:
            subprocess.run(["notify-send", "Error", str(e)])
        return True
    return True

def handle_generic_submenu(section_name, title):
    data = load_config()
    section = data.get(section_name, {})
    options = []
    keys_map = {}
    
    for key, val in section.items():
        if isinstance(val, (str, int, float, bool)):
            display = f"󰒓  {key}: {val}"
            options.append(display)
            keys_map[display] = key
            
    options.append("󰅙  Back")
    
    choice = wofi_menu(options, title)
    if not choice or "Back" in choice: return False
    
    key = keys_map.get(choice)
    if not key: return True
    current_val = section[key]
    
    if isinstance(current_val, bool):
        section[key] = not current_val
    elif key in ["background", "profile_image"]:
        # Use file picker for images
        cmd = ["zenity", "--file-selection", f"--title=Select {key.replace('_', ' ').title()}", "--file-filter=*.png *.jpg *.jpeg *.webp"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                section[key] = res.stdout.strip()
        except: pass
    else:
        new_val = wofi_input(f"Update {key}:", str(current_val))
        if new_val:
            try:
                if isinstance(current_val, int): section[key] = int(new_val)
                elif isinstance(current_val, float): section[key] = float(new_val)
                else: section[key] = new_val
            except: section[key] = new_val
            
    data[section_name] = section
    save_config(data)
    subprocess.run(["python3", BUILD_SCRIPT])
    subprocess.run(["hyprctl", "reload"])
    return True

def handle_appearance_submenu():
    themes_dir = os.path.join(CONFIG_DIR, "themes")
    current_symlink = os.path.join(themes_dir, "current.css")
    
    current_theme = "Dark"
    try:
        if os.path.exists(current_symlink):
            target = os.readlink(current_symlink)
            if "light" in target:
                current_theme = "Light"
    except:
        pass

    data = load_config()
    decoration = data.get("decoration", {})
    waybar_op = decoration.get("waybar_opacity", 0.5)
    wofi_op = decoration.get("wofi_opacity", 0.95)

    options = [
        f"󰔎  Toggle Theme (Current: {current_theme})",
        f"󰃟  Waybar Opacity (Current: {waybar_op})",
        f"󰓅  Wofi Opacity (Current: {wofi_op})",
        "󰅙  Back"
    ]
    
    choice = wofi_menu(options, "Appearance")
    if not choice or "Back" in choice: return False
    
    if "Toggle Theme" in choice:
        script_path = os.path.join(CONFIG_DIR, "scripts/theme-ctrl.sh")
        subprocess.run([script_path, "toggle"])
    
    elif "Waybar Opacity" in choice:
        val = wofi_input("Set Waybar Opacity (0.1 - 1.0):", str(waybar_op))
        if val:
            try:
                f_val = float(val)
                if 0.1 <= f_val <= 1.0:
                    decoration["waybar_opacity"] = f_val
                    data["decoration"] = decoration
                    save_config(data)
                    update_component_css_variable("--bar-opacity", val)
            except ValueError: pass

    elif "Wofi Opacity" in choice:
        val = wofi_input("Set Wofi Opacity (0.1 - 1.0):", str(wofi_op))
        if val:
            try:
                f_val = float(val)
                if 0.1 <= f_val <= 1.0:
                    decoration["wofi_opacity"] = f_val
                    data["decoration"] = decoration
                    save_config(data)
                    update_component_css_variable("--wofi-opacity", val)
            except ValueError: pass
        
    return True

def handle_shell_submenu():
    options = [
        "󰃚  Toggle Waybar Autohide",
        "󰓅  Modules: Visibility & Groups",
        "󰙏  Modules: Text Labels On/Off",
        "󰃢  Styling: Font & Spacing",
        "󰆒  Docking: Layout & Position",
        "󰅙  Back to Main Menu"
    ]
    choice = wofi_menu(options, "Shell & Bar")
    if not choice or "Back" in choice: return False

    if "Autohide" in choice:
        data = load_config()
        progs = data.get("programs", {})
        current = progs.get("autohide_bar", False)
        progs["autohide_bar"] = not current
        data["programs"] = progs
        save_config(data)
        subprocess.run(["python3", BUILD_SCRIPT])
        return True

    elif "Visibility" in choice:
        bars = {"󰃚 Status Bar": WAYBAR_MAIN_CONFIG, "󰕮 Control Center": WAYBAR_CC_CONFIG, "󰪥 System Metrics": WAYBAR_METRICS_CONFIG}
        b_choice = wofi_menu(list(bars.keys()), "Select Bar")
        if not b_choice: return True
        path = bars[b_choice]
        try:
            with open(path, 'r') as f: config = json.load(f)
            active = []
            for k, v in config.items():
                if k.startswith("group/") and "modules" in v: active.extend(v["modules"])
            all_mods = [k for k in config.keys() if not k.startswith("group/") and k not in ["id", "layer", "position", "margin", "spacing", "modules-right", "modules-left", "modules-center", "tray"]]
            mod_opts = [f"{('󰄬' if m in active else '󰄱')} {get_module_icon(config, m)}  {m}" for m in sorted(all_mods)]
            m_choice = wofi_menu(mod_opts, "Toggle Module")
            if m_choice:
                target = m_choice.split()[-1]
                found = False
                for k, v in config.items():
                    if k.startswith("group/") and "modules" in v:
                        if target in v["modules"]:
                            v["modules"].remove(target)
                            found = True
                if not found:
                    for k, v in config.items():
                        if k.startswith("group/") and "modules" in v:
                            v["modules"].append(target)
                            break
                with open(path, 'w') as f: json.dump(config, f, indent=4)
                subprocess.run(["pkill", "-USR2", "waybar"])
        except: pass

    elif "Label Mode" in choice:
        bars = {"󰃚 Status Bar": WAYBAR_MAIN_CONFIG, "󰕮 Control Center": WAYBAR_CC_CONFIG, "󰪥 System Metrics": WAYBAR_METRICS_CONFIG}
        b_choice = wofi_menu(list(bars.keys()), "Select Bar")
        if not b_choice: return True
        path = bars[b_choice]
        try:
            with open(path, 'r') as f: config = json.load(f)
            capable = ["cpu", "memory", "battery", "pulseaudio", "network"]
            m_choice = wofi_menu([f"{get_module_icon(config, m)} {m}" for m in capable], "Toggle Labels")
            if m_choice:
                mod = m_choice.split()[-1]
                mod_cfg = config.get(mod, {})
                current = mod_cfg.get("format", "")
                mod_cfg["format"] = "{icon}" if "{" in current and current != "{icon}" else ("{icon} {volume}%" if mod=="pulseaudio" else "{icon} {}%")
                config[mod] = mod_cfg
                with open(path, 'w') as f: json.dump(config, f, indent=4)
                subprocess.run(["pkill", "-USR2", "waybar"])
        except: pass

    elif "Styling" in choice and "Font" in choice:
        opts = ["󰦨 Main Bar Size", "󰦪 Panel Size", "󰦫 Module Gaps"]
        s_choice = wofi_menu(opts, "Styling")
        if not s_choice: return True
        val = wofi_input("Update Style Value:", "17px")
        if val:
            var = "--main-font-size" if "Main" in s_choice else "--panel-font-size" if "Panel" in s_choice else "--icon-spacing"
            update_component_css_variable(var, val)

    elif "Docking" in choice:
        bars = {"󰃚 Status Bar": WAYBAR_MAIN_CONFIG, "󰕮 Control Center": WAYBAR_CC_CONFIG, "󰪥 System Metrics": WAYBAR_METRICS_CONFIG}
        b_choice = wofi_menu(list(bars.keys()), "Select Bar")
        if b_choice:
            path = bars[b_choice]
            with open(path, 'r') as f: config = json.load(f)
            d_opts = [f"󰆒 Position: {config.get('position')}", f"󰃸 Margins: {config.get('margin')}"]
            d_choice = wofi_menu(d_opts, "Docking")
            if "Position" in d_choice:
                pos = wofi_menu(["top", "bottom", "left", "right"])
                if pos: config["position"] = pos
            elif "Margins" in d_choice:
                marg = wofi_input("Edit Margins:", config.get('margin'))
                if marg: config["margin"] = marg
            with open(path, 'w') as f: json.dump(config, f, indent=4)
            subprocess.run(["pkill", "-USR2", "waybar"])

    return True

def handle_plugins_submenu():
    data = load_config()
    plugins_cfg = data.get("plugins", {})
    enabled_plugins = plugins_cfg.get("enabled", [])
    
    # Common Hyprland plugins that HyprDE supports or are popular
    common_plugins = ["hyprexpo", "hyprscrolling", "hyprbars", "hyprfocus", "hyprtrails"]
    
    # Check what's actually installed via hyprpm list
    installed_plugins = []
    try:
        output = subprocess.check_output(["hyprpm", "list"], stderr=subprocess.STDOUT, text=True)
        for p in common_plugins:
            if f"Plugin {p}" in output:
                installed_plugins.append(p)
    except: pass

    options = []
    for p in common_plugins:
        status = "󰄬" if p in enabled_plugins else "󰄱"
        inst_mark = " (Installed)" if p in installed_plugins else " (Not Installed)"
        options.append(f"{status}  {p}{inst_mark}")
    
    options.append("󰆴  Remove All Plugins & Repos")
    options.append("󰅙  Back")
    
    choice = wofi_menu(options, "Manage Plugins")
    if not choice or "Back" in choice: return False
    
    if "Remove All" in choice:
        confirm = wofi_menu(["Yes, Uninstall All", "No, Cancel"], "This will uninstall the official hyprland-plugins repository and disable all plugins. Proceed?")
        if "Yes" in confirm:
            subprocess.run(["notify-send", "HyprDE Plugins", "Uninstalling all plugins..."])
            # Launch in terminal to show progress and handle potential sudo prompt if hyprpm needs it
            term = data.get("programs", {}).get("terminal", "ghostty")
            remove_cmd = "echo 'Uninstalling Hyprland Plugins repository...'; " \
                         "hyprpm remove hyprland-plugins; " \
                         "echo -e '\\nUninstallation finished. Press Enter to close...'; read"
            subprocess.run([term, "-e", "bash", "-c", remove_cmd])
            
            # Clear TOML config
            plugins_cfg["enabled"] = []
            data["plugins"] = plugins_cfg
            save_config(data)
            subprocess.run(["python3", BUILD_SCRIPT])
            subprocess.run(["hyprctl", "reload"])
            subprocess.run(["notify-send", "HyprDE Plugins", "All plugins removed and configuration cleared."])
        return True

    try:
        plugin_name = choice.split()[1] # Index 0 is icon, 1 is name
        is_enabling = plugin_name not in enabled_plugins
        
        if is_enabling:
            # Check if we need to install it first
            if plugin_name not in installed_plugins:
                confirm = wofi_menu(["Yes, Install", "No, Cancel"], f"Plugin {plugin_name} is not installed. Install via hyprpm?")
                if "Yes" in confirm:
                    subprocess.run(["notify-send", "HyprDE Plugins", f"Starting installation of {plugin_name} in terminal..."])
                    
                    # Define the installation command
                    # We use a subshell to run the commands and then wait for user input so the terminal doesn't close immediately on error/finish
                    install_cmd = f"echo -e 'Installing Hyprland Plugins repository and enabling {plugin_name}...\\n'; " \
                                 f"echo -e 'NOTE: hyprpm builds the entire official repository (including other plugins),\\n' " \
                                 f"        'but only \"{plugin_name}\" will be enabled and loaded.\\n'; " \
                                 f"hyprpm add https://github.com/hyprwm/hyprland-plugins || hyprpm update; " \
                                 f"hyprpm enable {plugin_name}; " \
                                 f"hyprpm reload -n; " \
                                 f"echo -e '\\nInstallation finished. \"{plugin_name}\" is now active.'; " \
                                 f"echo -e 'Press Enter to close...'; read"
                    
                    # Launch in the user's preferred terminal
                    # We assume the terminal supports -e for executing a command
                    # Fetch terminal from config or fallback
                    term = data.get("programs", {}).get("terminal", "ghostty")
                    subprocess.run([term, "-e", "bash", "-c", install_cmd])
                    
                    # Re-verify installation after terminal closes
                    try:
                        new_output = subprocess.check_output(["hyprpm", "list"], stderr=subprocess.STDOUT, text=True)
                        if f"Plugin {plugin_name}" in new_output and "enabled: true" in new_output:
                            pass # Success
                        else:
                            subprocess.run(["notify-send", "HyprDE Plugins", f"Installation of {plugin_name} may have failed or was cancelled."])
                            return True
                    except: pass
                    
            enabled_plugins.append(plugin_name)
        else:
            enabled_plugins.remove(plugin_name)
        
        plugins_cfg["enabled"] = enabled_plugins
        data["plugins"] = plugins_cfg
        save_config(data)
        
        # Run build script to update config (will also trigger Hyprland reload)
        subprocess.run(["python3", BUILD_SCRIPT])
        subprocess.run(["hyprctl", "reload"])
        
        status_text = "Enabled" if is_enabling else "Disabled"
        subprocess.run(["notify-send", "HyprDE Plugins", f"{status_text} {plugin_name} successfully."])
    except Exception as e:
        subprocess.run(["notify-send", "Error", str(e)])
        
    return True

def handle_keybinds_submenu():
    data = load_config()
    binds_cfg = data.get("binds", {})
    normal_binds = binds_cfg.get("normal", {}).get("list", [])
    
    options = ["󰐕  Add New Keybind"]
    for idx, bind in enumerate(normal_binds):
        options.append(f"󰌌  {idx+1}: {bind}")
    options.append("󰅙  Back")
    
    choice = wofi_menu(options, "Keyboard Binds")
    if not choice or "Back" in choice: return False
    
    if "Add New" in choice:
        new_bind = wofi_input("Define New Bind (MOD, KEY, DISPATCHER, ARGS):", "$mainMod, X, exec, notify-send 'Hello'")
        if new_bind:
            # Conflict detection
            new_key = new_bind.split(",")[0:2] # Get MOD and KEY
            for existing in normal_binds:
                if existing.split(",")[0:2] == new_key:
                    subprocess.run(["notify-send", "Conflict Detected", f"Key {new_key} is already bound!"])
                    return True
            
            normal_binds.append(new_bind)
            data.setdefault("binds", {}).setdefault("normal", {})["list"] = normal_binds
            save_config(data)
            subprocess.run(["python3", BUILD_SCRIPT])
            return True
            
    elif "󰌌" in choice:
        try:
            match = re.search(r'(\d+):', choice)
            if not match: return True
            idx = int(match.group(1)) - 1
            current_bind = normal_binds[idx]
            
            sub_opts = ["󰏫  Edit Keybind", "󰆴  Remove Keybind", "󰅙  Cancel"]
            sub_choice = wofi_menu(sub_opts, f"Edit Bind {idx+1}")
            
            if "Edit" in sub_choice:
                new_val = wofi_input("Modify Keybind:", current_bind)
                if new_val: 
                    # Conflict detection for edit
                    new_key = new_val.split(",")[0:2]
                    for i, existing in enumerate(normal_binds):
                        if i != idx and existing.split(",")[0:2] == new_key:
                            subprocess.run(["notify-send", "Conflict Detected", f"Key {new_key} is already bound!"])
                            return True
                    normal_binds[idx] = new_val
            elif "Remove" in sub_choice:
                normal_binds.pop(idx)
            else: return True
            
            data["binds"]["normal"]["list"] = normal_binds
            save_config(data)
            subprocess.run(["python3", BUILD_SCRIPT])
        except Exception as e:
            subprocess.run(["notify-send", "Error", str(e)])
        return True
    return True

def main():
    while True:
        menu_items = [
            "── Workspace ──",
            "󰍹  Monitor Layout",
            "󰌌  Input & Trackpad",
            "󰌌  Keyboard Binds",
            "── Interface ──",
            "󰔎  Appearance: Dark / Light",
            "󰸉  Wallpapers",
            "󰸉  Lock Screen Visuals",
            "󰓅  Shell & Status Bar",
            "󰏘  Window Decoration",
            "󰕧  Motion & Animations",
            "── System ──",
            "󰖔  Night Light",
            "󰒲  Power & Idle (Timeouts)",
            "󰏗  Software Plugins",
            "󰀉  Session Settings",
            "󰒓  System Internals",
            "󰅙  Close Settings"
        ]
        choice = wofi_menu(menu_items, "HyprDE Settings")
        if not choice or "Close" in choice: break
        
        if "Monitor" in choice:
            while handle_monitors_submenu(): pass
        elif "Input" in choice:
            while handle_generic_submenu("input", "Input Devices"): pass
        elif "Keyboard Binds" in choice:
            while handle_keybinds_submenu(): pass
        elif "Appearance" in choice:
            while handle_appearance_submenu(): pass
        elif "Input" in choice:
            while handle_generic_submenu("input", "Input Devices"): pass
        elif "Decoration" in choice:
            while handle_generic_submenu("decoration", "Window Style"): pass
        elif "Animations" in choice:
            while handle_generic_submenu("animations", "Motion Effects"): pass
        elif "Shell" in choice: 
            while handle_shell_submenu(): pass
        elif "Night Light" in choice:
            while handle_generic_submenu("nightlight", "Blue Light Filter"): pass
        elif "Power" in choice:
            while handle_generic_submenu("idle", "Power Management"): pass
        elif "Software Plugins" in choice:
            while handle_plugins_submenu(): pass
        elif "Wallpapers" in choice: 
            subprocess.run(["bash", os.path.join(CONFIG_DIR, "scripts/wallpaper-ctrl.sh"), "menu"])
        elif "Lock Screen" in choice:
            while handle_generic_submenu("lockscreen", "Lock Screen Style"): pass
        elif "Session" in choice: 
            subprocess.run(["bash", os.path.join(CONFIG_DIR, "scripts/session_menu.sh")])
        elif "Internals" in choice:
            while handle_generic_submenu("general", "System Internals"): pass
        
    sys.exit(0)

if __name__ == "__main__": main()