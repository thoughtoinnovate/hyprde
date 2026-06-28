#!/usr/bin/env python3
import sys
import os
import time
import gi
import subprocess
import tomlkit
import re
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GtkLayerShell, Gio, GLib, Pango

def get_theme_colors():
    theme_path = os.path.expanduser("~/.config/hypr/themes/current.css")
    # Base Defaults (Dark)
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
                    # Handle both plain variable and @define-color prefix
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

class SettingsManager(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.config_path = os.path.expanduser("~/.config/hypr/hyprde.toml")
        self.load_config()
        
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "hyprde-settings")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        for edge in [GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT]:
            GtkLayerShell.set_anchor(self, edge, True)

        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self.on_key_press)

        # 1. Background (Click to close)
        bg_event_box = Gtk.EventBox()
        bg_event_box.connect("button-press-event", lambda w, e: Gtk.main_quit())
        self.add(bg_event_box)
        
        overlay = Gtk.Overlay()
        bg_event_box.add(overlay)
        
        # 2. Main Catcher
        self.click_catcher = Gtk.EventBox()
        self.click_catcher.set_halign(Gtk.Align.CENTER); self.click_catcher.set_valign(Gtk.Align.CENTER)
        self.click_catcher.connect("button-press-event", lambda w, e: True)
        overlay.add(self.click_catcher)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.main_box.set_name("main-window")
        self.click_catcher.add(self.main_box)
        
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        if monitor:
            geo = monitor.get_geometry()
            self.win_w = int(geo.width * 0.65)
            self.win_h = int(geo.height * 0.75)
            self.main_box.set_size_request(self.win_w, self.win_h)
        else:
            self.main_box.set_size_request(1200, 900)
        
        # Header
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title_box.set_margin_top(30); title_box.set_margin_bottom(15); title_box.set_margin_start(45); title_box.set_margin_end(45)
        title_label = Gtk.Label(label="System Settings"); title_label.set_name("title-label")
        title_box.pack_start(title_label, False, False, 0)
        spacer = Gtk.Box(); title_box.pack_start(spacer, True, True, 0)
        close_btn = Gtk.Button(label="✕"); close_btn.set_name("close-button")
        close_btn.connect("clicked", lambda x: Gtk.main_quit())
        title_box.pack_end(close_btn, False, False, 0)
        self.main_box.pack_start(title_box, False, False, 0)

        # Body
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.main_box.pack_start(content_box, True, True, 0)
        
        sidebar_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar_vbox.set_name("sidebar-area")
        sidebar_vbox.set_size_request(300, -1)
        self.sidebar = Gtk.ListBox(); self.sidebar.set_name("sidebar")
        self.sidebar.connect("row-activated", self.on_sidebar_row_activated)
        
        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.add(self.sidebar)
        sidebar_vbox.pack_start(sidebar_scroll, True, True, 0)
        content_box.pack_start(sidebar_vbox, False, False, 0)
        
        # Stack
        self.stack = Gtk.Stack(); self.stack.set_homogeneous(False); self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack_scroll = Gtk.ScrolledWindow(); self.stack_scroll.set_name("content-scroll")
        self.stack_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.stack_scroll.add(self.stack)
        content_box.pack_start(self.stack_scroll, True, True, 0)
        
        # Footer
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        bottom_box.set_margin_top(25); bottom_box.set_margin_bottom(25); bottom_box.set_margin_start(45); bottom_box.set_margin_end(45)
        self.status_label = Gtk.Label(label=""); self.status_label.set_name("status-label"); bottom_box.pack_start(self.status_label, False, False, 0)
        spacer2 = Gtk.Box(); bottom_box.pack_start(spacer2, True, True, 0)
        self.save_btn = Gtk.Button(label="Apply Changes"); self.save_btn.set_name("save-button")
        self.save_btn.connect("clicked", self.on_save_clicked)
        bottom_box.pack_end(self.save_btn, False, False, 0)
        self.main_box.pack_start(bottom_box, False, False, 0)
        
        self.apply_css()
        self.create_settings_pages()
        self.show_all()
        self.sidebar.grab_focus()

    def load_config(self):
        with open(self.config_path, 'r') as f: self.doc = tomlkit.load(f)

    def apply_css(self):
        c = get_theme_colors()
        css = f"""
        window {{ background-color: transparent; }}
        #main-window {{ 
            background-color: {c['base_bg']}; 
            border-radius: 32px; 
            border: 1px solid {c['border']}; 
            color: {c['base_fg']}; 
        }}
        #title-label {{ font-size: 32px; font-weight: 800; color: {c['base_fg']}; }}
        
        #sidebar-area, #sidebar {{ background-color: rgba(0,0,0,0.1); border-right: 1px solid {c['border']}; }}
        #sidebar row {{ padding: 16px 22px; border-radius: 16px; margin: 4px 10px; color: {c['base_fg']}; opacity: 0.7; font-weight: 600; background: transparent; }}
        #sidebar row:selected {{ background-color: {c['active_bg']}; color: {c['active_fg']}; opacity: 1.0; font-weight: 800; }}
        #sidebar row label {{ color: inherit; }}
        
        #close-button {{ background: transparent; border: none; font-size: 26px; color: {c['base_fg']}; opacity: 0.5; }}
        #close-button:hover {{ opacity: 1.0; color: #ff5f57; }}
        
        #save-button {{ 
            background-color: {c['active_bg']}; 
            color: {c['active_fg']}; 
            font-weight: 800; 
            padding: 16px 55px; 
            border-radius: 18px; 
            border: none; 
            font-size: 17px; 
            box-shadow: 0 4px 20px rgba(0,122,255,0.4); 
        }}
        #save-button:hover {{ opacity: 0.88; box-shadow: 0 6px 28px rgba(0,122,255,0.6); }}
        #status-label.error {{ color: #ff5f57; font-weight: 700; }}
        
        .group-frame {{ 
            background: rgba(255,255,255,0.05); 
            border-radius: 24px; 
            padding: 30px; 
            margin-bottom: 25px; 
            border: 1px solid {c['border']}; 
        }}
        .section-title {{ font-size: 24px; font-weight: 800; margin-bottom: 25px; color: {c['base_fg']}; }}
        
        entry, spinbutton {{ 
            background: {c['module_bg']}; 
            color: {c['module_fg']}; 
            border: 1px solid {c['border']}; 
            border-radius: 14px; 
            padding: 12px; 
        }}
        
        button.picker {{ 
            background-color: {c['module_bg']}; 
            color: {c['module_fg']}; 
            border: 1px solid {c['border']}; 
            border-radius: 14px; 
            padding: 10px 25px; 
            font-weight: 700; 
        }}
        button.picker:hover {{ background-color: {c['hover_bg']}; }}
        
        scale slider {{ background: {c['accent']}; border-radius: 50%; min-height: 28px; min-width: 28px; }}
        scale trough {{ background: rgba(255,255,255,0.1); border-radius: 12px; min-height: 10px; }}
        switch:checked {{ background: {c['active_bg']}; }}
        
        /* Generic button styling */
        button {{
            background: {c['module_bg']};
            color: {c['module_fg']};
            border: 1px solid {c['border']};
            border-radius: 14px;
            padding: 10px 20px;
        }}
        button:hover {{
            background: {c['hover_bg']};
        }}
        
        scrollbar slider {{ background-color: rgba(255, 255, 255, 0.2); border-radius: 12px; min-width: 10px; }}
        """.encode()
        p = Gtk.CssProvider(); p.load_from_data(css); Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def open_picker(self, title, folder=False):
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.BOTTOM); GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.NONE)
        action = Gtk.FileChooserAction.SELECT_FOLDER if folder else Gtk.FileChooserAction.OPEN
        dialog = Gtk.FileChooserNative.new(title, self, action, "_Select", "_Cancel"); res = dialog.run()
        path = dialog.get_filename() if res == Gtk.ResponseType.ACCEPT else None; dialog.destroy()
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY); GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        return path

    def create_row(self, label_text, widget):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=30); hbox.set_margin_bottom(20); label = Gtk.Label(label=label_text); label.set_xalign(0); hbox.pack_start(label, True, True, 0); hbox.pack_end(widget, False, False, 0)
        return hbox

    def build_dynamic_list(self, items, label_title):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12); vbox.get_style_context().add_class("group-frame")
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15); title_box.pack_start(Gtk.Label(label=label_title), True, True, 0)
        add_btn = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON); add_btn.connect("clicked", lambda x: add_entry(""))
        title_box.pack_end(add_btn, False, False, 0); vbox.pack_start(title_box, False, False, 10)
        list_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10); vbox.pack_start(list_container, False, False, 0)
        def add_entry(val=""):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15); entry = Gtk.Entry(); entry.set_text(val); entry.set_hexpand(True)
            del_btn = Gtk.Button.new_from_icon_name("list-remove-symbolic", Gtk.IconSize.BUTTON); del_btn.connect("clicked", lambda x: list_container.remove(row))
            row.pack_start(entry, True, True, 0); row.pack_end(del_btn, False, False, 0); list_container.add(row); row.show_all(); return entry
        for item in items: add_entry(item)
        return vbox, list_container

    def create_settings_pages(self):
        self.widgets = {}
        pages = [("appearance", "Appearance", "preferences-desktop-theme", self.build_appearance), ("monitors", "Displays", "video-display", self.build_monitors), ("wallpapers", "Wallpapers", "background", self.build_wallpapers), ("launcher", "Launcher & Dock", "start-here", self.build_launcher), ("animations", "Motion Effects", "view-restore", self.build_animations), ("lockscreen", "Lock & Power", "system-lock-screen", self.build_lock), ("nightlight", "Nightlight", "weather-clear-night", self.build_nightlight), ("input", "Keyboard & Binds", "input-keyboard", self.build_input), ("plugins", "Extensions", "system-run", self.build_plugins), ("programs", "Default Apps", "applications-other", self.build_programs)]
        for name, title, icon, builder in pages:
            row = Gtk.ListBoxRow(); row.name = name; row.set_can_focus(True); box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20); box.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR), False, False, 0); box.pack_start(Gtk.Label(label=title), False, False, 0); row.add(box); self.sidebar.add(row); self.stack.add_titled(builder(), name, title)
        self.sidebar.select_row(self.sidebar.get_row_at_index(0))

    def build_page_vbox(self, title_text):
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20); v.set_margin_top(30); v.set_margin_bottom(30); v.set_margin_start(45); v.set_margin_end(45); lbl = Gtk.Label(label=title_text); lbl.set_xalign(0); lbl.get_style_context().add_class("section-title"); v.pack_start(lbl, False, False, 0); return v

    def build_appearance(self):
        v = self.build_page_vbox("Desktop Appearance"); f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")
        for k, l, t in [('gaps_in','Inner Gaps','general'),('gaps_out','Outer Gaps','general'),('border_size','Border Size','general'),('rounding','Rounding','decoration')]:
            self.widgets[k] = Gtk.SpinButton.new_with_range(0, 500, 1); self.widgets[k].set_value(self.doc[t].get(k, 0)); f.pack_start(self.create_row(l, self.widgets[k]), False, False, 0)
        v.pack_start(f, False, False, 0); f2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f2.get_style_context().add_class("group-frame")
        for k, l in [('active_opacity','Active Window'),('inactive_opacity','Inactive Window'),('waybar_opacity','Waybar Opacity'),('wofi_opacity','Launcher Opacity')]:
            self.widgets[k] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.1, 1.0, 0.05); self.widgets[k].set_value(self.doc['decoration'].get(k, 1.0)); self.widgets[k].set_size_request(300,-1); f2.pack_start(self.create_row(l, self.widgets[k]), False, False, 0)
        v.pack_start(f2, False, False, 0); return v

    def build_monitors(self):
        v = self.build_page_vbox("Displays & Layout"); f, self.widgets['monitor_list'] = self.build_dynamic_list(self.doc['monitors'].get('rules', []), "Monitor Configuration Rules"); v.pack_start(f, False, False, 0); return v

    def build_wallpapers(self):
        v = self.build_page_vbox("Wallpaper Management")
        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        f.get_style_context().add_class("group-frame")

        self.widgets['wp_mode'] = Gtk.ComboBoxText()
        for m in ["fixed", "dynamic", "disabled"]: self.widgets['wp_mode'].append(m, m.capitalize())
        self.widgets['wp_mode'].set_active_id(self.doc['wallpapers'].get('mode', "fixed"))
        f.pack_start(self.create_row("Active Mode", self.widgets['wp_mode']), False, False, 0)

        # Fixed image section
        self.widgets['wp_image_btn'] = Gtk.Button(label="Browse Image...")
        self.widgets['wp_image_btn'].get_style_context().add_class("picker")
        self.widgets['wp_image_btn'].connect("clicked", lambda x: self.update_picker_path('wp_image_path', "Select Wallpaper"))
        self.widgets['wp_image_path'] = Gtk.Entry()
        self.widgets['wp_image_path'].set_text(self.doc['wallpapers']['fixed'].get('image', ""))
        self.widgets['_wp_fixed_row'] = self.create_row("Static Image", self.widgets['wp_image_btn'])
        f.pack_start(self.widgets['_wp_fixed_row'], False, False, 0)
        f.pack_start(self.widgets['wp_image_path'], False, False, 0)

        # Dynamic folder section
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
        on_mode_changed(self.widgets['wp_mode'])  # apply initial visibility

        v.pack_start(f, False, False, 0)
        return v

    def update_picker_path(self, key, title, folder=False):
        p = self.open_picker(title, folder)
        if p: self.widgets[key].set_text(p)

    def build_animations(self):
        v = self.build_page_vbox("Motion Engine"); f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")
        self.widgets['anim_enabled'] = Gtk.Switch(); self.widgets['anim_enabled'].set_active(self.doc['animations'].get('enabled', True)); f.pack_start(self.create_row("Enable Motion Effects", self.widgets['anim_enabled']), False, False, 0)
        for k, l in [('windows','Open Style'),('windowsOut','Exit Style'),('border','Border Speed'),('fade','Fading Curve'),('workspaces','Workspace Transition')]:
            self.widgets[f'anim_{k}'] = Gtk.Entry(); self.widgets[f'anim_{k}'].set_text(str(self.doc['animations'].get(k, ""))); f.pack_start(self.create_row(l, self.widgets[f'anim_{k}']), False, False, 0)
        v.pack_start(f, False, False, 0); return v

    def build_lock(self):
        v = self.build_page_vbox("Lockscreen & Power")
        f1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f1.get_style_context().add_class("group-frame")
        self.widgets['idle_lock'] = Gtk.SpinButton.new_with_range(0, 3600, 30); self.widgets['idle_lock'].set_value(self.doc['idle'].get('lock_timeout', 300))
        f1.pack_start(self.create_row("Auto-Lock (s)", self.widgets['idle_lock']), False, False, 0); v.pack_start(f1, False, False, 0)
        f2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f2.get_style_context().add_class("group-frame")
        self.widgets['lock_wp_btn'] = Gtk.Button(label="Select Wallpaper..."); self.widgets['lock_wp_btn'].get_style_context().add_class("picker"); self.widgets['lock_wp_btn'].connect("clicked", lambda x: self.update_picker_path('lock_wp_path', "Select Lock Wallpaper"))
        self.widgets['lock_wp_path'] = Gtk.Entry(); self.widgets['lock_wp_path'].set_text(self.doc['lockscreen'].get('background', ""))
        f2.pack_start(self.create_row("Lock Wallpaper", self.widgets['lock_wp_btn']), False, False, 0); f2.pack_start(self.widgets['lock_wp_path'], False, False, 5)
        self.widgets['lock_blur_passes'] = Gtk.SpinButton.new_with_range(0, 20, 1); self.widgets['lock_blur_passes'].set_value(self.doc['lockscreen'].get('blur_passes', 3))
        f2.pack_start(self.create_row("Blur Passes", self.widgets['lock_blur_passes']), False, False, 0)
        self.widgets['lock_blur_size'] = Gtk.SpinButton.new_with_range(0, 20, 1); self.widgets['lock_blur_size'].set_value(self.doc['lockscreen'].get('blur_size', 8))
        f2.pack_start(self.create_row("Blur Size", self.widgets['lock_blur_size']), False, False, 0); v.pack_start(f2, False, False, 0)
        f3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f3.get_style_context().add_class("group-frame")
        self.widgets['profile_btn'] = Gtk.Button(label="Select Picture..."); self.widgets['profile_btn'].get_style_context().add_class("picker"); self.widgets['profile_btn'].connect("clicked", lambda x: self.update_picker_path('profile_path', "Select Profile Picture"))
        self.widgets['profile_path'] = Gtk.Entry(); self.widgets['profile_path'].set_text(self.doc['lockscreen'].get('profile_image', "")); f3.pack_start(self.create_row("User Picture", self.widgets['profile_btn']), False, False, 0); f3.pack_start(self.widgets['profile_path'], False, False, 0); v.pack_start(f3, False, False, 0); return v

    def build_nightlight(self):
        v = self.build_page_vbox("Eye Care"); f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame"); self.widgets['nl_enabled'] = Gtk.Switch(); self.widgets['nl_enabled'].set_active(self.doc['nightlight'].get('enabled', True)); f.pack_start(self.create_row("Enable Night Light", self.widgets['nl_enabled']), False, False, 0); v.pack_start(f, False, False, 0); return v

    def build_input(self):
        v = self.build_page_vbox("Keyboard & Shortcuts"); f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame"); self.widgets['kb_layout'] = Gtk.Entry(); self.widgets['kb_layout'].set_text(self.doc['input'].get('kb_layout', "us")); f.pack_start(self.create_row("Keyboard Layout", self.widgets['kb_layout']), False, False, 0); v.pack_start(f, False, False, 0); f2, self.widgets['bind_list'] = self.build_dynamic_list(self.doc['binds']['normal'].get('list', []), "Shortcuts (MOD, KEY, ACTION, ARGS)"); v.pack_start(f2, False, False, 0); return v

    def build_plugins(self):
        v = self.build_page_vbox("Extensions"); f, self.widgets['plugin_list'] = self.build_dynamic_list(self.doc['plugins'].get('enabled', []), "Active Plugins"); v.pack_start(f, False, False, 0); return v

    def build_programs(self):
        v = self.build_page_vbox("Default Apps"); f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f.get_style_context().add_class("group-frame")
        for k in ["terminal", "fileManager", "status_bar"]:
            self.widgets[k] = Gtk.Entry(); self.widgets[k].set_text(self.doc['programs'].get(k, "")); f.pack_start(self.create_row(k.capitalize(), self.widgets[k]), False, False, 0)
        v.pack_start(f, False, False, 0); return v

    def build_launcher(self):
        v = self.build_page_vbox("Navigation & Launcher")
        
        # 1. Launcher Layout
        f1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f1.get_style_context().add_class("group-frame")
        lbl1 = Gtk.Label(label="Launcher Layout"); lbl1.set_xalign(0); lbl1.set_margin_bottom(10); f1.pack_start(lbl1, False, False, 0)
        
        self.widgets['l_pos'] = Gtk.ComboBoxText()
        for p in ["top", "center"]: self.widgets['l_pos'].append(p, p.capitalize())
        self.widgets['l_pos'].set_active_id(self.doc['launcher'].get('position', "top"))
        f1.pack_start(self.create_row("Screen Position", self.widgets['l_pos']), False, False, 0)
        
        self.widgets['l_width'] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 20, 100, 1)
        self.widgets['l_width'].set_value(self.doc['launcher'].get('width_percent', 70))
        self.widgets['l_width'].set_size_request(300,-1)
        f1.pack_start(self.create_row("Width %", self.widgets['l_width']), False, False, 0)
        
        self.widgets['l_margin'] = Gtk.SpinButton.new_with_range(0, 1000, 10)
        self.widgets['l_margin'].set_value(self.doc['launcher'].get('margin_top', 100))
        f1.pack_start(self.create_row("Top Margin (px)", self.widgets['l_margin']), False, False, 0)
        v.pack_start(f1, False, False, 0)
        
        # 2. Content & Scaling
        f2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f2.get_style_context().add_class("group-frame")
        lbl2 = Gtk.Label(label="Content & Scaling"); lbl2.set_xalign(0); lbl2.set_margin_bottom(10); f2.pack_start(lbl2, False, False, 0)
        
        self.widgets['l_font'] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 12, 72, 1)
        self.widgets['l_font'].set_value(self.doc['launcher'].get('font_size', 24))
        self.widgets['l_font'].set_size_request(300,-1)
        f2.pack_start(self.create_row("Search Font Size", self.widgets['l_font']), False, False, 0)
        
        self.widgets['l_icon'] = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 16, 128, 4)
        self.widgets['l_icon'].set_value(self.doc['launcher'].get('icon_size', 32))
        self.widgets['l_icon'].set_size_request(300,-1)
        f2.pack_start(self.create_row("App Icon Size", self.widgets['l_icon']), False, False, 0)
        
        self.widgets['l_spacing'] = Gtk.SpinButton.new_with_range(0, 50, 1)
        self.widgets['l_spacing'].set_value(self.doc['launcher'].get('row_spacing', 10))
        f2.pack_start(self.create_row("Item Spacing", self.widgets['l_spacing']), False, False, 0)
        v.pack_start(f2, False, False, 0)
        
        # 3. Dock
        f3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); f3.get_style_context().add_class("group-frame")
        lbl3 = Gtk.Label(label="System Dock"); lbl3.set_xalign(0); lbl3.set_margin_bottom(10); f3.pack_start(lbl3, False, False, 0)
        self.widgets['dock_enabled'] = Gtk.Switch()
        self.widgets['dock_enabled'].set_active(self.doc['launcher']['dock'].get('enabled', True))
        f3.pack_start(self.create_row("Enable Mac-style Dock", self.widgets['dock_enabled']), False, False, 0)
        
        self.widgets['dock_pos'] = Gtk.ComboBoxText()
        for p in ["bottom", "top", "left", "right"]: self.widgets['dock_pos'].append(p, p.capitalize())
        self.widgets['dock_pos'].set_active_id(self.doc['launcher']['dock'].get('position', "bottom"))
        f3.pack_start(self.create_row("Dock Position", self.widgets['dock_pos']), False, False, 0)
        
        v.pack_start(f3, False, False, 0)
        
        return v

    def on_sidebar_row_activated(self, lb, row): self.stack.set_visible_child_name(row.name)

    def on_save_clicked(self, btn):
        self.save_btn.set_label("Applying...")
        try:
            if 'appearance' not in self.doc: self.doc['appearance'] = tomlkit.table()
            for k in ['gaps_in','gaps_out','border_size']: self.doc['general'][k] = int(self.widgets[k].get_value())
            for k in ['rounding','active_opacity','inactive_opacity','waybar_opacity','wofi_opacity']: self.doc['decoration'][k] = self.widgets[k].get_value() if 'opacity' in k else int(self.widgets[k].get_value())
            self.doc['wallpapers']['fixed']['image'] = self.widgets['wp_image_path'].get_text(); self.doc['wallpapers']['path'] = self.widgets['wp_dir_path'].get_text()
            self.doc['lockscreen']['profile_image'] = self.widgets['profile_path'].get_text(); self.doc['lockscreen']['background'] = self.widgets['lock_wp_path'].get_text()
            self.doc['lockscreen']['blur_passes'] = int(self.widgets['lock_blur_passes'].get_value()); self.doc['lockscreen']['blur_size'] = int(self.widgets['lock_blur_size'].get_value())
            def get_items(container): return [c.get_children()[0].get_text() for c in container.get_children() if c.get_children()[0].get_text().strip()]
            self.doc['monitors']['rules'] = get_items(self.widgets['monitor_list']); self.doc['binds']['normal']['list'] = get_items(self.widgets['bind_list']); self.doc['plugins']['enabled'] = get_items(self.widgets['plugin_list'])
            for k in ['windows','windowsOut','border','fade','workspaces']: self.doc['animations'][k] = self.widgets[f'anim_{k}'].get_text()
            self.doc['wallpapers']['mode'] = self.widgets['wp_mode'].get_active_id()
            
            # Launcher Settings
            self.doc['launcher']['position'] = self.widgets['l_pos'].get_active_id()
            self.doc['launcher']['width_percent'] = int(self.widgets['l_width'].get_value())
            self.doc['launcher']['margin_top'] = int(self.widgets['l_margin'].get_value())
            self.doc['launcher']['font_size'] = int(self.widgets['l_font'].get_value())
            self.doc['launcher']['icon_size'] = int(self.widgets['l_icon'].get_value())
            self.doc['launcher']['row_spacing'] = int(self.widgets['l_spacing'].get_value())
            
            self.doc['launcher']['dock']['enabled'] = self.widgets['dock_enabled'].get_active()
            self.doc['launcher']['dock']['position'] = self.widgets['dock_pos'].get_active_id()
            self.doc['idle']['lock_timeout'] = int(self.widgets['idle_lock'].get_value()); self.doc['nightlight']['enabled'] = self.widgets['nl_enabled'].get_active(); self.doc['input']['kb_layout'] = self.widgets['kb_layout'].get_text()
            for k in ["terminal", "fileManager", "status_bar"]: self.doc['programs'][k] = self.widgets[k].get_text()
            with open(self.config_path, 'w') as f: f.write(tomlkit.dumps(self.doc))
            subprocess.run(["python3", os.path.expanduser("~/.config/hypr/build_config.py")])
            
            # Apply wallpaper changes immediately
            subprocess.run(["sh", os.path.expanduser("~/.config/hypr/scripts/init_wallpaper.sh")])
            
            subprocess.run(["pkill", "-f", "hyprsearch --dock"])
            subprocess.run(["pkill", "-USR2", "waybar"])
            time.sleep(0.5) # Wait for old process to exit
            if self.widgets['dock_enabled'].get_active():
                # Start new process detached from parent
                subprocess.Popen([os.path.expanduser("~/.config/hypr/scripts/hyprsearch"), "--dock"], 
                               start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["notify-send", "Settings Applied", "System updated."])
            self.save_btn.set_label("Done!")
            time.sleep(0.3)
            Gtk.main_quit()
        except Exception as e:
            self.save_btn.set_label("Apply Changes")
            self.status_label.set_text(f"⚠ Error: {str(e)}")
            self.status_label.get_style_context().add_class("error")

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape: Gtk.main_quit()
        elif event.keyval == Gdk.KEY_Tab:
            if self.sidebar.has_focus():
                row = self.sidebar.get_selected_row(); idx = (row.get_index() + 1) % len(self.sidebar.get_children()) if row else 0
                next_row = self.sidebar.get_row_at_index(idx); self.sidebar.select_row(next_row); next_row.grab_focus(); return True
        elif event.keyval == Gdk.KEY_Right:
            if self.sidebar.has_focus(): self.stack_scroll.child_focus(Gtk.DirectionType.TAB_FORWARD); return True
        elif event.keyval == Gdk.KEY_Left:
            if not self.sidebar.has_focus(): self.sidebar.grab_focus(); return True
        return False

if __name__ == "__main__":
    win = SettingsManager()
    Gtk.main()
