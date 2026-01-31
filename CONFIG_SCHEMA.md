# HyprDE Configuration Schema

This document describes the complete schema for `hyprde.toml` - the single source of truth for your Hyprland desktop environment configuration.

## Table of Contents

- [Overview](#overview)
- [Schema Sections](#schema-sections)
  - [monitors](#monitors)
  - [programs](#programs)
  - [autostart](#autostart)
  - [wallpapers](#wallpapers)
  - [idle](#idle)
  - [nightlight](#nightlight)
  - [plugins](#plugins)
  - [submaps](#submaps)
  - [env](#env)
  - [input](#input)
  - [general](#general)
  - [decoration](#decoration)
  - [animations](#animations)
  - [dwindle](#dwindle)
  - [master](#master)
  - [misc](#misc)
  - [binds](#binds)
  - [rules](#rules)
  - [custom](#custom)
- [Value Types](#value-types)
- [Security Considerations](#security-considerations)

## Overview

The `hyprde.toml` file uses the [TOML](https://toml.io/) format. The configuration is organized into logical sections, each controlling a specific aspect of your Hyprland environment.

### Example Structure

```toml
[monitors]
rules = [
    ", highres, auto, 1.0",
    "HDMI-A-1, 1920x1080@120, auto, 1"
]

[programs]
terminal = "ghostty"
fileManager = "thunar"
```

## Schema Sections

### monitors

Configure display outputs and their properties.

```toml
[monitors]
rules = [
    # Format: "name, resolution, position, scale"
    # Use empty name (,) for wildcard matching
    ", highres, auto, 1.0",
    "HDMI-A-1, 1920x1080@120, auto, 1"
]
```

**Fields:**
- `rules` (array of strings): Monitor configuration rules following Hyprland syntax

**Value Formats:**
- Resolution: `preferred`, `highres`, `highrr`, or `WIDTHxHEIGHT@RATE`
- Position: `auto` or `XxY`
- Scale: Float value (e.g., `1.0`, `1.5`, `2.0`)

### programs

Define default applications for various actions.

```toml
[programs]
terminal = "ghostty"           # Terminal emulator
fileManager = "thunar"         # File manager
launcher = "wofi"              # Application launcher
launcher_cmd = "wofi --show drun"  # Launcher command
notification_service = "mako"  # Notification daemon
status_bar = "waybar"          # Status bar
```

**Fields:**
- `terminal` (string): Terminal emulator command
- `fileManager` (string): File manager command
- `launcher` (string): Launcher program name
- `launcher_cmd` (string): Full launcher command with arguments
- `notification_service` (string): Notification daemon
- `status_bar` (string): Status bar program

### autostart

Applications to start automatically when Hyprland launches.

```toml
[autostart]
exec_once = [
    "$notification_service & $status_bar & hyprpaper & hypridle"
]
```

**Fields:**
- `exec_once` (array of strings): Commands to execute once at startup

### wallpapers

Configure dynamic wallpaper switching.

```toml
[wallpapers]
enable_dynamic = true                      # Enable auto-switching
path = "$HOME/Pictures/wallpapers/"        # Wallpaper directory
interval = 60                              # Switch interval in seconds
```

**Fields:**
- `enable_dynamic` (boolean): Enable automatic wallpaper switching
- `path` (string): Path to wallpaper directory (supports `$HOME` expansion)
- `interval` (integer): Seconds between wallpaper changes (minimum: 10)

**Security Note:** Path values are validated to prevent shell injection attacks.

### idle

Configure idle behavior and automatic locking.

```toml
[idle]
lock_timeout = 300          # Seconds before locking (5 minutes)
screen_off_timeout = 330    # Seconds before screen off (5.5 minutes)
suspend_timeout = 1800      # Seconds before suspend (30 minutes)
```

**Fields:**
- `lock_timeout` (integer): Seconds of inactivity before screen lock
- `screen_off_timeout` (integer): Seconds before turning off display
- `suspend_timeout` (integer): Seconds before system suspend

**Validation:**
- All timeouts must be positive integers
- `screen_off_timeout` should be >= `lock_timeout`
- `suspend_timeout` should be >= `screen_off_timeout`

### nightlight

Configure blue light filter using gammastep.

```toml
[nightlight]
enabled = false        # Enable night light
 temp_day = 6500       # Color temperature during day (Kelvin)
temp_night = 3400      # Color temperature at night (Kelvin)
```

**Fields:**
- `enabled` (boolean): Enable automatic night light
- `temp_day` (integer): Daytime color temperature (1000-6500K)
- `temp_night` (integer): Nighttime color temperature (1000-6500K)

### plugins

Manage Hyprland plugins via hyprpm.

```toml
[plugins]
manage_official = false    # Enable official plugin management
enabled = []               # List of plugin names to enable

[plugin.hyprexpo]         # Plugin-specific configuration
columns = 3
gap_size = 5
bg_col = "rgb(111111)"
workspace_method = "center current"
enable_gesture = true
gesture_fingers = 3
gesture_distance = 300
gesture_positive = false
```

**Fields:**
- `manage_official` (boolean): Enable hyprpm official plugin management
- `enabled` (array of strings): List of plugins to enable
- `[plugin.<name>]` (table): Plugin-specific configuration sections

### submaps

Define keyboard submaps (modes) for complex keybindings.

```toml
[submaps.expo]
binds = [
    ", escape, hyprexpo:expo, off",
    ", escape, submap, reset",
    ", return, hyprexpo:expo, off",
    ", left, movefocus, l",
    ", right, movefocus, r"
]
```

**Fields:**
- `[submaps.<name>]` (table): Define a submap with given name
- `binds` (array of strings): Keybindings active in this submap

### env

Set environment variables for the Hyprland session.

```toml
[env]
vars = [
    "XCURSOR_SIZE,24",
    "HYPRCURSOR_SIZE,24",
    "GDK_SCALE,1.3",
    "binds:allow_workspace_cycles,true"
]
```

**Fields:**
- `vars` (array of strings): Environment variable assignments in "KEY,VALUE" format

### input

Configure input devices including keyboard and touchpad.

```toml
[input]
kb_layout = "us"
kb_variant = ""
kb_model = ""
kb_options = "caps:escape"      # Map Caps Lock to Escape
kb_rules = ""
follow_mouse = 1
sensitivity = 0

[input.touchpad]
natural_scroll = false
```

**Fields:**
- `kb_layout` (string): Keyboard layout (e.g., "us", "de", "fr")
- `kb_variant` (string): Keyboard variant
- `kb_model` (string): Keyboard model
- `kb_options` (string): XKB options (e.g., "caps:escape")
- `kb_rules` (string): XKB rules
- `follow_mouse` (integer): Window focus follows mouse (0=off, 1=on, 2=strict, 3=hyprland)
- `sensitivity` (float): Mouse sensitivity multiplier (-1.0 to 1.0)
- `[input.touchpad]` (table): Touchpad-specific settings

### general

General window management and appearance settings.

```toml
[general]
gaps_in = 5
 gaps_out = 20
border_size = 2
col_active_border = "rgba(33ccffee) rgba(00ff99ee) 45deg"
col_inactive_border = "rgba(595959aa)"
resize_on_border = false
allow_tearing = false
layout = "dwindle"
```

**Fields:**
- `gaps_in` (integer): Inner gaps between windows (pixels)
- `gaps_out` (integer): Outer gaps from screen edges (pixels)
- `border_size` (integer): Window border thickness (pixels)
- `col_active_border` (string): Active window border color
- `col_inactive_border` (string): Inactive window border color
- `resize_on_border` (boolean): Allow resizing by dragging border
- `allow_tearing` (boolean): Allow screen tearing for reduced latency
- `layout` (string): Default layout ("dwindle" or "master")

**Note:** Color values use `col_` prefix in TOML but are converted to `col.` in Hyprland config.

### decoration

Window decoration settings including blur and opacity.

```toml
[decoration]
rounding = 10
active_opacity = 1.0
inactive_opacity = 1.0

[decoration.blur]
enabled = true
size = 3
passes = 1
vibrancy = 0.1696
```

**Fields:**
- `rounding` (integer): Window corner radius (pixels)
- `active_opacity` (float): Active window opacity (0.0-1.0)
- `inactive_opacity` (float): Inactive window opacity (0.0-1.0)
- `[decoration.blur]` (table): Blur effect settings

### animations

Configure window and workspace animations.

```toml
[animations]
enabled = true
bezier = "myBezier, 0.05, 0.9, 0.1, 1.05"
windows = "1, 7, myBezier"
windowsOut = "1, 7, default, popin 80%"
border = "1, 10, default"
borderangle = "1, 8, default"
fade = "1, 7, default"
workspaces = "1, 6, default"
```

**Fields:**
- `enabled` (boolean): Enable animations
- `bezier` (string): Define custom bezier curve
- Other fields define animation properties for various elements

### dwindle

Dwindle layout configuration.

```toml
[dwindle]
pseudotile = true      # Enable pseudotiling
preserve_split = true  # Preserve split orientation
```

**Fields:**
- `pseudotile` (boolean): Enable pseudotile behavior
- `preserve_split` (boolean): Maintain split orientation when moving windows

### master

Master layout configuration.

```toml
[master]
new_status = "master"  # Position of new windows
```

**Fields:**
- `new_status` (string): Placement of new windows ("master" or "slave")

### misc

Miscellaneous settings.

```toml
[misc]
force_default_wallpaper = 1
disable_hyprland_logo = true
```

**Fields:**
- `force_default_wallpaper` (integer): Force default wallpaper (0-2)
- `disable_hyprland_logo` (boolean): Disable Hyprland logo on startup

### binds

Keyboard and mouse bindings.

```toml
[binds]
mainMod = "SUPER"

[binds.normal]
list = [
    "$mainMod, T, exec, $terminal",
    "$mainMod, Q, killactive,",
    "$mainMod, E, exec, $fileManager"
]

[binds.release]
list = [
    "$mainMod, space, exec, wofi --show drun"
]

[binds.mouse]
list = [
    "$mainMod, mouse:272, movewindow",
    "$mainMod, mouse:273, resizewindow"
]

[binds.repeat]
list = [
    ", XF86MonBrightnessUp, exec, ~/.config/hypr/scripts/brightness-ctrl.sh --inc"
]

[binds.locked]
list = [
    ", XF86AudioMute, exec, ~/.config/hypr/scripts/audio-ctrl.sh --mute"
]
```

**Fields:**
- `mainMod` (string): Main modifier key (SUPER, ALT, CTRL, SHIFT)
- `[binds.normal]` (table): Normal keybindings (bind)
- `[binds.release]` (table): Key release bindings (bindr)
- `[binds.mouse]` (table): Mouse bindings (bindm)
- `[binds.repeat]` (table): Repeating key bindings (binde)
- `[binds.locked]` (table): Bindings active when screen is locked (bindl)

**Binding Format:**
```
"MODIFIERS, KEY, DISPATCHER, ARGUMENTS"
```

### rules

Window rules for specific applications.

```toml
[rules]
window = [
    "float, class:^(Picture-in-Picture)$",
    "pin, class:^(Picture-in-Picture)$",
    "float, class:(com.fzf.launcher)",
    "size 80% 85%, class:(com.fzf.launcher)",
    "center, class:(com.fzf.launcher)",
    "opacity 0.95 0.95, class:(com.fzf.launcher)"
]
```

**Fields:**
- `window` (array of strings): Window rules in "action, selector" format

**Rule Format:**
- Action: Window property to set (float, pin, center, size, opacity, etc.)
- Selector: `class:REGEX` or `title:REGEX` to match windows

**Note:** Rules are automatically converted to Hyprland 0.53+ syntax.

### custom

Raw configuration lines not covered by the schema.

```toml
[custom]
lines = [
    "# Custom configuration lines",
    "# These are passed through directly to the config"
]
```

**Fields:**
- `lines` (array of strings): Raw configuration lines

## Value Types

### Boolean Values

Use TOML boolean literals:
- `true`, `false`

### String Values

Use double quotes for strings:
- `"ghostty"`, `"$HOME/Pictures"`

### Integer Values

Plain integers without quotes:
- `60`, `1920`, `300`

### Float Values

Decimal numbers:
- `1.0`, `0.95`, `1.5`

### Arrays

TOML arrays use square brackets:
```toml
list = [
    "item1",
    "item2"
]
```

### Tables (Nested Sections)

Use dot notation for nested sections:
```toml
[section.subsection]
key = "value"
```

## Security Considerations

### Path Validation

All file paths in the configuration are validated to prevent directory traversal attacks:
- Paths cannot contain `..`, `//`, or shell metacharacters
- Invalid paths fall back to safe defaults

### Shell Command Safety

Values used in shell commands (like wallpaper paths) are validated:
- Dangerous characters (`;`, `|`, `&`, `$`, etc.) are rejected
- Commands are constructed safely to prevent injection

### Download Security

When downloading base configurations:
- SSL certificates are verified
- Download size is limited (5MB max)
- Content-Type is validated
- Timeouts prevent hanging

### Atomic Writes

All configuration files are written atomically:
- Temporary files are created first
- Data is synced to disk before rename
- Partial writes cannot corrupt existing configs

---

For more information, see the [Hyprland Wiki](https://wiki.hyprland.org/) and the [TOML Specification](https://toml.io/en/v1.0.0).
