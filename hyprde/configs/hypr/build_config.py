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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def update_waybar_autohide(autohide: bool) -> None:
    """Update Waybar configuration to enable or disable autohide (mode: invisible vs dock)."""
    waybar_config_path = os.path.expanduser("~/.config/waybar/config")
    if not os.path.exists(waybar_config_path):
        return

    try:
        with open(waybar_config_path, 'r') as f:
            config = json.load(f)
        
        # Use "invisible" mode for true autohide that doesn't overlay
        # or "dock" for always visible.
        config["mode"] = "invisible" if autohide else "dock"
        
        # Atomically write updated config
        temp_path = f"{waybar_config_path}.tmp"
        with open(temp_path, 'w') as f:
            json.dump(config, f, indent=4)
        os.replace(temp_path, waybar_config_path)
        logger.info(f"Updated Waybar autohide mode to: {'invisible' if autohide else 'dock'}")
        
        # Signal waybar to reload config
        subprocess.run(["pkill", "-USR2", "waybar"], capture_output=True)
    except Exception as e:
        logger.error(f"Failed to update Waybar autohide mode: {e}")

def get_hyprland_version() -> str:
    """Detect local Hyprland version tag.
    
    Returns:
        Version tag (e.g., "v0.40.0") or "main" if not detected.
    """
    try:
        output = subprocess.check_output(["Hyprland", "--version"], stderr=subprocess.STDOUT, text=True)
        # Try to find 'Tag: vX.Y.Z'
        tag_match = re.search(r"Tag: (v[\d\.]+)", output)
        if tag_match:
            return tag_match.group(1)
        
        # Fallback to 'Hyprland X.Y.Z' -> vX.Y.Z
        ver_match = re.search(r"Hyprland ([\d\.]+)", output)
        if ver_match:
            return f"v{ver_match.group(1)}"
            
        return "main"
        
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        logger.warning(f"Could not detect Hyprland version: {e}")
        return "main"

def get_cached_version() -> Optional[str]:
    """Get the version currently stored in cache."""
    cache_file = Path.home() / ".cache" / "hyprde" / "version"
    if cache_file.exists():
        try:
            return cache_file.read_text().strip()
        except (OSError, IOError):
            pass
    return None

def update_version_cache(version: str) -> None:
    """Write version to cache file."""
    cache_dir = Path.home() / ".cache" / "hyprde"
    cache_file = cache_dir / "version"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(version)
    except (OSError, IOError) as e:
        logger.warning(f"Could not write version cache: {e}")

# Constants
MAX_DOWNLOAD_SIZE = 5 * 1024 * 1024  # 5MB limit
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = True
SSL_CONTEXT.verify_mode = ssl.CERT_REQUIRED

HYPR_VERSION = get_hyprland_version()
CACHED_VERSION = get_cached_version()
BASE_URL = f"https://raw.githubusercontent.com/hyprwm/Hyprland/{HYPR_VERSION}/example/hyprland.conf"

# Determine config directory. Default to ~/.config/hypr, but allow override.
def get_config_dir() -> str:
    """Get and validate the configuration directory."""
    config_dir = os.getenv("HYPR_CONFIG_DIR")
    if config_dir:
        # Validate path to prevent directory traversal
        config_dir = os.path.abspath(os.path.expanduser(config_dir))
        # Ensure path doesn't contain dangerous patterns
        dangerous_patterns = ['..', '//', '~', '$']
        if any(pattern in config_dir for pattern in dangerous_patterns):
            logger.warning(f"Potentially unsafe path in HYPR_CONFIG_DIR: {config_dir}")
            logger.info("Falling back to default config directory")
            config_dir = None
    
    if not config_dir:
        config_dir = os.path.join(os.path.expanduser("~"), ".config/hypr")
    
    return config_dir

CONFIG_DIR = get_config_dir()

# Prioritize ~/.config/hypr/hyprde.toml if it exists, otherwise fallback to script dir
def get_toml_file(config_dir):
    user_toml = os.path.join(config_dir, "hyprde.toml")
    if os.path.exists(user_toml):
        return user_toml
    return os.path.join(os.path.dirname(__file__), "hyprde.toml")

TOML_FILE = get_toml_file(CONFIG_DIR)
BASE_CONF = os.path.join(CONFIG_DIR, "hyprland.base.conf")
USER_CONF = os.path.join(CONFIG_DIR, "hyprde.generated.conf")
MAIN_CONF = os.path.join(CONFIG_DIR, "hyprland.conf")

def _load_fallback_config(monolithic_fallback: str) -> bytes:
    """Load fallback config if download fails.
    
    Args:
        monolithic_fallback: Path to local fallback config file
        
    Returns:
        Raw bytes of the fallback config or placeholder
    """
    if os.path.exists(monolithic_fallback):
        logger.info("Using local monolithic config as fallback base.")
        with open(monolithic_fallback, "rb") as f:
            return f.read()
    else:
        logger.warning("No fallback found. Creating placeholder.")
        return b"# Placeholder base config\n"

def _process_and_save_base_config(raw_content: bytes) -> None:
    """Process downloaded content and save to base config file."""
    # Process and Clean the Content
    # We comment out binds, monitors, and execs to avoid duplication/conflicts
    # because Hyprland accumulates these instead of overriding them.
    clean_lines = []
    text_content = raw_content.decode('utf-8', errors='ignore')
    
    for line in text_content.splitlines():
        stripped = line.strip()
        # Check for keywords to disable
        if (stripped.startswith("bind") or 
            stripped.startswith("monitor") or 
            stripped.startswith("exec")):
            clean_lines.append(f"# [DISABLED BY HYPRDE] {line}")
        else:
            clean_lines.append(line)
            
    atomic_write(BASE_CONF, "\n".join(clean_lines))
    logger.info(f"Processed and saved base config to {BASE_CONF}")

def download_base() -> None:
    """Download base Hyprland config from GitHub with security validation and caching."""
    monolithic_fallback = os.path.join(os.path.dirname(__file__), "hyprland.conf.monolithic")
    
    # Check if base config already exists
    if os.path.exists(BASE_CONF):
        try:
            # Check version cache to see if we need to force update due to version change
            force_update = False
            if CACHED_VERSION and CACHED_VERSION != HYPR_VERSION:
                logger.info(f"Hyprland version changed ({CACHED_VERSION} -> {HYPR_VERSION}). Forcing base config update.")
                force_update = True
            
            if not force_update:
                file_age = time.time() - os.path.getmtime(BASE_CONF)
                if file_age < 86400:  # 24 hours
                    logger.info("Using existing base config (fresh).")
                    return
        except OSError:
            pass

    logger.info(f"Downloading base config from {BASE_URL}...")
    raw_content = b""
    
    try:
        # Use a user agent and a 10s timeout with SSL verification
        req = urllib.request.Request(
            BASE_URL, 
            data=None, 
            headers={'User-Agent': 'Hyprde/1.0'}
        )
        with urllib.request.urlopen(req, timeout=10, context=SSL_CONTEXT) as response:
            # Validate Content-Type
            content_type = response.headers.get('Content-Type', '')
            if content_type and not content_type.startswith(('text/plain', 'application/octet-stream')):
                raise ValueError(f"Unexpected content type: {content_type}")
            
            # Validate Content-Length if available
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > MAX_DOWNLOAD_SIZE:
                raise ValueError(f"File too large: {content_length} bytes (max: {MAX_DOWNLOAD_SIZE})")
            
            # Read with size limit to prevent memory exhaustion
            raw_content = response.read(MAX_DOWNLOAD_SIZE)
            if len(raw_content) == MAX_DOWNLOAD_SIZE:
                raise ValueError("Download exceeded maximum size limit")
                
        logger.info("Download successful.")
    except Exception as e:
        logger.error(f"Download failed: {e}")
        if os.path.exists(BASE_CONF):
            logger.info("Falling back to existing base config.")
            return
        raw_content = _load_fallback_config(monolithic_fallback)
    
    # Process and save the config
    _process_and_save_base_config(raw_content)

def expand_user_path(path: str) -> str:
    """Expand $HOME and ~ to absolute user home path."""
    if not path:
        return ""
    # Replace $HOME with actual home dir
    path = path.replace("$HOME", os.path.expanduser("~"))
    # Let os.path.expanduser handle ~
    return os.path.expanduser(path)

def validate_shell_safe(value: str, field_name: str) -> str:
    """Validate that a value is safe to use in shell commands.
    
    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        
    Returns:
        The validated value
        
    Raises:
        ValueError: If the value contains dangerous shell characters
    """
    dangerous_chars = [';', '|', '&', '$', '`', '$(', '<', '>', '\n', '\r']
    for char in dangerous_chars:
        if char in value:
            raise ValueError(f"Potentially unsafe character '{char}' in {field_name}: {value}")
    return value

def atomic_write(filepath: str, content: str, mode: str = "w") -> None:
    """Write content to file atomically using temp file + rename pattern.
    
    This prevents partial/corrupted files if the write is interrupted.
    
    Args:
        filepath: Target file path
        content: Content to write
        mode: File mode ('w' for text, 'wb' for binary)
        
    Raises:
        OSError: If write fails
    """
    temp_path = f"{filepath}.tmp.{os.getpid()}"
    try:
        if 'b' in mode:
            with open(temp_path, mode) as f:
                f.write(content)
                f.flush()
                try:
                    os.fsync(f.fileno())  # Ensure data is flushed to disk
                except (OSError, ValueError, TypeError):
                    pass  # fsync may fail in testing environments
        else:
            with open(temp_path, mode, encoding='utf-8') as f:
                f.write(content)
                f.flush()
                try:
                    os.fsync(f.fileno())  # Ensure data is flushed to disk
                except (OSError, ValueError, TypeError):
                    pass  # fsync may fail in testing environments
        os.replace(temp_path, filepath)  # Atomic on POSIX
        logger.debug(f"Atomically wrote {filepath}")
    except Exception as e:
        # Clean up temp file on failure
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass  # Ignore cleanup errors
        raise OSError(f"Failed to write {filepath}: {e}") from e

def format_config_value(val: Any) -> str:
    """Format a value for Hyprland config output.
    
    Args:
        val: Value to format (bool, int, float, str)
        
    Returns:
        Formatted string for config file
    """
    if isinstance(val, bool):
        return str(val).lower()
    return str(val)

def convert_12h_to_24h(time_str: str) -> str:
    """Convert 12-hour time format (e.g., '6:00 AM') to 24-hour format (e.g., '06:00').
    
    Args:
        time_str: Time string in 12-hour format with AM/PM
        
    Returns:
        Time string in 24-hour format (HH:MM)
        
    Raises:
        ValueError: If time format is invalid
    """
    import re
    match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)", time_str.strip())
    if not match:
        raise ValueError(f"Invalid time format: {time_str}. Expected format: 'HH:MM AM/PM'")
    
    hours = int(match.group(1))
    minutes = int(match.group(2))
    period = match.group(3).upper()
    
    # Validate ranges
    if hours < 1 or hours > 12:
        raise ValueError(f"Invalid hour: {hours}. Must be between 1 and 12")
    if minutes < 0 or minutes > 59:
        raise ValueError(f"Invalid minutes: {minutes}. Must be between 0 and 59")
    
    # Convert to 24-hour format
    if period == "PM" and hours != 12:
        hours += 12
    elif period == "AM" and hours == 12:
        hours = 0
    
    return f"{hours:02d}:{minutes:02d}"

def generate_wallpaper_schedule_config(data: Dict[str, Any]) -> None:
    """Generate wallpaper schedule configuration file for dynamic mode.
    
    Three time slots: morning, noon, evening
    - morning: 6AM - 12PM
    - noon: 12PM - 6PM  
    - evening: 6PM - 6AM (covers night)
    
    Args:
        data: Parsed TOML data containing wallpaper configuration
    """
    if "wallpapers" not in data:
        return
    
    wp = data["wallpapers"]
    schedule = wp.get("schedule", {})
    directories = wp.get("directories", {})
    
    # Convert times from 12-hour to 24-hour format
    try:
        morning_start = convert_12h_to_24h(schedule.get("morning_start", "6:00 AM"))
        noon_start = convert_12h_to_24h(schedule.get("noon_start", "12:00 PM"))
        evening_start = convert_12h_to_24h(schedule.get("evening_start", "6:00 PM"))
    except ValueError as e:
        logger.error(f"Invalid time format in wallpaper schedule: {e}")
        # Use defaults
        morning_start = "06:00"
        noon_start = "12:00"
        evening_start = "18:00"
    
    # Get directory names (with defaults for 3-slot system)
    morning_dir = directories.get("morning", "morning")
    noon_dir = directories.get("noon", "noon")
    evening_dir = directories.get("evening", "evening")
    
    # Get interval from TOML (default to 300 if not set)
    interval = wp.get("interval", 300)
    
    # Generate config file content
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
    """Generate fixed wallpaper configuration file for static mode.
    
    Args:
        data: Parsed TOML data containing wallpaper configuration
    """
    if "wallpapers" not in data:
        return
    
    wp = data["wallpapers"]
    fixed = wp.get("fixed", {})
    
    wp_type = fixed.get("type", "image")
    image = fixed.get("image", "")
    directory = fixed.get("directory", "")
    
    # Generate config file content
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

def generate_config_section(lines: List[str], section_name: str, data: Dict[str, Any], key_transform = None) -> None:
    """Generate a standard config section.
    
    Args:
        lines: List to append generated lines to
        section_name: Name of the config section
        data: Dictionary of config values
        key_transform: Optional function to transform keys (e.g., col_ -> col.)
    """
    lines.append(f"\n# {section_name.title()}")
    lines.append(f"{section_name} {{")
    
    for key, val in data.items():
        if isinstance(val, dict):
            continue
        
        display_key = key_transform(key) if key_transform else key
        val_str = format_config_value(val)
        lines.append(f"    {display_key} = {val_str}")
    
    lines.append("}")

def is_plugin_installed_and_enabled(plugin_name: str) -> bool:
    """Check if a plugin is actually installed and enabled in the system via hyprpm."""
    # Cache results per process run
    if not hasattr(is_plugin_installed_and_enabled, "_cache"):
        is_plugin_installed_and_enabled._cache = {}
        
    if plugin_name in is_plugin_installed_and_enabled._cache:
        return is_plugin_installed_and_enabled._cache[plugin_name]
        
    is_active = False
    try:
        # Check if hyprpm is available
        if subprocess.run(["which", "hyprpm"], capture_output=True, text=True).returncode == 0:
            # Run hyprpm list to check for the plugin
            output = subprocess.check_output(["hyprpm", "list"], stderr=subprocess.STDOUT, text=True)
            # Find the plugin entry and check if it's enabled
            # Format: 
            #   │ Plugin <name>
            #   └─ enabled: true
            plugin_pattern = rf"Plugin {plugin_name}\s+└─ enabled: true"
            if re.search(plugin_pattern, output, re.MULTILINE):
                is_active = True
    except Exception:
        pass

    is_plugin_installed_and_enabled._cache[plugin_name] = is_active
    return is_active

def is_plugin_enabled(data: Dict[str, Any], plugin_name: str) -> bool:
    """Check if a plugin is enabled in the configuration.
    
    A plugin is enabled if:
    1. It's explicitly listed in plugins.enabled, OR
    2. manage_official is True and the plugin config exists
    
    Args:
        data: Parsed TOML data
        plugin_name: Name of the plugin to check
        
    Returns:
        True if the plugin should be enabled, False otherwise
    """
    if "plugins" not in data:
        return False
    
    pl = data["plugins"]
    
    # Check if explicitly enabled
    enabled_plugins = pl.get("enabled", [])
    if plugin_name in enabled_plugins:
        return True
    
    # Check if managing official and plugin config exists
    if pl.get("manage_official", False):
        if "plugin" in data and plugin_name in data["plugin"]:
            return True
    
    return False

def generate_user_conf() -> None:
    """Generate user configuration from TOML file.
    
    Reads hyprde.toml and generates hyprde.generated.conf with all
    user-defined settings in Hyprland config format.
    """
    logger.info(f"Reading TOML from {TOML_FILE}...")
    try:
        with open(TOML_FILE, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError as e:
        logger.error(f"TOML file not found: {e}")
        return
    except tomllib.TOMLDecodeError as e:
        logger.error(f"Invalid TOML syntax: {e}")
        return
    except OSError as e:
        logger.error(f"File I/O error: {e}")
        return
    
    lines = []
    lines.append("# Generated from hyprde.toml")
    
    # Check plugin status
    # We distinguish between 'enabled' (TOML) and 'available' (System)
    hyprexpo_enabled = is_plugin_enabled(data, "hyprexpo")
    hyprexpo_available = is_plugin_installed_and_enabled("hyprexpo") if hyprexpo_enabled else False
    
    if hyprexpo_enabled:
        if hyprexpo_available:
            logger.info("Hyprexpo plugin is enabled and active - including configuration")
        else:
            logger.warning("Hyprexpo plugin is enabled in TOML but NOT found in hyprpm. Excluding dispatcher bindings to prevent errors.")
    
    # Monitors
    if "monitors" in data:
        lines.append("\n# Monitors")
        for rule in data["monitors"].get("rules", []):
            lines.append(f"monitor = {rule}")

    # Programs
    if "programs" in data:
        lines.append("\n# Programs")
        # Handle waybar autohide (mode: hide vs dock)
        autohide = data["programs"].get("autohide_bar", False)
        update_waybar_autohide(autohide)

        for key, val in data["programs"].items():
            lines.append(f"${key} = {val}")

    # Autostart
    if "autostart" in data:
        lines.append("\n# Autostart")
        for cmd in data["autostart"].get("exec_once", []):
            lines.append(f"exec-once = {cmd}")

    # Wallpapers
    if "wallpapers" in data:
        wp = data["wallpapers"]
        mode = wp.get("mode", "fixed")  # Default to fixed for new users
        
        if mode == "dynamic":
            # Start dynamic wallpaper service
            if wp.get("enable_dynamic", False):
                path = wp.get("path", "$HOME/Pictures/wallpapers/")
                interval = wp.get("interval", 60)
                try:
                    validate_shell_safe(str(path), "wallpapers.path")
                    validate_shell_safe(str(interval), "wallpapers.interval")
                    cmd = f"sh $HOME/.config/hypr/scripts/init_wallpaper.sh {path} {interval}"
                    lines.append(f"exec-once = {cmd}")
                except ValueError as e:
                    logger.error(f"Skipping dynamic wallpaper due to unsafe value: {e}")
                    lines.append(f"# Skipped dynamic wallpaper: {e}")
                    
        elif mode == "fixed":
            # Set fixed wallpaper
            cmd = "sh $HOME/.config/hypr/scripts/init_wallpaper.sh"
            lines.append(f"exec-once = {cmd}")
            
        elif mode == "disabled":
            # No wallpaper management
            lines.append("# Wallpaper management disabled")
            logger.info("Wallpaper management disabled")

    # Nightlight
    if "nightlight" in data:
        nl = data["nightlight"]
        if nl.get("enabled", False):
            t_day = nl.get("temp_day", 6500)
            t_night = nl.get("temp_night", 3400)
            # Add gammastep command
            # Note: The original scripts use -O which is one-shot manual mode.
            # Standard auto usage is: gammastep -t 6500:3400
            # If we want simple manual persistent mode, we might just set one temp.
            # But "Night Light" usually implies auto adjustment or persistent warm.
            # Let's assume the user wants persistent warm if they enabled "nightlight" manually here,
            # OR standard auto behavior.
            # Given the existing scripts use manual toggles, let's use the auto mode here so it runs in background.
            lines.append(f"exec-once = gammastep -t {t_day}:{t_night}")

    # Plugins
    if "plugins" in data:
        pl = data["plugins"]
        # If we are managing plugins, we should ensure hyprpm is reloaded on startup
        # This is standard practice for hyprpm managed plugins
        if pl.get("manage_official", False) or len(pl.get("enabled", [])) > 0:
             lines.append("exec-once = hyprpm reload -n")

    # Env
    if "env" in data:
        lines.append("\n# Environment")
        for var in data["env"].get("vars", []):
             lines.append(f"env = {var}")

    # Input
    if "input" in data:
        lines.append("\n# Input")
        lines.append("input {")
        for key, val in data["input"].items():
            if isinstance(val, dict): continue
            val_str = str(val).lower() if isinstance(val, bool) else str(val)
            lines.append(f"    {key} = {val_str}")
        
        if "touchpad" in data["input"]:
            lines.append("    touchpad {")
            for k, v in data["input"]["touchpad"].items():
                 v_str = str(v).lower() if isinstance(v, bool) else str(v)
                 lines.append(f"        {k} = {v_str}")
            lines.append("    }")
        lines.append("}")

    # General
    if "general" in data:
        lines.append("\n# General")
        lines.append("general {")
        for key, val in data["general"].items():
             # Convert col_ to col. for Hyprland 0.53+
             clean_key = key.replace("col_", "col.")
             val_str = str(val).lower() if isinstance(val, bool) else str(val)
             lines.append(f"    {clean_key} = {val_str}")
        lines.append("}")

    # Decoration
    if "decoration" in data:
        lines.append("\n# Decoration")
        lines.append("decoration {")
        for key, val in data["decoration"].items():
            if isinstance(val, dict): continue
            
            # Skip internal HyprDE settings used for CSS generation
            if key in ["waybar_opacity", "wofi_opacity"]:
                continue
                
            clean_key = key.replace("col_", "col.")
            val_str = str(val).lower() if isinstance(val, bool) else str(val)
            lines.append(f"    {clean_key} = {val_str}")
        
        if "blur" in data["decoration"]:
            lines.append("    blur {")
            for k, v in data["decoration"]["blur"].items():
                v_str = str(v).lower() if isinstance(v, bool) else str(v)
                lines.append(f"        {k} = {v_str}")
            lines.append("    }")
        lines.append("}")
    
    # Animations
    if "animations" in data:
        lines.append("\n# Animations")
        lines.append("animations {")
        for key, val in data["animations"].items():
            if key == "enabled":
                lines.append(f"    enabled = {str(val).lower()}")
            elif key == "bezier":
                lines.append(f"    bezier = {val}")
            else:
                # Use 'animation =' keyword for all animation rules
                lines.append(f"    animation = {key}, {val}")
        lines.append("}")
        
    # Dwindle
    if "dwindle" in data:
        lines.append("\n# Dwindle")
        lines.append("dwindle {")
        for key, val in data["dwindle"].items():
            val_str = str(val).lower() if isinstance(val, bool) else str(val)
            lines.append(f"    {key} = {val_str}")
        lines.append("}")

    # Master
    if "master" in data:
        lines.append("\n# Master")
        lines.append("master {")
        for key, val in data["master"].items():
            val_str = str(val).lower() if isinstance(val, bool) else str(val)
            lines.append(f"    {key} = {val_str}")
        lines.append("}")

    # Scrolling Layout (Native 0.54.0+)
    if "scrolling" in data:
        lines.append("\n# Scrolling Layout")
        lines.append("scrolling {")
        for key, val in data["scrolling"].items():
            val_str = str(val).lower() if isinstance(val, bool) else str(val)
            lines.append(f"    {key} = {val_str}")
        lines.append("}")

    # Misc
    if "misc" in data:
        lines.append("\n# Misc")
        lines.append("misc {")
        for key, val in data["misc"].items():
            val_str = str(val).lower() if isinstance(val, bool) else str(val)
            lines.append(f"    {key} = {val_str}")
        lines.append("}")
        
    # Binds
    if "binds" in data:
        lines.append("\n# Keybindings")
        main_mod = data["binds"].get("mainMod", "SUPER")
        lines.append(f"$mainMod = {main_mod}")
        
        def add_binds(section, prefix="bind"):
            if section in data["binds"]:
                for b in data["binds"].get(section, {}).get("list", []):
                    # Skip hyprexpo-related bindings if plugin not available on system
                    if "hyprexpo" in str(b).lower():
                        if not hyprexpo_available:
                            continue
                    lines.append(f"{prefix} = {b}")

        add_binds("normal", "bind")
        add_binds("release", "bindr")
        add_binds("mouse", "bindm")
        add_binds("repeat", "binde")
        add_binds("locked", "bindl")

    # Submaps
    if "submaps" in data:
        lines.append("\n# Submaps")
        for submap_name, submap_data in data["submaps"].items():
            # Skip expo submap if hyprexpo not available
            if submap_name == "expo" and not hyprexpo_available:
                continue
            lines.append(f"\nsubmap = {submap_name}")
            for b in submap_data.get("binds", []):
                # Also filter hyprexpo bindings within submap if not available
                if "hyprexpo" in str(b).lower() and not hyprexpo_available:
                    continue
                lines.append(f"bind = {b}")
            lines.append("submap = reset")

    # Window Rules (Converted to Hyprland 0.54+ block syntax)
    if "rules" in data:
        lines.append("\n# Window Rules (Converted to Hyprland 0.54+ block syntax)")
        for i, rule in enumerate(data["rules"].get("window", [])):
            # Parse legacy rule: "action, selector"
            parts = [p.strip() for p in rule.split(",", 1)]
            if len(parts) != 2:
                lines.append(f"# Skipping invalid rule: {rule}")
                continue
            
            action_raw = parts[0]
            selector_raw = parts[1]
            
            # Generate a reasonably unique name for the rule
            # Sanitized selector: remove non-alphanumeric
            safe_selector = re.sub(r'[^a-zA-Z0-9]', '-', selector_raw).strip('-')
            rule_name = f"rule-{i}-{action_raw.split()[0]}-{safe_selector}"
            
            lines.append("windowrule {")
            lines.append(f"    name = {rule_name}")
            
            # Extract selector type and value
            if selector_raw.startswith("class:"):
                lines.append(f"    match:class = {selector_raw[6:]}")
            elif selector_raw.startswith("title:"):
                lines.append(f"    match:title = {selector_raw[6:]}")
            else:
                lines.append(f"    match:class = {selector_raw}")
            
            # Map simple actions to new properties
            if action_raw == "float":
                lines.append("    float = true")
            elif action_raw == "pin":
                lines.append("    pin = true")
            elif action_raw == "center":
                lines.append("    center = true")
            elif action_raw.startswith("size"):
                # "size 800 600" -> "size = 800 600"
                parts = action_raw.split(None, 1)
                lines.append(f"    {parts[0]} = {parts[1]}")
            elif action_raw.startswith("opacity"):
                # "opacity 0.9 0.9" -> "opacity = 0.9 0.9"
                parts = action_raw.split(None, 1)
                lines.append(f"    {parts[0]} = {parts[1]}")
            elif action_raw.startswith("animation"):
                # "animation slide" -> "animation = slide"
                parts = action_raw.split(None, 1)
                lines.append(f"    {parts[0]} = {parts[1]}")
            elif action_raw.startswith("rounding"):
                # "rounding 10" -> "rounding = 10"
                parts = action_raw.split(None, 1)
                lines.append(f"    {parts[0]} = {parts[1]}")
            elif action_raw.startswith("suppressevent"):
                # "suppressevent maximize" -> "suppress_event = maximize"
                parts = action_raw.split()
                if len(parts) > 1:
                     lines.append(f"    suppress_event = {parts[1]}")
                else:
                     lines.append(f"    {action_raw}")
            else:
                # Generic fallback (some might need = , some not)
                # Let's try to split by space to put '='
                parts = action_raw.split(None, 1)
                if len(parts) > 1:
                     lines.append(f"    {parts[0]} = {parts[1]}")
                else:
                     lines.append(f"    {action_raw}")
                
            lines.append("}")

    # Plugin Configuration
    if "plugin" in data:
        # Filter plugins based on enablement and availability
        plugins_to_include = {}
        for plugin_name, config in data["plugin"].items():
            # Skip hyprexpo if not active on system
            if plugin_name == "hyprexpo":
                if hyprexpo_available:
                    plugins_to_include[plugin_name] = config
                continue
            # Include all other plugins
            plugins_to_include[plugin_name] = config
        
        # Only output plugin section if there are plugins to include
        if plugins_to_include:
            lines.append("\n# Plugin Configuration")
            lines.append("plugin {")
            for plugin_name, config in plugins_to_include.items():
                lines.append(f"    {plugin_name} {{")
                for k, v in config.items():
                    v_str = str(v).lower() if isinstance(v, bool) else str(v)
                    lines.append(f"        {k} = {v_str}")
                lines.append("    }")
            lines.append("}")

    # Gestures for plugins
    if "gesture" in data:
        lines.append("\n# Gestures")
        for g in data["gesture"].get("list", []):
            lines.append(g)

    # Custom Raw Lines
    if "custom" in data:
        lines.append("\n# Custom / Legacy Settings")
        for line in data["custom"].get("lines", []):
            lines.append(line)

    logger.info(f"Writing user config to {USER_CONF}...")
    atomic_write(USER_CONF, "\n".join(lines))

HYPRIDLE_CONF = os.path.join(CONFIG_DIR, "hypridle.conf")
HYPRLOCK_CONF = os.path.join(CONFIG_DIR, "hyprlock.conf")
HYPRPAPER_CONF = os.path.join(CONFIG_DIR, "hyprpaper.conf")

def generate_hyprpaper_conf(data: Dict[str, Any]) -> None:
    """Generate hyprpaper configuration from TOML data.
    
    Args:
        data: Parsed TOML data containing wallpaper configuration
    """
    if "wallpapers" not in data:
        return

    logger.info(f"Generating hyprpaper config at {HYPRPAPER_CONF}...")
    wp = data["wallpapers"]
    mode = wp.get("mode", "fixed")
    
    # Defaults
    ipc = "on"
    preload_list = []
    wallpaper_list = []
    
    if mode == "fixed":
        fixed = wp.get("fixed", {})
        wp_type = fixed.get("type", "image")
        
        if wp_type == "image":
            image_path = fixed.get("image", "")
            if image_path:
                # Expand path for hyprpaper compatibility
                expanded_path = expand_user_path(image_path)
                preload_list.append(expanded_path)
                wallpaper_list.append(f",{expanded_path}")
        elif wp_type == "directory":
            # For directory mode, pick a random one to show at boot
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
            
    # Automatic monitor detection for reliable wallpaper application
    monitors = []
    try:
        # Query Hyprland for active monitors
        output = subprocess.check_output(["hyprctl", "monitors", "-j"], text=True)
        mon_data = json.loads(output)
        monitors = [m["name"] for m in mon_data]
        logger.info(f"Detected monitors for hyprpaper: {', '.join(monitors)}")
    except Exception as e:
        logger.warning(f"Could not detect monitors via hyprctl: {e}. Falling back to wildcard.")
            
    if not wallpaper_list:
        logger.warning("No wallpaper configured, hyprpaper may show blank screen")
            
    # Generate content
    content = [f"ipc = {ipc}"]
    
    # Disable splash text by default
    splash = wp.get("splash", False)
    content.append(f"splash = {str(splash).lower()}")
    
    for p in set(preload_list): # Use set to avoid double preloads
        content.append(f"preload = {p}")
        
    for w in wallpaper_list:
        # w is in format ",/path"
        path = w[1:] if w.startswith(",") else w
        if monitors:
            # Generate explicit mapping for every detected monitor
            for m in monitors:
                content.append(f"wallpaper = {m},{path}")
        else:
            # Fallback to wildcard if no monitors detected
            content.append(f"wallpaper = ,{path}")
        
    atomic_write(HYPRPAPER_CONF, "\n".join(content) + "\n")

def generate_hyprlock_conf(data: Dict[str, Any]) -> None:
    """Generate hyprlock configuration from TOML data.
    
    Args:
        data: Parsed TOML data containing lockscreen configuration
    """
    logger.info(f"Generating hyprlock config at {HYPRLOCK_CONF}...")
    
    lock = data.get("lockscreen", {})
    
    # Defaults
    bg_path = expand_user_path(lock.get("background", "$HOME/Pictures/wallpapers/wall1.png"))
    profile_path = expand_user_path(lock.get("profile_image", "$HOME/.face"))
    
    # Visual settings
    blur_passes = lock.get("blur_passes", 3)
    blur_size = lock.get("blur_size", 8)
    
    # Text settings
    fail_text = lock.get("fail_text", "<i>$FAIL <b>($ATTEMPTS)</b></i>")
    placeholder_text = lock.get("placeholder_text", "<i>Input Password...</i>")
    
    # Check if profile image exists, fallback if not
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
    blur_passes = {blur_passes} # 0 disables blurring
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
    dots_size = 0.26 # Scale of input-field height, 0.2 - 0.8
    dots_spacing = 0.15 # Scale of dots' absolute size, 0.0 - 1.0
    dots_center = true
    dots_rounding = -1 # -1 default circle, -2 follow input-field rounding
    outer_color = rgb(151515)
    inner_color = rgb(200, 200, 200)
    font_color = rgb(10, 10, 10)
    fade_on_empty = true
    fade_timeout = 1000 # Milliseconds before fade_on_empty is triggered.
    placeholder_text = {placeholder_text} # Text rendered in the input box when it's empty.
    hide_input = false
    rounding = -1 # -1 default circle, -2 follow input-field rounding
    check_color = rgb(204, 136, 34)
    fail_color = rgb(204, 34, 34) # if authentication failed, changes outer_color and fail message color
    fail_text = {fail_text} # can be set to empty
    fail_transition = 300 # transition time in ms between normal outer_color and fail_color
    capslock_color = -1
    numlock_color = -1
    bothlock_color = -1 # when both locks are active. -1 means don't change outer color (same for above)
    invert_numlock = false # change color if numlock is off
    swap_font_color = false # see below

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
    rotate = 0 # degrees, counter-clockwise
    reload_time = -1 # seconds between reloading, 0 to reload with SIGUSR2
    reload_cmd =  # command to get new path. if empty, old path will be used. don't run "follow" commands like tail -F

    position = 0, 220
    halign = center
    valign = center
}}
"""
    atomic_write(HYPRLOCK_CONF, content)

def generate_hypridle_conf(data: Dict[str, Any]) -> None:
    """Generate hypridle configuration from TOML data.
    
    Args:
        data: Parsed TOML data containing idle configuration
        
    Creates hypridle.conf with lock, screen off, and suspend timeouts.
    """
    if "idle" not in data:
        logger.info("No [idle] section found. Skipping hypridle.conf generation.")
        return

    logger.info(f"Generating hypridle config at {HYPRIDLE_CONF}...")
    idle = data["idle"]
    
    # Defaults
    lock_cmd = "pidof hyprlock || hyprlock"
    before_sleep = "loginctl lock-session"
    after_sleep = "hyprctl dispatch dpms on"
    
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
    on-timeout = hyprctl dispatch dpms off
    on-resume = hyprctl dispatch dpms on
}}

listener {{
    timeout = {suspend_timeout}
    on-timeout = systemctl suspend
}}
"""
    atomic_write(HYPRIDLE_CONF, content)

def generate_hyrocket_systemd_units(data: Dict[str, Any]) -> None:
    """Generate systemd user units for HyprRocket events.
    
    Args:
        data: Parsed TOML data containing hyprrocket configuration
    """
    if "hyprrocket" not in data:
        return
        
    events = data["hyprrocket"].get("events", {})
    if not events:
        return

    logger.info("Generating HyprRocket systemd units...")
    systemd_dir = os.path.expanduser("~/.config/systemd/user")
    os.makedirs(systemd_dir, exist_ok=True)
    
    for name, ev in events.items():
        trigger = ev.get("trigger", "")
        if not trigger:
            continue
            
        # Service unit
        service_content = f"""[Unit]
Description=HyprRocket {name} - Event Bus Handler
After=graphical-session.target

[Service]
Type=oneshot
ExecStart=%h/.config/hypr/scripts/hyprrocket.sh --trigger {name}
"""
        service_path = os.path.join(systemd_dir, f"hyprrocket@{name}.service")
        atomic_write(service_path, service_content)
        
        # Timer unit
        timer_content = f"""[Unit]
Description=HyprRocket {name} - Event Bus Timer

[Timer]
OnCalendar=*-*-* {trigger}:00
Persistent=true

[Install]
WantedBy=timers.target
"""
        timer_path = os.path.join(systemd_dir, f"hyprrocket@{name}.timer")
        atomic_write(timer_path, timer_content)
        
    logger.info(f"Generated HyprRocket systemd units in {systemd_dir}")

def generate_css_overrides(data: Dict[str, Any]) -> None:
    """Apply TOML settings (like transparency) to component CSS files."""
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

def create_main_conf() -> None:
    """Create the main hyprland.conf that sources base and user configs.
    
    This file is the entry point that Hyprland reads, which then
    sources the base config and generated user overrides.
    """
    logger.info(f"Generating main config at {MAIN_CONF}...")
    content = f"""# Hyprland Config - Auto Generated
# Base: {BASE_URL}
# User Overrides: hyprde.generated.conf

source = ./hyprland.base.conf
source = ./hyprde.generated.conf
"""
    atomic_write(MAIN_CONF, content)

if __name__ == "__main__":
    if not os.path.exists(CONFIG_DIR):
        print(f"Creating directory: {CONFIG_DIR}")
        os.makedirs(CONFIG_DIR)
        
    download_base()
    
    # Update version cache after download check
    update_version_cache(HYPR_VERSION)
    
    # Load data once
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

    generate_user_conf() # Refactor this later to pass data, but for now it reads file again internally which is fine or we can pass it if we refactor.
    # Actually generate_user_conf reads the file itself. I'll leave it as is to minimize diff, 
    # but I'll pass data_full to hypridle gen.
    
    generate_hypridle_conf(data_full)
    generate_hyprlock_conf(data_full)
    generate_hyprpaper_conf(data_full)
    generate_fixed_wallpaper_config(data_full)
    generate_hyrocket_systemd_units(data_full)
    generate_wallpaper_schedule_config(data_full)
    generate_css_overrides(data_full)
    
    create_main_conf()
    print("Configuration build complete.")
