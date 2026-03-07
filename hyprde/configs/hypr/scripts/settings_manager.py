#!/usr/bin/env python3
import sys
import os
import gi
import subprocess
import tomlkit
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GtkLayerShell, Gio, GLib, Pango

def get_theme_colors():
    theme_path = os.path.expanduser("~/.config/hypr/themes/current.css")
    # Robust high-contrast defaults
    colors = {
        "bg": "rgba(30, 30, 35, 0.96)",
        "fg": "#ffffff",
        "fg_dim": "rgba(255, 255, 255, 0.7)",
        "entry_bg": "rgba(255, 255, 255, 0.08)",
        "sel_bg": "#33ccff",
        "sel_fg": "#000000",
        "border": "rgba(255, 255, 255, 0.15)",
        "accent": "#33ccff"
    }
    
    if os.path.exists(theme_path):
        try:
            with open(theme_path, 'r') as f:
                content = f.read()
                import re
                def find_color(var):
                    m = re.search(f"{var}\\s+([^;]+);", content)
                    return m.group(1).strip() if m else None
                
                colors["bg"] = find_color("theme_wofi_bg_alpha") or colors["bg"]
                colors["fg"] = find_color("theme_wofi_fg") or colors["fg"]
                colors["sel_bg"] = find_color("theme_wofi_sel_bg") or colors["sel_bg"]
                colors["sel_fg"] = find_color("theme_wofi_sel_fg") or colors["sel_fg"]
                colors["accent"] = colors["sel_bg"]
                
                if "light" in content.lower():
                    colors["fg_dim"] = "rgba(0, 0, 0, 0.6)"
                    colors["entry_bg"] = "rgba(0, 0, 0, 0.06)"
                    colors["border"] = "rgba(0, 0, 0, 0.15)"
                else:
                    colors["fg_dim"] = "rgba(255, 255, 255, 0.6)"
                    colors["entry_bg"] = "rgba(255, 255, 255, 0.08)"
                    colors["border"] = "rgba(255, 255, 255, 0.15)"
        except:
            pass
    return colors

class SettingsManager(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.config_path = os.path.expanduser("~/.config/hypr/hyprde.toml")
        self.load_config()
        
        # Setup Layer Shell
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "hyprde-settings")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)

        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self.on_key_press)

        # 1. Outer Background (Click to close)
        bg_event_box = Gtk.EventBox()
        bg_event_box.connect("button-press-event", lambda w, e: sys.exit(0))
        self.add(bg_event_box)
        
        overlay = Gtk.Overlay()
        bg_event_box.add(overlay)
        
        # 2. Main Container (Catch clicks)
        self.click_catcher = Gtk.EventBox()
        self.click_catcher.set_halign(Gtk.Align.CENTER)
        self.click_catcher.set_valign(Gtk.Align.CENTER)
        self.click_catcher.connect("button-press-event", lambda w, e: True) # Stop propagation
        overlay.add(self.click_catcher)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.main_box.set_name("main-window")
        self.click_catcher.add(self.main_box)
        
        # Size
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        if monitor:
            geo = monitor.get_geometry()
            self.main_box.set_size_request(int(geo.width * 0.55), int(geo.height * 0.65))
        else:
            self.main_box.set_size_request(1000, 750)
        
        # Title Bar
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title_box.set_margin_top(20)
        title_box.set_margin_bottom(10)
        title_box.set_margin_start(25)
        title_box.set_margin_end(25)
        
        title_label = Gtk.Label(label="HyprDE Settings")
        title_label.set_name("title-label")
        title_box.pack_start(title_label, False, False, 0)
        
        spacer = Gtk.Box()
        title_box.pack_start(spacer, True, True, 0)
        
        close_btn = Gtk.Button(label="✕")
        close_btn.set_name("close-button")
        close_btn.connect("clicked", lambda x: sys.exit(0))
        title_box.pack_end(close_btn, False, False, 0)
        
        self.main_box.pack_start(title_box, False, False, 0)

        # Content Area
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.main_box.pack_start(content_box, True, True, 0)
        
        # Sidebar
        self.sidebar = Gtk.ListBox()
        self.sidebar.set_name("sidebar")
        self.sidebar.set_size_request(240, -1)
        self.sidebar.connect("row-activated", self.on_sidebar_row_activated)
        
        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.add(self.sidebar)
        content_box.pack_start(sidebar_scroll, False, False, 0)
        
        # Stack
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(250)
        
        self.stack_scroll = Gtk.ScrolledWindow()
        self.stack_scroll.set_name("content-scroll")
        self.stack_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.stack_scroll.add(self.stack)
        content_box.pack_start(self.stack_scroll, True, True, 0)
        
        # Bottom Bar
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bottom_box.set_margin_top(15)
        bottom_box.set_margin_bottom(15)
        bottom_box.set_margin_start(25)
        bottom_box.set_margin_end(25)
        
        self.status_label = Gtk.Label(label="")
        self.status_label.set_name("status-label")
        bottom_box.pack_start(self.status_label, False, False, 0)
        
        spacer2 = Gtk.Box()
        bottom_box.pack_start(spacer2, True, True, 0)
        
        self.save_btn = Gtk.Button(label="Apply Changes")
        self.save_btn.set_name("save-button")
        self.save_btn.connect("clicked", self.on_save_clicked)
        bottom_box.pack_end(self.save_btn, False, False, 0)
        
        self.main_box.pack_start(bottom_box, False, False, 0)
        
        self.apply_css()
        self.create_settings_pages()
        self.show_all()
        self.sidebar.grab_focus()

    def load_config(self):
        with open(self.config_path, 'r') as f:
            self.doc = tomlkit.load(f)

    def apply_css(self):
        c = get_theme_colors()
        css_data = f"""
        window {{ background-color: transparent; }}
        #main-window {{
            background-color: {c['bg']};
            border-radius: 20px;
            border: 1px solid {c['border']};
            color: {c['fg']};
        }}
        #title-label {{ font-size: 24px; font-weight: 800; color: {c['fg']}; }}
        #sidebar {{ background: rgba(0,0,0,0.15); padding: 15px; }}
        #sidebar row {{ 
            padding: 12px 15px; 
            border-radius: 10px; 
            margin-bottom: 5px; 
            color: {c['fg_dim']}; 
            font-weight: 600;
        }}
        #sidebar row:selected {{ background-color: {c['accent']}; color: {c['sel_fg']}; font-weight: 800; }}
        
        #close-button {{ background: transparent; border: none; font-size: 20px; color: {c['fg']}; opacity: 0.6; }}
        #close-button:hover {{ opacity: 1.0; color: #ff5f57; }}
        
        #save-button {{ 
            background-color: {c['accent']}; 
            color: {c['sel_fg']}; 
            font-weight: 800; 
            padding: 12px 30px; 
            border-radius: 12px; 
            border: none;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }}
        #save-button:hover {{ opacity: 0.95; box-shadow: 0 6px 18px rgba(0,0,0,0.4); }}
        
        #content-scroll {{ padding: 25px; }}
        label {{ color: {c['fg']}; font-weight: 600; }}
        .section-title {{ font-size: 20px; font-weight: 800; margin-bottom: 20px; color: {c['accent']}; }}
        .group-frame {{ 
            background: {c['entry_bg']}; 
            border-radius: 14px; 
            padding: 20px; 
            margin-bottom: 20px; 
            border: 1px solid {c['border']};
        }}
        
        entry, spinbutton {{ 
            background: rgba(0,0,0,0.3); 
            color: {c['fg']}; 
            border: 1px solid {c['border']}; 
            border-radius: 8px; 
            padding: 8px;
        }}
        
        scale slider {{ background: {c['accent']}; border-radius: 50%; min-height: 20px; min-width: 20px; }}
        switch:checked {{ background: {c['accent']}; }}
        scrollbar slider {{ background-color: rgba(255, 255, 255, 0.2); border-radius: 10px; }}
        """.encode()
        
        provider = Gtk.CssProvider()
        provider.load_from_data(css_data)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def create_row(self, label_text, widget):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        hbox.set_margin_bottom(12)
        label = Gtk.Label(label=label_text)
        label.set_xalign(0)
        hbox.pack_start(label, True, True, 0)
        hbox.pack_end(widget, False, False, 0)
        return hbox

    def add_sidebar_item(self, name, title, icon_name):
        row = Gtk.ListBoxRow()
        row.name = name
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        box.pack_start(icon, False, False, 0)
        box.pack_start(Gtk.Label(label=title), False, False, 0)
        row.add(box)
        self.sidebar.add(row)
        return row

    def create_settings_pages(self):
        self.widgets = {}
        pages = [
            ("appearance", "Appearance", "preferences-desktop-theme", self.build_appearance_page),
            ("wallpapers", "Wallpapers", "background", self.build_wallpapers_page),
            ("launcher", "Launcher & Dock", "start-here", self.build_launcher_page),
            ("lockscreen", "Lock & Power", "system-lock-screen", self.build_lock_page),
            ("nightlight", "Nightlight", "weather-clear-night", self.build_nightlight_page),
            ("input", "Input Devices", "input-keyboard", self.build_input_page),
            ("layout", "Layout & Tiling", "view-grid", self.build_layout_page),
            ("programs", "Default Apps", "applications-other", self.build_programs_page),
            ("system", "System", "emblem-system", self.build_system_page)
        ]
        for name, title, icon, builder in pages:
            self.add_sidebar_item(name, title, icon)
            self.stack.add_titled(builder(), name, title)

        self.sidebar.select_row(self.sidebar.get_row_at_index(0))
        self.stack.set_visible_child_name("appearance")

    def build_page_vbox(self, title_text):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        title = Gtk.Label(label=title_text)
        title.set_xalign(0)
        title.get_style_context().add_class("section-title")
        vbox.pack_start(title, False, False, 0)
        return vbox

    def build_appearance_page(self):
        vbox = self.build_page_vbox("Window & Desktop Appearance")
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        group.get_style_context().add_class("group-frame")
        
        for key, label, min_val, max_val in [
            ('gaps_in', 'Inner Gaps (px)', 0, 100),
            ('gaps_out', 'Outer Gaps (px)', 0, 200),
            ('border_size', 'Border Size (px)', 0, 20),
            ('rounding', 'Window Rounding', 0, 50)
        ]:
            self.widgets[key] = Gtk.SpinButton.new_with_range(min_val, max_val, 1)
            # Handle both 'general' and 'decoration' tables from TOML
            table = 'general' if 'gaps' in key or 'border' in key else 'decoration'
            self.widgets[key].set_value(self.doc[table].get(key, 0))
            group.pack_start(self.create_row(label, self.widgets[key]), False, False, 0)
        
        for key, label in [('active_opacity', 'Active Opacity'), ('inactive_opacity', 'Inactive Opacity')]:
            self.widgets[key] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.1, 1.0, 0.05)
            self.widgets[key].set_size_request(150, -1)
            self.widgets[key].set_value(self.doc['decoration'].get(key, 1.0))
            group.pack_start(self.create_row(label, self.widgets[key]), False, False, 0)

        vbox.pack_start(group, False, False, 0)
        return vbox

    def build_wallpapers_page(self):
        vbox = self.build_page_vbox("Wallpaper Management")
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        group.get_style_context().add_class("group-frame")
        
        self.widgets['wp_mode'] = Gtk.ComboBoxText()
        for m in ["fixed", "dynamic", "disabled"]: self.widgets['wp_mode'].append(m, m.capitalize())
        self.widgets['wp_mode'].set_active_id(self.doc['wallpapers'].get('mode', "fixed"))
        group.pack_start(self.create_row("Mode", self.widgets['wp_mode']), False, False, 0)
        
        self.widgets['wp_image'] = Gtk.Entry()
        self.widgets['wp_image'].set_width_chars(30)
        self.widgets['wp_image'].set_text(self.doc['wallpapers']['fixed'].get('image', ""))
        group.pack_start(self.create_row("Fixed Image Path", self.widgets['wp_image']), False, False, 0)
        
        self.widgets['wp_interval'] = Gtk.SpinButton.new_with_range(10, 3600, 60)
        self.widgets['wp_interval'].set_value(self.doc['wallpapers'].get('interval', 60))
        group.pack_start(self.create_row("Dynamic Interval (s)", self.widgets['wp_interval']), False, False, 0)
        
        vbox.pack_start(group, False, False, 0)
        return vbox

    def build_launcher_page(self):
        vbox = self.build_page_vbox("Launcher & Dock")
        l_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        l_group.get_style_context().add_class("group-frame")
        self.widgets['l_width'] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 20, 100, 1)
        self.widgets['l_width'].set_value(self.doc['launcher'].get('width_percent', 70))
        l_group.pack_start(self.create_row("Spotlight Width %", self.widgets['l_width']), False, False, 0)
        vbox.pack_start(l_group, False, False, 0)
        
        d_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        d_group.get_style_context().add_class("group-frame")
        self.widgets['dock_enabled'] = Gtk.Switch()
        self.widgets['dock_enabled'].set_active(self.doc['launcher']['dock'].get('enabled', True))
        d_group.pack_start(self.create_row("Enable Dock", self.widgets['dock_enabled']), False, False, 0)
        
        self.widgets['dock_size'] = Gtk.SpinButton.new_with_range(24, 128, 4)
        self.widgets['dock_size'].set_value(self.doc['launcher']['dock'].get('icon_size', 48))
        d_group.pack_start(self.create_row("Icon Size", self.widgets['dock_size']), False, False, 0)
        vbox.pack_start(d_group, False, False, 0)
        return vbox

    def build_lock_page(self):
        vbox = self.build_page_vbox("Lockscreen & Power")
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        group.get_style_context().add_class("group-frame")
        self.widgets['idle_lock'] = Gtk.SpinButton.new_with_range(0, 3600, 30)
        self.widgets['idle_lock'].set_value(self.doc['idle'].get('lock_timeout', 300))
        group.pack_start(self.create_row("Lock Timeout (s)", self.widgets['idle_lock']), False, False, 0)
        vbox.pack_start(group, False, False, 0)
        return vbox

    def build_nightlight_page(self):
        vbox = self.build_page_vbox("Nightlight Settings")
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        group.get_style_context().add_class("group-frame")
        self.widgets['nl_enabled'] = Gtk.Switch()
        self.widgets['nl_enabled'].set_active(self.doc['nightlight'].get('enabled', True))
        group.pack_start(self.create_row("Enabled", self.widgets['nl_enabled']), False, False, 0)
        vbox.pack_start(group, False, False, 0)
        return vbox

    def build_input_page(self):
        vbox = self.build_page_vbox("Input Devices")
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        group.get_style_context().add_class("group-frame")
        self.widgets['kb_layout'] = Gtk.Entry()
        self.widgets['kb_layout'].set_text(self.doc['input'].get('kb_layout', "us"))
        group.pack_start(self.create_row("Keyboard Layout", self.widgets['kb_layout']), False, False, 0)
        vbox.pack_start(group, False, False, 0)
        return vbox

    def build_layout_page(self):
        vbox = self.build_page_vbox("Layout & Tiling")
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        group.get_style_context().add_class("group-frame")
        self.widgets['active_layout'] = Gtk.ComboBoxText()
        for l in ["scroll", "dwindle", "master"]: self.widgets['active_layout'].append(l, l.capitalize())
        self.widgets['active_layout'].set_active_id(self.doc['general'].get('layout', "scroll"))
        group.pack_start(self.create_row("Tiling Layout", self.widgets['active_layout']), False, False, 0)
        vbox.pack_start(group, False, False, 0)
        return vbox

    def build_programs_page(self):
        vbox = self.build_page_vbox("Default Applications")
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        group.get_style_context().add_class("group-frame")
        for app in ["terminal", "fileManager", "status_bar"]:
            self.widgets[app] = Gtk.Entry()
            self.widgets[app].set_text(self.doc['programs'].get(app, ""))
            group.pack_start(self.create_row(app.capitalize(), self.widgets[app]), False, False, 0)
        vbox.pack_start(group, False, False, 0)
        return vbox

    def build_system_page(self):
        vbox = self.build_page_vbox("System Automation")
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        group.get_style_context().add_class("group-frame")
        self.widgets['hyprrocket_enabled'] = Gtk.Switch()
        self.widgets['hyprrocket_enabled'].set_active(self.doc['hyprrocket'].get('enabled', True))
        group.pack_start(self.create_row("HyprRocket Enabled", self.widgets['hyprrocket_enabled']), False, False, 0)
        vbox.pack_start(group, False, False, 0)
        return vbox

    def on_sidebar_row_activated(self, listbox, row):
        self.stack.set_visible_child_name(row.name)

    def on_save_clicked(self, btn):
        try:
            # Sync all values back to self.doc
            self.doc['general']['gaps_in'] = int(self.widgets['gaps_in'].get_value())
            self.doc['general']['gaps_out'] = int(self.widgets['gaps_out'].get_value())
            self.doc['general']['border_size'] = int(self.widgets['border_size'].get_value())
            self.doc['decoration']['rounding'] = int(self.widgets['rounding'].get_value())
            self.doc['decoration']['active_opacity'] = self.widgets['active_opacity'].get_value()
            self.doc['decoration']['inactive_opacity'] = self.widgets['inactive_opacity'].get_value()
            self.doc['wallpapers']['mode'] = self.widgets['wp_mode'].get_active_id()
            self.doc['wallpapers']['fixed']['image'] = self.widgets['wp_image'].get_text()
            self.doc['wallpapers']['interval'] = int(self.widgets['wp_interval'].get_value())
            self.doc['launcher']['width_percent'] = int(self.widgets['l_width'].get_value())
            self.doc['launcher']['dock']['enabled'] = self.widgets['dock_enabled'].get_active()
            self.doc['launcher']['dock']['icon_size'] = int(self.widgets['dock_size'].get_value())
            self.doc['idle']['lock_timeout'] = int(self.widgets['idle_lock'].get_value())
            self.doc['nightlight']['enabled'] = self.widgets['nl_enabled'].get_active()
            self.doc['input']['kb_layout'] = self.widgets['kb_layout'].get_text()
            self.doc['general']['layout'] = self.widgets['active_layout'].get_active_id()
            for app in ["terminal", "fileManager", "status_bar"]:
                self.doc['programs'][app] = self.widgets[app].get_text()
            self.doc['hyprrocket']['enabled'] = self.widgets['hyprrocket_enabled'].get_active()

            with open(self.config_path, 'w') as f:
                f.write(tomlkit.dumps(self.doc))
            
            self.status_label.set_text("Settings Applied Successfully")
            GLib.idle_add(self.rebuild_and_exit)
        except Exception as e:
            self.status_label.set_text(f"Error: {str(e)}")

    def rebuild_and_exit(self):
        subprocess.run(["python3", os.path.expanduser("~/.config/hypr/build_config.py")])
        subprocess.run(["pkill", "-f", "hyprsearch --dock"])
        if self.widgets['dock_enabled'].get_active():
            subprocess.Popen([os.path.expanduser("~/.config/hypr/scripts/hyprsearch"), "--dock"])
        subprocess.run(["notify-send", "Settings Saved", "Hyprland reloaded."])
        sys.exit(0)

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            sys.exit(0)
        elif event.keyval in [Gdk.KEY_Tab, Gdk.KEY_Right]:
            if self.sidebar.has_focus():
                self.stack_scroll.child_focus(Gtk.DirectionType.TAB_FORWARD)
                return True
        elif event.keyval == Gdk.KEY_Left:
            if not self.sidebar.has_focus():
                self.sidebar.grab_focus()
                return True
        return False

if __name__ == "__main__":
    win = SettingsManager()
    Gtk.main()
