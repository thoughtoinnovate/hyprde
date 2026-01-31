import tomllib
import urllib.request
import urllib.error
import os
import subprocess
import re
import ssl
import logging
from typing import Optional, Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_hyprland_version() -> str:
    """Detect local Hyprland version tag.
    
    Returns:
        Version tag (e.g., "v0.40.0") or "main" if not detected.
    """
    try:
        # Run Hyprland --version and capture output
        output = subprocess.check_output(["Hyprland", "--version"], stderr=subprocess.STDOUT, text=True)
        # Try to find 'Tag: vX.Y.Z'
        tag_match = re.search(r"Tag: (v[\d\.]+)", output)
        if tag_match:
            return tag_match.group(1)
        # Fallback to 'Hyprland X.Y.Z' -> vX.Y.Z
        ver_match = re.search(r"Hyprland ([\d\.]+)", output)
        if ver_match:
            return f"v{ver_match.group(1)}"
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        logger.warning(f"Could not detect Hyprland version: {e}")
    return "main"

# Constants
MAX_DOWNLOAD_SIZE = 5 * 1024 * 1024  # 5MB limit
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = True
SSL_CONTEXT.verify_mode = ssl.CERT_REQUIRED

HYPR_VERSION = get_hyprland_version()
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

TOML_FILE = os.path.join(os.path.dirname(__file__), "hyprde.toml")
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
    """Download base Hyprland config from GitHub with security validation."""
    logger.info(f"Downloading base config from {BASE_URL}...")
    monolithic_fallback = os.path.join(os.path.dirname(__file__), "hyprland.conf.monolithic")
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
    except urllib.error.URLError as e:
        logger.error(f"Download failed (network error): {e}")
        raw_content = _load_fallback_config(monolithic_fallback)
    except (ValueError, TimeoutError) as e:
        logger.error(f"Download failed (validation error): {e}")
        raw_content = _load_fallback_config(monolithic_fallback)
    except Exception as e:
        logger.error(f"Download failed (unexpected error): {e}")
        raw_content = _load_fallback_config(monolithic_fallback)
    
    # Process and save the config
    _process_and_save_base_config(raw_content)

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
    
    # Monitors
    if "monitors" in data:
        lines.append("\n# Monitors")
        for rule in data["monitors"].get("rules", []):
            lines.append(f"monitor = {rule}")

    # Programs
    if "programs" in data:
        lines.append("\n# Programs")
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
        if wp.get("enable_dynamic", False):
            # Default values if missing in TOML
            path = wp.get("path", "$HOME/Pictures/wallpapers/")
            interval = wp.get("interval", 60)
            # Validate path to prevent shell injection
            try:
                validate_shell_safe(str(path), "wallpapers.path")
                validate_shell_safe(str(interval), "wallpapers.interval")
                # Add as a separate exec-once
                cmd = f"sh $HOME/.config/hypr/scripts/dynamic-wallpapers.sh {path} {interval}"
                lines.append(f"exec-once = {cmd}")
            except ValueError as e:
                logger.error(f"Skipping dynamic wallpaper due to unsafe value: {e}")
                lines.append(f"# Skipped dynamic wallpaper: {e}")

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
            lines.append(f"\nsubmap = {submap_name}")
            for b in submap_data.get("binds", []):
                lines.append(f"bind = {b}")
            lines.append("submap = reset")

    # Window Rules (Converted to Hyprland 0.53+ syntax)
    if "rules" in data:
        lines.append("\n# Window Rules (Converted to Hyprland 0.53+ syntax)")
        for rule in data["rules"].get("window", []):
            # Parse legacy rule: "action, selector"
            parts = [p.strip() for p in rule.split(",", 1)]
            if len(parts) != 2:
                lines.append(f"# Skipping invalid rule: {rule}")
                continue
            
            action = parts[0]
            selector_raw = parts[1]
            
            # Convert selector "class:regex" -> "match:class regex"
            if selector_raw.startswith("class:"):
                selector = f"match:class {selector_raw[6:]}"
            elif selector_raw.startswith("title:"):
                selector = f"match:title {selector_raw[6:]}"
            else:
                # Fallback or assume it's just a regex for class (v1 behavior)
                selector = f"match:class {selector_raw}"
            
            # Convert actions
            # Old: "float" -> New: "float true"
            if action == "float":
                new_rule = f"windowrule = {selector}, float true"
            elif action == "pin":
                new_rule = f"windowrule = {selector}, pin true"
            elif action == "center":
                new_rule = f"windowrule = {selector}, center true"
            elif action.startswith("size"):
                # "size 800 600" -> "size 800 600" (likely needs no change, or "size 800 600")
                new_rule = f"windowrule = {selector}, {action}"
            elif action.startswith("opacity"):
                new_rule = f"windowrule = {selector}, {action}"
            elif action.startswith("animation"):
                new_rule = f"windowrule = {selector}, {action}"
            elif action.startswith("rounding"):
                new_rule = f"windowrule = {selector}, {action}"
            elif action.startswith("suppressevent"):
                # "suppressevent maximize" -> "suppressevent maximize"
                # Syntax: windowrule = match:..., suppressevent maximize
                new_rule = f"windowrule = {selector}, {action}"
            else:
                # Generic fallback
                new_rule = f"windowrule = {selector}, {action}"
                
            lines.append(new_rule)

    # Gestures (v0.53+ syntax)
    if "gesture" in data:
        lines.append("\n# Gestures (v0.53+ syntax)")
        for g in data["gesture"].get("list", []):
             lines.append(f"gesture = {g}")

    # Plugin Configuration
    if "plugin" in data:
        lines.append("\n# Plugin Configuration")
        lines.append("plugin {")
        for plugin_name, config in data["plugin"].items():
            lines.append(f"    {plugin_name} {{")
            for k, v in config.items():
                v_str = str(v).lower() if isinstance(v, bool) else str(v)
                lines.append(f"        {k} = {v_str}")
            lines.append("    }")
        lines.append("}")

    # Custom Raw Lines
    if "custom" in data:
        lines.append("\n# Custom / Legacy Settings")
        for line in data["custom"].get("lines", []):
            lines.append(line)

    logger.info(f"Writing user config to {USER_CONF}...")
    atomic_write(USER_CONF, "\n".join(lines))

HYPRIDLE_CONF = os.path.join(CONFIG_DIR, "hypridle.conf")

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
    
    create_main_conf()
    print("Configuration build complete.")
