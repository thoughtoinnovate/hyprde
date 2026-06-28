# Development Guidelines

## 🛠 Build & Test Commands

### Installation
- **Full Install**: `sudo ./hyprde/install.sh`

### Configuration Building
- **Edit Config**: `hyprde/configs/hypr/hyprde.toml`
- **Rebuild**: `python3 hyprde/configs/hypr/build_config.py`
- **Output**: `~/.config/hypr/hyprland.lua` (Hyprland 0.55+ Lua format)

### Testing
- **Run Unit Tests**: `./hyprde/configs/hypr/run_tests.sh`
- **Shell Check**: `bash -n hyprde/configs/hypr/scripts/*.sh`

## 📜 Code Style

### Python (Config Builder)
- Use standard library (`tomllib`, `json`, `subprocess`).
- Compatible with Python 3.11+.
- Use `unittest` for all logic verification.

### Lua Generator (`lua_generator.py`)
- New modules go in `configs/hypr/` next to `build_config.py`.
- Use `hl.config({...})` for structured settings.
- Use `hl.bind("MOD + KEY", hl.dsp.dispatcher(args))` for keybinds (`+` separator, not comma).
- Use `hl.on("hyprland.start", function() ... end)` for autostart.
- Use `_parse_bind()` for converting raw comma-separated bind strings.
- Animations: use `hl.curve()` for bezier definitions, `hl.animation({leaf="...", ...})` for each leaf.
- Monitors: use `hl.monitor({output="...", mode="...", position="...", scale="..."})` table format.
- Window rules: use `hl.window_rule({ match = { class = "..." } }, { ... })` with `match` wrapper.

### Shell Scripts
- `#!/bin/bash` shebang.
- Functions: `function_name() { ... }`.
- Double-quote variables: `"$var"`.

### `hyprctl dispatch` Syntax (Hyprland 0.55+)
- Old: `hyprctl dispatch exit`
- New: `hyprctl dispatch 'hl.dsp.exit()'`
- Old: `hyprctl dispatch closewindow class:foo`
- New: `hyprctl dispatch 'hl.dsp.closewindow("class:foo")'`

### TOML Config
- `[binds.normal]` supports both `list = []` (raw) and `shortcuts = {}` (shorthand dict):
  ```toml
  [binds.normal]
  shortcuts = { "SUPER, T" = "exec, kitty", "SUPER, Q" = "killactive" }
  ```
- `[custom].lines` is **deprecated** in Lua mode. Use `[custom].lua_lines` instead.
- `mainMod` in `[binds]` must be uppercase (`SUPER`, `ALT`, `CTRL`).
- If `[monitors]` is omitted, monitors are auto-detected at build time.

### Keybind Dispatcher Mapping
| hyprlang name | Lua function |
|---|---|---|
| `exec` | `hl.dsp.exec_cmd` |
| `killactive` | `hl.dsp.window.close` |
| `movefocus` | `hl.dsp.focus({ direction = "..." })` |
| `movewindow` | `hl.dsp.window.drag()` (mouse) / `hl.dsp.window.move({ direction = "..." })` |
| `workspace` | `hl.dsp.focus({ workspace = N })` |
| `movetoworkspace` | `hl.dsp.window.move({ workspace = N })` |
| `togglespecialworkspace` | `hl.dsp.workspace.toggle_special("name")` |
| `fullscreen` | `hl.dsp.window.fullscreen({ mode = "maximized" })` |
| `togglefloating` | `hl.dsp.window.float({ action = "toggle" })` |
| `exit` | `hl.dsp.exit` |
| `closewindow` | `hl.dsp.closewindow` |
| `dpms` | `hl.dsp.dpms` |
| `togglesplit` | `hl.dsp.layout("togglesplit")` |
| `layoutmsg` | `hl.dsp.layout("...")` |
| `resizeactive` | `hl.dsp.window.resize({ x = N, y = N, relative = true })` |
| `hyprexpo:expo` | `hl.dsp.custom("hyprexpo:expo", args)` |

### Git Workflow
- Atomic commits preferred.
- Conventional commit messages (`feat:`, `fix:`, `test:`, `docs:`).
