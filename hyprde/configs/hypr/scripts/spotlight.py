#!/usr/bin/env python3
import sys
import os
import gi
import subprocess
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GtkLayerShell, Gio, GLib, Pango
import ast
import operator as op

# Math Evaluator
operators = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
             ast.Div: op.truediv, ast.Pow: op.pow, ast.BitXor: op.xor,
             ast.USub: op.neg}

def eval_expr(expr):
    def eval_(node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            return operators[type(node.op)](eval_(node.left), eval_(node.right))
        elif isinstance(node, ast.UnaryOp):
            return operators[type(node.op)](eval_(node.operand))
        else:
            raise TypeError(node)
    
    expr = expr.replace('^', '**')
    return eval_(ast.parse(expr, mode='eval').body)

def get_theme_colors():
    # Path to the symlinked current theme
    theme_path = os.path.expanduser("~/.config/hypr/themes/current.css")
    
    # Defaults (Dark)
    colors = {
        "bg": "rgba(26, 26, 26, 0.95)",
        "fg": "#ffffff",
        "entry_bg": "#2a2a2a",
        "sel_bg": "#33ccff",
        "sel_fg": "#000000",
        "border": "rgba(255, 255, 255, 0.1)"
    }
    
    if os.path.exists(theme_path):
        try:
            with open(theme_path, 'r') as f:
                content = f.read()
                if "theme_wofi_bg_alpha" in content:
                    import re
                    # Simple regex to extract colors from CSS @define-color
                    def find_color(var):
                        m = re.search(f"{var}\\s+([^;]+);", content)
                        return m.group(1).strip() if m else None
                    
                    colors["bg"] = find_color("theme_wofi_bg_alpha") or colors["bg"]
                    colors["fg"] = find_color("theme_wofi_fg") or colors["fg"]
                    colors["sel_bg"] = find_color("theme_wofi_sel_bg") or colors["sel_bg"]
                    colors["sel_fg"] = find_color("theme_wofi_sel_fg") or colors["sel_fg"]
                    
                    # Entry background should be a bit lighter/darker than main bg
                    if "light" in content.lower():
                        colors["entry_bg"] = "rgba(0, 0, 0, 0.05)"
                        colors["border"] = "rgba(0, 0, 0, 0.1)"
                    else:
                        colors["entry_bg"] = "rgba(255, 255, 255, 0.05)"
                        colors["border"] = "rgba(255, 255, 255, 0.1)"
        except:
            pass
    return colors

class App:
    def __init__(self, app_info):
        self.app_info = app_info
        self.name = app_info.get_name()
        icon = app_info.get_icon()
        self.icon_name = "distributor-logo"
        if icon and hasattr(icon, 'get_names'):
            theme = Gtk.IconTheme.get_default()
            for name in icon.get_names():
                if theme.has_icon(name):
                    self.icon_name = name
                    break

class LauncherWindow(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        
        # Setup Layer Shell
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "hyprde-spotlight")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        
        # Anchor to all edges to fill the screen (allows catching clicks 'outside')
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)

        self.connect("destroy", Gtk.main_quit)        
        self.connect("key-press-event", self.on_global_key_press)
        self.connect("button-press-event", self.on_button_press)
        
        # Main container (Transparent full-screen)
        outer_box = Gtk.EventBox()
        outer_box.set_visible_window(False)
        self.add(outer_box)
        
        # Center alignment
        overlay = Gtk.Overlay()
        outer_box.add(overlay)
        
        # The actual centered UI box
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.main_box.set_name("main-window") # For CSS targeting
        self.main_box.set_halign(Gtk.Align.CENTER)
        self.main_box.set_valign(Gtk.Align.CENTER)
        
        # Dynamically calculate size
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        if monitor:
            geo = monitor.get_geometry()
            self.main_box.set_size_request(int(geo.width * 0.4), int(geo.height * 0.5))
        else:
            self.main_box.set_size_request(700, 600)
            
        overlay.add(self.main_box)
        
        # UI Setup inside main_box
        vbox = self.main_box
        
        # Search Entry
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Search Apps or Calculate...")
        self.entry.set_margin_top(10)
        self.entry.set_margin_bottom(10)
        self.entry.set_margin_start(10)
        self.entry.set_margin_end(10)
        self.entry.connect("changed", self.on_search_changed)
        self.entry.connect("activate", self.on_activate)
        vbox.pack_start(self.entry, False, False, 0)
        
        # ListBox for results
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vbox.pack_start(self.scrolled, True, True, 0)
        
        self.listbox = Gtk.ListBox()
        self.listbox.connect("row-activated", self.on_row_activated)
        self.scrolled.add(self.listbox)
        
        # Apply CSS
        self.apply_css()
        
        # Load Apps
        self.apps = []
        for appinfo in Gio.AppInfo.get_all():
            if appinfo.should_show():
                self.apps.append(App(appinfo))
        
        self.apps.sort(key=lambda x: x.name.lower())
        self.populate_list("")

    def apply_css(self):
        c = get_theme_colors()
        css_data = f"""
        window {{
            background-color: transparent;
        }}
        #main-window {{
            background-color: {c['bg']};
            border-radius: 10px;
        }}
        entry {{
            font-size: 20px;
            padding: 10px;
            background: {c['entry_bg']};
            color: {c['fg']};
            border: none;
            border-radius: 5px;
        }}
        list {{
            background: transparent;
        }}
        row {{
            padding: 5px 10px;
            color: {c['fg']};
        }}
        row:selected {{
            background-color: {c['sel_bg']};
            color: {c['sel_fg']};
            border-radius: 5px;
        }}
        scrollbar {{
            background-color: transparent;
        }}
        scrollbar slider {{
            background-color: rgba(255, 255, 255, 0.2);
            border-radius: 5px;
            min-width: 8px;
            min-height: 40px;
        }}
        scrollbar slider:hover {{
            background-color: rgba(255, 255, 255, 0.4);
        }}
        """.encode()
        
        provider = Gtk.CssProvider()
        provider.load_from_data(css_data)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), 
            provider, 
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_button_press(self, widget, event):
        # Close if click is outside the main_box
        allocation = self.main_box.get_allocation()
        if not (allocation.x <= event.x <= allocation.x + allocation.width and
                allocation.y <= event.y <= allocation.y + allocation.height):
            sys.exit(0)
        return False

    def create_row(self, title, icon_name, obj):
        row = Gtk.ListBoxRow()
        row.obj = obj # Store the App object or math result string
        
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DND)
        icon.set_pixel_size(28)
        box.pack_start(icon, False, False, 0)
        
        label = Gtk.Label(label=title)
        label.set_xalign(0)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(50)
        box.pack_start(label, True, True, 0)
        
        row.add(box)
        return row

    def try_math(self, query):
        if not any(c in "+-*/^" for c in query): return None
        allowed = set("0123456789+-*/() .^")
        if not all(c in allowed for c in query): return None
        
        try:
            res = eval_expr(query)
            if isinstance(res, float) and res.is_integer():
                res = int(res)
            elif isinstance(res, float):
                res = round(res, 4)
            return res
        except:
            return None

    def populate_list(self, query):
        for child in self.listbox.get_children():
            self.listbox.remove(child)
            
        query = query.lower()
        
        # Check Math First
        if query:
            math_res = self.try_math(query)
            if math_res is not None:
                row = self.create_row(f"{query} = {math_res}", "accessories-calculator", str(math_res))
                self.listbox.add(row)
                self.listbox.show_all()
                self.listbox.select_row(row)
                return # If math is valid, only show math

        # Otherwise show apps
        count = 0
        for app in self.apps:
            if not query or query in app.name.lower():
                row = self.create_row(app.name, app.icon_name, app.app_info)
                self.listbox.add(row)
                count += 1
        
        self.listbox.show_all()
        # Select first item
        if count > 0:
            first_row = self.listbox.get_row_at_index(0)
            self.listbox.select_row(first_row)

    def on_search_changed(self, entry):
        self.populate_list(entry.get_text())

    def on_activate(self, entry):
        selected = self.listbox.get_selected_row()
        if selected:
            self.on_row_activated(self.listbox, selected)

    def on_row_activated(self, listbox, row):
        obj = row.obj
        if isinstance(obj, Gio.AppInfo):
            obj.launch(None, None)
        elif isinstance(obj, str):
            # It's a math result, copy to clipboard
            subprocess.run(['wl-copy'], input=obj.encode())
            subprocess.run(['notify-send', '-t', '2000', 'Calculator', f'Copied {obj} to clipboard'])
        
        Gtk.main_quit()

    def on_global_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            sys.exit(0)
            return True
        elif event.keyval == Gdk.KEY_Up and self.entry.has_focus():
            self.listbox.grab_focus()
            self.listbox.emit("move-cursor", Gtk.MovementStep.DISPLAY_LINES, -1, False)
            return True
        elif event.keyval == Gdk.KEY_Down and self.entry.has_focus():
            self.listbox.grab_focus()
            self.listbox.emit("move-cursor", Gtk.MovementStep.DISPLAY_LINES, 1, False)
            return True
        elif not self.entry.has_focus():
            # If not focused on entry, check if it's a key that should be redirected
            is_nav = event.keyval in [Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Return, Gdk.KEY_KP_Enter, 
                                     Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab, Gdk.KEY_Escape]
            if not is_nav:
                self.entry.grab_focus()
                # If it's backspace, we need to manually handle it or let it propagate
                # Propagating is better
                return False
        return False

if __name__ == '__main__':
    win = LauncherWindow()
    win.show_all()
    Gtk.main()