import json
import tomllib
import urllib.request
import urllib.error
import os
import subprocess
import re
import ssl
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from lua_generator import generate_user_lua

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MAX_DOWNLOAD_SIZE = 5 * 1024 * 1024  # 5MB limit
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = True
SSL_CONTEXT.verify_mode = ssl.CERT_REQUIRED

# Determine config directory. Default to ~/.config/hypr, but allow override.
def get_config_dir() -> str:
    """Get and validate the configuration directory."""
    config_dir = os.getenv("HYPR_CONFIG_DIR")
    if config_dir:
        config_dir = os.path.abspath(os.path.expanduser(config_dir))
        dangerous_patterns = ['..', '//', '~', '$']
        if any(pattern in config_dir for pattern in dangerous_patterns):
            logger.warning(f"Potentially unsafe path in HYPR_CONFIG_DIR: {config_dir}")
            logger.info("Falling back to default config directory")
            config_dir = None

    if not config_dir:
        config_dir = os.path.join(os.path.expanduser("~"), ".config/hypr")

    return config_dir

CONFIG_DIR = get_config_dir()

def get_toml_file(config_dir):
    user_toml = os.path.join(config_dir, "hyprde.toml")
    if os.path.exists(user_toml):
        return user_toml
    return os.path.join(os.path.dirname(__file__), "hyprde.toml")

TOML_FILE = get_toml_file(CONFIG_DIR)
LUA_CONF = os.path.join(CONFIG_DIR, "hyprland.lua")

def update_waybar_autohide(autohide: bool) -> None:
    waybar_config_path = os.path.expanduser("~/.config/waybar/config")
    if not os.path.exists(waybar_config_path):
        return

    try:
        with open(waybar_config_path, 'r') as f:
            config = json.load(f)

        config["mode"] = "invisible" if autohide else "dock"

        temp_path = f"{waybar_config_path}.tmp"
        with open(temp_path, 'w') as f:
            json.dump(config, f, indent=4)
        os.replace(temp_path, waybar_config_path)
        logger.info(f"Updated Waybar autohide mode to: {'invisible' if autohide else 'dock'}")

        subprocess.run(["pkill", "-USR2", "waybar"], capture_output=True)
    except Exception as e:
        logger.error(f"Failed to update Waybar autohide mode: {e}")

def expand_user_path(path: str) -> str:
    if not path:
        return ""
    path = path.replace("$HOME", os.path.expanduser("~"))
    return os.path.expanduser(path)

def validate_shell_safe(value: str, field_name: str) -> str:
    dangerous_chars = [';', '|', '&', '$', '`', '$(', '<', '>', '\n', '\r']
    for char in dangerous_chars:
        if char in value:
            raise ValueError(f"Potentially unsafe character '{char}' in {field_name}: {value}")
    return value

def atomic_write(filepath: str, content: str, mode: str = "w") -> None:
    temp_path = f"{filepath}.tmp.{os.getpid()}"
    try:
        if 'b' in mode:
            with open(temp_path, mode) as f:
                f.write(content)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except (OSError, ValueError, TypeError):
                    pass
        else:
            with open(temp_path, mode, encoding='utf-8') as f:
                f.write(content)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except (OSError, ValueError, TypeError):
                    pass
        os.replace(temp_path, filepath)
        logger.debug(f"Atomically wrote {filepath}")
    except Exception as e:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        raise OSError(f"Failed to write {filepath}: {e}") from e

def convert_12h_to_24h(time_str: str) -> str:
    import re
    match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)", time_str.strip())
    if not match:
        raise ValueError(f"Invalid time format: {time_str}. Expected format: 'HH:MM AM/PM'")

    hours = int(match.group(1))
    minutes = int(match.group(2))
    period = match.group(3).upper()

    if hours < 1 or hours > 12:
        raise ValueError(f"Invalid hour: {hours}. Must be between 1 and 12")
    if minutes < 0 or minutes > 59:
        raise ValueError(f"Invalid minutes: {minutes}. Must be between 0 and 59")

    if period == "PM" and hours != 12:
        hours += 12
    elif period == "AM" and hours == 12:
        hours = 0

    return f"{hours:02d}:{minutes:02d}"

def generate_wallpaper_schedule_config(data: Dict[str, Any]) -> None:
    if "wallpapers" not in data:
        return

    wp = data["wallpapers"]
    schedule = wp.get("schedule", {})
    directories = wp.get("directories", {})

    try:
        morning_start = convert_12h_to_24h(schedule.get("morning_start", "6:00 AM"))
        noon_start = convert_12h_to_24h(schedule.get("noon_start", "12:00 PM"))
        evening_start = convert_12h_to_24h(schedule.get("evening_start", "6:00 PM"))
    except ValueError as e:
        logger.error(f"Invalid time format in wallpaper schedule: {e}")
        morning_start = "06:00"
        noon_start = "12:00"
        evening_start = "18:00"

    morning_dir = directories.get("morning", "morning")
    noon_dir = directories.get("noon", "noon")
    evening_dir = directories.get("evening", "evening")

    interval = wp.get("interval", 300)

    schedule_conf = f"""# Generated from hyprde.toml - Do not edit manually
# Run 'python3 build_config.py' to regenerate after TOML changes

WALLPAPER_MODE="dynamic"
WALLPAPER_MORNING_START="{morning_start}"
WALLPAPER_NOON_START="{noon_start}"
WALLPAPER_EVENING_START="{evening_start}"

WALLPAPER_MORNING_DIR="{morning_dir}"
WALLPAPER_NOON_DIR="{noon_dir}"
WALLPAPER_EVENING_DIR="{evening_dir}"

WALLPAPER_RELOAD_INTERVAL={interval}
"""

    schedule_file = os.path.join(CONFIG_DIR, "wallpaper-schedule.conf")
    atomic_write(schedule_file, schedule_conf)
    logger.info(f"Generated wallpaper schedule config at {schedule_file}")

def generate_fixed_wallpaper_config(data: Dict[str, Any]) -> None:
    if "wallpapers" not in data:
        return

    wp = data["wallpapers"]
    fixed = wp.get("fixed", {})

    wp_type = fixed.get("type", "image")
    image = fixed.get("image", "")
    directory = fixed.get("directory", "")

    fixed_conf = f"""# Generated from hyprde.toml - Do not edit manually
# Run 'python3 build_config.py' to regenerate after TOML changes

WALLPAPER_MODE="fixed"
WALLPAPER_TYPE="{wp_type}"
WALLPAPER_IMAGE="{image}"
WALLPAPER_DIRECTORY="{directory}"
"""

    fixed_file = os.path.join(CONFIG_DIR, "wallpaper-fixed.conf")
    atomic_write(fixed_file, fixed_conf)
    logger.info(f"Generated fixed wallpaper config at {fixed_file}")

def is_plugin_installed_and_enabled(plugin_name: str) -> bool:
    if not hasattr(is_plugin_installed_and_enabled, "_cache"):
        is_plugin_installed_and_enabled._cache = {}

    if plugin_name in is_plugin_installed_and_enabled._cache:
        return is_plugin_installed_and_enabled._cache[plugin_name]

    is_active = False
    try:
        if subprocess.run(["which", "hyprpm"], capture_output=True, text=True).returncode == 0:
            output = subprocess.check_output(["hyprpm", "list"], stderr=subprocess.STDOUT, text=True)
            plugin_pattern = rf"Plugin {plugin_name}\s+└─ enabled: true"
            if re.search(plugin_pattern, output, re.MULTILINE):
                is_active = True
    except Exception:
        pass

    is_plugin_installed_and_enabled._cache[plugin_name] = is_active
    return is_active

def is_plugin_enabled(data: Dict[str, Any], plugin_name: str) -> bool:
    if "plugins" not in data:
        return False

    pl = data["plugins"]

    enabled_plugins = pl.get("enabled", [])
    if plugin_name in enabled_plugins:
        return True

    if pl.get("manage_official", False):
        if "plugin" in data and plugin_name in data["plugin"]:
            return True

    return False

VALID_TOP_LEVEL_SECTIONS = {
    "monitors", "programs", "autostart", "wallpapers", "lockscreen", "idle",
    "nightlight", "plugins", "plugin", "scrolling", "launcher", "hyprrocket",
    "gesture", "submaps", "env", "input", "general", "decoration", "animations",
    "dwindle", "master", "misc", "binds", "binds_config", "rules", "custom", "color",
    "theme", "appearance", "group", "cursor", "render", "ecosystem", "debug",
    "devices", "permission", "permissions",
}

# Sections intentionally kept TOML-only (handled by scripts/sidecars, not hl.config).
# See lua_generator.EXTERNAL_SECTIONS for manager mapping.
EXTERNAL_MANAGERS = {
    "theme": "theme-ctrl.sh + ~/.config/hypr/themes/current.css",
    "appearance": "theme-ctrl.sh + Waybar/Wofi CSS",
    "launcher": "hyprsearch binary reads [launcher] live from TOML",
    "hyprrocket": "systemd timers via generate_hyrocket_systemd_units()",
    "wallpapers": "hyprpaper.conf + wallpaper-*.conf + init_wallpaper.sh",
    "lockscreen": "hyprlock.conf",
    "idle": "hypridle.conf",
    "nightlight": "gammastep/gamma.sh via screen_shader",
}


def validate_config(data: Dict[str, Any]) -> List[str]:
    """Validate TOML config and return list of warnings/errors."""
    warnings = []

    # Check for unknown top-level sections
    for key in data:
        if key not in VALID_TOP_LEVEL_SECTIONS:
            warnings.append(f"Unknown section '[{key}]' — check for typos")

    custom = data.get("custom", {})


    # Check binds section
    binds = data.get("binds", {})
    if binds:
        main_mod = binds.get("mainMod", "SUPER")
        if not isinstance(main_mod, str) or not main_mod.isupper():
            warnings.append(f"binds.mainMod should be uppercase (e.g., SUPER, ALT, CTRL). Got: {main_mod}")

    # Check monitors format
    monitors = data.get("monitors", {})
    if monitors:
        for rule in monitors.get("rules", []):
            if rule.count(",") < 1:
                warnings.append(f"Monitor rule seems malformed (needs at least 2 comma-separated fields): {rule}")

    # Info: external (TOML-only) sections are not emitted to hyprland.lua by design.
    for key in data:
        if key in EXTERNAL_MANAGERS:
            warnings.append(
                f"Section '[{key}]' is managed externally ({EXTERNAL_MANAGERS[key]}), "
                f"not emitted to hyprland.lua — intentional."
            )

    return warnings


def auto_detect_monitors() -> List[str]:
    """Auto-detect monitors via hyprctl and return monitor rules."""
    try:
        output = subprocess.check_output(["hyprctl", "monitors", "-j"], text=True)
        monitors = json.loads(output)
        rules = []
        for m in monitors:
            name = m["name"]
            w = m["width"]
            h = m["height"]
            rate = m.get("refreshRate", 60)
            x = m.get("x", 0)
            y = m.get("y", 0)
            scale = m.get("scale", 1)
            rules.append(f"{name}, {w}x{h}@{rate}, {x}x{y}, {scale}")
        if rules:
            logger.info(f"Auto-detected monitors: {', '.join(rules)}")
        return rules
    except FileNotFoundError:
        logger.info("Hyprctl not available — cannot auto-detect monitors")
        return []
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Monitor auto-detection failed: {e}")
        return []


def inject_defaults(data: Dict[str, Any]) -> Dict[str, Any]:
    """Fill in sensible defaults for common omissions."""
    data = dict(data)

    # Auto-detect monitors if section is missing or empty
    if "monitors" not in data or not data["monitors"].get("rules"):
        detected = auto_detect_monitors()
        if detected:
            data["monitors"] = {"rules": detected}

    # Ensure binds section exists with mainMod
    if "binds" not in data:
        data["binds"] = {"mainMod": "SUPER", "normal": {"list": []}}

    return data


OLD_CONFIGS = [
    os.path.join(CONFIG_DIR, "hyprland.conf"),
    os.path.join(CONFIG_DIR, "hyprland.base.conf"),
    os.path.join(CONFIG_DIR, "hyprde.generated.conf"),
]


def cleanup_old_configs() -> None:
    """Remove old hyprlang config files that are no longer generated."""
    for path in OLD_CONFIGS:
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Removed old config file: {path}")
            except OSError as e:
                logger.warning(f"Could not remove {path}: {e}")


def resolve_string(s: str, full_data: Dict[str, Any]) -> str:
    import re
    pattern = re.compile(r'\$\{([^}]+)\}')
    def replacer(match):
        path = match.group(1).split('.')
        val = full_data
        for p in path:
            if isinstance(val, dict) and p in val:
                val = val[p]
            else:
                return match.group(0)
        return str(val)
    return pattern.sub(replacer, s)

def resolve_variables(data: Any, full_data: Dict[str, Any]) -> None:
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = resolve_string(v, full_data)
            elif isinstance(v, (dict, list)):
                resolve_variables(v, full_data)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, str):
                data[i] = resolve_string(item, full_data)
            elif isinstance(item, (dict, list)):
                resolve_variables(item, full_data)

def generate_and_write_lua(data: Dict[str, Any]) -> None:
    """Generate Lua config and write to hyprland.lua. Also cleans up old configs."""
    # Clean old hyprlang configs
    cleanup_old_configs()

    # Validate
    warnings = validate_config(data)
    for w in warnings:
        logger.warning(w)

    # Inject defaults
    data = inject_defaults(data)

    logger.info(f"Generating Lua config at {LUA_CONF}...")
    lua_content = generate_user_lua(data)
    atomic_write(LUA_CONF, lua_content)
    logger.info(f"Written Lua config to {LUA_CONF}")

HYPRIDLE_CONF = os.path.join(CONFIG_DIR, "hypridle.conf")
HYPRLOCK_CONF = os.path.join(CONFIG_DIR, "hyprlock.conf")
HYPRPAPER_CONF = os.path.join(CONFIG_DIR, "hyprpaper.conf")

def generate_hyprpaper_conf(data: Dict[str, Any]) -> None:
    if "wallpapers" not in data:
        return

    logger.info(f"Generating hyprpaper config at {HYPRPAPER_CONF}...")
    wp = data["wallpapers"]
    mode = wp.get("mode", "fixed")

    ipc = "on"
    preload_list = []
    wallpaper_list = []

    if mode == "fixed":
        fixed = wp.get("fixed", {})
        wp_type = fixed.get("type", "image")

        if wp_type == "image":
            image_path = fixed.get("image", "")
            if image_path:
                expanded_path = expand_user_path(image_path)
                preload_list.append(expanded_path)
                wallpaper_list.append(f",{expanded_path}")
        elif wp_type == "directory":
            dir_path = expand_user_path(fixed.get("directory", ""))
            if dir_path and os.path.isdir(dir_path):
                import glob
                files = []
                for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp']:
                    files.extend(glob.glob(os.path.join(dir_path, ext)))
                if files:
                    import random
                    wallpaper = random.choice(files)
                    preload_list.append(wallpaper)
                    wallpaper_list.append(f",{wallpaper}")

    if mode in ("dynamic", "disabled") or not wallpaper_list:
        default_wp = expand_user_path(wp.get("path", "$HOME/Pictures/wallpapers/"))
        default_wp = os.path.join(default_wp, "wall0.png") if os.path.isdir(default_wp) else default_wp
        if not os.path.exists(default_wp):
            default_wp = expand_user_path("$HOME/Pictures/wallpapers/wall0.png")
        if os.path.exists(default_wp):
            preload_list.append(default_wp)
            wallpaper_list.append(f",{default_wp}")

    monitors = []
    try:
        output = subprocess.check_output(["hyprctl", "monitors", "-j"], text=True)
        mon_data = json.loads(output)
        monitors = [m["name"] for m in mon_data]
        logger.info(f"Detected monitors for hyprpaper: {', '.join(monitors)}")
    except Exception as e:
        logger.warning(f"Could not detect monitors via hyprctl: {e}. Falling back to wildcard.")

    if not wallpaper_list:
        logger.warning("No wallpaper configured, hyprpaper may show blank screen")

    content = [f"ipc = {ipc}"]

    splash = wp.get("splash", False)
    content.append(f"splash = {str(splash).lower()}")

    for p in set(preload_list):
        content.append(f"preload = {p}")

    for w in wallpaper_list:
        path = w[1:] if w.startswith(",") else w
        if monitors:
            for m in monitors:
                content.append(f"wallpaper = {m},{path}")
        else:
            content.append(f"wallpaper = ,{path}")

    atomic_write(HYPRPAPER_CONF, "\n".join(content) + "\n")

def generate_hyprlock_conf(data: Dict[str, Any]) -> None:
    logger.info(f"Generating hyprlock config at {HYPRLOCK_CONF}...")

    lock = data.get("lockscreen", {})

    bg_path = expand_user_path(lock.get("background", "$HOME/Pictures/wallpapers/wall1.png"))
    profile_path = expand_user_path(lock.get("profile_image", "$HOME/.face"))

    blur_passes = lock.get("blur_passes", 3)
    blur_size = lock.get("blur_size", 8)

    fail_text = lock.get("fail_text", "<i>$FAIL <b>($ATTEMPTS)</b></i>")
    placeholder_text = lock.get("placeholder_text", "<i>Input Password...</i>")

    expanded_profile = os.path.expandvars(profile_path.replace("$HOME", os.path.expanduser("~")))
    if not os.path.exists(expanded_profile) and profile_path == "$HOME/.face":
         pass

    content = f"""
general {{
    no_fade_in = false
    grace = 0
    disable_loading_bar = true
}}

background {{
    monitor =
    path = {bg_path}
    color = rgba(25, 20, 20, 1.0)
    blur_passes = {blur_passes}
    blur_size = {blur_size}
    noise = 0.0117
    contrast = 0.8916
    brightness = 0.8172
    vibrancy = 0.1696
    vibrancy_darkness = 0.0
}}

input-field {{
    monitor =
    size = 250, 50
    outline_thickness = 3
    dots_size = 0.26
    dots_spacing = 0.15
    dots_center = true
    dots_rounding = -1
    outer_color = rgb(151515)
    inner_color = rgb(200, 200, 200)
    font_color = rgb(10, 10, 10)
    fade_on_empty = true
    ignore_empty_input = true
    fade_timeout = 1000
    placeholder_text = {placeholder_text}
    hide_input = false
    rounding = -1
    check_color = rgb(204, 136, 34)
    fail_color = rgb(204, 34, 34)
    fail_text = {fail_text}
    fail_transition = 300
    capslock_color = -1
    numlock_color = -1
    bothlock_color = -1
    invert_numlock = false
    swap_font_color = false

    position = 0, -100
    halign = center
    valign = center
}}

label {{
    monitor =
    text = cmd[update:1000] echo "$TIME"
    color = rgba(200, 200, 200, 1.0)
    font_size = 64
    font_family = JetBrains Mono Nerd Font Mono
    position = 0, 60
    halign = center
    valign = center
}}

label {{
    monitor =
    text = Hello, $USER
    color = rgba(200, 200, 200, 1.0)
    font_size = 20
    font_family = JetBrains Mono Nerd Font Mono
    position = 0, 0
    halign = center
    valign = center
}}
"""

    if lock.get("enable_profile_image", True):
        content += f"""
image {{
    monitor =
    path = {profile_path}
    size = 200, 200
    rounding = 1000
    border_size = 6
    border_color = rgb(221, 221, 221)
    rotate = 0
    reload_time = -1
    reload_cmd =

    position = 0, 220
    halign = center
    valign = center
}}
"""
    atomic_write(HYPRLOCK_CONF, content)

def generate_hypridle_conf(data: Dict[str, Any]) -> None:
    if "idle" not in data:
        logger.info("No [idle] section found. Skipping hypridle.conf generation.")
        return

    logger.info(f"Generating hypridle config at {HYPRIDLE_CONF}...")
    idle = data["idle"]

    lock_cmd = "pidof hyprlock || hyprlock"
    before_sleep = "loginctl lock-session && sleep 1"
    after_sleep = "hyprctl dispatch 'hl.dsp.dpms(\"on\")'"

    lock_timeout = idle.get("lock_timeout", 300)
    screen_off_timeout = idle.get("screen_off_timeout", 330)
    suspend_timeout = idle.get("suspend_timeout", 1800)

    content = f"""
general {{
    lock_cmd = {lock_cmd}
    before_sleep_cmd = {before_sleep}
    after_sleep_cmd = {after_sleep}
}}

listener {{
    timeout = 150
    on-timeout = brightnessctl -s set 10
    on-resume = brightnessctl -r
}}

listener {{
    timeout = 150
    on-timeout = brightnessctl -sd rgb:kbd_backlight set 0
    on-resume = brightnessctl -rd rgb:kbd_backlight
}}

listener {{
    timeout = {lock_timeout}
    on-timeout = loginctl lock-session
}}

listener {{
    timeout = {screen_off_timeout}
    on-timeout = hyprctl dispatch 'hl.dsp.dpms("off")'
    on-resume = hyprctl dispatch 'hl.dsp.dpms("on")'
}}

listener {{
    timeout = {suspend_timeout}
    on-timeout = systemctl suspend
}}
"""
    atomic_write(HYPRIDLE_CONF, content)

def generate_hyrocket_systemd_units(data: Dict[str, Any]) -> None:
    if "hyprrocket" not in data:
        return

    rocket = data["hyprrocket"]
    if rocket.get("enabled", True) is False:
        logger.info("HyprRocket disabled — skipping systemd units.")
        return

    events = rocket.get("events", {})
    if not events:
        return

    logger.info("Generating HyprRocket systemd units...")
    systemd_dir = os.path.expanduser("~/.config/systemd/user")
    os.makedirs(systemd_dir, exist_ok=True)

    enabled_timers = []
    disabled_timers = []
    for name, ev in events.items():
        if not isinstance(ev, dict):
            logger.warning(f"HyprRocket event '{name}' is not a table — skipped.")
            continue
        if ev.get("enabled", True) is False:
            logger.info(f"HyprRocket event '{name}' disabled — skipping timer.")
            disabled_timers.append(f"hyprrocket@{name}.timer")
            continue
        trigger = ev.get("trigger", "")
        if not trigger:
            logger.warning(f"HyprRocket event '{name}' missing trigger — skipped.")
            continue
        # Optional: days="Mon..Fri" or "Mon,Wed,Fri"; description free text.
        days = str(ev.get("days", "") or "").strip()
        description = str(ev.get("description", "") or "").strip()
        if days:
            on_calendar = f"{days} *-*-* {trigger}:00"
        else:
            on_calendar = f"*-*-* {trigger}:00"
        # Breaking schema: actions[] list only (no singular action string).
        actions = ev.get("actions", [])
        if not actions:
            logger.warning(
                f"HyprRocket event '{name}' has no actions[] — timer still created but will no-op."
            )

        unit_desc = f"HyprRocket {name} - Event Bus Handler"
        if description:
            unit_desc += f" ({description})"
        service_content = f"""[Unit]
Description={unit_desc}
After=graphical-session.target

[Service]
Type=oneshot
ExecStart=%h/.config/hypr/scripts/hyprrocket.sh --trigger {name}
"""
        service_path = os.path.join(systemd_dir, f"hyprrocket@{name}.service")
        atomic_write(service_path, service_content)

        timer_content = f"""[Unit]
Description=HyprRocket {name} - Event Bus Timer

[Timer]
OnCalendar={on_calendar}
Persistent=true

[Install]
WantedBy=timers.target
"""
        timer_path = os.path.join(systemd_dir, f"hyprrocket@{name}.timer")
        atomic_write(timer_path, timer_content)
        enabled_timers.append(f"hyprrocket@{name}.timer")

    logger.info(f"Generated HyprRocket systemd units in {systemd_dir}")

    # Disable timers for events with enabled=false (stale units from
    # previous runs must not keep firing).
    for timer in disabled_timers:
        try:
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", timer],
                capture_output=True, timeout=15,
            )
            logger.info(f"Disabled HyprRocket timer: {timer}")
        except Exception as e:
            logger.warning(f"Could not disable {timer}: {e}")

    # Reload + enable timers when systemd user instance is available.
    for timer in enabled_timers:
        try:
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True, timeout=10,
            )
            break
        except Exception as e:
            logger.warning(f"systemctl daemon-reload failed: {e}")
            return
    for timer in enabled_timers:
        try:
            subprocess.run(
                ["systemctl", "--user", "enable", "--now", timer],
                capture_output=True, timeout=15,
            )
            logger.info(f"Enabled HyprRocket timer: {timer}")
        except Exception as e:
            logger.warning(f"Could not enable {timer}: {e}")

def generate_css_overrides(data: Dict[str, Any]) -> None:
    decoration = data.get("decoration", {})
    waybar_op = decoration.get("waybar_opacity", 0.5)
    wofi_op = decoration.get("wofi_opacity", 0.95)

    tag_map = {
        "SETTINGS_BAR_OPACITY": str(waybar_op),
        "SETTINGS_WOFI_OPACITY": str(wofi_op)
    }

    css_files = [
        os.path.expanduser("~/.config/waybar/style.css"),
        os.path.expanduser("~/.config/waybar/control-center/style.css"),
        os.path.expanduser("~/.config/waybar/system-metrics/style.css"),
        os.path.expanduser("~/.config/waybar/bluetooth-center/style.css"),
        os.path.expanduser("~/.config/wofi/style.css")
    ]

    for css_path in css_files:
        if not os.path.exists(css_path):
            continue

        try:
            with open(css_path, 'r') as f:
                lines = f.readlines()

            new_lines = []
            modified = False
            for line in lines:
                found_tag = False
                for tag, value in tag_map.items():
                    if tag in line:
                        found_tag = True
                        indent = line[:line.find(line.strip())]
                        if "background-color" in line and "alpha(" in line:
                            new_line = re.sub(r'alpha\(([^,]+),\s*([^)]+)\)', f'alpha(\\1, {value})', line)
                            new_lines.append(new_line)
                            modified = True
                        else:
                            new_lines.append(line)
                        break
                if not found_tag:
                    new_lines.append(line)

            if modified:
                atomic_write(css_path, "".join(new_lines))
                logger.info(f"Applied transparency overrides to {css_path}")
        except Exception as e:
            logger.error(f"Failed to apply CSS overrides to {css_path}: {e}")

if __name__ == "__main__":
    if not os.path.exists(CONFIG_DIR):
        print(f"Creating directory: {CONFIG_DIR}")
        os.makedirs(CONFIG_DIR)

    data_full = {}
    try:
        with open(TOML_FILE, "rb") as f:
            data_full = tomllib.load(f)
    except FileNotFoundError as e:
        logger.error(f"TOML file not found: {e}")
    except tomllib.TOMLDecodeError as e:
        logger.error(f"Invalid TOML syntax: {e}")
    except OSError as e:
        logger.error(f"File I/O error: {e}")

    data_full = inject_defaults(data_full)
    resolve_variables(data_full, data_full)
    generate_and_write_lua(data_full)
    generate_hypridle_conf(data_full)
    generate_hyprlock_conf(data_full)
    generate_hyprpaper_conf(data_full)
    generate_fixed_wallpaper_config(data_full)
    generate_hyrocket_systemd_units(data_full)
    generate_wallpaper_schedule_config(data_full)
    generate_css_overrides(data_full)

    print("Configuration build complete.")
