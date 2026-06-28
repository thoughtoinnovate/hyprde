# Hyprde Lua Migration Plan

**Date:** 2026-06-28
**Target:** Hyprland 0.55+ (Lua-based configuration)
**Status:** Ready for Implementation

---

## Why Migrate

- Hyprland 0.55+ deprecates hyprlang (`.conf`) in favor of Lua (`.lua`)
- hyprlang will be dropped in 1-2 releases
- Lua enables programmable configs (conditionals, loops, functions)
- Current pipeline: TOML → Python → hyprlang `.conf` (+ download base config + merge)
- Target pipeline: TOML → Python → single `hyprland.lua` (no base config, no merge)

---

## Phase 0: Script Infra — Shell & App Changes

### 0.1 `hyprctl dispatch` → Lua Syntax

Hyprland 0.55 changes the dispatcher string format for `hyprctl dispatch`:

| Old | New |
|-----|-----|
| `hyprctl dispatch exec kitty` | `hyprctl dispatch 'hl.dsp.exec_cmd("kitty")'` |
| `hyprctl dispatch exit` | `hyprctl dispatch 'hl.dsp.exit()'` |
| `hyprctl dispatch dpms on` | `hyprctl dispatch 'hl.dsp.dpms("on")'` |
| `hyprctl dispatch closewindow class:foo` | `hyprctl dispatch 'hl.dsp.closewindow("class:foo")'` |

### 0.2 Files to Update (excludes `build_config.py` — handled in Phase 2)

| File | Change | Notes |
|------|--------|-------|
| `configs/applications/logout.desktop:3` | → `hl.dsp.exit()` | Static file |
| `src/launcher/src/launcher.c:237` | → `hl.dsp.exit()` | C source — **must rebuild** with `zig build` |
| `scripts/waybars.sh:64-65` | → `hl.dsp.closewindow()` | Shell script |
| `scripts/session_menu.sh:25` | → `hl.dsp.exit()` | Shell script |
| `scripts/theme-ctrl.sh:88-89` | **Verify** `hyprctl keyword` | Affects theme switching workflow |
| `scripts/layout-ctrl.sh:6,9` | **Verify** `hyprctl keyword` | Affects layout switching |
| `scripts/gammastep/gamma.sh:97-112` | **Verify** `hyprctl keyword` | Affects nightlight |

### 0.3 `hyprctl keyword` Verification
The `hyprctl keyword` command is used for **runtime** config changes:
- `theme-ctrl.sh` sets border colors immediately via `hyprctl keyword general:col.active_border`
- `layout-ctrl.sh` switches layout via `hyprctl keyword general:layout`
- `gamma.sh` applies/reverts screen shader via `hyprctl keyword decoration:screen_shader`

These may need updating in 0.55 if the `keyword` syntax changed. **Verify against Hyprland 0.55+ during implementation.**

**Fallback if `hyprctl keyword` is removed in 0.55:** Replace runtime keyword calls with `build_config.py && hyprctl reload`. This is slower but guaranteed to work, since `build_config.py` writes full Lua configs and `hyprctl reload` reads them fresh. The theme/layout/gamma scripts would call the config builder instead of directly setting keywords.

### 0.4 `hypridle.conf` DPMS Note
The static `hypridle.conf` in the repo is **generated** by `build_config.py`. The dpms command changes are handled in Phase 2 when we update `generate_hypridle_conf()`. The `hypridle.conf` file format (hyprlang) itself is unchanged — only the shell commands *inside* it need updating.

---

## Phase 1: Lua Generation Engine (`lua_generator.py`)

New Python module. Walks the TOML and emits Lua code.

### 1.1 Config Section → Lua API Mapping

| TOML Section | Lua Output |
|---|---|
| `[programs]` → `key: value` | `local key = "value"` |
| `[monitors]` → `rules[]` | `hl.monitor(name, desc)` |
| `[env]` → `vars[]` | `hl.config({ env = { env = {"KEY,VAL"} } })` |
| `[input]` → settings | `hl.config({ input = { kb_layout = "us", ... } })` |
| `[input.touchpad]` → settings | Nested: `touchpad = { ... }` |
| `[general]` → settings | `hl.config({ general = { gaps_in = 5, ... } })` |
| `[general]` → `col_*` keys | Auto-rename `col_active_border` → `active_border` (no `col.` prefix in Lua) |
| `[decoration]` → settings | `hl.config({ decoration = { rounding = 10, ... } })` |
| `[decoration.blur]` → settings | Nested: `blur = { ... }` |
| `[animations]` | **Verify exact Lua format** during implementation |
| `[dwindle]` | `hl.config({ dwindle = { ... } })` |
| `[master]` | `hl.config({ master = { ... } })` |
| `[scrolling]` | `hl.config({ scrolling = { ... } })` |
| `[misc]` | `hl.config({ misc = { ... } })` |
| `[binds.normal]` | `hl.bind("keys", hl.dsp.dispatcher, { flags })` |
| `[binds.release]` | `hl.bind("keys", hl.dsp.dispatcher, { release = true })` |
| `[binds.mouse]` | `hl.bind()` ... (mouse-specific) |
| `[binds.repeat]` | `hl.bind("keys", hl.dsp.dispatcher, { repeating = true })` |
| `[binds.locked]` | `hl.bind("keys", hl.dsp.dispatcher, { locked = true })` |
| `[rules.window]` | `hl.windowrule({ class = "^...$" }, { float = true, ... })` |
| `[plugin.*]` | `hl.config({ plugin = { name = { ... } } })` |
| `[gesture]` | `hl.config({ gestures = { ... } })` |
| `[submaps.*]` | `hl.on("submap", name, function() ... end)` |
| `[autostart]` → `exec_once[]` | `hl.on("hyprland.start", function() hl.dsp.exec_once("cmd") end)` |
| `[wallpapers]` | `hl.on("hyprland.start", function() hl.dsp.exec_once("script") end)` |
| `[nightlight]` | `hl.on("hyprland.start", function() hl.dsp.exec_once("gammastep ...") end)` |
| `[plugins]` | `hl.on("hyprland.start", function() hl.dsp.exec_once("hyprpm reload -n") end)` |

### 1.2 `$mainMod` Variable

```lua
local mainMod = "SUPER"  -- from TOML [binds] mainMod
```
All binds reference `mainMod` as a Lua variable, not a `$variable` string.

### 1.3 Dispatcher Name Mapping

| hyprlang | Lua |
|---|---|
| `exec` | `hl.dsp.exec_cmd` |
| `exec-once` | `hl.dsp.exec_once` |
| `killactive` | `hl.dsp.window.close` |
| `movewindow` | `hl.dsp.window.move` |
| `resizewindow` | `hl.dsp.window.resize` |
| `workspace` | `hl.dsp.workspace` |
| `movetoworkspace` | `hl.dsp.window.move_to_workspace` |
| `togglespecialworkspace` | `hl.dsp.togglespecialworkspace` |
| `fullscreen` | `hl.dsp.fullscreen` |
| `togglefloating` | `hl.dsp.togglefloating` |
| `pin` | `hl.dsp.window.pin` |
| `hyprexpo:expo` | `hl.dsp.custom("hyprexpo:expo")` (verify) |
| `submap` | `hl.dsp.submap` |

### 1.4 Window Rules → `hl.windowrule()`

```hyprlang
windowrule = float, class:^(kitty)$
```
becomes:
```lua
hl.windowrule({ class = "^(kitty)$" }, { float = true })
```

The current Python conversion logic (selector parsing, action mapping) is reused — only the output format changes from hyprlang block syntax to Lua function calls.

### 1.5 Bind Flag Mapping

Raw TOML bind strings are parsed to extract flags:
```
bind = $mainMod, Q, killactive,        → hl.bind("mainMod, Q", hl.dsp.window.close)
bind = , escape, hyprexpo:expo, toggle → hl.bind(", escape", hl.dsp.custom("hyprexpo:expo"))
```

Each bind type maps to flags:
- `normal` → `{}` (no flags)
- `release` → `{ release = true }`
- `repeat` → `{ repeating = true }`
- `locked` → `{ locked = true }`
- `mouse` → `hl.bind()` with mouse-specific arg

### 1.6 Bind Parsing Complexity

Unlike the current system which passes through raw strings, Lua generation requires **parsing** each bind string:

```
Raw: "$mainMod, T, exec, $terminal"
     ↓ parsed
Keys: "SUPER, T" | Disp: exec | Args: "$terminal"
     ↓ mapped
hl.bind("SUPER, T", hl.dsp.exec_cmd("kitty"))
```

Challenges:
| Pattern | Example | Complexity |
|---------|---------|------------|
| Simple dispatcher | `$mainMod, Q, killactive,` | Easy — no args |
| Dispatcher with args | `$mainMod, left, movefocus, l` | Medium — one arg |
| `exec` with multi-word cmd | `, XF86Audio... exec, wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+` | Hard — variable # of args |
| Plugin dispatcher | `, escape, hyprexpo:expo, off` | Needs `hl.dsp.custom()` |
| Variable substitution | `$mainMod, T, exec, $terminal` | Must resolve `$terminal` to Lua var |
| Empty mod (leading comma) | `, escape, submap, reset` | Must handle empty mod correctly |
| Bind flags (`binde`/`bindl`) | `binde = $mainMod SHIFT, up, resizeactive, 0 -10` | Must extract flag from bind type |

**Strategy:** Split on commas by counting fields. The format is always:
`MODIFIERS, KEY, DISPATCHER [, ARGS...]`
- Field 0: Modifiers (may be empty)
- Field 1: Key
- Field 2: Dispatcher name
- Field 3+: Dispatcher arguments (joined with `, `)

### 1.7 `[custom]` → Lua Passthrough

**Important:** When generating Lua output, old `[custom].lines` (hyprlang) will produce invalid Lua. Solutions:
1. **Preferred:** Support only `[custom].lua_lines` in Lua mode
2. **Transition:** If `[custom].lines` is non-empty in Lua mode, warn but still emit (may fail)
3. **Auto-detect:** Attempt to detect hyprlang vs Lua content (brittle - not recommended)

```toml
[custom]
lua_lines = [  # Only this works in Lua output mode
    "hl.config({ misc = { disable_hyprland_logo = false } })",
    "-- random Lua comment"
]
lines = []     # Ignored in Lua mode, warn if non-empty
```

### 1.8 ICC Profile Support (NEW in 0.55)

New optional TOML section:
```toml
[color]
icc_profiles = [
    "DP-1,/home/user/profiles/srgb.icc",
]
```
Generated to:
```lua
hl.config({
    color = {
        icc_profiles = { "DP-1,/home/user/profiles/srgb.icc" }
    }
})
```

---

## Phase 2: `build_config.py` Surgery

### Remove
- `download_base()` — no more upstream config download
- `generate_user_conf()` — replaced by Lua generator
- `create_main_conf()` — replaced by `create_main_lua()`
- `BASE_CONF`, `USER_CONF`, `MAIN_CONF` path constants
- Base config sanitization logic
- Version change detection for base config caching

### Keep (unchanged)
- `generate_hyprpaper_conf()` — hyprpaper still uses hyprlang format
- `generate_hyprlock_conf()` — hyprlock still uses hyprlang format
- `generate_wallpaper_schedule_config()`
- `generate_fixed_wallpaper_config()`
- `generate_css_overrides()`
- `generate_hyrocket_systemd_units()`
- `is_plugin_installed_and_enabled()` — still needed for hyprpm checks
- `validate_shell_safe()` — still needed for exec commands
- `atomic_write()` — still needed for all file writes
- `get_config_dir()` — still needed for path resolution

### Add
- `generate_user_lua()` → returns string of Lua config
- `create_main_lua(content)` → writes `~/.config/hypr/hyprland.lua`

### Modified
- `generate_hypridle_conf()` — change shell commands inside from `hyprctl dispatch dpms on/off` → `hyprctl dispatch 'hl.dsp.dpms("on"/"off")'`. The *file format* stays hyprlang, only the *shell command strings* change.
- `generate_hyprpaper_conf()` — **verify** if hyprpaper commands also changed

---

## Phase 3: Config Simplification

### 4.1 TOML Simplifications

- **Auto-detect monitors** at build time: `hyprctl monitors -j` data can fill in defaults if user omits `[monitors]`
- **Simpler binds**: Support shorthand syntax in TOML:
  ```toml
  [binds.normal]
  shortcuts = {
    "SUPER, T" = "exec, kitty",
    "SUPER, Q" = "killactive",
  }
  ```
  (Keeps backward compat with existing `list = []` format too)
- **Sensible defaults**: Reduce required TOML fields — everything has a default
- **Validation**: Add TOML schema validation with clear error messages before generation
- **`hyprctl getoption` integration**: Warn if TOML values conflict with Hyprland's own defaults

### 4.2 Lua Output Readability

Generated Lua will be well-commented and sectioned so users can:
- Read and understand the generated config
- Manually edit the Lua if they need escape hatches
- See exactly which TOML section produced which Lua block

Example:
```lua
-- [[ Generated by hyprde build_config.py ]]
-- Edit ~/.config/hypr/hyprde.toml, then run: python3 build_config.py

-- [[ Programs ]]
local terminal     = "kitty"
local fileManager  = "thunar"
local menu         = "rofi -show drun"
local mainMod      = "SUPER"

-- [[ Monitors ]]
hl.monitor("DP-1", "1920x1080@60,0x0,1")
hl.monitor("HDMI-A-1", "preferred,auto,1")

-- [[ General ]]
hl.config({
    general = {
        gaps_in             = 5,
        gaps_out            = 10,
        border_size         = 2,
        active_border       = "rgba(33ccffee) rgba(00ff99ee) 45deg",
        inactive_border     = "rgba(595959aa)",
        cursor_inactive_timeout = 3,
        layout              = "dwindle",
    }
})
...
```

---

## Phase 4: Testing

### Unit Tests (`test_builder.py`)
- Update all existing tests to expect Lua output instead of hyprlang
- Add Lua-specific tests:
  - Each TOML section → correct Lua API call
  - Bind parsing → correct dispatcher mapping
  - Window rules → correct `hl.windowrule()` format
  - Color key conversion (no more `col.` prefix)
  - Boolean normalization (Lua `true`/`false` not lowercase)
  - `[custom]` passthrough
  - ICC profile generation (new)

### Syntax Validation
- Add `luacheck` or `lua -e "loadfile(...)"` to CI/CD
- Verify generated Lua files parse without errors

### Integration Tests
- Update `validate_config_headless.sh` to test Lua config
- Requires Hyprland 0.55+ with Lua parser support
- Docker image may need updating

### Script Testing
- Test every `hyprctl dispatch` change with `dry-run` or mock
- Verify `hyprctl keyword` still works in 0.55

---

## Phase 5: Documentation

- Update `AGENTS.md` — new build/test commands, Lua-specific conventions
- Update `CONFIG_SCHEMA.md` — add `[custom].lua_lines`, `[color].icc_profiles`, deprecate `[custom].lines`
- Migration notes for users — especially `hyprctl dispatch` syntax change and 0.55+ requirement
- Update README with 0.55+ requirement

---

## Implementation Order

```
Phase 0 — Script Infra (excludes build_config.py)
├── Update hyprctl dispatch calls in scripts + launcher.c
├── Rebuild launcher binary: zig build
├── Verify hyprctl keyword syntax in 0.55
└── Test all runtime scripts

Phase 1 — Lua Generator
├── Create lua_generator.py
├── Implement section→Lua for all TOML sections
├── Handle bind parsing complexity (field splitting + mapping)
├── Handle edge cases: booleans, colors, animations
├── Handle [custom].lua_lines passthrough
└── Write unit tests alongside

Phase 2 — build_config.py Surgery
├── Remove download_base/hyprlang output functions
├── Wire in lua_generator.py
├── Update generate_hypridle_conf() dpms commands (dispatch syntax)
├── Add ICC profile support
└── Remove/handle old [custom].lines for Lua mode

Phase 3 — Config Simplification
├── TOML schema validation with error messages
├── Monitor auto-detection via hyprctl monitors -j
├── Shorthand binds format (dict style)
└── Sensible defaults reduction

Phase 4 — Testing
├── Update all unit tests for Lua output
├── Lua syntax validation in CI
├── Integration test with Hyprland 0.55+
└── Script regression tests (dispatch + keyword paths)

Phase 5 — Documentation
├── Update AGENTS.md
├── Update CONFIG_SCHEMA.md
├── Migration notes for users (esp. dispatch syntax)
└── Update README with 0.55+ requirement
```

---

## Items Needing Verification During Implementation

These are open questions that need testing against a real Hyprland 0.55+ instance:

1. **`hyprctl keyword` in 0.55** — Does `hyprctl keyword general:layout dwindle` still work, or does it need the Lua syntax? Affects `theme-ctrl.sh`, `layout-ctrl.sh`, `gamma.sh`.
2. **Animation Lua format** — Exact Lua API for bezier curves and named animation rules
3. **Plugin config Lua format** — Does `hl.config({ plugin = { hyprscrolling = { ... } } })` work?
4. **`hl.bind()` dispatcher as string vs function** — Can you pass a string or must it be a function reference?
5. **`hl.dsp.custom()`** — Does this exist for plugin dispatchers like `hyprexpo:expo`?
6. **Hyprland version detection** — `hyprctl version` output format for version checking
7. **Companion tool compatibility** — Do hypridle/hyprlock/hyprpaper work with 0.55 unchanged?
8. **`hyprctl reload` with Lua configs** — Does `hyprctl reload` correctly detect and reload `hyprland.lua` instead of `hyprland.conf`? If a stale `.conf` exists, which wins?
9. **Theme switch workflow** — `theme-ctrl.sh` calls `build_config.py` then `hyprctl keyword`. Will the `keyword` call work post-migration? Or does the theme script need to only use `build_config.py` + `hyprctl reload`?

---

## Backward Compatibility

No backward compatibility. Hyprland 0.55+ is required. Old hyprlang code paths (`download_base()`, `generate_user_conf()`, `create_main_conf()`) are removed entirely.

---

## Key Benefits After Migration

1. **Simpler pipeline** — One output file instead of multiple .conf files
2. **No more base config download** — Lua configs are self-contained
3. **Programmability** — Conditional logic, loops, functions in config
4. **Future-proof** — Ready for hyprlang removal
5. **Easier debugging** — Single file to inspect
6. **Better UX** — Monitor auto-detection, simpler binds, validation
