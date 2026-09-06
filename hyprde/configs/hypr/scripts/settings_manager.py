#!/usr/bin/env python3
import sys
import os
import time
import logging
import atexit
import fcntl
import subprocess
import re
import threading
import traceback

LOCK_FILE = "/tmp/hyprde-settings.pid"
LOG_FILE = os.path.expanduser("~/.config/hypr/settings.log")
_LOCK_FD = None

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s settings_manager %(levelname)s %(message)s',
)
logger = logging.getLogger(__name__)


def _notify_error(summary, body=""):
    try:
        subprocess.run(["notify-send", "-t", "5000", summary, body],
                       capture_output=True, timeout=5)
    except Exception:
        pass


def _missing_dep_exit(dep, hint):
    msg = f"Missing dependency '{dep}': {hint}. See {LOG_FILE}"
    logger.error(msg)
    _notify_error("HyprDE Settings", msg)
    print(msg, file=sys.stderr)
    sys.exit(1)


try:
    import tomlkit
except ImportError:
    _missing_dep_exit("tomlkit", "install python-tomlkit (Arch) / python3-tomlkit (Debian)")

try:
    import gi
except ImportError:
    _missing_dep_exit("pygobject", "install python-gobject (Arch) / python3-gi (Debian)")

try:
    gi.require_version('Gtk', '3.0')
except (ValueError, ImportError) as e:
    _missing_dep_exit("Gtk", f"{e}; install gtk3")

try:
    gi.require_version('GdkPixbuf', '2.0')
except (ValueError, ImportError):
    pass

from gi.repository import Gtk, Gdk, Gio, GLib, Pango
try:
    from gi.repository import GdkPixbuf
except ImportError:
    GdkPixbuf = None
import signal

def check_single_instance():
    global _LOCK_FD
    try:
        _LOCK_FD = open(LOCK_FILE, 'w')
        fcntl.flock(_LOCK_FD.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _LOCK_FD.write(str(os.getpid()))
        _LOCK_FD.flush()
        atexit.register(cleanup_lock)
    except (OSError, IOError) as e:
        logger.info(f"Another settings instance is running, attempting to close it...")
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            import signal
            os.kill(old_pid, signal.SIGTERM)
        except Exception:
            pass
        sys.exit(0)

def cleanup_lock():
    global _LOCK_FD
    try:
        if _LOCK_FD is not None:
            try:
                fcntl.flock(_LOCK_FD.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                _LOCK_FD.close()
            except Exception:
                pass
            _LOCK_FD = None
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass
    except Exception:
        pass

def get_theme_colors():
    theme_path = os.path.expanduser("~/.config/hypr/themes/current.css")
    colors = {
        "is_light": False,
        "base_bg": "#1e1e21",
        "base_fg": "#ffffff",
        "module_bg": "#2d2d2d",
        "module_fg": "#ffffff",
        "active_bg": "#007aff",
        "active_fg": "#ffffff",
        "hover_bg": "#505050",
        "border": "rgba(255, 255, 255, 0.15)",
        "accent": "#007aff"
    }
    if os.path.exists(theme_path):
        try:
            with open(theme_path, 'r') as f:
                content = f.read()
                def find_color(var):
                    m = re.search(f"@define-color\\s+{var}\\s+([^;]+);", content)
                    if not m:
                        m = re.search(f"{var}\\s+([^;]+);", content)
                    return m.group(1).strip() if m else None
                colors["base_bg"] = find_color("theme_base_bg") or colors["base_bg"]
                colors["base_fg"] = find_color("theme_base_fg") or colors["base_fg"]
                colors["module_bg"] = find_color("theme_module_bg") or colors["module_bg"]
                colors["module_fg"] = find_color("theme_module_fg") or colors["module_fg"]
                colors["active_bg"] = find_color("theme_active_bg") or colors["active_bg"]
                colors["active_fg"] = find_color("theme_active_fg") or colors["active_fg"]
                colors["hover_bg"] = find_color("theme_panel_hover_bg") or colors["hover_bg"]
                colors["border"] = find_color("theme_border_color") or colors["border"]
                colors["accent"] = find_color("theme_accent") or colors["accent"]
                if "light" in content.lower():
                    colors["is_light"] = True
        except: pass
    return colors


# Second-line explanations for setting rows, keyed by row label text.
# Shared across pages when a label repeats (e.g. Blur Size on desktop + lock).
DESCRIPTIONS = {
    "Inner Gaps": "Space between tiled windows, in pixels.",
    "Outer Gaps": "Space between windows and the screen edges.",
    "Border Size": "Thickness of the focused window border.",
    "Rounding": "Corner radius for windows and surfaces.",
    "Active Window": "Opacity of the focused window.",
    "Inactive Window": "Opacity of background windows.",
    "Waybar Opacity": "Transparency of the top bar.",
    "Launcher Opacity": "Transparency of the app launcher.",
    "Window Layout": "Tiling algorithm: dwindle, master, or scroll.",
    "Resize on Border Drag": "Resize windows by dragging their borders with SUPER held.",
    "Allow Tearing": "Lets fullscreen games tear frames to cut input latency.",
    "Enable Blur": "Blur content behind translucent surfaces. Costs GPU.",
    "Blur Size": "Blur radius. Higher is softer but slower.",
    "Blur Passes": "Blur quality passes. Higher is smoother but slower.",
    "Active Border": "Gradient colors of the focused window border.",
    "Inactive Border": "Gradient colors of unfocused window borders.",
    "Theme Mode": "Dark, light, or automatic by time of day.",
    "Accent Color": "Highlight color for selections, sliders, and active UI.",
    "Active Mode": "Fixed image, rotating collection, or disabled.",
    "Static Image": "Single wallpaper shown on all monitors.",
    "Collection Folder": "Folder cycled when dynamic mode is active.",
    "Enable Motion Effects": "Master switch for all window animations.",
    "Open Style": "Animation played when a window opens.",
    "Exit Style": "Animation played when a window closes.",
    "Border Speed": "Duration of the border animation.",
    "Fading Curve": "Easing curve used for fade in and out.",
    "Workspace Transition": "Animation played when switching workspaces.",
    "Global UI Scale": "Display scaling factor, e.g. 1.0, 1.5, 2.0.",
    "Advanced Monitor Rules (name, res, pos, scale)": "Raw per-monitor rules, one per line.",
    "Layout": "Keyboard layout code, e.g. us, de.",
    "Variant": "Keyboard layout variant, e.g. colemak.",
    "Model": "Keyboard model, e.g. pc105.",
    "Rules": "Extra xkb rules file, rarely needed.",
    "Caps Lock Behavior": "Remap Caps Lock to Control, Escape, or swap it with Esc.",
    "Advanced Options String": "Raw xkb_options passed to the keyboard.",
    "Natural Scrolling (Touchpad)": "Invert the touchpad scroll direction.",
    "Focus Follows Mouse": "Focus windows by hovering, without clicking.",
    "Sensitivity": "Pointer speed. Negative values slow it down.",
    "Main Modifier": "Primary shortcut key used by all keybinds.",
    "Normal (MOD, KEY, ACTION, ARGS)": "Standard keybinds, one per line.",
    "Release": "Binds fired when the key is released.",
    "Repeat": "Binds that repeat while the key is held.",
    "Locked": "Binds that also work on the lock screen.",
    "Mouse": "Mouse button binds.",
    "Gesture Rules (fingers = N, direction = \"...\", action = \"...\")": "Touchpad gestures, one rule per line.",
    "Auto-Lock (s)": "Idle seconds before the screen locks.",
    "Screen Off (s)": "Idle seconds before the display powers off.",
    "Suspend (s)": "Idle seconds before the machine suspends.",
    "Lock Wallpaper": "Background image of the lock screen.",
    "User Picture": "Avatar shown on the lock screen.",
    "Fail Text": "Message shown after a wrong password.",
    "Placeholder Text": "Prompt inside the password field.",
    "Enable Night Light": "Warm the screen colors in the evening.",
    "Day Temp (K)": "Daytime color temperature. Lower is warmer.",
    "Night Strength / Temp (K)": "Nighttime warmth. Lower is more orange.",
    "Launch at Startup (one per line)": "Commands run once at login.",
    "Enable Scheduler": "Master switch for the timed routines below.",
    "Time (24h)": "Trigger time in HH:MM format.",
    "Days": "Optional day filter, e.g. Mon-Fri.",
    "Enabled": "Whether this routine runs.",
    "Active Plugins (hyprpm names)": "Hyprland plugins loaded at startup.",
    "Rules (ACTION, class:REGEX or title:REGEX)": "Per-window rules matched by app class or title.",
    "KEY,VALUE pairs": "Environment variables exported to the session.",
    "New Window Status": "Where new windows open in the dwindle layout.",
    "Preserve Split": "Keep manual split directions when moving windows.",
    "Column Width": "Default width of columns in the scrolling layout.",
    "Explicit Widths": "Per-column width overrides.",
    "Focus Fit Method": "How focus moves between tiles when scrolling.",
    "Fullscreen Single Column": "Fullscreen spans a single column only.",
    "Screen Position": "Where on screen this element appears.",
    "Position": "Screen edge or area this element anchors to.",
    "Width %": "Width as a percentage of the screen.",
    "Width (%)": "Width as a percentage of the screen.",
    "Top Margin": "Gap from the top screen edge.",
    "Top Margin (px)": "Gap from the top screen edge, in pixels.",
    "Screen Margin": "Gap between the element and the screen edge.",
    "Icon Size": "Pixel size of icons.",
    "App Icon Size": "Pixel size of application icons.",
    "Item Spacing": "Gap between items in the list.",
    "Padding": "Inner padding around the content.",
    "Search Font Size": "Text size inside the launcher search box.",
    "Dock Apps (binary names)": "Apps pinned to the dock, one binary name per line.",
    "Dock Position": "Screen edge the dock sits on.",
    "Autohide": "Fade the dock until the cursor touches it.",
    "Enable Mac-style Dock": "Show the bottom icon dock.",
    "Terminal": "Preferred terminal emulator.",
    "Filemanager": "Preferred file manager.",
    "Launcher": "Preferred application for this role.",
    "Status bar": "Preferred status bar application.",
    "Notification service": "Preferred notification daemon.",
    "Autohide Status Bar": "Hide the bar until the cursor touches its edge.",
    "Disable Splash Text": "Skip the startup splash message.",
    "Disable Startup Logo": "Skip the logo shown at compositor start.",
    "Force Default Wallpaper": "Always use the bundled wallpaper.",
}

WIDGET_CELL_WIDTH = 240

# Instant-apply: whitelisted widget keys apply live (debounced) without Apply.
# Second layer of defense: only sections in LIVE_SAFE_SECTIONS may differ —
# anything else dirty (binds, lua text, monitors, ...) forces manual Apply.
LIVE_SAFE_WIDGETS = {
    'gaps_in', 'gaps_out', 'border_size', 'rounding',
    'active_opacity', 'inactive_opacity', 'waybar_opacity', 'launcher_opacity',
    'blur_enabled', 'blur_size', 'blur_passes',
    'nl_enabled', 'nl_temp_day', 'nl_temp_night',
    'anim_enabled',
}
LIVE_SAFE_SECTIONS = {'general', 'decoration', 'nightlight', 'animations'}
LIVE_APPLY_DEBOUNCE_MS = 600

# Guided keybind editor: modifiers, action names, parse/serialize helpers.
# Stored bind strings use "$mainMod"-style variables and mixed-case keys;
# the parser preserves unknown mod tokens verbatim so round-trips are lossless.
BIND_MODS = ("SUPER", "SHIFT", "ALT", "CTRL")

BIND_ACTIONS_FALLBACK = [
    "exec", "exec-once", "killactive", "closewindow", "fullscreen",
    "fakefullscreen", "togglefloating", "toggleopaque",
    "togglespecialworkspace", "workspace", "movetoworkspace",
    "movetoworkspacesilent", "movewindow", "resizewindow", "resizeactive",
    "movefocus", "moveintogroup", "moveoutofgroup", "togglegroup",
    "changegroupactive", "lockgroups", "pin", "centerwindow", "focuswindow",
    "focusurgentorlast", "bringactivetotop", "tagwindow", "togglesplit",
    "layoutmsg", "splitratio", "alterzone", "submap", "dpms", "exit",
    "focusmonitor", "movecurrentworkspacetomonitor", "mouse",
]


def _bind_action_names():
    """Action names for the guided editor dropdown.

    Prefers the live DISPATCHER_MAP from lua_generator so the editor and the
    config builder can never disagree; falls back to a static list (notably
    when running from ~/.config where lua_generator is not on sys.path)."""
    try:
        import lua_generator
        return sorted(lua_generator.DISPATCHER_MAP.keys())
    except Exception:
        return list(BIND_ACTIONS_FALLBACK)


class SettingsManager(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.connect("key-press-event", self.on_key_press)
        self.config_path = os.path.expanduser("~/.config/hypr/hyprde.toml")
        self.load_config()
        # Older/preserved TOMLs may lack sections added later; every page
        # builder and the save handler index self.doc directly, so a missing
        # section used to crash startup with a bare KeyError. Fill tables
        # in-memory (persisted only when the user hits Done with changes).
        self.ensure_defaults()
        self._bind_actions = _bind_action_names()
        self._key_capture = None
        # Normalize stored bind strings (case, spacing) so untouched binds
        # serialize identically on collect — otherwise every close would look dirty.
        self._normalize_binds()
        self.initial_config_str = tomlkit.dumps(self.doc)
        self._initial_sections = self._snapshot_sections()

        self.set_app_paintable(True)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        try:
            gi.require_version('GtkLayerShell', '0.1')
            from gi.repository import GtkLayerShell
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_namespace(self, "hyprde-settings")
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
            for edge in [GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT]:
                GtkLayerShell.set_anchor(self, edge, True)
        except Exception as e:
            logger.error(f"GtkLayerShell init failed (continuing as normal window): {e}")
            self.set_title("HyprDE Settings")
            self.set_wmclass("hyprde-settings", "hyprde-settings")
            self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)

        self.init_time = time.time()
        self.connect("destroy", lambda w: (self.cleanup_lock(), Gtk.main_quit()))
        self.connect("key-press-event", self.on_key_press)

        bg_event_box = Gtk.EventBox()
        bg_event_box.set_name("bg-overlay")
        bg_event_box.connect("button-press-event", lambda w, e: self.close_window() if (time.time() - self.init_time) > 0.3 else None)
        self.add(bg_event_box)

        overlay = Gtk.Overlay()
        bg_event_box.add(overlay)

        self.click_catcher = Gtk.EventBox()
        self.click_catcher.set_halign(Gtk.Align.CENTER); self.click_catcher.set_valign(Gtk.Align.CENTER)
        self.click_catcher.connect("button-press-event", lambda w, e: True)
        overlay.add(self.click_catcher)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.main_box.set_name("main-window")
        self.click_catcher.add(self.main_box)

        try:
            display = Gdk.Display.get_default()
            monitor = None
            if display is not None:
                try:
                    monitor = display.get_primary_monitor() or display.get_monitor(0)
                except Exception as e:
                    logger.warning(f"Monitor lookup failed: {e}")
            if monitor:
                geo = monitor.get_geometry()
                self.win_w = min(860, int(geo.width * 0.85))
                self.win_h = min(580, int(geo.height * 0.85))
                self.main_box.set_size_request(self.win_w, self.win_h)
            else:
                self.main_box.set_size_request(860, 580)
        except Exception as e:
            logger.warning(f"Display sizing failed, using defaults: {e}")
            self.main_box.set_size_request(860, 580)

        titlebar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        titlebar.set_name("titlebar")
        titlebar.set_margin_start(14); titlebar.set_margin_end(14)

        tl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tl_box.set_valign(Gtk.Align.CENTER)
        tl_box.set_margin_top(12); tl_box.set_margin_bottom(12)
        dot = Gtk.Button(); dot.set_name("tl-close")
        dot.set_size_request(13, 13); dot.set_can_focus(False)
        dot.set_tooltip_text("Close")
        dot.connect("clicked", lambda x: self.close_window())
        tl_box.pack_start(dot, False, False, 0)
        self.close_dot = dot
        titlebar.pack_start(tl_box, False, False, 0)

        tl_spacer1 = Gtk.Box(); titlebar.pack_start(tl_spacer1, True, True, 0)
        title_label = Gtk.Label(label="System Settings"); title_label.set_name("title-label")
        titlebar.pack_start(title_label, False, False, 0)
        tl_spacer2 = Gtk.Box(); titlebar.pack_start(tl_spacer2, True, True, 0)

        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        right_box.set_valign(Gtk.Align.CENTER)
        self.status_label = Gtk.Label(label=""); self.status_label.set_name("status-label")
        right_box.pack_start(self.status_label, False, False, 0)
        self.save_btn = Gtk.Button(label="Apply"); self.save_btn.set_name("save-button")
        self.save_btn.connect("clicked", self.on_save_clicked)
        right_box.pack_start(self.save_btn, False, False, 0)
        titlebar.pack_end(right_box, False, False, 0)
        self.main_box.pack_start(titlebar, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL); sep.set_name("titlebar-sep")
        self.main_box.pack_start(sep, False, False, 0)

        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.main_box.pack_start(content_box, True, True, 0)

        sidebar_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar_vbox.set_name("sidebar-area")
        sidebar_vbox.set_size_request(200, -1)
        self.search_entry = Gtk.SearchEntry(); self.search_entry.set_name("settings-search")
        self.search_entry.set_placeholder_text("Search settings…")
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.search_entry.connect("activate", self.on_search_activate)
        sidebar_vbox.pack_start(self.search_entry, False, False, 0)
        self.sidebar = Gtk.ListBox(); self.sidebar.set_name("sidebar")
        self.sidebar.connect("row-activated", self.on_sidebar_row_activated)
        self.sidebar.connect("row-selected", lambda lb, row: self.on_sidebar_row_activated(lb, row) if row else None)

        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.add(self.sidebar)
        sidebar_vbox.pack_start(sidebar_scroll, True, True, 0)
        content_box.pack_start(sidebar_vbox, False, False, 0)

        self.stack = Gtk.Stack(); self.stack.set_homogeneous(False); self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack_scroll = Gtk.ScrolledWindow(); self.stack_scroll.set_name("content-scroll")
        self.stack_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.stack_scroll.add(self.stack)
        content_box.pack_start(self.stack_scroll, True, True, 0)

        self.apply_css()
        self.create_settings_pages()
        self.main_box.get_style_context().add_class("opening")
        self.show_all()
        self.sidebar.grab_focus()
        GLib.timeout_add(300, lambda: self.main_box.get_style_context().remove_class("opening"))

    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                self.doc = tomlkit.load(f)
            self.initial_config_str = tomlkit.dumps(self.doc)
        except FileNotFoundError as e:
            logger.error(f"Config not found: {self.config_path}: {e}")
            _notify_error("HyprDE Settings",
                          f"Config not found: {self.config_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to parse {self.config_path}: {e}\n{traceback.format_exc()}")
            _notify_error("HyprDE Settings",
                          f"Invalid TOML: {e}. See {LOG_FILE}")
            raise

    def cleanup_lock(self):
        cleanup_lock()

    def close_window(self):
        self._closed = True
        if getattr(self, '_live_apply_id', None) is not None:
            try:
                GLib.source_remove(self._live_apply_id)
            except Exception:
                pass
            self._live_apply_id = None
        if getattr(self, '_dirty', False) and self._has_unsaved_changes():
            dialog = Gtk.MessageDialog(
                transient_for=self, modal=True,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.NONE,
                text="Discard unsaved changes?")
            dialog.format_secondary_text(
                "You have unapplied changes. Closing now will lose them.")
            dialog.add_button("Keep Editing", Gtk.ResponseType.CANCEL)
            discard = dialog.add_button("Discard Changes", Gtk.ResponseType.OK)
            discard.get_style_context().add_class("destructive-action")
            
            def on_response(dlg, res):
                dlg.destroy()
                if res == Gtk.ResponseType.OK:
                    self.cleanup_lock()
                    self.main_box.get_style_context().add_class("closing")
                    GLib.timeout_add(200, Gtk.main_quit)
                    
            dialog.connect("response", on_response)
            dialog.show_all()
            return
            
        self.cleanup_lock()
        self.main_box.get_style_context().add_class("closing")
        GLib.timeout_add(200, Gtk.main_quit)

    def _has_unsaved_changes(self):
        """Authoritative dirty check: collect widget state, diff vs last apply."""
        try:
            snap = self._collect_widget_state()
        except Exception:
            return True
        return snap.get("config_str") != self.initial_config_str

    # --- DIRTY TRACKING / REVERT ---
    def _mark_dirty(self, *args):
        if getattr(self, '_restoring', False):
            return
        self._dirty = True
        dot = getattr(self, 'close_dot', None)
        if dot is not None:
            dot.get_style_context().add_class("dirty")
            dot.set_tooltip_text("Close • unsaved changes")

    def _mark_clean(self):
        self._dirty = False
        dot = getattr(self, 'close_dot', None)
        if dot is not None:
            dot.get_style_context().remove_class("dirty")
            dot.set_tooltip_text("Close")

    def _track_dirty_signals(self):
        """Optimistic dirty flag: any widget interaction marks dirty.

        The close dialog re-verifies authoritatively, so false positives
        (change then change back) only tint the dot — they never lie."""
        seen = set()

        def hook(w):
            if w is None or id(w) in seen:
                return
            seen.add(id(w))
            if isinstance(w, Gtk.Entry):
                w.connect("changed", self._mark_dirty)
            elif isinstance(w, (Gtk.SpinButton, Gtk.Scale)):
                w.connect("value-changed", self._mark_dirty)
            elif isinstance(w, Gtk.Switch):
                w.connect("notify::active", self._mark_dirty)
            elif isinstance(w, Gtk.ComboBoxText):
                w.connect("changed", self._mark_dirty)
            elif isinstance(w, Gtk.TextView):
                w.get_buffer().connect("changed", self._mark_dirty)
            elif isinstance(w, Gtk.TextBuffer):
                w.connect("changed", self._mark_dirty)
            elif isinstance(w, Gtk.Container):
                w.connect("add", self._mark_dirty)
                w.connect("remove", self._mark_dirty)
            elif isinstance(w, list):
                for item in w:
                    if isinstance(item, dict):
                        for v in item.values():
                            hook(v)
                    else:
                        hook(item)

        for w in self.widgets.values():
            hook(w)
        # Accent picker mutates the doc directly (no widget signal to catch)
        if 'theme_accent_btn' in self.widgets:
            self.widgets['theme_accent_btn'].connect("clicked", self._mark_dirty)

    def _read_widget_value(self, w):
        # NOTE: SpinButton subclasses Entry — numeric check must come first,
        # and restore must use set_value (set_text does not move the adjustment).
        if isinstance(w, (Gtk.SpinButton, Gtk.Scale)):
            return ("num", w.get_value())
        if isinstance(w, Gtk.Entry):
            return ("entry", w.get_text())
        if isinstance(w, Gtk.Switch):
            return ("bool", w.get_active())
        if isinstance(w, Gtk.ComboBoxText):
            return ("combo", w.get_active_id())
        if isinstance(w, Gtk.TextView):
            buf = w.get_buffer()
            return ("text", buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True))
        if isinstance(w, Gtk.TextBuffer):
            return ("text", w.get_text(w.get_start_iter(), w.get_end_iter(), True))
        if w is self.widgets.get('theme_accent_btn'):
            return ("accent", self._tg('theme', 'accent', '#007aff'))
        if isinstance(w, Gtk.Container) and getattr(w, 'is_dynamic_list', False):
            if getattr(w, 'bind_kind', None) == 'binds':
                try:
                    return ("binditems", self.get_bind_items(w))
                except Exception:
                    return None
            try:
                items = [c.get_children()[0].get_text()
                         for c in w.get_children()
                         if c.get_children() and isinstance(c.get_children()[0], Gtk.Entry)]
                return ("items", items)
            except Exception:
                return None
        return None

    def _write_widget_value(self, w, val):
        kind, data = val
        if kind == "entry" and isinstance(w, Gtk.Entry):
            w.set_text(data)
        elif kind == "num" and isinstance(w, (Gtk.SpinButton, Gtk.Scale)):
            adj = w.get_adjustment()
            w.set_value(max(adj.get_lower(), min(data, adj.get_upper())))
        elif kind == "bool" and isinstance(w, Gtk.Switch):
            w.set_active(data)
        elif kind == "combo" and isinstance(w, Gtk.ComboBoxText):
            w.set_active_id(data)
        elif kind == "text":
            buf = w.get_buffer() if isinstance(w, Gtk.TextView) else w
            if isinstance(buf, Gtk.TextBuffer):
                buf.set_text(data)
        elif kind == "accent" and w is self.widgets.get('theme_accent_btn'):
            self._st('theme', 'accent', data)
            self._update_accent_preview(self._parse_color(data))
        elif kind == "binditems" and isinstance(w, Gtk.Container):
            self._dynamic_list_set(w, data)
        elif kind == "items" and isinstance(w, Gtk.Container):
            self._dynamic_list_set(w, data)

    def _dynamic_list_set(self, container, items):
        """Restore a dynamic list to an exact item set (mirrors the builders)."""
        if getattr(container, 'bind_kind', None) == 'binds':
            for ch in list(container.get_children()):
                container.remove(ch)
            for s in items:
                try:
                    self._add_bind_row(container, str(s))
                except Exception:
                    continue
            return
        for ch in list(container.get_children()):
            container.remove(ch)
        for text in items:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
            entry = Gtk.Entry(); entry.set_text(text); entry.set_hexpand(True)
            del_btn = Gtk.Button.new_from_icon_name("list-remove-symbolic", Gtk.IconSize.BUTTON)
            del_btn.connect("clicked", lambda x, r=row: container.remove(r))
            row.pack_start(entry, True, True, 0); row.pack_end(del_btn, False, False, 0)
            container.add(row)
        container.show_all()

    def _snapshot_widget_values(self):
        self._initial_widget_values = {}
        self._initial_routines = {}

        def snap(w):
            if w is None or id(w) in self._initial_widget_values:
                return
            if isinstance(w, list):
                for item in w:
                    if isinstance(item, dict):
                        for v in item.values():
                            snap(v)
                    else:
                        snap(item)
                return
            v = self._read_widget_value(w)
            if v is not None:
                self._initial_widget_values[id(w)] = (w, v)

        for w in self.widgets.values():
            snap(w)
        for u in self.widgets.get('rocket_events_list', []):
            if isinstance(u, dict) and isinstance(u.get('name'), str):
                buf = u['actions'].get_buffer()
                self._initial_routines[u['name']] = {
                    'trig': u['trig'].get_text(), 'days': u['days'].get_text(),
                    'on': u['on'].get_active(),
                    'actions': buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)}

    def _revert_routines(self):
        """Added routines are destroyed, deleted ones re-created, values restored."""
        current = {u['name']: u for u in self.widgets.get('rocket_events_list', [])
                   if isinstance(u, dict)}
        for name, u in list(current.items()):
            if name not in self._initial_routines:
                self.remove_rocket_routine_ui(u)
        for name, vals in self._initial_routines.items():
            u = next((x for x in self.widgets['rocket_events_list']
                      if isinstance(x, dict) and x.get('name') == name), None)
            if u is None:
                self.add_rocket_routine_ui(name, {
                    'trigger': vals['trig'], 'days': vals['days'],
                    'enabled': vals['on'], 'actions': vals['actions'].split('\n')})
            else:
                u['trig'].set_text(vals['trig'])
                u['days'].set_text(vals['days'])
                u['on'].set_active(vals['on'])
                u['actions'].get_buffer().set_text(vals['actions'])

    def _on_revert_page(self, page_name):
        page = self.stack.get_child_by_name(page_name)
        if page is None:
            return
        restored = 0

        def walk(w):
            nonlocal restored
            if id(w) in self._initial_widget_values:
                w0, v = self._initial_widget_values[id(w)]
                self._write_widget_value(w0, v)
                restored += 1
            if isinstance(w, Gtk.Container):
                for ch in w.get_children():
                    walk(ch)

        self._restoring = True
        try:
            if page_name == 'hyprrocket':
                self._revert_routines()
            walk(page)
        finally:
            self._restoring = False
        if not self._has_unsaved_changes():
            self._mark_clean()
        self.status_label.set_text(f"Reverted {restored} setting(s) on this page")

    def apply_css(self):
        c = get_theme_colors()
        css = f"""
        @define-color accent_color {c['accent']};
        @define-color accent_bg_color {c['accent']};
        window {{ background-color: transparent; }}
        #bg-overlay {{ background-color: rgba(0,0,0,0.5); animation: backdrop-in 240ms ease-out; }}
        @keyframes backdrop-in {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
        #main-window {{
            background-color: {c['base_bg']};
            border-radius: 12px;
            border: 1px solid {c['border']};
            color: {c['base_fg']};
        }}
        #main-window.opening {{ animation: panel-in 260ms cubic-bezier(0.34, 1.56, 0.64, 1); }}
        #main-window.closing {{ animation: panel-out 200ms ease-in forwards; }}
        @keyframes panel-in {{ from {{ opacity: 0; margin-top: 16px; }} to {{ opacity: 1; margin-top: 0px; }} }}
        @keyframes panel-out {{ from {{ opacity: 1; margin-top: 0px; }} to {{ opacity: 0; margin-top: -10px; }} }}

        #titlebar {{ min-height: 38px; }}
        #titlebar-sep {{ background-color: {c['border']}; min-height: 1px; }}
        #title-label {{ font-size: 13px; font-weight: 500; color: {c['base_fg']}; opacity: 0.8; }}

        #tl-close {{
            border-radius: 50%; min-width: 13px; min-height: 13px;
            padding: 0; border: none; box-shadow: none;
            background-color: #ff5f57;
        }}
        #tl-close:hover {{ background-color: #e0443c; }}
        #tl-close.dirty {{ background-color: #ff9f0a; }}
        #tl-close.dirty:hover {{ background-color: #e08a06; }}
        #revert-btn {{
            font-size: 11px; padding: 2px 10px; border-radius: 6px;
            opacity: 0.55; background: transparent;
            border: 1px solid {c['border']}; color: {c['base_fg']};
        }}
        #revert-btn:hover {{ opacity: 1.0; background: {c['hover_bg']}; }}
        .anchor-btn {{
            font-size: 11px; padding: 2px 10px; border-radius: 6px;
            opacity: 0.7; background: transparent;
            border: 1px solid {c['border']}; color: {c['base_fg']};
        }}
        .anchor-btn:hover {{ opacity: 1.0; background: {c['hover_bg']}; }}

        #sidebar-area, #sidebar {{ background-color: rgba(0,0,0,0.1); border-right: 1px solid {c['border']}; }}
        #sidebar row {{ padding: 8px 10px; border-radius: 8px; margin: 2px 6px; color: {c['base_fg']}; opacity: 0.8; font-weight: 400; font-size: 12px; background: transparent; }}
        #sidebar row:selected {{ background-color: rgba(255,255,255,0.07); color: {c['base_fg']}; opacity: 1.0; font-weight: 600; border-left: 3px solid {c['accent']}; padding-left: 7px; }}
        #sidebar row label {{ color: inherit; font-size: 12px; }}
        .sidebar-group-label {{ font-size: 11px; font-weight: 700; opacity: 0.5; color: {c['base_fg']}; padding: 10px 12px 3px 12px; letter-spacing: 1px; background: transparent; }}
        #settings-search {{ margin: 8px 8px 4px 8px; }}
        .search-highlight {{ box-shadow: inset 0 0 0 2px {c['accent']}; border-radius: 8px; background: rgba(255,255,255,0.05); }}

        #save-button {{
            background-color: {c['active_bg']};
            color: {c['active_fg']};
            font-weight: 600;
            padding: 5px 16px;
            border-radius: 7px;
            border: none;
            font-size: 13px;
        }}
        #save-button:hover {{ opacity: 0.85; }}
        #status-label {{ font-size: 11px; opacity: 0.75; color: {c['base_fg']}; }}
        #status-label.error {{ color: #ff5f57; font-weight: 600; opacity: 1.0; }}

        .section-title {{ font-size: 10px; font-weight: 700; letter-spacing: 1px; margin-bottom: 12px; color: {c['base_fg']}; opacity: 0.65; }}
        .setting-desc {{ font-size: 11px; opacity: 0.7; color: {c['base_fg']}; }}

        .group-frame {{
            background: rgba(255,255,255,0.04);
            border-radius: 10px;
            padding: 4px;
            margin-bottom: 12px;
            border: 1px solid rgba(255,255,255,0.07);
        }}

        entry, spinbutton {{
            background: {c['module_bg']};
            color: {c['module_fg']};
            border: 1px solid {c['border']};
            border-radius: 7px;
            padding: 6px 10px;
            font-size: 13px;
        }}
        button.picker {{
            background-color: {c['module_bg']};
            color: {c['module_fg']};
            border: 1px solid {c['border']};
            border-radius: 7px;
            padding: 5px 14px;
            font-weight: 500;
            font-size: 13px;
        }}
        button.picker:hover {{ background-color: {c['hover_bg']}; }}

        scale slider {{ background: {c['accent']}; border-radius: 50%; min-height: 18px; min-width: 18px; }}
        scale trough {{ background: rgba(255,255,255,0.1); border-radius: 6px; min-height: 4px; }}
        scale value {{ font-size: 11px; color: {c['base_fg']}; opacity: 0.55; }}
        switch:checked {{ background: {c['active_bg']}; }}
        switch {{ background: rgba(255,255,255,0.15); border-radius: 12px; border: none; }}
        switch slider {{ background: #ffffff; border-radius: 50%; min-width: 20px; min-height: 20px; border: none; }}

        button {{
            background: {c['module_bg']};
            color: {c['module_fg']};
            border: 1px solid {c['border']};
            border-radius: 7px;
            padding: 5px 12px;
            font-size: 13px;
        }}
        button:hover {{ background: {c['hover_bg']}; }}

        .color-swatch {{
            min-height: 28px; min-width: 28px;
            border-radius: 6px;
            border: 1px solid rgba(255,255,255,0.15);
        }}
        .theme-label {{
            font-size: 16px; font-weight: 600; margin-bottom: 4px;
        }}
        .accent-preview {{
            min-height: 32px; border-radius: 8px; margin-top: 6px;
        }}

        scrollbar slider {{ background-color: rgba(255,255,255,0.2); border-radius: 6px; min-width: 6px; }}
        textview {{ background: {c['module_bg']}; color: {c['module_fg']}; border: 1px solid {c['border']}; border-radius: 7px; font-size: 12px; }}
        textview text {{ background: {c['module_bg']}; color: {c['module_fg']}; }}
        """.encode()
        p = Gtk.CssProvider(); p.load_from_data(css); Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def open_picker(self, title, folder=False):
        try:
            from gi.repository import GtkLayerShell
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.BOTTOM); GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.NONE)
        except: pass
        action = Gtk.FileChooserAction.SELECT_FOLDER if folder else Gtk.FileChooserAction.OPEN
        dialog = Gtk.FileChooserNative.new(title, self, action, "_Select", "_Cancel"); res = dialog.run()
        path = dialog.get_filename() if res == Gtk.ResponseType.ACCEPT else None; dialog.destroy()
        try:
            from gi.repository import GtkLayerShell
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY); GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        except: pass
        return path

    def open_color_picker(self, title, initial_color=None):
        try:
            from gi.repository import GtkLayerShell
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.BOTTOM); GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.NONE)
        except: pass
        dialog = Gtk.ColorChooserDialog.new(title, None)
        dialog.set_modal(True)
        if initial_color:
            rgba = Gdk.RGBA()
            if rgba.parse(initial_color):
                dialog.set_rgba(rgba)
        dialog.set_use_alpha(True)
        res = dialog.run()
        color = dialog.get_rgba() if res == Gtk.ResponseType.OK else None
        dialog.destroy()
        try:
            from gi.repository import GtkLayerShell
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY); GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        except: pass
        if color:
            return f"rgba({int(color.red*255)}, {int(color.green*255)}, {int(color.blue*255)}, {color.alpha:.2f})"
        return None

    def create_row(self, label_text, widget):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16); hbox.set_margin_bottom(8)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label=label_text); title.set_xalign(0)
        text.pack_start(title, False, False, 0)
        desc = DESCRIPTIONS.get(label_text)
        if desc:
            d = Gtk.Label(label=desc); d.set_xalign(0); d.set_line_wrap(True)
            d.get_style_context().add_class("setting-desc")
            text.pack_start(d, False, False, 0)
        hbox.pack_start(text, True, True, 0)
        cell = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        cell.set_size_request(WIDGET_CELL_WIDTH, -1)
        # Fill widgets (entries, spins, scales, combos) span the cell;
        # fixed-size controls (switches, buttons) keep natural size, right aligned.
        if isinstance(widget, (Gtk.Entry, Gtk.SpinButton, Gtk.Scale, Gtk.ComboBox)):
            widget.set_hexpand(True)
            cell.pack_start(widget, True, True, 0)
        else:
            widget.set_hexpand(False)
            widget.set_halign(Gtk.Align.END)
            widget.set_valign(Gtk.Align.CENTER)
            cell.pack_end(widget, False, False, 0)
        hbox.pack_end(cell, False, False, 0)
        return hbox

    def create_row_with_btn(self, label_text, widget, btn_label, btn_cb):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10); hbox.set_margin_bottom(8); label = Gtk.Label(label=label_text); label.set_xalign(0); hbox.pack_start(label, True, True, 0); btn = Gtk.Button(label=btn_label); btn.get_style_context().add_class("picker"); btn.connect("clicked", btn_cb); hbox.pack_end(btn, False, False, 0); hbox.pack_end(widget, False, False, 0)
        return hbox, btn, widget

    def build_dynamic_list(self, items, label_title):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12); vbox.get_style_context().add_class("group-frame")
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15); title_box.pack_start(Gtk.Label(label=label_title), True, True, 0)
        add_btn = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON); add_btn.connect("clicked", lambda x: add_entry(""))
        title_box.pack_end(add_btn, False, False, 0); vbox.pack_start(title_box, False, False, 10)
        list_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10); vbox.pack_start(list_container, False, False, 0)
        list_container.is_dynamic_list = True
        hint = Gtk.Label(label="No entries yet — use + to add one"); hint.set_xalign(0); hint.set_opacity(0.5)
        vbox.pack_start(hint, False, False, 0)

        def refresh_hint(*_a):
            hint.set_visible(len(list_container.get_children()) == 0)

        list_container.connect("add", refresh_hint)
        list_container.connect("remove", refresh_hint)
        def add_entry(val=""):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15); entry = Gtk.Entry(); entry.set_text(val); entry.set_hexpand(True)
            del_btn = Gtk.Button.new_from_icon_name("list-remove-symbolic", Gtk.IconSize.BUTTON); del_btn.connect("clicked", lambda x: list_container.remove(row))
            row.pack_start(entry, True, True, 0); row.pack_end(del_btn, False, False, 0); list_container.add(row); row.show_all(); return entry
        for item in items: add_entry(item)
        refresh_hint()
        return vbox, list_container

    def build_page_vbox(self, title_text):
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12); v.set_margin_top(20); v.set_margin_bottom(20); v.set_margin_start(28); v.set_margin_end(28); lbl = Gtk.Label(label=title_text.upper()); lbl.set_xalign(0); lbl.get_style_context().add_class("section-title"); v.pack_start(lbl, False, False, 0); return v

    # --- GUIDED KEYBIND EDITOR ---
    @staticmethod
    def _parse_bind_string(s):
        """Split 'MODS, KEY, ACTION, ARGS' without losing anything.

        Unknown mod tokens ($mainMod etc.) are preserved verbatim in `extra`
        so parse->serialize round-trips losslessly."""
        parts = [p.strip() for p in str(s).split(",", 3)]
        raw_mods = parts[0].split() if parts and parts[0] else []
        uppers = [t.upper() for t in raw_mods]
        sel = [m for m in BIND_MODS if m in uppers]
        extra = [t for t in raw_mods if t.upper() not in BIND_MODS]
        key = parts[1] if len(parts) > 1 else ""
        if len(key) == 1 and key.isalpha():
            key = key.upper()
        action = parts[2] if len(parts) > 2 else ""
        args = parts[3] if len(parts) > 3 else ""
        return extra, sel, key, action, args

    @staticmethod
    def _serialize_bind(extra, sel, key, action, args):
        mods = " ".join(list(extra) + list(sel))
        s = f"{mods}, {key}, {action}"
        return s + f", {args}" if args else s

    def build_bind_list(self, items, label_title):
        """Structured editor for one bind subsection (normal/release/...)."""
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12); vbox.get_style_context().add_class("group-frame")
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15); title_box.pack_start(Gtk.Label(label=label_title), True, True, 0)
        add_btn = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON)
        add_btn.set_tooltip_text("Add bind")
        add_btn.connect("clicked", lambda x: self._add_bind_row(list_container, None))
        title_box.pack_end(add_btn, False, False, 0); vbox.pack_start(title_box, False, False, 10)
        list_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6); vbox.pack_start(list_container, False, False, 0)
        list_container.is_dynamic_list = True
        list_container.bind_kind = "binds"
        hint = Gtk.Label(label="No binds here — use + to add one"); hint.set_xalign(0); hint.set_opacity(0.5)
        vbox.pack_start(hint, False, False, 0)

        def refresh_hint(*_a):
            hint.set_visible(len(list_container.get_children()) == 0)

        list_container.connect("add", refresh_hint)
        list_container.connect("remove", refresh_hint)
        for item in items:
            self._add_bind_row(list_container, str(item))
        refresh_hint()
        return vbox, list_container

    def _add_bind_row(self, container, bind_str):
        if bind_str is None:
            main = self.doc.get('binds', {}).get('mainMod', 'SUPER')
            extra, sel, key, action, args = [], ([main] if main in BIND_MODS else ["SUPER"]), "", "", ""
        else:
            extra, sel, key, action, args = self._parse_bind_string(bind_str)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.set_margin_bottom(2)
        mod_checks = {}
        for m in BIND_MODS:
            cb = Gtk.CheckButton(label=m)
            cb.set_tooltip_text(f"Require {m} modifier")
            cb.set_active(m in sel)
            cb.connect("toggled", self._mark_dirty)
            mod_checks[m] = cb
            row.pack_start(cb, False, False, 0)
        key_btn = Gtk.Button(label=key or "Set…")
        key_btn.set_size_request(84, -1)
        key_btn.set_tooltip_text("Left-click: press a key • Right-click: type a key name")
        key_btn.connect("clicked", lambda b: self._start_key_capture(b, row))
        key_btn.connect("button-press-event", lambda b, e: self._on_key_btn_press(b, e, row))
        row.pack_start(key_btn, False, False, 0)
        action_combo = Gtk.ComboBoxText.new_with_entry()
        for a in self._bind_actions:
            action_combo.append(a, a)
        if action and action in self._bind_actions:
            action_combo.set_active_id(action)
        elif action:
            action_combo.get_child().set_text(action)
        action_combo.get_child().set_width_chars(14)
        action_combo.set_tooltip_text("Dispatcher action (type a custom/plugin one if needed)")
        action_combo.connect("changed", self._mark_dirty)
        row.pack_start(action_combo, False, False, 0)
        args_entry = Gtk.Entry()
        args_entry.set_text(args)
        args_entry.set_placeholder_text("args…")
        args_entry.set_hexpand(True)
        args_entry.connect("changed", self._mark_dirty)
        row.pack_start(args_entry, True, True, 0)
        del_btn = Gtk.Button.new_from_icon_name("list-remove-symbolic", Gtk.IconSize.BUTTON)
        del_btn.connect("clicked", lambda x: container.remove(row))
        row.pack_end(del_btn, False, False, 0)
        row.bind_mods = mod_checks
        row.bind_mods_extra = list(extra)
        row.bind_key = key
        row.bind_key_btn = key_btn
        row.bind_action = action_combo
        row.bind_args = args_entry
        container.add(row)
        row.show_all()
        return row

    def _read_bind_row(self, row):
        sel = [m for m in BIND_MODS if row.bind_mods[m].get_active()]
        key = row.bind_key or ""
        action = (row.bind_action.get_active_text() or "").strip()
        args = row.bind_args.get_text().strip()
        return self._serialize_bind(row.bind_mods_extra, sel, key, action, args)

    def _bind_rows(self, container):
        return [ch for ch in container.get_children() if hasattr(ch, 'bind_mods')]

    def get_bind_items(self, container):
        return [self._read_bind_row(r) for r in self._bind_rows(container)]

    def validate_binds(self):
        errors = []
        for key, label in [('bind_list', 'Normal'), ('bind_release_list', 'Release'),
                           ('bind_mouse_list', 'Mouse'), ('bind_repeat_list', 'Repeat'),
                           ('bind_locked_list', 'Locked')]:
            c = self.widgets.get(key)
            if c is None:
                continue
            for i, row in enumerate(self._bind_rows(c), 1):
                parts = [p.strip() for p in self._read_bind_row(row).split(",", 3)]
                k = parts[1] if len(parts) > 1 else ""
                a = parts[2] if len(parts) > 2 else ""
                if not k:
                    errors.append(f"{label} row {i}: missing key")
                if not a:
                    errors.append(f"{label} row {i}: missing action")
        return errors

    def _start_key_capture(self, btn, row):
        self._key_capture = {'btn': btn, 'row': row, 'prev': btn.get_label()}
        btn.set_label("Press key…")
        self._mark_dirty()

    def _on_key_btn_press(self, btn, event, row):
        if event.button == 3:
            self._manual_key_dialog(row)
            return True
        return False

    def _manual_key_dialog(self, row):
        dialog = Gtk.MessageDialog(transient_for=self, modal=True,
                                   message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text="Key name (e.g. Q, F5, XF86AudioRaiseVolume, mouse:272)")
        entry = Gtk.Entry(); entry.set_text(row.bind_key or ""); entry.show()
        dialog.get_content_area().pack_start(entry, True, True, 0)
        res = dialog.run()
        name = entry.get_text().strip()
        dialog.destroy()
        if res == Gtk.ResponseType.OK and name:
            row.bind_key = name
            row.bind_key_btn.set_label(name)
            self._mark_dirty()

    def _finish_key_capture(self, event):
        cap = self._key_capture
        if event.keyval == Gdk.KEY_Escape:
            cap['btn'].set_label(cap['prev'])
            self._key_capture = None
            return True
        name = Gdk.keyval_name(event.keyval)
        if not name:
            return True
        # Ignore pure modifier presses; keep waiting for the real key.
        if name in ('Shift_L', 'Shift_R', 'Control_L', 'Control_R',
                    'Alt_L', 'Alt_R', 'Super_L', 'Super_R', 'Meta_L', 'Meta_R',
                    'ISO_Level3_Shift', 'Caps_Lock', 'Num_Lock'):
            return True
        if len(name) == 1 and name.isalpha():
            name = name.upper()
        cap['row'].bind_key = name
        cap['btn'].set_label(name)
        self._key_capture = None
        self._mark_dirty()
        return True

    def _normalize_binds(self):
        """Rewrite stored bind strings to canonical form, in place.

        In-place item assignment preserves each array's TOML formatting, so
        the startup snapshot matches what collect will later produce."""
        binds = self.doc.get('binds')
        if not isinstance(binds, dict):
            return
        for sub in ('normal', 'release', 'mouse', 'repeat', 'locked'):
            sec = binds.get(sub)
            if not isinstance(sec, dict):
                continue
            lst = sec.get('list')
            if not isinstance(lst, list):
                continue
            for i, s in enumerate(lst):
                try:
                    n = self._serialize_bind(*self._parse_bind_string(s))
                except Exception:
                    continue
                if n != str(s):
                    lst[i] = n

    def _tg(self, section, key, default):
        """Thread-safe get for nested TOML sections that may not exist."""
        d = self.doc
        for part in section.split('.'):
            if not isinstance(d, dict) or part not in d:
                return default
            d = d[part]
        if isinstance(d, dict) and key in d:
            return d[key]
        return default

    def _snapshot_sections(self):
        """Per-top-level-section dumps for change detection.

        Used to run only the side effects (reload, wallpaper/theme/dock
        scripts) relevant to what actually changed, so Apply doesn't stomp
        unrelated live state (e.g. restarting the wallpaper engine when
        only keybinds changed).
        """
        try:
            return {k: tomlkit.dumps(v) for k, v in self.doc.items()}
        except Exception:
            return {}

    def _st(self, section, key, value):
        """Set a value in the TOML doc, creating sections as needed."""
        d = self.doc
        for part in section.split('.'):
            if part not in d:
                d[part] = tomlkit.table()
            d = d[part]
        d[key] = value

    def _ensure_table(self, dotted):
        """Create nested TOML tables along a dotted path if missing."""
        d = self.doc
        for part in dotted.split('.'):
            if part not in d or not isinstance(d[part], dict):
                d[part] = tomlkit.table()
            d = d[part]
        return d

    def ensure_defaults(self):
        """Create every section the UI indexes directly.

        Preserved TOMLs from older installs may lack newer sections;
        without this, page builders crash startup with KeyError.
        In-memory only — written out solely via the normal Apply flow.
        """
        for section in (
            "general", "decoration", "decoration.blur", "input",
            "input.touchpad", "monitors", "wallpapers", "wallpapers.fixed",
            "animations", "binds", "binds.normal", "binds.release",
            "binds.mouse", "binds.repeat", "binds.locked", "idle",
            "lockscreen", "nightlight", "launcher", "launcher.dock",
            "launcher.drun", "launcher.power_menu", "launcher.dmenu",
            "programs", "plugins", "scrolling", "rules", "misc", "dwindle",
            "master", "gesture", "autostart", "env", "custom", "theme",
            "hyprrocket", "hyprrocket.events",
        ):
            self._ensure_table(section)

    def _accent_to_hex(self, color):
        """Normalize a CSS color (#hex, rgb(), rgba()) to RRGGBB hex."""
        import re as _re
        s = (color or "").strip()
        m = _re.match(r'#([0-9a-fA-F]{6})', s)
        if m:
            return m.group(1).lower()
        m = _re.match(
            r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', s)
        if m:
            r, g, b = (max(0, min(255, int(m.group(i)))) for i in (1, 2, 3))
            return f"{r:02x}{g:02x}{b:02x}"
        return "007aff"

    def _color_button(self, rgba_str, callback):
        """Create a color swatch button that opens color chooser."""
        btn = Gtk.Button()
        btn.get_style_context().add_class("color-swatch")
        rgba = Gdk.RGBA()
        rgba.parse(rgba_str or "rgba(0,0,0,0)")
        btn.override_background_color(Gtk.StateFlags.NORMAL, rgba)
        btn.connect("clicked", callback)
        btn._current_rgba = rgba_str
        return btn

    def _update_swatch(self, btn, color_str):
        rgba = Gdk.RGBA()
        rgba.parse(color_str)
        btn.override_background_color(Gtk.StateFlags.NORMAL, rgba)
        btn._current_rgba = color_str

    def create_settings_pages(self):
        self.widgets = {}
        groups = [
            ("PERSONALIZATION", [
                ("appearance","Desktop","preferences-desktop-theme",self.build_appearance),
                ("colors","Border Colors","preferences-desktop-color",self.build_colors),
                ("themes","Themes & Accent","gnome-twist",self.build_themes),
                ("wallpapers","Wallpapers","background",self.build_wallpapers),
                ("animations","Motion Effects","view-restore",self.build_animations),
            ]),
            ("DISPLAY & WINDOWS", [
                ("monitors","Displays & Layout","video-display",self.build_monitors),
                ("display_flags","Startup & Splash","video-display",self.build_display_flags),
                ("window_rules","Window Rules","preferences-other",self.build_window_rules),
                ("scrolling","Scrolling Layout","go-down",self.build_scrolling),
                ("layouts","Tiling Layouts","view-grid",self.build_layouts),
            ]),
            ("INPUT", [
                ("keyboard","Keyboard","input-keyboard",self.build_keyboard),
                ("mouse","Mouse & Trackpad","input-mouse",self.build_mouse),
                ("gestures","Gestures","touchscreen",self.build_gestures),
                ("keybinds","Keybinds","input-keyboard",self.build_keybinds),
            ]),
            ("SYSTEM", [
                ("lockscreen","Lock & Power","system-lock-screen",self.build_lock),
                ("nightlight","Nightlight","weather-clear-night",self.build_nightlight),
                ("autostart","Autostart","system-run",self.build_autostart),
                ("hyprrocket","Routines","alarm",self.build_hyprrocket),
                ("environment","Environment","preferences-system",self.build_environment),
            ]),
            ("APPS", [
                ("launcher","Launcher & Dock","start-here",self.build_launcher),
                ("programs","Default Apps","application-x-executable",self.build_programs),
            ]),
            ("ADVANCED", [
                ("plugins","Extensions","preferences-plugin",self.build_plugins),
                ("custom_lua","Custom Lua","accessories-text-editor",self.build_custom_lua),
            ]),
        ]
        first_row = None
        for group_label, pages in groups:
            lbl = Gtk.Label(label=group_label); lbl.set_xalign(0); lbl.get_style_context().add_class("sidebar-group-label")
            lbl_row = Gtk.ListBoxRow(); lbl_row.set_selectable(False); lbl_row.set_activatable(False); lbl_row.add(lbl); self.sidebar.add(lbl_row)
            lbl_row.is_group_label = True; lbl_row.group_label = group_label
            for name, title, icon, builder in pages:
                row = Gtk.ListBoxRow(); row.row_name = name; row.set_name(name); row.set_can_focus(True)
                row.page_title = title; row.page_group = group_label
                box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                box.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU), False, False, 0)
                box.pack_start(Gtk.Label(label=title), False, False, 0)
                row.add(box); self.sidebar.add(row)
                page = builder()
                revert_wrap = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
                revert_wrap.pack_start(Gtk.Box(), True, True, 0)
                revert = Gtk.Button(label="Revert page"); revert.set_name("revert-btn")
                revert.set_tooltip_text("Restore this page to the values it had when Settings was opened")
                revert.connect("clicked", lambda _b, n=name: self._on_revert_page(n))
                revert_wrap.pack_end(revert, False, False, 0)
                page.pack_start(revert_wrap, False, False, 0); page.reorder_child(revert_wrap, 1); revert_wrap.show_all()
                self.stack.add_titled(page, name, title)
                if first_row is None: first_row = row
        if first_row: self.sidebar.select_row(first_row)
        self._search_index = {}
        self._build_search_index()
        self.sidebar.set_filter_func(self._sidebar_filter_func, None)
        self._dirty = False
        self._restoring = False
        self._closed = False
        self._live_apply_id = None
        self._initial_widget_values = {}
        self._snapshot_widget_values()
        self._track_dirty_signals()
        self._track_live_apply()
        self._mark_clean()

    # --- PAGE BUILDERS ---

    def build_appearance(self):
        v = self.build_page_vbox("Desktop Appearance")
        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")
        for k, l, t in [('gaps_in','Inner Gaps','general'),('gaps_out','Outer Gaps','general'),('border_size','Border Size','general'),('rounding','Rounding','decoration')]:
            self.widgets[k] = Gtk.SpinButton.new_with_range(0, 500, 1); self.widgets[k].set_value(self.doc[t].get(k, 0)); f.pack_start(self.create_row(l, self.widgets[k]), False, False, 0)
        v.pack_start(f, False, False, 0)
        f2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f2.get_style_context().add_class("group-frame")
        for k, l in [('active_opacity','Active Window'),('inactive_opacity','Inactive Window'),('waybar_opacity','Waybar Opacity'),('launcher_opacity','Launcher Opacity')]:
            self.widgets[k] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.1, 1.0, 0.05); self.widgets[k].set_value(self.doc['decoration'].get(k, 1.0)); self.widgets[k].set_draw_value(True); self.widgets[k].set_value_pos(Gtk.PositionType.RIGHT); self.widgets[k].set_size_request(220,-1); f2.pack_start(self.create_row(l, self.widgets[k]), False, False, 0)
        v.pack_start(f2, False, False, 0)
        f3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f3.get_style_context().add_class("group-frame")
        self.widgets['blur_enabled'] = Gtk.Switch(); self.widgets['blur_enabled'].set_active(self._tg('decoration.blur','enabled',True)); f3.pack_start(self.create_row("Enable Blur", self.widgets['blur_enabled']), False, False, 0)
        self.widgets['blur_size'] = Gtk.SpinButton.new_with_range(0, 20, 1); self.widgets['blur_size'].set_value(self._tg('decoration.blur','size',3)); f3.pack_start(self.create_row("Blur Size", self.widgets['blur_size']), False, False, 0)
        self.widgets['blur_passes'] = Gtk.SpinButton.new_with_range(0, 10, 1); self.widgets['blur_passes'].set_value(self._tg('decoration.blur','passes',1)); f3.pack_start(self.create_row("Blur Passes", self.widgets['blur_passes']), False, False, 0)
        v.pack_start(f3, False, False, 0)
        f4 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f4.get_style_context().add_class("group-frame")
        self.widgets['layout'] = Gtk.ComboBoxText()
        for val in ["dwindle", "master", "scroll"]: self.widgets['layout'].append(val, val.capitalize())
        self.widgets['layout'].set_active_id(self._tg('general','layout','scroll'))
        f4.pack_start(self.create_row("Window Layout", self.widgets['layout']), False, False, 0)
        self.widgets['resize_on_border'] = Gtk.Switch(); self.widgets['resize_on_border'].set_active(self._tg('general','resize_on_border',False)); f4.pack_start(self.create_row("Resize on Border Drag", self.widgets['resize_on_border']), False, False, 0)
        self.widgets['allow_tearing'] = Gtk.Switch(); self.widgets['allow_tearing'].set_active(self._tg('general','allow_tearing',False)); f4.pack_start(self.create_row("Allow Tearing", self.widgets['allow_tearing']), False, False, 0)
        v.pack_start(f4, False, False, 0)
        return v

    def build_colors(self):
        v = self.build_page_vbox("Border Colors")
        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")

        active_border = Gtk.Entry(); active_border.set_text(self._tg('general','col_active_border','rgba(33ccffee) rgba(00ff99ee) 45deg'))
        self.widgets['col_active_border'] = active_border
        active_pick = Gtk.Button(label="Pick"); active_pick.get_style_context().add_class("picker")
        def on_pick_active(b):
            c = self.open_color_picker("Active Border Color")
            if c: active_border.set_text(c)
        active_pick.connect("clicked", on_pick_active)
        hba = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10); hba.set_margin_bottom(8)
        hba.pack_start(Gtk.Label(label="Active Border"), True, True, 0); hba.pack_end(active_pick, False, False, 0); hba.pack_end(active_border, False, False, 0)
        f.pack_start(hba, False, False, 0)

        inactive_border = Gtk.Entry(); inactive_border.set_text(self._tg('general','col_inactive_border','rgba(595959aa)'))
        self.widgets['col_inactive_border'] = inactive_border
        inactive_pick = Gtk.Button(label="Pick"); inactive_pick.get_style_context().add_class("picker")
        def on_pick_inactive(b):
            c = self.open_color_picker("Inactive Border Color")
            if c: inactive_border.set_text(c)
        inactive_pick.connect("clicked", on_pick_inactive)
        hbi = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10); hbi.set_margin_bottom(8)
        hbi.pack_start(Gtk.Label(label="Inactive Border"), True, True, 0); hbi.pack_end(inactive_pick, False, False, 0); hbi.pack_end(inactive_border, False, False, 0)
        f.pack_start(hbi, False, False, 0)

        v.pack_start(f, False, False, 0)
        return v

    def build_themes(self):
        v = self.build_page_vbox("Themes & Accent Color")

        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")

        self.widgets['theme_mode'] = Gtk.ComboBoxText()
        for val, label in [("dark","Dark"), ("light","Light"), ("auto","Auto (Time)")]:
            self.widgets['theme_mode'].append(val, label)
        self.widgets['theme_mode'].set_active_id(self._tg('theme','mode','dark'))
        f.pack_start(self.create_row("Theme Mode", self.widgets['theme_mode']), False, False, 0)

        # Accent color picker
        accent_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        accent_hbox.set_margin_bottom(8)
        accent_label = Gtk.Label(label="Accent Color"); accent_label.set_xalign(0)
        accent_hbox.pack_start(accent_label, True, True, 0)

        current_accent = self._tg('theme','accent','#007aff')
        self.widgets['theme_accent_btn'] = Gtk.Button.new_with_label("Pick Color")
        self.widgets['theme_accent_btn'].get_style_context().add_class("picker")
        def on_accent_pick(b):
            c = self.open_color_picker("Accent Color", self._tg('theme','accent','#007aff'))
            if c:
                self._st('theme','accent',c)
                self._update_accent_preview(self._parse_color(c))
        self.widgets['theme_accent_btn'].connect("clicked", on_accent_pick)
        accent_hbox.pack_end(self.widgets['theme_accent_btn'], False, False, 0)
        f.pack_start(accent_hbox, False, False, 0)

        # Accent preview strip
        self.widgets['accent_preview'] = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.widgets['accent_preview'].set_size_request(-1, 32)
        self.widgets['accent_preview'].get_style_context().add_class("accent-preview")
        self._update_accent_preview(self._parse_color(current_accent))
        f.pack_start(self.widgets['accent_preview'], False, False, 8)

        v.pack_start(f, False, False, 0)

        # Theme description
        desc = Gtk.Label(label="Dark/Light switches the CSS theme files.\nAuto follows time of day via hyprrocket.\nAccent color affects highlights and active UI elements.")
        desc.set_xalign(0); desc.set_line_wrap(True); desc.set_opacity(0.6); desc.set_margin_top(8)
        v.pack_start(desc, False, False, 0)

        return v

    def _parse_color(self, s):
        rgba = Gdk.RGBA()
        rgba.parse(s if s else "#007aff")
        return rgba

    def _update_accent_preview(self, rgba):
        css = f"* {{ background-color: {rgba.to_string()}; border-radius: 8px; min-height: 24px; }}"
        if not hasattr(self, '_accent_css_provider'):
            self._accent_css_provider = Gtk.CssProvider()
            self.widgets['accent_preview'].get_style_context().add_provider(
                self._accent_css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._accent_css_provider.load_from_data(css.encode())

    def build_monitors(self):
        v = self.build_page_vbox("Displays & Layout")
        
        # Scale Slider
        f1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f1.get_style_context().add_class("group-frame")
        self.widgets['monitor_scale'] = Gtk.ComboBoxText()
        for s in ["0.5", "0.75", "0.8", "1.0", "1.25", "1.5", "1.75", "2.0", "2.5"]: 
            self.widgets['monitor_scale'].append(s, f"{int(float(s)*100)}%")
        
        current_scale = "1.0"
        rules = self.doc['monitors'].get('rules', [])
        if rules and len(rules) > 0:
            parts = rules[0].split(',')
            if len(parts) >= 4:
                current_scale = parts[3].strip()
        self.widgets['monitor_scale'].set_active_id(current_scale)
        f1.pack_start(self.create_row("Global UI Scale", self.widgets['monitor_scale']), False, False, 0)
        v.pack_start(f1, False, False, 0)

        f, self.widgets['monitor_list'] = self.build_dynamic_list(rules, "Advanced Monitor Rules (name, res, pos, scale)")
        v.pack_start(f, False, False, 0)
        v.pack_start(self._anchor_bar('monitors', [("Scale", f1), ("Rules", f)]), False, False, 0)
        v.reorder_child(v.get_children()[-1], 1)
        return v

    def build_wallpapers(self):
        v = self.build_page_vbox("Wallpaper Management")
        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        f.get_style_context().add_class("group-frame")

        self.widgets['wp_mode'] = Gtk.ComboBoxText()
        for m in ["fixed", "dynamic", "disabled"]: self.widgets['wp_mode'].append(m, m.capitalize())
        self.widgets['wp_mode'].set_active_id(self.doc['wallpapers'].get('mode', "fixed"))
        f.pack_start(self.create_row("Active Mode", self.widgets['wp_mode']), False, False, 0)

        self.widgets['wp_image_btn'] = Gtk.Button(label="Browse Image...")
        self.widgets['wp_image_btn'].get_style_context().add_class("picker")
        self.widgets['wp_image_btn'].connect("clicked", lambda x: self.update_picker_path('wp_image_path', "Select Wallpaper"))
        self.widgets['wp_image_path'] = Gtk.Entry()
        self.widgets['wp_image_path'].set_text(self.doc['wallpapers']['fixed'].get('image', ""))
        self.widgets['_wp_fixed_row'] = self.create_row("Static Image", self.widgets['wp_image_btn'])
        f.pack_start(self.widgets['_wp_fixed_row'], False, False, 0)
        f.pack_start(self._wrap_with_thumbnail('wp_image_path'), False, False, 0)

        self.widgets['wp_dir_btn'] = Gtk.Button(label="Browse Folder...")
        self.widgets['wp_dir_btn'].get_style_context().add_class("picker")
        self.widgets['wp_dir_btn'].connect("clicked", lambda x: self.update_picker_path('wp_dir_path', "Select Wallpaper Folder", True))
        self.widgets['wp_dir_path'] = Gtk.Entry()
        self.widgets['wp_dir_path'].set_text(self.doc['wallpapers'].get('path', "~/Pictures/wallpapers"))
        self.widgets['_wp_dir_row'] = self.create_row("Collection Folder", self.widgets['wp_dir_btn'])
        f.pack_start(self.widgets['_wp_dir_row'], False, False, 0)
        f.pack_start(self.widgets['wp_dir_path'], False, False, 0)

        def on_mode_changed(combo):
            mode = combo.get_active_id()
            self.widgets['_wp_fixed_row'].set_visible(mode == "fixed")
            self.widgets['wp_image_path'].set_visible(mode == "fixed")
            self.widgets['_wp_dir_row'].set_visible(mode == "dynamic")
            self.widgets['wp_dir_path'].set_visible(mode == "dynamic")

        self.widgets['wp_mode'].connect("changed", on_mode_changed)
        on_mode_changed(self.widgets['wp_mode'])

        v.pack_start(f, False, False, 0)
        return v

    def update_picker_path(self, key, title, folder=False):
        p = self.open_picker(title, folder)
        if p: self.widgets[key].set_text(p)

    def _wrap_with_thumbnail(self, entry_key, size=56):
        """Pack a path entry with a small image preview (file paths only).

        Display-only: the entry itself stays the tracked/saved widget."""
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        entry = self.widgets[entry_key]
        if GdkPixbuf is not None:
            thumb = Gtk.Image()
            thumb.set_size_request(size, size)

            def refresh(*_a):
                path = os.path.expanduser(os.path.expandvars(entry.get_text().strip()))
                try:
                    if path and os.path.isfile(path):
                        pb = GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size)
                        thumb.set_from_pixbuf(pb)
                        thumb.set_visible(True)
                    else:
                        thumb.set_visible(False)
                except Exception:
                    thumb.set_visible(False)

            entry.connect("changed", refresh)
            hbox.pack_start(thumb, False, False, 0)
            refresh()
        entry.set_hexpand(True)
        hbox.pack_start(entry, True, True, 0)
        return hbox

    def build_animations(self):
        v = self.build_page_vbox("Motion Engine"); f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")
        self.widgets['anim_enabled'] = Gtk.Switch(); self.widgets['anim_enabled'].set_active(self.doc['animations'].get('enabled', True)); f.pack_start(self.create_row("Enable Motion Effects", self.widgets['anim_enabled']), False, False, 0)
        for k, l in [('windows','Open Style'),('windowsOut','Exit Style'),('border','Border Speed'),('fade','Fading Curve'),('workspaces','Workspace Transition')]:
            self.widgets[f'anim_{k}'] = Gtk.Entry(); self.widgets[f'anim_{k}'].set_text(str(self.doc['animations'].get(k, ""))); f.pack_start(self.create_row(l, self.widgets[f'anim_{k}']), False, False, 0)
        v.pack_start(f, False, False, 0); return v

    def build_keyboard(self):
        v = self.build_page_vbox("Keyboard & Touchpad")
        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")
        for k, l in [('kb_layout','Layout'),('kb_variant','Variant'),('kb_model','Model'),('kb_rules','Rules')]:
            self.widgets[k] = Gtk.Entry(); self.widgets[k].set_text(self.doc['input'].get(k, "")); f.pack_start(self.create_row(l, self.widgets[k]), False, False, 0)
        
        # Caps Lock Behavior Dropdown (mapped to kb_options)
        self.widgets['caps_behavior'] = Gtk.ComboBoxText()
        for opt_id, opt_name in [("", "Default"), ("ctrl:nocaps", "Map to Control"), ("caps:escape", "Map to Escape"), ("caps:swapescape", "Swap Esc and CapsLock")]:
            self.widgets['caps_behavior'].append(opt_id, opt_name)
        
        current_opts = self.doc['input'].get('kb_options', "")
        # Try to match the current options to our dropdown, otherwise fallback to Default
        matched = False
        for opt_id in ["ctrl:nocaps", "caps:escape", "caps:swapescape"]:
            if opt_id in current_opts:
                self.widgets['caps_behavior'].set_active_id(opt_id)
                matched = True
                break
        if not matched: self.widgets['caps_behavior'].set_active_id("")
        
        f.pack_start(self.create_row("Caps Lock Behavior", self.widgets['caps_behavior']), False, False, 0)
        
        # Keep kb_options entry for advanced users
        self.widgets['kb_options'] = Gtk.Entry(); self.widgets['kb_options'].set_text(current_opts); f.pack_start(self.create_row("Advanced Options String", self.widgets['kb_options']), False, False, 0)
        
        v.pack_start(f, False, False, 0)
        f2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f2.get_style_context().add_class("group-frame")
        self.widgets['natural_scroll'] = Gtk.Switch(); self.widgets['natural_scroll'].set_active(self._tg('input.touchpad','natural_scroll',False)); f2.pack_start(self.create_row("Natural Scrolling (Touchpad)", self.widgets['natural_scroll']), False, False, 0)
        v.pack_start(f2, False, False, 0)
        return v

    def build_mouse(self):
        v = self.build_page_vbox("Mouse Settings")
        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")
        self.widgets['follow_mouse'] = Gtk.ComboBoxText()
        for val, label in [("0","Off"), ("1","On"), ("2","Always"), ("3","On (Fullscreen)")]:
            self.widgets['follow_mouse'].append(val, label)
        self.widgets['follow_mouse'].set_active_id(str(self._tg('input','follow_mouse',1)))
        f.pack_start(self.create_row("Focus Follows Mouse", self.widgets['follow_mouse']), False, False, 0)
        self.widgets['sensitivity'] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -1.0, 1.0, 0.05)
        self.widgets['sensitivity'].set_value(self._tg('input','sensitivity',0.0))
        self.widgets['sensitivity'].set_draw_value(True); self.widgets['sensitivity'].set_value_pos(Gtk.PositionType.RIGHT); self.widgets['sensitivity'].set_size_request(220,-1)
        f.pack_start(self.create_row("Sensitivity", self.widgets['sensitivity']), False, False, 0)
        v.pack_start(f, False, False, 0)
        return v

    def build_gestures(self):
        v = self.build_page_vbox("Trackpad Gestures")
        f, self.widgets['gesture_list'] = self.build_dynamic_list(self.doc.get('gesture', {}).get('list', []), 'Gesture Rules (fingers = N, direction = "...", action = "...")')
        v.pack_start(f, False, False, 0)
        return v

    def build_keybinds(self):
        v = self.build_page_vbox("Keybinds")
        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")
        self.widgets['mainMod'] = Gtk.ComboBoxText()
        for val in ["SUPER", "ALT", "CTRL"]: self.widgets['mainMod'].append(val, val.capitalize())
        self.widgets['mainMod'].set_active_id(self.doc['binds'].get('mainMod', 'SUPER'))
        f.pack_start(self.create_row("Main Modifier", self.widgets['mainMod']), False, False, 0)
        v.pack_start(f, False, False, 0)

        binds_norm = self.doc['binds'].get('normal', {}).get('list', [])
        f2, self.widgets['bind_list'] = self.build_bind_list(binds_norm, "Normal (MOD, KEY, ACTION, ARGS)")
        v.pack_start(f2, False, False, 0)

        binds_rel = self.doc['binds'].get('release', {}).get('list', [])
        f3, self.widgets['bind_release_list'] = self.build_bind_list(binds_rel, "Release")
        v.pack_start(f3, False, False, 0)

        binds_mouse = self.doc['binds'].get('mouse', {}).get('list', [])
        f4, self.widgets['bind_mouse_list'] = self.build_bind_list(binds_mouse, "Mouse")
        v.pack_start(f4, False, False, 0)

        binds_repeat = self.doc['binds'].get('repeat', {}).get('list', [])
        f5, self.widgets['bind_repeat_list'] = self.build_bind_list(binds_repeat, "Repeat")
        v.pack_start(f5, False, False, 0)

        binds_locked = self.doc['binds'].get('locked', {}).get('list', [])
        f6, self.widgets['bind_locked_list'] = self.build_bind_list(binds_locked, "Locked")
        v.pack_start(f6, False, False, 0)
        v.pack_start(self._anchor_bar('keybinds', [
            ("Normal", f2), ("Release", f3), ("Mouse", f4),
            ("Repeat", f5), ("Locked", f6)]), False, False, 0)
        v.reorder_child(v.get_children()[-1], 1)
        return v

    def build_lock(self):
        v = self.build_page_vbox("Lockscreen & Power")
        f1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f1.get_style_context().add_class("group-frame")
        for k, l in [('lock_timeout','Auto-Lock (s)'),('screen_off_timeout','Screen Off (s)'),('suspend_timeout','Suspend (s)')]:
            self.widgets[f'idle_{k}'] = Gtk.SpinButton.new_with_range(0, 7200, 30); self.widgets[f'idle_{k}'].set_value(self.doc['idle'].get(k, 300)); f1.pack_start(self.create_row(l, self.widgets[f'idle_{k}']), False, False, 0)
        v.pack_start(f1, False, False, 0)
        f2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f2.get_style_context().add_class("group-frame")
        self.widgets['lock_wp_btn'] = Gtk.Button(label="Select Wallpaper..."); self.widgets['lock_wp_btn'].get_style_context().add_class("picker"); self.widgets['lock_wp_btn'].connect("clicked", lambda x: self.update_picker_path('lock_wp_path', "Select Lock Wallpaper"))
        self.widgets['lock_wp_path'] = Gtk.Entry(); self.widgets['lock_wp_path'].set_text(self.doc['lockscreen'].get('background', ""))
        f2.pack_start(self.create_row("Lock Wallpaper", self.widgets['lock_wp_btn']), False, False, 0); f2.pack_start(self._wrap_with_thumbnail('lock_wp_path'), False, False, 5)
        self.widgets['lock_blur_passes'] = Gtk.SpinButton.new_with_range(0, 20, 1); self.widgets['lock_blur_passes'].set_value(self.doc['lockscreen'].get('blur_passes', 3))
        f2.pack_start(self.create_row("Blur Passes", self.widgets['lock_blur_passes']), False, False, 0)
        self.widgets['lock_blur_size'] = Gtk.SpinButton.new_with_range(0, 20, 1); self.widgets['lock_blur_size'].set_value(self.doc['lockscreen'].get('blur_size', 8))
        f2.pack_start(self.create_row("Blur Size", self.widgets['lock_blur_size']), False, False, 0); v.pack_start(f2, False, False, 0)
        f3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f3.get_style_context().add_class("group-frame")
        self.widgets['profile_btn'] = Gtk.Button(label="Select Picture..."); self.widgets['profile_btn'].get_style_context().add_class("picker"); self.widgets['profile_btn'].connect("clicked", lambda x: self.update_picker_path('profile_path', "Select Profile Picture"))
        self.widgets['profile_path'] = Gtk.Entry(); self.widgets['profile_path'].set_text(self.doc['lockscreen'].get('profile_image', "")); f3.pack_start(self.create_row("User Picture", self.widgets['profile_btn']), False, False, 0); f3.pack_start(self._wrap_with_thumbnail('profile_path'), False, False, 0); v.pack_start(f3, False, False, 0)
        f4 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f4.get_style_context().add_class("group-frame")
        self.widgets['lock_fail_text'] = Gtk.Entry(); self.widgets['lock_fail_text'].set_text(self.doc['lockscreen'].get('fail_text', '')); f4.pack_start(self.create_row("Fail Text", self.widgets['lock_fail_text']), False, False, 0)
        self.widgets['lock_placeholder_text'] = Gtk.Entry(); self.widgets['lock_placeholder_text'].set_text(self.doc['lockscreen'].get('placeholder_text', '')); f4.pack_start(self.create_row("Placeholder Text", self.widgets['lock_placeholder_text']), False, False, 0)
        v.pack_start(f4, False, False, 0)
        return v

    def build_nightlight(self):
        v = self.build_page_vbox("Eye Care")
        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")
        self.widgets['nl_enabled'] = Gtk.Switch(); self.widgets['nl_enabled'].set_active(self.doc['nightlight'].get('enabled', True)); f.pack_start(self.create_row("Enable Night Light", self.widgets['nl_enabled']), False, False, 0)
        self.widgets['nl_temp_day'] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1000, 10000, 100)
        self.widgets['nl_temp_day'].set_value(self._tg('nightlight','temp_day',6500)); self.widgets['nl_temp_day'].set_draw_value(True); self.widgets['nl_temp_day'].set_size_request(220,-1); f.pack_start(self.create_row("Day Temp (K)", self.widgets['nl_temp_day']), False, False, 0)
        self.widgets['nl_temp_night'] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1000, 10000, 100)
        self.widgets['nl_temp_night'].set_value(self._tg('nightlight','temp_night',3400)); self.widgets['nl_temp_night'].set_draw_value(True); self.widgets['nl_temp_night'].set_size_request(220,-1); f.pack_start(self.create_row("Night Strength / Temp (K)", self.widgets['nl_temp_night']), False, False, 0)
        v.pack_start(f, False, False, 0); return v

    def build_autostart(self):
        v = self.build_page_vbox("Autostart Applications")
        f, self.widgets['autostart_list'] = self.build_dynamic_list(self.doc.get('autostart', {}).get('exec_once', []), "Launch at Startup (one per line)")
        v.pack_start(f, False, False, 0)
        return v

    def build_hyprrocket(self):
        v = self.build_page_vbox("Scheduled Routines")
        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")
        self.widgets['rocket_enabled'] = Gtk.Switch()
        self.widgets['rocket_enabled'].set_active(self._tg('hyprrocket', 'enabled', True))
        f.pack_start(self.create_row("Enable Scheduler", self.widgets['rocket_enabled']), False, False, 0)
        v.pack_start(f, False, False, 0)

        self.widgets['rocket_routines_box'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        v.pack_start(self.widgets['rocket_routines_box'], False, False, 0)

        add_btn = Gtk.Button(label="+ Add Routine")
        add_btn.get_style_context().add_class("picker")
        add_btn.connect("clicked", self.on_add_rocket_routine)
        v.pack_start(add_btn, False, False, 0)

        events = {}
        try:
            rocket = self.doc.get('hyprrocket', {})
            if isinstance(rocket, dict):
                events = rocket.get('events', {})
                if not isinstance(events, dict): events = {}
        except Exception:
            events = {}
            
        self.widgets['rocket_events_list'] = []
        for name, ev in events.items():
            self.add_rocket_routine_ui(name, ev)

        return v

    def on_add_rocket_routine(self, btn):
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL, text="New Routine Name (e.g. morning)")
        entry = Gtk.Entry(); entry.set_placeholder_text("routine_name"); entry.show()
        dialog.get_content_area().pack_start(entry, True, True, 0)
        res = dialog.run()
        name = entry.get_text().strip()
        dialog.destroy()
        if res == Gtk.ResponseType.OK and name:
            self.add_rocket_routine_ui(name, {})

    def add_rocket_routine_ui(self, name, ev):
        ef = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); ef.get_style_context().add_class("group-frame")
        
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        title = Gtk.Label(label=f"Routine: {name}"); title.set_xalign(0); title.set_margin_bottom(6)
        title.get_style_context().add_class("section-title")
        del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.BUTTON)
        del_btn.get_style_context().add_class("destructive-action")
        header.pack_start(title, True, True, 0)
        header.pack_end(del_btn, False, False, 0)
        ef.pack_start(header, False, False, 0)
        
        trig = Gtk.Entry(); trig.set_text(str(ev.get('trigger', '')) if isinstance(ev, dict) else "")
        trig.set_placeholder_text("HH:MM (e.g. 09:00)")
        ef.pack_start(self.create_row("Time (24h)", trig), False, False, 0)
        
        days = Gtk.Entry(); days.set_text(str(ev.get('days', '')) if isinstance(ev, dict) else "")
        days.set_placeholder_text("Optional: Mon-Fri")
        ef.pack_start(self.create_row("Days", days), False, False, 0)
        
        on = Gtk.Switch(); on.set_active(bool(ev.get('enabled', True)) if isinstance(ev, dict) else True)
        ef.pack_start(self.create_row("Enabled", on), False, False, 0)
        
        act_lbl = Gtk.Label(label="Actions (one shell command per line):"); act_lbl.set_xalign(0); act_lbl.set_margin_top(5)
        ef.pack_start(act_lbl, False, False, 0)
        
        act_view = Gtk.TextView(); act_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        actions_list = ev.get('actions', []) if isinstance(ev, dict) else []
        if isinstance(actions_list, list):
            act_view.get_buffer().set_text("\n".join(str(a) for a in actions_list))
        
        scroll = Gtk.ScrolledWindow(); scroll.set_min_content_height(80); scroll.add(act_view)
        ef.pack_start(scroll, True, True, 0)
        
        ui_obj = {'name': name, 'box': ef, 'trig': trig, 'days': days, 'on': on, 'actions': act_view}
        self.widgets['rocket_events_list'].append(ui_obj)
        
        del_btn.connect("clicked", lambda x: self.remove_rocket_routine_ui(ui_obj))

        trig.connect("changed", self._mark_dirty)
        days.connect("changed", self._mark_dirty)
        on.connect("notify::active", self._mark_dirty)
        act_view.get_buffer().connect("changed", self._mark_dirty)

        self.widgets['rocket_routines_box'].pack_start(ef, False, False, 0)
        self.widgets['rocket_routines_box'].show_all()

    def remove_rocket_routine_ui(self, ui_obj):
        self.widgets['rocket_events_list'].remove(ui_obj)
        ui_obj['box'].destroy()

    def build_environment(self):
        v = self.build_page_vbox("Environment Variables")
        f, self.widgets['env_list'] = self.build_dynamic_list(self._tg('env','vars',[]), "KEY,VALUE pairs")
        v.pack_start(f, False, False, 0)
        return v

    def build_launcher(self):
        v = self.build_page_vbox("Navigation & Dock")

        # 1. Launcher Layout
        f1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f1.get_style_context().add_class("group-frame")
        lbl1 = Gtk.Label(label="Launcher Layout"); lbl1.set_xalign(0); lbl1.set_margin_bottom(10); f1.pack_start(lbl1, False, False, 0)

        self.widgets['l_pos'] = Gtk.ComboBoxText()
        for p in ["top", "center"]: self.widgets['l_pos'].append(p, p.capitalize())
        self.widgets['l_pos'].set_active_id(self.doc['launcher'].get('position', "top"))
        f1.pack_start(self.create_row("Screen Position", self.widgets['l_pos']), False, False, 0)

        self.widgets['l_width'] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 20, 100, 1)
        self.widgets['l_width'].set_value(self.doc['launcher'].get('width_percent', 70))
        self.widgets['l_width'].set_size_request(220,-1)
        f1.pack_start(self.create_row("Width (%)", self.widgets['l_width']), False, False, 0)

        self.widgets['l_margin'] = Gtk.SpinButton.new_with_range(0, 1000, 10)
        self.widgets['l_margin'].set_value(self.doc['launcher'].get('margin_top', 100))
        f1.pack_start(self.create_row("Top Margin (px)", self.widgets['l_margin']), False, False, 0)
        v.pack_start(f1, False, False, 0)

        # 2. Content & Scaling
        f2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f2.get_style_context().add_class("group-frame")
        lbl2 = Gtk.Label(label="Content & Scaling"); lbl2.set_xalign(0); lbl2.set_margin_bottom(10); f2.pack_start(lbl2, False, False, 0)

        self.widgets['l_font'] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 12, 72, 1)
        self.widgets['l_font'].set_value(self.doc['launcher'].get('font_size', 24))
        self.widgets['l_font'].set_size_request(220,-1)
        f2.pack_start(self.create_row("Search Font Size", self.widgets['l_font']), False, False, 0)

        self.widgets['l_icon'] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 16, 128, 4)
        self.widgets['l_icon'].set_value(self.doc['launcher'].get('icon_size', 32))
        self.widgets['l_icon'].set_size_request(220,-1)
        f2.pack_start(self.create_row("App Icon Size", self.widgets['l_icon']), False, False, 0)

        self.widgets['l_spacing'] = Gtk.SpinButton.new_with_range(0, 50, 1)
        self.widgets['l_spacing'].set_value(self.doc['launcher'].get('row_spacing', 10))
        f2.pack_start(self.create_row("Item Spacing", self.widgets['l_spacing']), False, False, 0)
        v.pack_start(f2, False, False, 0)

        # 3. Sub-mode overrides
        for mode_key, mode_title in [("drun","App Launcher Override"), ("power_menu","Power Menu Override"), ("dmenu","Dmenu Override")]:
            expander = Gtk.Expander(label=mode_title)
            expander.set_margin_bottom(6)
            ef = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            ef.set_margin_top(6)
            sub = self.doc['launcher'].get(mode_key, {}) if isinstance(self.doc['launcher'].get(mode_key), dict) else {}

            wp = Gtk.SpinButton.new_with_range(20, 100, 1)
            wp.set_value(sub.get('width_percent', 60))
            self.widgets[f'l_{mode_key}_width'] = wp
            ef.pack_start(self.create_row("Width %", wp), False, False, 0)

            pp = Gtk.ComboBoxText()
            for p in ["top", "center"]: pp.append(p, p.capitalize())
            pp.set_active_id(sub.get('position', "center"))
            self.widgets[f'l_{mode_key}_pos'] = pp
            ef.pack_start(self.create_row("Position", pp), False, False, 0)

            mt = Gtk.SpinButton.new_with_range(0, 1000, 10)
            mt.set_value(sub.get('margin_top', 100))
            self.widgets[f'l_{mode_key}_margin'] = mt
            ef.pack_start(self.create_row("Top Margin", mt), False, False, 0)

            expander.add(ef)
            v.pack_start(expander, False, False, 0)

        # 4. Dock
        f3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f3.get_style_context().add_class("group-frame")
        lbl3 = Gtk.Label(label="System Dock"); lbl3.set_xalign(0); lbl3.set_margin_bottom(10); f3.pack_start(lbl3, False, False, 0)
        self.widgets['dock_enabled'] = Gtk.Switch()
        self.widgets['dock_enabled'].set_active(self.doc['launcher']['dock'].get('enabled', True))
        f3.pack_start(self.create_row("Enable Mac-style Dock", self.widgets['dock_enabled']), False, False, 0)

        self.widgets['dock_pos'] = Gtk.ComboBoxText()
        for p in ["bottom", "top", "left", "right"]: self.widgets['dock_pos'].append(p, p.capitalize())
        self.widgets['dock_pos'].set_active_id(self.doc['launcher']['dock'].get('position', "bottom"))
        f3.pack_start(self.create_row("Dock Position", self.widgets['dock_pos']), False, False, 0)

        self.widgets['dock_autohide'] = Gtk.Switch()
        self.widgets['dock_autohide'].set_active(self._tg('launcher.dock','autohide',True))
        f3.pack_start(self.create_row("Autohide", self.widgets['dock_autohide']), False, False, 0)

        self.widgets['dock_icon_size'] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 24, 96, 4)
        self.widgets['dock_icon_size'].set_value(self._tg('launcher.dock','icon_size',48)); self.widgets['dock_icon_size'].set_draw_value(True); self.widgets['dock_icon_size'].set_size_request(200,-1)
        f3.pack_start(self.create_row("Icon Size", self.widgets['dock_icon_size']), False, False, 0)

        self.widgets['dock_padding'] = Gtk.SpinButton.new_with_range(4, 48, 2)
        self.widgets['dock_padding'].set_value(self._tg('launcher.dock','padding',12))
        f3.pack_start(self.create_row("Padding", self.widgets['dock_padding']), False, False, 0)

        self.widgets['dock_rounding'] = Gtk.SpinButton.new_with_range(0, 48, 2)
        self.widgets['dock_rounding'].set_value(self._tg('launcher.dock','rounding',24))
        f3.pack_start(self.create_row("Rounding", self.widgets['dock_rounding']), False, False, 0)

        self.widgets['dock_margin'] = Gtk.SpinButton.new_with_range(0, 100, 2)
        self.widgets['dock_margin'].set_value(self._tg('launcher.dock','margin',10))
        f3.pack_start(self.create_row("Screen Margin", self.widgets['dock_margin']), False, False, 0)

        apps = self._tg('launcher.dock','apps',[])
        f3b, self.widgets['dock_apps_list'] = self.build_dynamic_list(apps, "Dock Apps (binary names)")
        v.pack_start(f3, False, False, 0)
        v.pack_start(f3b, False, False, 0)

        return v

    def build_programs(self):
        v = self.build_page_vbox("Default Apps")
        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")
        for k in ["terminal", "fileManager", "status_bar", "launcher", "notification_service"]:
            self.widgets[k] = Gtk.Entry(); self.widgets[k].set_text(self.doc['programs'].get(k, "")); f.pack_start(self.create_row(k.replace('_',' ').capitalize(), self.widgets[k]), False, False, 0)
        self.widgets['autohide_bar'] = Gtk.Switch(); self.widgets['autohide_bar'].set_active(self.doc['programs'].get('autohide_bar', False)); f.pack_start(self.create_row("Autohide Status Bar", self.widgets['autohide_bar']), False, False, 0)
        v.pack_start(f, False, False, 0); return v

    def build_scrolling(self):
        v = self.build_page_vbox("Scrolling Layout")
        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")
        self.widgets['scroll_column_width'] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.2, 1.0, 0.05)
        self.widgets['scroll_column_width'].set_value(self._tg('scrolling','column_width',0.5)); self.widgets['scroll_column_width'].set_size_request(220,-1); self.widgets['scroll_column_width'].set_draw_value(True)
        f.pack_start(self.create_row("Column Width", self.widgets['scroll_column_width']), False, False, 0)
        self.widgets['scroll_fullscreen'] = Gtk.Switch(); self.widgets['scroll_fullscreen'].set_active(self._tg('scrolling','fullscreen_on_one_column',True)); f.pack_start(self.create_row("Fullscreen Single Column", self.widgets['scroll_fullscreen']), False, False, 0)
        self.widgets['scroll_focus_fit'] = Gtk.ComboBoxText()
        for vv, ll in [("0","Center Focused"),("1","Fit to Screen")]: self.widgets['scroll_focus_fit'].append(vv, ll)
        self.widgets['scroll_focus_fit'].set_active_id(str(self._tg('scrolling','focus_fit_method',0)))
        f.pack_start(self.create_row("Focus Fit Method", self.widgets['scroll_focus_fit']), False, False, 0)
        self.widgets['scroll_explicit_widths'] = Gtk.Entry()
        self.widgets['scroll_explicit_widths'].set_text(str(self._tg('scrolling','explicit_column_widths','')))
        f.pack_start(self.create_row("Explicit Widths", self.widgets['scroll_explicit_widths']), False, False, 0)
        v.pack_start(f, False, False, 0); return v

    def build_window_rules(self):
        v = self.build_page_vbox("Window Rules")
        f, self.widgets['window_rules_list'] = self.build_dynamic_list(self.doc.get('rules', {}).get('window', []), 'Rules (ACTION, class:REGEX or title:REGEX)')
        v.pack_start(f, False, False, 0)
        return v

    def build_display_flags(self):
        v = self.build_page_vbox("Startup & Splash")
        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")
        self.widgets['force_default_wallpaper'] = Gtk.ComboBoxText()
        for vv, ll in [("0","Off"),("1","On"),("2","On (Hyprland)")]: self.widgets['force_default_wallpaper'].append(vv, ll)
        self.widgets['force_default_wallpaper'].set_active_id(str(self._tg('misc','force_default_wallpaper',0)))
        f.pack_start(self.create_row("Force Default Wallpaper", self.widgets['force_default_wallpaper']), False, False, 0)
        self.widgets['disable_logo'] = Gtk.Switch(); self.widgets['disable_logo'].set_active(self._tg('misc','disable_hyprland_logo',True)); f.pack_start(self.create_row("Disable Startup Logo", self.widgets['disable_logo']), False, False, 0)
        self.widgets['disable_splash'] = Gtk.Switch(); self.widgets['disable_splash'].set_active(self._tg('misc','disable_splash_rendering',True)); f.pack_start(self.create_row("Disable Splash Text", self.widgets['disable_splash']), False, False, 0)
        v.pack_start(f, False, False, 0); return v

    def build_layouts(self):
        v = self.build_page_vbox("Layout Tuning")
        f1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f1.get_style_context().add_class("group-frame")
        lbl1 = Gtk.Label(label="Dwindle"); lbl1.set_xalign(0); lbl1.set_margin_bottom(6); f1.pack_start(lbl1, False, False, 0)
        self.widgets['dwindle_preserve_split'] = Gtk.Switch(); self.widgets['dwindle_preserve_split'].set_active(self._tg('dwindle','preserve_split',True)); f1.pack_start(self.create_row("Preserve Split", self.widgets['dwindle_preserve_split']), False, False, 0)
        v.pack_start(f1, False, False, 0)
        f2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f2.get_style_context().add_class("group-frame")
        lbl2 = Gtk.Label(label="Master"); lbl2.set_xalign(0); lbl2.set_margin_bottom(6); f2.pack_start(lbl2, False, False, 0)
        self.widgets['master_new_status'] = Gtk.ComboBoxText()
        for vv in ["master", "slave"]: self.widgets['master_new_status'].append(vv, vv.capitalize())
        self.widgets['master_new_status'].set_active_id(self._tg('master','new_status','master'))
        f2.pack_start(self.create_row("New Window Status", self.widgets['master_new_status']), False, False, 0)
        v.pack_start(f2, False, False, 0); return v

    def build_plugins(self):
        v = self.build_page_vbox("Extensions")
        f, self.widgets['plugin_list'] = self.build_dynamic_list(self.doc['plugins'].get('enabled', []), "Active Plugins (hyprpm names)")
        v.pack_start(f, False, False, 0); return v

    def build_custom_lua(self):
        v = self.build_page_vbox("Custom Lua Lines")
        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")
        lbl = Gtk.Label(label="Raw Lua injected before reload. One statement per line."); lbl.set_xalign(0); lbl.set_opacity(0.6); lbl.set_line_wrap(True)
        f.pack_start(lbl, False, False, 8)
        buffer = Gtk.TextBuffer()
        lua_lines = self._tg('custom','lua_lines',[])
        buffer.set_text("\n".join(lua_lines))
        tv = Gtk.TextView.new_with_buffer(buffer); tv.set_wrap_mode(Gtk.WrapMode.WORD); tv.set_size_request(-1, 200)
        sw = Gtk.ScrolledWindow(); sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC); sw.add(tv)
        f.pack_start(sw, True, True, 0)
        self.widgets['custom_lua_buffer'] = buffer
        v.pack_start(f, True, True, 0); return v

    def on_sidebar_row_activated(self, lb, row):
        if hasattr(row, 'row_name'):
            self.stack.set_visible_child_name(row.row_name)

    # --- SEARCH ---
    def _build_search_index(self):
        """Auto-index every page: label text -> setting row widget.

        Walks each page's widget tree once. A label counts as a setting row
        when it sits directly in a horizontal box (legacy rows, list titles)
        or in the vertical text cell of a create_row() hbox (title + second-line
        description both index to the same row). Stays in sync automatically
        when pages gain options."""
        self._search_index = {}
        for row in self.sidebar.get_children():
            if getattr(row, 'is_group_label', False) or not hasattr(row, 'row_name'):
                continue
            page = self.stack.get_child_by_name(row.row_name)
            if page is None:
                continue
            entries = []

            def walk(w):
                if isinstance(w, Gtk.Label):
                    t = (w.get_text() or "").strip()
                    p = w.get_parent()
                    target = None
                    if t and isinstance(p, Gtk.Box):
                        if p.get_orientation() == Gtk.Orientation.HORIZONTAL:
                            target = p
                        else:
                            gp = p.get_parent()
                            if (isinstance(gp, Gtk.Box)
                                    and gp.get_orientation() == Gtk.Orientation.HORIZONTAL):
                                target = gp
                    if target is not None and (t, id(target)) not in seen_pairs:
                        seen_pairs.add((t, id(target)))
                        entries.append((t, target))
                if isinstance(w, Gtk.Container):
                    try:
                        children = w.get_children()
                    except Exception:
                        children = []
                    for ch in children:
                        walk(ch)

            seen_pairs = set()
            walk(page)
            self._search_index[row.row_name] = entries

    def _row_matches(self, name, title, q):
        if q in title.lower():
            return True, title
        for label_text, _w in self._search_index.get(name, []):
            if q in label_text.lower():
                return True, label_text
        return False, None

    def _sidebar_filter_func(self, row, _data):
        q = (self.search_entry.get_text() or "").strip().lower()
        if not q:
            return True
        if getattr(row, 'is_group_label', False):
            for r in self.sidebar.get_children():
                if getattr(r, 'is_group_label', False) or not hasattr(r, 'row_name'):
                    continue
                if getattr(r, 'page_group', None) == row.group_label:
                    ok, _ = self._row_matches(r.row_name, r.page_title, q)
                    if ok:
                        return True
            return False
        if hasattr(row, 'row_name'):
            ok, _ = self._row_matches(row.row_name, row.page_title, q)
            return ok
        return True

    def _current_matches(self):
        q = (self.search_entry.get_text() or "").strip().lower()
        if not q:
            return []
        out = []
        for r in self.sidebar.get_children():
            if getattr(r, 'is_group_label', False) or not hasattr(r, 'row_name'):
                continue
            ok, anchor = self._row_matches(r.row_name, r.page_title, q)
            if ok:
                out.append((r, anchor))
        return out

    def on_search_changed(self, entry):
        self.sidebar.invalidate_filter()

    def on_search_activate(self, entry):
        """Enter: jump to the top match and flash the matched setting row."""
        matches = self._current_matches()
        if not matches:
            return
        row, anchor = matches[0]
        self.sidebar.select_row(row)
        self.stack.set_visible_child_name(row.row_name)
        self._highlight_anchor(row.row_name, anchor)

    def _highlight_anchor(self, page_name, anchor):
        if not anchor:
            return
        target = None
        for label_text, w in self._search_index.get(page_name, []):
            if anchor.lower() in label_text.lower():
                target = w
                break
        if target is None:
            return
        self.reveal_widget(page_name, target)

    # --- IN-PAGE ANCHORS ---
    def reveal_widget(self, page_name, target, flash=True):
        """Scroll a page so `target` is visible, optionally flashing it."""
        if target is None:
            return
        try:
            if self.stack.get_visible_child_name() != page_name:
                self.stack.set_visible_child_name(page_name)
        except Exception:
            pass
        if flash:
            ctx = target.get_style_context()
            ctx.add_class("search-highlight")
            GLib.timeout_add(1600, lambda: ctx.remove_class("search-highlight") or False)

        def _scroll():
            try:
                page = self.stack.get_child_by_name(page_name)
                y = target.translate_coordinates(page, 0, 0)[-1]
                adj = self.stack_scroll.get_vadjustment()
                adj.set_value(max(0, min(y - adj.get_page_size() / 2,
                                         adj.get_upper() - adj.get_page_size())))
            except Exception as e:
                logger.warning(f"Reveal scroll failed: {e}")
            return False

        GLib.idle_add(_scroll)

    def _anchor_bar(self, page_name, targets):
        """Compact jump-link bar: [(button label, widget), ...]."""
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for label, target in targets:
            b = Gtk.Button(label=label)
            b.get_style_context().add_class("anchor-btn")
            b.set_tooltip_text(f"Jump to {label}")
            b.connect("clicked", lambda _x, t=target: self.reveal_widget(page_name, t))
            bar.pack_start(b, False, False, 0)
        bar.show_all()
        return bar

    def on_save_clicked(self, btn):
        """Apply settings without freezing the UI or closing the window.

        Widget reads + TOML assembly run on the main thread (fast), then a
        daemon worker thread runs the slow part (file writes, build_config,
        wallpaper/theme scripts, dock restart). Status is reported inline
        and via notify-send; the window stays open for further tweaks.
        """
        if getattr(self, '_applying', False):
            return
        self.status_label.get_style_context().remove_class("error")
        bind_errors = self.validate_binds()
        if bind_errors:
            msg = "; ".join(bind_errors[:4])
            if len(bind_errors) > 4:
                msg += f" (+{len(bind_errors) - 4} more)"
            logger.error(f"Bind validation failed: {msg}")
            self.status_label.set_text(f"⚠ Invalid binds: {msg}")
            self.status_label.get_style_context().add_class("error")
            try:
                subprocess.run(["notify-send", "-t", "5000", "HyprDE Settings",
                                f"Invalid binds: {msg}"],
                               capture_output=True, timeout=5)
            except Exception:
                pass
            return
        try:
            snapshot = self._collect_widget_state()
        except Exception as e:
            logger.error(f"Settings collect failed: {e}\n{traceback.format_exc()}")
            self.status_label.set_text(f"⚠ Error: {str(e)}")
            self.status_label.get_style_context().add_class("error")
            return

        if snapshot["config_str"] == self.initial_config_str:
            self.status_label.set_text("No changes to apply")
            return

        self._begin_apply(snapshot)

    def _begin_apply(self, snapshot, light=False):
        """Kick off the background worker. Light applies (instant-apply path)
        only write the file, rebuild and reload — heavy fan-out (theme
        scripts, dock/bar restarts, wallpaper engine) is manual-Apply only,
        otherwise every slider tick would churn the whole session."""
        snapshot["light"] = light
        self._applying = True
        self.save_btn.set_label("Applying…")
        self.save_btn.set_sensitive(False)
        self.status_label.set_text("Applying settings…")
        threading.Thread(target=self._apply_worker, args=(snapshot,),
                         daemon=True).start()

    # --- INSTANT-APPLY (lightweight widgets only) ---
    def _track_live_apply(self):
        """Debounced live-apply for whitelisted widgets (no Apply press needed)."""
        self._live_apply_id = None
        for key in LIVE_SAFE_WIDGETS:
            w = self.widgets.get(key)
            if w is None:
                continue
            if isinstance(w, Gtk.Entry):
                w.connect("changed", lambda *_a: self._schedule_live_apply())
            elif isinstance(w, (Gtk.SpinButton, Gtk.Scale)):
                w.connect("value-changed", lambda *_a: self._schedule_live_apply())
            elif isinstance(w, Gtk.Switch):
                w.connect("notify::active", lambda *_a: self._schedule_live_apply())
            elif isinstance(w, Gtk.ComboBoxText):
                w.connect("changed", lambda *_a: self._schedule_live_apply())

    def _schedule_live_apply(self):
        if getattr(self, '_restoring', False) or getattr(self, '_closed', False):
            return
        if getattr(self, '_live_apply_id', None) is not None:
            GLib.source_remove(self._live_apply_id)
            self._live_apply_id = None
        # While an apply is running, re-arm instead of dropping the change.
        delay = 1000 if getattr(self, '_applying', False) else LIVE_APPLY_DEBOUNCE_MS
        self._live_apply_id = GLib.timeout_add(delay, self._maybe_live_apply)

    def _maybe_live_apply(self):
        self._live_apply_id = None
        if getattr(self, '_closed', False):
            return False
        if getattr(self, '_applying', False) or getattr(self, '_restoring', False):
            return False
        try:
            snapshot = self._collect_widget_state()
        except Exception:
            return False
        changed = set(snapshot.get("changed", []))
        if not changed:
            return False
        # Anything outside the safe sections (binds, lua text, monitors,
        # autostart, ...) forces manual Apply — never auto-apply half-typed input.
        if changed - LIVE_SAFE_SECTIONS:
            return False
        if snapshot["config_str"] == self.initial_config_str:
            return False
        self._begin_apply(snapshot, light=True)
        return False

    def _collect_widget_state(self):
        """Read all widgets into self.doc (main thread) and snapshot what's
        needed for the background apply. Returns a plain-data dict."""
        def get_items(container):
            return [c.get_children()[0].get_text() for c in container.get_children() if c.get_children()[0].get_text().strip()]

        # General / Decoration
        for k in ['gaps_in','gaps_out','border_size']: self.doc['general'][k] = int(self.widgets[k].get_value())
        for k in ['rounding','active_opacity','inactive_opacity','waybar_opacity','launcher_opacity']:
            self.doc['decoration'][k] = self.widgets[k].get_value() if 'opacity' in k else int(self.widgets[k].get_value())
        self.doc['general']['layout'] = self.widgets['layout'].get_active_id()
        self.doc['general']['resize_on_border'] = self.widgets['resize_on_border'].get_active()
        self.doc['general']['allow_tearing'] = self.widgets['allow_tearing'].get_active()

        # Blur
        if 'decoration.blur' not in self.doc and 'decoration' in self.doc:
            self.doc['decoration']['blur'] = tomlkit.table()
        self.doc['decoration']['blur']['enabled'] = self.widgets['blur_enabled'].get_active()
        self.doc['decoration']['blur']['size'] = int(self.widgets['blur_size'].get_value())
        self.doc['decoration']['blur']['passes'] = int(self.widgets['blur_passes'].get_value())

        # Border colors
        self.doc['general']['col_active_border'] = self.widgets['col_active_border'].get_text()
        self.doc['general']['col_inactive_border'] = self.widgets['col_inactive_border'].get_text()

        # Theme
        if 'theme' not in self.doc: self.doc['theme'] = tomlkit.table()
        new_mode = self.widgets['theme_mode'].get_active_id()
        self.doc['theme']['mode'] = new_mode
        self.doc['theme']['accent'] = self._tg('theme', 'accent', '#007aff')

        # Accent-follow for the active window border: when the accent changed
        # in this Apply and the user did not hand-edit the border field,
        # re-derive the gradient's first stop from the accent (alpha ee),
        # preserving the rest of a custom gradient. Hyprland chrome then
        # stays in the same family as every other component.
        old_acc_m = re.search(r'accent\s*=\s*"([^"]+)"',
                              self._initial_sections.get('theme', ''))
        old_acc = old_acc_m.group(1) if old_acc_m else None
        new_acc = self.doc['theme'].get('accent')
        base_m = re.search(r'col_active_border\s*=\s*"([^"]+)"',
                           self._initial_sections.get('general', ''))
        base_border = base_m.group(1) if base_m else None
        cur_border = self.widgets['col_active_border'].get_text()
        if (new_acc and old_acc and new_acc != old_acc
                and base_border and cur_border == base_border):
            first, _, rest = base_border.partition(' ')
            new_first = 'rgba(%see)' % self._accent_to_hex(new_acc)
            new_border = (new_first + ' ' + rest).strip()
            self.doc['general']['col_active_border'] = new_border
            self.widgets['col_active_border'].set_text(new_border)

        # Lockscreen
        self.doc['lockscreen']['profile_image'] = self.widgets['profile_path'].get_text()
        self.doc['lockscreen']['background'] = self.widgets['lock_wp_path'].get_text()
        self.doc['lockscreen']['blur_passes'] = int(self.widgets['lock_blur_passes'].get_value())
        self.doc['lockscreen']['blur_size'] = int(self.widgets['lock_blur_size'].get_value())
        self.doc['lockscreen']['fail_text'] = self.widgets['lock_fail_text'].get_text()
        self.doc['lockscreen']['placeholder_text'] = self.widgets['lock_placeholder_text'].get_text()

        # Idle
        for k in ['lock_timeout','screen_off_timeout','suspend_timeout']:
            self.doc['idle'][k] = int(self.widgets[f'idle_{k}'].get_value())

        # Nightlight
        self.doc['nightlight']['enabled'] = self.widgets['nl_enabled'].get_active()
        self.doc['nightlight']['temp_day'] = int(self.widgets['nl_temp_day'].get_value())
        self.doc['nightlight']['temp_night'] = int(self.widgets['nl_temp_night'].get_value())

        # Wallpapers
        self.doc['wallpapers']['fixed']['image'] = self.widgets['wp_image_path'].get_text()
        self.doc['wallpapers']['path'] = self.widgets['wp_dir_path'].get_text()
        self.doc['wallpapers']['mode'] = self.widgets['wp_mode'].get_active_id()

        # Monitors
        mlist = get_items(self.widgets['monitor_list'])
        scale = self.widgets['monitor_scale'].get_active_id() or "1.0"
        if mlist:
            for i in range(len(mlist)):
                parts = [p.strip() for p in mlist[i].split(',')]
                if len(parts) >= 3:
                    while len(parts) < 4: parts.append("1.0")
                    parts[3] = scale
                    mlist[i] = ", ".join(parts)
        self.doc['monitors']['rules'] = mlist
        self.doc['binds']['normal']['list'] = self.get_bind_items(self.widgets['bind_list'])
        self.doc['binds']['mainMod'] = self.widgets['mainMod'].get_active_id()
        # Ensure all bind subsections exist
        for sub in ['release','mouse','repeat','locked']:
            lblist = self.get_bind_items(self.widgets[f'bind_{sub}_list'])
            if sub not in self.doc['binds']: self.doc['binds'][sub] = tomlkit.table()
            self.doc['binds'][sub]['list'] = lblist
        self.doc['plugins']['enabled'] = get_items(self.widgets['plugin_list'])

        # Gestures
        gl = get_items(self.widgets['gesture_list'])
        if 'gesture' not in self.doc: self.doc['gesture'] = tomlkit.table()
        self.doc['gesture']['list'] = gl

        # Autostart
        al = get_items(self.widgets['autostart_list'])
        if 'autostart' not in self.doc: self.doc['autostart'] = tomlkit.table()
        self.doc['autostart']['exec_once'] = al

        # Hyprrocket event bus
        if 'hyprrocket' not in self.doc: self.doc['hyprrocket'] = tomlkit.table()
        self.doc['hyprrocket']['enabled'] = self.widgets['rocket_enabled'].get_active()
        
        events_table = tomlkit.table()
        for ui_obj in self.widgets.get('rocket_events_list', []):
            name = ui_obj['name']
            ev_table = tomlkit.table()
            ev_table['trigger'] = ui_obj['trig'].get_text().strip()
            days_val = ui_obj['days'].get_text().strip()
            if days_val:
                ev_table['days'] = days_val
            ev_table['enabled'] = ui_obj['on'].get_active()
            
            buf = ui_obj['actions'].get_buffer()
            text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
            actions = [line.strip() for line in text.split('\n') if line.strip()]
            
            arr = tomlkit.array()
            for a in actions: arr.append(a)
            if actions: arr.multiline(True)
            ev_table['actions'] = arr
            
            events_table[name] = ev_table
            
        self.doc['hyprrocket']['events'] = events_table

        # Environment
        el = get_items(self.widgets['env_list'])
        if 'env' not in self.doc: self.doc['env'] = tomlkit.table()
        self.doc['env']['vars'] = el

        # Animations
        for k in ['windows','windowsOut','border','fade','workspaces']:
            self.doc['animations'][k] = self.widgets[f'anim_{k}'].get_text()
        self.doc['animations']['enabled'] = self.widgets['anim_enabled'].get_active()

        # Input
        for k in ['kb_layout','kb_variant','kb_model','kb_rules']:
            self.doc['input'][k] = self.widgets[k].get_text()
            
        adv_opts = self.widgets['kb_options'].get_text()
        caps_opt = self.widgets['caps_behavior'].get_active_id() or ""
        
        # Remove existing caps options from adv_opts string
        adv_opts = re.sub(r'ctrl:nocaps|caps:escape|caps:swapescape', '', adv_opts)
        adv_opts = ','.join(filter(bool, [x.strip() for x in adv_opts.split(',')]))
        
        final_opts = f"{caps_opt},{adv_opts}" if caps_opt and adv_opts else (caps_opt or adv_opts)
        self.doc['input']['kb_options'] = final_opts
        
        if 'input' not in self.doc: self.doc['input'] = tomlkit.table()
        if 'touchpad' not in self.doc['input']: self.doc['input']['touchpad'] = tomlkit.table()
        self.doc['input']['touchpad']['natural_scroll'] = self.widgets['natural_scroll'].get_active()

        # Mouse
        self.doc['input']['follow_mouse'] = int(self.widgets['follow_mouse'].get_active_id())
        self.doc['input']['sensitivity'] = self.widgets['sensitivity'].get_value()

        # Launcher
        self.doc['launcher']['position'] = self.widgets['l_pos'].get_active_id()
        self.doc['launcher']['width_percent'] = int(self.widgets['l_width'].get_value())
        self.doc['launcher']['margin_top'] = int(self.widgets['l_margin'].get_value())
        self.doc['launcher']['font_size'] = int(self.widgets['l_font'].get_value())
        self.doc['launcher']['icon_size'] = int(self.widgets['l_icon'].get_value())
        self.doc['launcher']['row_spacing'] = int(self.widgets['l_spacing'].get_value())

        # Launcher sub-modes
        for mode_key in ["drun", "power_menu", "dmenu"]:
            if mode_key not in self.doc['launcher']: self.doc['launcher'][mode_key] = tomlkit.table()
            self.doc['launcher'][mode_key]['width_percent'] = int(self.widgets[f'l_{mode_key}_width'].get_value())
            self.doc['launcher'][mode_key]['position'] = self.widgets[f'l_{mode_key}_pos'].get_active_id()
            self.doc['launcher'][mode_key]['margin_top'] = int(self.widgets[f'l_{mode_key}_margin'].get_value())

        # Dock
        self.doc['launcher']['dock']['enabled'] = self.widgets['dock_enabled'].get_active()
        self.doc['launcher']['dock']['position'] = self.widgets['dock_pos'].get_active_id()
        self.doc['launcher']['dock']['autohide'] = self.widgets['dock_autohide'].get_active()
        self.doc['launcher']['dock']['icon_size'] = int(self.widgets['dock_icon_size'].get_value())
        self.doc['launcher']['dock']['padding'] = int(self.widgets['dock_padding'].get_value())
        self.doc['launcher']['dock']['rounding'] = int(self.widgets['dock_rounding'].get_value())
        self.doc['launcher']['dock']['margin'] = int(self.widgets['dock_margin'].get_value())
        self.doc['launcher']['dock']['apps'] = get_items(self.widgets['dock_apps_list'])

        # Programs
        for k in ["terminal", "fileManager", "status_bar", "launcher", "notification_service"]:
            self.doc['programs'][k] = self.widgets[k].get_text()
        self.doc['programs']['autohide_bar'] = self.widgets['autohide_bar'].get_active()

        # Scrolling
        if 'scrolling' not in self.doc: self.doc['scrolling'] = tomlkit.table()
        self.doc['scrolling']['column_width'] = self.widgets['scroll_column_width'].get_value()
        self.doc['scrolling']['fullscreen_on_one_column'] = self.widgets['scroll_fullscreen'].get_active()
        self.doc['scrolling']['focus_fit_method'] = int(self.widgets['scroll_focus_fit'].get_active_id())
        self.doc['scrolling']['explicit_column_widths'] = self.widgets['scroll_explicit_widths'].get_text()

        # Window rules
        wr = get_items(self.widgets['window_rules_list'])
        if 'rules' not in self.doc: self.doc['rules'] = tomlkit.table()
        self.doc['rules']['window'] = wr

        # Display flags
        if 'misc' not in self.doc: self.doc['misc'] = tomlkit.table()
        self.doc['misc']['force_default_wallpaper'] = int(self.widgets['force_default_wallpaper'].get_active_id())
        self.doc['misc']['disable_hyprland_logo'] = self.widgets['disable_logo'].get_active()
        self.doc['misc']['disable_splash_rendering'] = self.widgets['disable_splash'].get_active()

        # Layouts
        if 'dwindle' not in self.doc: self.doc['dwindle'] = tomlkit.table()
        self.doc['dwindle']['preserve_split'] = self.widgets['dwindle_preserve_split'].get_active()
        if 'master' not in self.doc: self.doc['master'] = tomlkit.table()
        self.doc['master']['new_status'] = self.widgets['master_new_status'].get_active_id()

        # Custom Lua
        buffer = self.widgets['custom_lua_buffer']
        lua_text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        lua_lines = [l for l in lua_text.split("\n") if l.strip()]
        if 'custom' not in self.doc: self.doc['custom'] = tomlkit.table()
        self.doc['custom']['lua_lines'] = lua_lines

        # Snapshot everything the background worker needs (plain data only —
        # the worker thread must never touch Gtk widgets).
        changed = sorted(
            k for k, v in self.doc.items()
            if tomlkit.dumps(v) != self._initial_sections.get(k)
        )
        return {
            "config_str": tomlkit.dumps(self.doc),
            "sections": {k: tomlkit.dumps(v) for k, v in self.doc.items()},
            "changed": changed,
            "new_mode": self.widgets['theme_mode'].get_active_id(),
            "dock_enabled": self.widgets['dock_enabled'].get_active(),
            "accent_hex": self._tg('theme', 'accent', '#007aff'),
        }

    def _apply_worker(self, snapshot):
        """Slow apply step: file writes, rebuild, scripts (background thread).

        Only the side effects relevant to `snapshot["changed"]` run, so
        Apply never stomps unrelated live state (wallpaper engine, theme,
        dock) when e.g. only keybinds changed.
        """
        # Sections emitted into hyprland.lua (need build + reload when changed).
        LUA_SECTIONS = {
            "monitors", "programs", "autostart", "nightlight", "plugins",
            "plugin", "scrolling", "gesture", "submaps", "env", "input",
            "general", "decoration", "animations", "dwindle", "master",
            "misc", "binds", "binds_config", "rules", "custom", "color",
            "group", "cursor", "render", "ecosystem", "debug", "devices",
            "permission", "permissions",
        }
        changed = set(snapshot.get("changed", []))
        light = snapshot.get("light", False)
        # Be conservative: if change detection failed, run everything.
        if not changed:
            changed = LUA_SECTIONS | {"wallpapers", "lockscreen", "idle",
                                      "theme", "launcher", "programs"}
            light = False
        try:
            with open(self.config_path, 'w') as f:
                f.write(snapshot["config_str"])

            if light:
                # Instant-apply path: file + rebuild + reload only. Heavy
                # fan-out stays manual so slider drags can't churn the session.
                subprocess.run(["python3", os.path.expanduser("~/.config/hypr/build_config.py")],
                               capture_output=True, timeout=120)
                if changed & LUA_SECTIONS:
                    subprocess.run(["hyprctl", "reload"], capture_output=True, timeout=30)
                logger.info("Settings live-applied (sections: %s)",
                            ",".join(sorted(changed)))
                GLib.idle_add(self._on_apply_done, snapshot["config_str"],
                              snapshot["sections"])
                return

            # Fan out the accent color to every component (theme CSS vars,
            # wofi selection, notif borders, Mako). Non-fatal on failure.
            accent_rc = subprocess.run(
                ["sh", os.path.expanduser("~/.config/hypr/scripts/apply-accent.sh"),
                 snapshot["accent_hex"]],
                capture_output=True, timeout=30)
            if accent_rc.returncode != 0:
                logger.warning(
                    "apply-accent.sh failed: %s",
                    accent_rc.stderr.decode(errors="replace")[:300])

            # Update current.css symlink to match mode
            themes_dir = os.path.expanduser("~/.config/hypr/themes")
            current_link = os.path.join(themes_dir, "current.css")
            want = "light.css" if snapshot["new_mode"] == "light" else "dark.css"
            try:
                if os.path.islink(current_link) and os.readlink(current_link) != want:
                    os.symlink(want, current_link + ".tmp")
                    os.replace(current_link + ".tmp", current_link)
                elif not os.path.islink(current_link):
                    if os.path.lexists(current_link):
                        os.remove(current_link)
                    os.symlink(want, current_link)
            except OSError as e:
                logger.warning(f"Theme symlink update failed: {e}")

            subprocess.run(["python3", os.path.expanduser("~/.config/hypr/build_config.py")],
                           capture_output=True, timeout=120)

            # Reload Hyprland so the rebuilt hyprland.lua takes effect live,
            # but only when a Lua-emitted section actually changed. Without
            # this, Apply updates files but the running session keeps old
            # values (e.g. gaps, borders, opacity, layout).
            if changed & LUA_SECTIONS:
                subprocess.run(["hyprctl", "reload"], capture_output=True, timeout=30)

            # Wallpaper engine only when [wallpapers] changed — restarting it
            # otherwise snaps a manually-picked wallpaper back to the TOML one.
            if "wallpapers" in changed:
                subprocess.run(["sh", os.path.expanduser("~/.config/hypr/scripts/init_wallpaper.sh")],
                               capture_output=True, timeout=120)

            # Theme stack only when theme/appearance-affecting sections changed.
            if changed & {"theme", "appearance", "general", "decoration"}:
                subprocess.run([
                    "sh", os.path.expanduser("~/.config/hypr/scripts/theme-ctrl.sh"),
                    snapshot["new_mode"]
                ], capture_output=True, timeout=120)

            # Dock + bar only when launcher/programs/theme/decoration changed.
            if changed & {"launcher", "programs", "theme", "decoration"}:
                subprocess.run(["pkill", "-f", "hyprsearch --dock"], capture_output=True)
                subprocess.run(["pkill", "-USR2", "waybar"], capture_output=True)
                time.sleep(0.5)
                if snapshot["dock_enabled"]:
                    subprocess.Popen([os.path.expanduser("~/.config/hypr/scripts/hyprsearch"), "--dock"],
                                     start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["notify-send", "Settings Applied", "System updated."],
                           capture_output=True, timeout=5)
            logger.info("Settings applied successfully (sections: %s)",
                        ",".join(sorted(changed)))
            GLib.idle_add(self._on_apply_done, snapshot["config_str"],
                          snapshot["sections"])
        except Exception as e:
            logger.error(f"Settings apply failed: {e}\n{traceback.format_exc()}")
            GLib.idle_add(self._on_apply_error, str(e))

    def _on_apply_done(self, config_str, sections):
        """Main-thread callback: report success, stay open for more tweaks."""
        self.initial_config_str = config_str
        self._initial_sections = dict(sections)
        self._applying = False
        self.save_btn.set_label("Apply")
        self.save_btn.set_sensitive(True)
        self._mark_clean()
        self.status_label.get_style_context().remove_class("error")
        self.status_label.set_text("✓ Settings applied")
        try:
            subprocess.run(["notify-send", "-t", "2500", "HyprDE Settings",
                            "✓ Settings applied"],
                           capture_output=True, timeout=5)
        except Exception:
            pass
        GLib.timeout_add(4000, self._clear_status)
        return False

    def _clear_status(self):
        if self.status_label.get_text() == "✓ Settings applied":
            self.status_label.set_text("")
        return False

    def _on_apply_error(self, message):
        """Main-thread callback: report failure inline, stay open."""
        self._applying = False
        self.save_btn.set_label("Apply")
        self.save_btn.set_sensitive(True)
        self.status_label.set_text(f"⚠ Error: {message}")
        self.status_label.get_style_context().add_class("error")
        _notify_error("HyprDE Settings", f"Apply failed: {message}")
        return False

    def on_key_press(self, widget, event):
        # Single canonical key handler (one definition only — do not duplicate).
        # Press-to-capture for the guided keybind editor pre-empts everything.
        if getattr(self, '_key_capture', None) is not None:
            return self._finish_key_capture(event)
        if event.keyval == Gdk.KEY_Escape:
            if (getattr(self, 'search_entry', None) is not None
                    and self.search_entry.has_focus()
                    and self.search_entry.get_text()):
                self.search_entry.set_text("")
                return True
            self.close_window()
            return True
        elif event.keyval in [Gdk.KEY_Return, Gdk.KEY_KP_Enter]:
            if self.sidebar.has_focus():
                row = self.sidebar.get_selected_row()
                if row:
                    self.sidebar.row_activated(row)
                    return True
        elif event.keyval == Gdk.KEY_Right:
            if self.sidebar.has_focus():
                self.stack_scroll.child_focus(Gtk.DirectionType.TAB_FORWARD)
                return True
        elif event.keyval == Gdk.KEY_Left:
            if not self.sidebar.has_focus():
                self.sidebar.grab_focus()
                return True
        # Catch CTRL+F: focus search
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            if event.keyval in [Gdk.KEY_f, Gdk.KEY_F]:
                if getattr(self, 'search_entry', None) is not None:
                    self.search_entry.grab_focus()
                    return True
        # Catch SUPER+Q, SUPER+C, CTRL+Q, CTRL+C
        if event.state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SUPER_MASK):
            if event.keyval in [Gdk.KEY_q, Gdk.KEY_Q, Gdk.KEY_c, Gdk.KEY_C]:
                self.close_window()
                return True
        return False

if __name__ == "__main__":
    logger.info(f"SettingsManager starting (pid={os.getpid()})")
    try:
        check_single_instance()
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"Single-instance check failed: {e}")
        _notify_error("HyprDE Settings", f"Startup failed: {e}")
        sys.exit(1)
    try:
        win = SettingsManager()
    except Exception as e:
        logger.error(f"Settings startup failed: {e}\n{traceback.format_exc()}")
        _notify_error("HyprDE Settings",
                      f"Failed to open: {e}. See {LOG_FILE}")
        cleanup_lock()
        sys.exit(1)
    try:
        Gtk.main()
    except Exception as e:
        logger.error(f"Gtk.main failed: {e}\n{traceback.format_exc()}")
    finally:
        cleanup_lock()
