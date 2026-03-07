#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import tomlkit
import os
import subprocess

class SettingsManager(Gtk.Window):
    def __init__(self):
        super().__init__(title="HyprDE Settings")
        self.set_border_width(20)
        self.set_default_size(800, 600)
        self.config_path = os.path.expanduser("~/.config/hypr/hyprde.toml")
        self.load_config()

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(self.main_box)

        # Header
        header = Gtk.Label(label="Desktop Environment Settings")
        header.get_style_context().add_class("h1")
        self.main_box.pack_start(header, False, False, 10)

        # Tabs
        self.notebook = Gtk.Notebook()
        self.main_box.pack_start(self.notebook, True, True, 0)

        self.add_launcher_tab()
        self.add_monitors_tab()
        self.add_general_tab()

        # Action Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        save_btn = Gtk.Button(label="Apply & Save")
        save_btn.connect("clicked", self.on_save_clicked)
        btn_box.pack_end(save_btn, False, False, 0)
        self.main_box.pack_start(btn_box, False, False, 10)

        self.show_all()

    def load_config(self):
        with open(self.config_path, 'r') as f:
            self.doc = tomlkit.load(f)

    def add_launcher_tab(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        vbox.set_border_width(15)
        
        # Spotlight (drun) Settings
        group = Gtk.Frame(label="Spotlight / App Launcher")
        gvbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        gvbox.set_border_width(10)
        group.add(gvbox)
        
        # Width %
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.pack_start(Gtk.Label(label="Width %"), False, False, 0)
        val = self.doc['launcher'].get('width_percent', 80)
        self.launcher_width = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 20, 100, 1)
        self.launcher_width.set_value(val)
        hbox.pack_start(self.launcher_width, True, True, 0)
        gvbox.add(hbox)

        # Top Margin
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.pack_start(Gtk.Label(label="Top Offset (px)"), False, False, 0)
        val = self.doc['launcher']['drun'].get('margin_top', 100)
        self.launcher_top = Gtk.SpinButton.new_with_range(0, 500, 10)
        self.launcher_top.set_value(val)
        hbox.pack_start(self.launcher_top, False, False, 0)
        gvbox.add(hbox)

        # Bottom Margin
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.pack_start(Gtk.Label(label="Bottom Safety (px)"), False, False, 0)
        val = self.doc['launcher']['drun'].get('margin_bottom', 50)
        self.launcher_bottom = Gtk.SpinButton.new_with_range(0, 800, 10)
        self.launcher_bottom.set_value(val)
        hbox.pack_start(self.launcher_bottom, False, False, 0)
        gvbox.add(hbox)
        vbox.add(group)

        # Dock Settings
        group = Gtk.Frame(label="Mac-Style Dock")
        gvbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        gvbox.set_border_width(10)
        group.add(gvbox)

        self.dock_enabled = Gtk.CheckButton(label="Enable Persistent Dock")
        self.dock_enabled.set_active(self.doc['launcher']['dock'].get('enabled', True))
        gvbox.add(self.dock_enabled)

        self.dock_autohide = Gtk.CheckButton(label="Hotzone Autohide (Hover to show)")
        self.dock_autohide.set_active(self.doc['launcher']['dock'].get('autohide', True))
        gvbox.add(self.dock_autohide)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.pack_start(Gtk.Label(label="Position"), False, False, 0)
        self.dock_pos = Gtk.ComboBoxText()
        for p in ["bottom", "left", "right"]: self.dock_pos.append_text(p)
        self.dock_pos.set_active_id(self.doc['launcher']['dock'].get('position', "bottom"))
        hbox.pack_start(self.dock_pos, False, False, 0)
        gvbox.add(hbox)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.pack_start(Gtk.Label(label="Icon Size"), False, False, 0)
        self.dock_size = Gtk.SpinButton.new_with_range(24, 128, 4)
        self.dock_size.set_value(self.doc['launcher']['dock'].get('icon_size', 48))
        hbox.pack_start(self.dock_size, False, False, 0)
        gvbox.add(hbox)
        vbox.add(group)

        scroll = Gtk.ScrolledWindow()
        scroll.add(vbox)
        self.notebook.append_page(scroll, Gtk.Label(label="Launcher & Dock"))

    def add_monitors_tab(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_border_width(15)
        vbox.add(Gtk.Label(label="Monitor configuration rules"))
        # Placeholder for more complex monitor logic
        self.notebook.append_page(vbox, Gtk.Label(label="Monitors"))

    def add_general_tab(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_border_width(15)
        # Placeholder for gaps, borders, etc.
        self.notebook.append_page(vbox, Gtk.Label(label="Windows"))

    def on_save_clicked(self, btn):
        # Update Launcher
        self.doc['launcher']['width_percent'] = int(self.launcher_width.get_value())
        self.doc['launcher']['drun']['margin_top'] = int(self.launcher_top.get_value())
        self.doc['launcher']['drun']['margin_bottom'] = int(self.launcher_bottom.get_value())
        
        # Update Dock
        self.doc['launcher']['dock']['enabled'] = self.dock_enabled.get_active()
        self.doc['launcher']['dock']['autohide'] = self.dock_autohide.get_active()
        self.doc['launcher']['dock']['position'] = self.dock_pos.get_active_text()
        self.doc['launcher']['dock']['icon_size'] = int(self.dock_size.get_value())

        with open(self.config_path, 'w') as f:
            f.write(tomlkit.dumps(self.doc))
        
        # Trigger reload/rebuild
        subprocess.run(["python3", os.path.expanduser("~/.config/hypr/build_config.py")])
        subprocess.run(["pkill", "-f", "hyprsearch --dock"])
        if self.dock_enabled.get_active():
            subprocess.Popen([os.path.expanduser("~/.config/hypr/scripts/hyprsearch"), "--dock"])
        
        subprocess.run(["notify-send", "Settings Saved", "Hyprland configuration reloaded."])

if __name__ == "__main__":
    style_provider = Gtk.CssProvider()
    style_provider.load_from_data(b"""
        .h1 { font-size: 24px; font-weight: bold; }
        frame { margin-bottom: 10px; }
    """)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        style_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    win = SettingsManager()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
