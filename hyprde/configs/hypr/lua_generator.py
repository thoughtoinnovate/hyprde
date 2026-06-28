"""Generate Hyprland Lua configuration from parsed TOML data."""

import logging
import os
import subprocess
import re

logger = logging.getLogger(__name__)

# Dispatcher name mapping: hyprlang name → hl.dsp.* function
DISPATCHER_MAP = {
    "exec": "hl.dsp.exec_cmd",
    "exec-once": "hl.dsp.exec_cmd",
    "killactive": "hl.dsp.window.close",
    "movewindow": "hl.dsp.window.move",
    "resizewindow": "hl.dsp.window.resize",
    "movefocus": "hl.dsp.focus",
    "workspace": "hl.dsp.focus",
    "movetoworkspace": "hl.dsp.window.move",
    "togglespecialworkspace": "hl.dsp.workspace.toggle_special",
    "fullscreen": "hl.dsp.window.fullscreen",
    "togglefloating": "hl.dsp.window.float",
    "pin": "hl.dsp.window.pin",
    "exit": "hl.dsp.exit",
    "closewindow": "hl.dsp.closewindow",
    "dpms": "hl.dsp.dpms",
    "submap": "hl.dsp.submap",
    "togglesplit": "hl.dsp.layout",
    "layoutmsg": "hl.dsp.layout",
    "resizeactive": "hl.dsp.window.resize",
    "mouse": "hl.dsp.mouse",
}

# Dispatchers whose argument must be a Lua table instead of a quoted string.
# The value is a callable(old_arg_string) → table string (without outer braces).
TABLE_ARG_DISPATCHERS = {
    "fullscreen":      lambda a: 'mode = "maximized"' if a == "1" else ('mode = "fullscreen"' if a == "0" else f'mode = "{a}"'),
    "togglefloating":  lambda a: 'action = "toggle"',
    "workspace":       lambda a: f'workspace = {_try_int(a)}',
    "movefocus":       lambda a: f'direction = {_value_to_lua(a)}',
    "movetoworkspace": lambda a: f'workspace = {_try_int(a)}',
    "movewindow":      lambda a: f'direction = {_value_to_lua(a)}',
    "resizeactive":    lambda a: _parse_resizeactive(a),
}

# Default arguments for dispatchers that need a non-empty arg even when omitted
DEFAULT_DISPATCHER_ARGS = {
    "togglesplit": "togglesplit",
}

# Cache for hyprpm check results (shared across calls)
_PLUGIN_CACHE: dict = {}


def _try_int(s: str):
    try:
        return int(s)
    except ValueError:
        return f'"{s}"'


def _parse_resizeactive(s: str) -> str:
    parts = s.strip().split()
    if len(parts) >= 2:
        return f'x = {parts[0]}, y = {parts[1]}, relative = true'
    return s


def _is_plugin_installed(plugin_name: str) -> bool:
    if plugin_name in _PLUGIN_CACHE:
        return _PLUGIN_CACHE[plugin_name]
    try:
        output = subprocess.check_output(["hyprpm", "list"], stderr=subprocess.STDOUT, text=True)
        pattern = rf"Plugin {re.escape(plugin_name)}\s+└─ enabled: true"
        result = bool(re.search(pattern, output, re.MULTILINE))
        _PLUGIN_CACHE[plugin_name] = result
        return result
    except Exception:
        _PLUGIN_CACHE[plugin_name] = False
        return False


def _value_to_lua(val):
    """Convert a Python value to a Lua literal string."""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, str):
        escaped = val.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(val, (list, tuple)):
        items = [_value_to_lua(v) for v in val]
        if not items:
            return "{}"
        return "{ " + ", ".join(items) + " }"
    if isinstance(val, dict):
        return _dict_to_lua_table(val, 1)
    logger.warning("Unsupported config value type: %s", type(val).__name__)
    return str(val)


def _dict_to_lua_table(d, indent=1):
    """Convert a Python dict to a Lua table string with proper indentation."""
    if not d:
        return "{}"
    pad = "    " * indent
    inner = "    " * (indent + 1)
    items = []
    for k, v in d.items():
        if isinstance(v, dict):
            items.append(f"{inner}{k} = {_dict_to_lua_table(v, indent + 1)}")
        else:
            items.append(f"{inner}{k} = {_value_to_lua(v)}")
    return "{\n" + ",\n".join(items) + f"\n{pad}}}"


def _resolve_var(val: str, programs: dict, main_mod: str) -> str:
    """Replace $variables with their values."""
    result = val
    result = result.replace("$mainMod", main_mod)
    result = result.replace("$HOME", os.path.expanduser("~"))
    if result.startswith("~/"):
        result = os.path.expanduser("~") + result[1:]
    for k, v in programs.items():
        result = result.replace(f"${k}", str(v))
    return result


def _parse_bind(raw: str, programs: dict, main_mod: str, bind_type: str) -> str:
    """Parse a raw bind string and return a Lua hl.bind() call.

    Old format: MODIFIERS, KEY, DISPATCHER [, ARGS...]
    """
    raw_parts = [p.strip() for p in raw.split(",")]
    if len(raw_parts) < 3:
        logger.warning("Cannot parse bind (too few fields): %s", raw)
        return f"-- [[ SKIPPED: {raw} ]]"

    mods = raw_parts[0]
    key = raw_parts[1]
    dispatcher = raw_parts[2]
    args_list = [p for p in raw_parts[3:] if p]
    args = ",".join(args_list) if args_list else ""

    mods = _resolve_var(mods, programs, main_mod)
    key = _resolve_var(key, programs, main_mod)
    args = _resolve_var(args, programs, main_mod)

    # New Hyprland 0.55 key format: "MOD + KEY" with + separator
    mod_parts = [m for m in mods.split() if m]
    mods_joined = " + ".join(mod_parts) if mod_parts else ""
    bind_key = f"{mods_joined} + {key}" if mods_joined else key

    if dispatcher == "movewindow" and bind_type == "mouse":
        dsp_call = "hl.dsp.window.drag()"
    elif dispatcher in DISPATCHER_MAP:
        dsp_func = DISPATCHER_MAP[dispatcher]
        if dispatcher in TABLE_ARG_DISPATCHERS:
            arg_str = TABLE_ARG_DISPATCHERS[dispatcher](args)
            dsp_call = f"{dsp_func}({{ {arg_str} }})"
        elif args:
            dsp_call = f'{dsp_func}("{args}")'
        elif dispatcher in DEFAULT_DISPATCHER_ARGS:
            dsp_call = f'{dsp_func}("{DEFAULT_DISPATCHER_ARGS[dispatcher]}")'
        else:
            dsp_call = f"{dsp_func}()"
    else:
        if args:
            dsp_call = f'function() hl.dispatch("{dispatcher}", "{args}") end'
        else:
            dsp_call = f'function() hl.dispatch("{dispatcher}") end'

    flag_map = {
        "normal": "",
        "release": ', { release = true }',
        "mouse": ", nil",
        "repeat": ', { repeating = true }',
        "locked": ', { locked = true }',
    }
    flags = flag_map.get(bind_type, "")
    return f'hl.bind("{bind_key}", {dsp_call}{flags})'


def generate_user_lua(data: dict) -> str:
    """Generate a complete Hyprland Lua configuration string from TOML data."""
    lines = []
    _header(lines)
    programs = data.get("programs", {})
    main_mod = data.get("binds", {}).get("mainMod", "SUPER")

    _write_programs(lines, programs)
    lines.append(f'local mainMod = "{main_mod}"')
    lines.append("")
    _write_autostart(lines, data)
    _write_wallpapers(lines, data)
    _write_nightlight(lines, data)
    _write_plugins(lines, data)
    _write_env(lines, data)
    _write_monitors(lines, data)
    _write_gestures(lines, data)
    hl_config_parts = _collect_hl_config(data)

    if hl_config_parts:
        lines.append(f"hl.config({_dict_to_lua_table(hl_config_parts, 0)})")

    _write_animations(lines, data)

    hyprexpo_available = _check_hyprexpo(data)
    _write_binds(lines, data, programs, main_mod, hyprexpo_available)
    _write_window_rules(lines, data)
    _write_submaps(lines, data, hyprexpo_available)
    _write_custom(lines, data)

    return "\n".join(lines)


def _header(lines: list):
    lines.append("-- [[ Generated by hyprde build_config.py ]]")
    lines.append("-- Edit ~/.config/hypr/hyprde.toml, then run: python3 build_config.py")
    lines.append("")


def _write_programs(lines: list, programs: dict):
    if not programs:
        return
    lines.append("-- [[ Programs ]]")
    for k, v in programs.items():
        if k == "autohide_bar":
            continue
        lines.append(f'local {k} = {_value_to_lua(v)}')


def _expand_vars_in_cmd(cmd: str, programs: dict, main_mod: str) -> str:
    """Expand $variables in a command string using programs dict."""
    result = cmd
    result = result.replace("$mainMod", main_mod)
    result = result.replace("$HOME", os.path.expanduser("~"))
    for k, v in programs.items():
        result = result.replace(f"${k}", str(v))
    return result


def _write_autostart(lines: list, data: dict):
    cmds = data.get("autostart", {}).get("exec_once", [])
    if not cmds:
        return
    programs = data.get("programs", {})
    main_mod = data.get("binds", {}).get("mainMod", "SUPER")
    lines.append("-- [[ Autostart ]]")
    for cmd in cmds:
        expanded = _expand_vars_in_cmd(cmd, programs, main_mod)
        escaped = expanded.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'hl.on("hyprland.start", function() hl.exec_cmd("{escaped}") end)')
    lines.append("")


def _write_wallpapers(lines: list, data: dict):
    wp = data.get("wallpapers", {})
    mode = wp.get("mode", "fixed")
    if mode in ("fixed", "dynamic"):
        home = os.path.expanduser("~")
        cmd = f"sh {home}/.config/hypr/scripts/init_wallpaper.sh"
        lines.append("-- [[ Wallpapers ]]")
        lines.append(f'hl.on("hyprland.start", function() hl.exec_cmd("{cmd}") end)')
        lines.append("")


def _write_nightlight(lines: list, data: dict):
    nl = data.get("nightlight", {})
    if nl.get("enabled", False):
        t_day = nl.get("temp_day", 6500)
        t_night = nl.get("temp_night", 3400)
        cmd = f"gammastep -t {t_day}:{t_night}"
        lines.append("-- [[ Nightlight ]]")
        lines.append(f'hl.on("hyprland.start", function() hl.exec_cmd("{cmd}") end)')
        lines.append("")


def _write_plugins(lines: list, data: dict):
    pl = data.get("plugins", {})
    if pl.get("enabled", []):
        lines.append("-- [[ Hyprpm Plugin Reload ]]")
        lines.append('hl.on("hyprland.start", function() hl.exec_cmd("hyprpm reload -n") end)')
        lines.append("")


def _write_env(lines: list, data: dict):
    env_vars = data.get("env", {}).get("vars", [])
    if not env_vars:
        return
    lines.append("-- [[ Environment Variables ]]")
    lines.append("hl.config({")
    lines.append("    env = {")
    for var in env_vars:
        lines.append(f"        \"{var}\",")
    lines.append("    }")
    lines.append("})")
    lines.append("")


def _write_monitors(lines: list, data: dict):
    monitor_rules = data.get("monitors", {}).get("rules", [])
    if not monitor_rules:
        return
    lines.append("-- [[ Monitors ]]")
    for rule in monitor_rules:
        parts = [p.strip() for p in rule.split(",", 3)]
        name = parts[0] if len(parts) > 0 else ""
        mode = parts[1] if len(parts) > 1 else "preferred"
        position = parts[2] if len(parts) > 2 else "auto"
        scale = parts[3] if len(parts) > 3 else "auto"
        table_fields = [
            f"output = {_value_to_lua(name)}",
            f"mode = {_value_to_lua(mode)}",
            f"position = {_value_to_lua(position)}",
            f"scale = {_value_to_lua(scale)}",
        ]
        lines.append(f"hl.monitor({{ {', '.join(table_fields)} }})")
    lines.append("")


def _collect_hl_config(data: dict) -> dict:
    """Collect all sections that go into a single hl.config({...}) call."""
    config = {}

    _merge_input(config, data)
    _merge_general(config, data)
    _merge_decoration(config, data)
    _merge_animations(config, data)
    _merge_dwindle(config, data)
    _merge_master(config, data)
    _merge_scrolling(config, data)
    _merge_misc(config, data)
    _merge_plugin_config(config, data)

    return config


def _merge_input(config: dict, data: dict):
    inp = data.get("input")
    if not inp:
        return
    section = {}
    for k, v in inp.items():
        if isinstance(v, dict):
            continue
        section[k] = v
    if "touchpad" in inp:
        section["touchpad"] = dict(inp["touchpad"])
    if section:
        config["input"] = section


def _parse_border_value(value: str):
    """Parse old border color/gradient into Lua table or string for col subtable."""
    parts = value.strip().split()
    if len(parts) == 1:
        return parts[0]
    colors = []
    angle = None
    for p in parts:
        if p.endswith("deg"):
            angle = int(p[:-3])
        else:
            colors.append(p)
    result = {"colors": colors}
    if angle is not None:
        result["angle"] = angle
    return result


def _merge_general(config: dict, data: dict):
    gen = data.get("general")
    if not gen:
        return
    section = {}
    color_section = {}
    for k, v in gen.items():
        if k.startswith("col_"):
            color_section[k[4:]] = _parse_border_value(v)
        else:
            section[k] = v
    if color_section:
        section["col"] = color_section
    config["general"] = section


def _merge_decoration(config: dict, data: dict):
    deco = data.get("decoration")
    if not deco:
        return
    section = {}
    for k, v in deco.items():
        if isinstance(v, dict):
            continue
        if k in ("waybar_opacity", "wofi_opacity"):
            continue
        clean_key = k.replace("col_", "")
        section[clean_key] = v
    if "blur" in deco:
        section["blur"] = dict(deco["blur"])
    if section:
        config["decoration"] = section


def _merge_animations(config: dict, data: dict):
    anim = data.get("animations")
    if not anim:
        return
    section = {}
    if "enabled" in anim:
        section["enabled"] = anim["enabled"]
    if "speed" in anim:
        section["speed"] = anim["speed"]
    if section:
        config["animations"] = section


def _write_animations(lines: list, data: dict):
    anim = data.get("animations")
    if not anim:
        return

    wrote_header = False
    curves_written = set()

    for key, value in anim.items():
        if key in ("enabled", "speed"):
            continue

        if key == "bezier" and isinstance(value, str):
            parts = [p.strip() for p in value.split(",", 4)]
            name = parts[0]
            if len(parts) == 5:
                pts = [f"{{ {parts[1]}, {parts[2]} }}", f"{{ {parts[3]}, {parts[4]} }}"]
                if not wrote_header:
                    lines.append("-- [[ Animations ]]")
                    wrote_header = True
                lines.append(f'hl.curve("{name}", {{ type = "bezier", points = {{ {", ".join(pts)} }} }})')
                curves_written.add(name)
            continue

        if isinstance(value, str) and "," in value:
            vparts = [p.strip() for p in value.split(",", 3)]
            if len(vparts) < 3:
                continue
            enabled = vparts[0] == "1"
            speed = vparts[1]
            curve = vparts[2]
            style = vparts[3] if len(vparts) > 3 else None

            if not wrote_header:
                lines.append("-- [[ Animations ]]")
                wrote_header = True

            fields = [f'leaf = "{key}"', f"enabled = {str(enabled).lower()}", f"speed = {speed}"]
            if curve:
                fields.append(f'bezier = "{curve}"')
            if style:
                fields.append(f'style = "{style}"')

            lines.append(f"hl.animation({{ {', '.join(fields)} }})")

    if wrote_header:
        lines.append("")


def _merge_dwindle(config: dict, data: dict):
    dwindle = data.get("dwindle")
    if dwindle:
        filtered = {k: v for k, v in dwindle.items() if k not in ("pseudotile",)}
        if filtered:
            config["dwindle"] = filtered


def _merge_master(config: dict, data: dict):
    master = data.get("master")
    if master:
        config["master"] = dict(master)


def _merge_scrolling(config: dict, data: dict):
    scrolling = data.get("scrolling")
    if scrolling:
        config["scrolling"] = dict(scrolling)


def _merge_misc(config: dict, data: dict):
    misc = data.get("misc")
    if misc:
        config["misc"] = dict(misc)


def _write_gestures(lines: list, data: dict):
    gesture_data = data.get("gesture")
    if not gesture_data:
        return
    gesture_list = gesture_data.get("list", [])
    if not gesture_list:
        return
    lines.append("-- [[ Gestures ]]")
    for gesture_str in gesture_list:
        lines.append(f"hl.gesture({{ {gesture_str} }})")
    lines.append("")


def _merge_plugin_config(config: dict, data: dict):
    plugin = data.get("plugin")
    if not plugin:
        return
    pl = data.get("plugins", {})
    enabled_plugins = pl.get("enabled", [])
    filtered = {}
    for plugin_name, plugin_config in plugin.items():
        if plugin_name in enabled_plugins and _is_plugin_installed(plugin_name):
            filtered[plugin_name] = plugin_config
    if filtered:
        config["plugin"] = filtered


def _check_hyprexpo(data: dict) -> bool:
    """Check if hyprexpo plugin is enabled."""
    pl = data.get("plugins", {})
    if "hyprexpo" not in pl.get("enabled", []):
        return False
    return _is_plugin_installed("hyprexpo")


def _shortcut_to_bind_string(key: str, value: str) -> str:
    """Convert a shorthand bind entry to a raw bind string.

    Shorthand: "SUPER, T" = "exec, kitty"  →  "SUPER, T, exec, kitty"
    """
    dispatcher_and_args = value.strip()
    return f"{key}, {dispatcher_and_args}"


def _collect_raw_binds(section: dict) -> list:
    """Collect all bind strings from a section, supporting both list and shortcuts dict."""
    result = list(section.get("list", []))
    for key, value in section.get("shortcuts", {}).items():
        result.append(_shortcut_to_bind_string(key, value))
    return result


def _write_binds(lines: list, data: dict, programs: dict, main_mod: str, hyprexpo_available: bool):
    binds = data.get("binds")
    if not binds:
        return
    lines.append("-- [[ Keybindings ]]")
    bind_sections = {
        "normal": "",
        "release": "release",
        "mouse": "mouse",
        "repeat": "repeat",
        "locked": "locked",
    }
    for section_name, bind_type in bind_sections.items():
        section = binds.get(section_name, {})
        bind_list = _collect_raw_binds(section)
        for b in bind_list:
            if "hyprexpo" in b.lower() and not hyprexpo_available:
                lines.append(f"-- [[ SKIPPED hyprexpo (not available): {b} ]]")
                continue
            try:
                out = _parse_bind(b, programs, main_mod, bind_type or "normal")
                lines.append(f"{out}")
            except Exception as e:
                lines.append(f'-- [[ ERROR parsing bind: {e} ]]')
                lines.append(f"-- {b}")
    lines.append("")


def _write_window_rules(lines: list, data: dict):
    rules = data.get("rules", {}).get("window", [])
    if not rules:
        return
    lines.append("-- [[ Window Rules ]]")
    for rule in rules:
        import re
        parts = [p.strip() for p in rule.split(",", 1)]
        if len(parts) != 2:
            lines.append(f"-- [[ SKIPPED invalid rule: {rule} ]]")
            continue
        action_raw = parts[0]
        selector_raw = parts[1]
        if selector_raw.startswith("class:"):
            selector_val = selector_raw[6:]
            selector = f'{{ match = {{ class = "{selector_val}" }} }}'
        elif selector_raw.startswith("title:"):
            selector_val = selector_raw[6:]
            selector = f'{{ match = {{ title = "{selector_val}" }} }}'
        else:
            selector = f'{{ match = {{ class = "{selector_raw}" }} }}'
        props = _rule_action_to_props(action_raw)
        lines.append(f"hl.window_rule({selector}, {props})")
    lines.append("")


def _rule_action_to_props(action_raw: str) -> str:
    """Convert a legacy window rule action string to a Lua props table."""
    action = action_raw.strip()
    parts = action.split(None, 1)
    cmd = parts[0]
    arg = parts[1] if len(parts) > 1 else ""
    prop_map = {
        "float": "{ float = true }",
        "pin": "{ pin = true }",
        "center": "{ center = true }",
    }
    if cmd in prop_map:
        return prop_map[cmd]
    if cmd in ("size", "opacity", "animation", "rounding"):
        return f'{{ {cmd} = "{arg}" }}'
    if cmd == "suppressevent":
        return f'{{ suppress_event = "{arg}" }}'
    return f'{{ ["{action}"] = true }}'


def _write_submaps(lines: list, data: dict, hyprexpo_available: bool):
    submaps = data.get("submaps")
    if not submaps:
        return
    lines.append("-- [[ Submaps ]]")
    for submap_name, submap_data in submaps.items():
        if submap_name == "expo" and not hyprexpo_available:
            lines.append(f"-- [[ SKIPPED submap expo (hyprexpo not available) ]]")
            continue
        binds = submap_data.get("binds", [])
        if not binds:
            continue
        lines.append(f'hl.on("submap", "{submap_name}", function()')
        for b in binds:
            if "hyprexpo" in b.lower() and not hyprexpo_available:
                continue
            try:
                out = _parse_bind(b, data.get("programs", {}), data.get("binds", {}).get("mainMod", "SUPER"), "normal")
                lines.append(f"    {out}")
            except Exception as e:
                lines.append(f"    -- ERROR parsing bind: {e}")
        lines.append("end)")
        lines.append("")


def _write_custom(lines: list, data: dict):
    custom = data.get("custom")
    if not custom:
        return
    lua_lines = custom.get("lua_lines", [])
    hyprlang_lines = custom.get("lines", [])
    if lua_lines:
        lines.append("-- [[ Custom Lua Lines ]]")
        lines.extend(lua_lines)
        lines.append("")
    if hyprlang_lines:
        logger.warning(
            "[custom].lines contains hyprlang content which is not valid in Lua mode. "
            "Use [custom].lua_lines instead."
        )
        lines.append("-- [[ WARNING: [custom].lines is ignored in Lua mode ]]")
        for l in hyprlang_lines:
            lines.append(f"-- [[ IGNORED: {l} ]]")
        lines.append("")
