#include <gtk/gtk.h>
#include <gtk-layer-shell/gtk-layer-shell.h>
#include <gio/gio.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include "toml.h"

/* Structs */
typedef struct {
    double width_percent; double height_percent; int rounding; int border_size;
    char *border_color; char *bg_color; char *fg_color; char *sel_bg_color; char *sel_fg_color;
    char *sel_shadow_color; char *glow_color; int font_size; int row_spacing; int icon_size;
    char *position; int margin_top; int margin_bottom;
} LauncherConfig;

typedef struct {
    int enabled; int autohide; char **apps; int apps_count; int icon_size;
    char *bg_color; int rounding; int margin; int padding; char *position;
} DockConfig;

typedef struct {
    char *name; char *name_lower; char *icon; char *exec; GAppInfo *info; GtkWidget *label;
} App;

/* Globals */
GtkWidget *main_window; GtkWidget *centered_box; GtkWidget *entry = NULL;
GtkWidget *listbox = NULL; GtkWidget *dock_shelf = NULL; GtkWidget *scrolled_window = NULL;
GtkWidget *dock_label = NULL; GList *apps_list = NULL;
LauncherConfig config; DockConfig dock_config;
char *current_mode = "drun"; int is_dark_mode = 1;
int is_pin_mode = 0; char *instance_name = "hyprsearch";
char *custom_config_path = NULL; char *prompt_text = "Search...";

/* Prototypes */
void quit_launcher();
void launch_app(App *app);
void pin_app(App *app);
void on_row_activated(GtkListBox *lb, GtkListBoxRow *row, gpointer user_data);
gboolean on_list_button_press(GtkWidget *widget, GdkEventButton *event, gpointer user_data);
gboolean on_dock_button_press(GtkWidget *widget, GdkEventButton *event, gpointer user_data);
gboolean on_add_button_press(GtkWidget *widget, GdkEventButton *event, gpointer user_data);
gboolean on_dock_enter(GtkWidget *widget, GdkEventCrossing *event, gpointer user_data);
gboolean on_dock_leave(GtkWidget *widget, GdkEventCrossing *event, gpointer user_data);
void populate_list(const char *query);
void on_search_changed(GtkEditable *e, gpointer user_data);
void load_dock_apps();
void load_apps();
void load_power_menu();
void load_custom_items(toml_table_t* table);
char* extract_color(const char *line);
void load_theme_css();
void set_default_config();
void apply_table_to_config(toml_table_t* table);
void load_config();
gboolean on_key_press(GtkWidget *widget, GdkEventKey *event, gpointer user_data);
gboolean on_main_button_press(GtkWidget *widget, GdkEventButton *event, gpointer user_data);
gboolean on_list_motion(GtkWidget *widget, GdkEventMotion *event, gpointer user_data);
char* try_math(const char *query);

/* Implementations */
void quit_launcher() { gtk_main_quit(); }

void pin_app(App *app) {
    if (!app) return;
    char *cmd = g_strdup_printf(
        "python3 -c \"import tomlkit, os; path=os.path.expanduser('~/.config/hypr/hyprde.toml'); "
        "d=tomlkit.load(open(path)); apps=d['launcher']['dock']['apps']; "
        "if '%s' not in apps: apps.append('%s'); "
        "with open(path, 'w') as f: f.write(tomlkit.dumps(d))\"",
        app->name, app->name
    );
    system(cmd); g_free(cmd);
    system("pkill -f 'hyprsearch --dock'; ~/.config/hypr/scripts/hyprsearch --dock &");
    quit_launcher();
}

void launch_app(App *app) {
    if (!app) return;
    if (is_pin_mode) { pin_app(app); return; }
    if (strcmp(current_mode, "dmenu") == 0 || strcmp(current_mode, "power-menu") == 0) {
        printf("%s\n", app->name); fflush(stdout);
    } else if (app->exec) {
        system(app->exec);
    } else if (app->info) {
        GdkAppLaunchContext *context = gdk_display_get_app_launch_context(gdk_display_get_default());
        g_app_info_launch(app->info, NULL, G_APP_LAUNCH_CONTEXT(context), NULL);
        g_object_unref(context);
    }
    if (strcmp(current_mode, "dock") != 0) quit_launcher();
}

void on_row_activated(GtkListBox *lb, GtkListBoxRow *row, gpointer user_data) {
    if (!row) return;
    char *math = g_object_get_data(G_OBJECT(row), "math_result");
    if (math) {
        char *cmd = g_strdup_printf("echo -n '%s' | wl-copy", math);
        system(cmd); g_free(cmd);
        system("notify-send -t 2000 'Calculator' 'Copied to clipboard'");
        quit_launcher();
    } else {
        App *app = g_object_get_data(G_OBJECT(row), "app_data"); launch_app(app);
    }
}

gboolean on_list_motion(GtkWidget *widget, GdkEventMotion *event, gpointer user_data) {
    GtkListBoxRow *row = gtk_list_box_get_row_at_y(GTK_LIST_BOX(listbox), (int)event->y);
    if (row) gtk_list_box_select_row(GTK_LIST_BOX(listbox), row);
    return FALSE;
}

gboolean on_list_button_press(GtkWidget *widget, GdkEventButton *event, gpointer user_data) {
    if (event->button == 1) { 
        GtkListBoxRow *row = gtk_list_box_get_row_at_y(GTK_LIST_BOX(listbox), (int)event->y);
        if (row) on_row_activated(GTK_LIST_BOX(listbox), row, NULL);
        return TRUE;
    }
    return FALSE;
}

gboolean on_dock_button_press(GtkWidget *widget, GdkEventButton *event, gpointer user_data) {
    if (event->button == 1) launch_app((App*)user_data);
    return TRUE;
}

gboolean on_add_button_press(GtkWidget *widget, GdkEventButton *event, gpointer user_data) {
    if (event->button == 1) { system("~/.config/hypr/scripts/hyprsearch --pin &"); return TRUE; }
    return FALSE;
}

gboolean on_dock_enter(GtkWidget *widget, GdkEventCrossing *event, gpointer user_data) {
    App *app = (App*)user_data;
    if (app && dock_label) {
        gtk_label_set_text(GTK_LABEL(dock_label), app->name);
        GtkAllocation alloc; gtk_widget_get_allocation(widget, &alloc);
        int x, y; gtk_widget_translate_coordinates(widget, gtk_widget_get_parent(dock_shelf), 0, 0, &x, &y);
        GtkRequisition req; gtk_widget_get_preferred_size(dock_label, NULL, &req);
        gtk_widget_set_margin_start(dock_label, 0); gtk_widget_set_margin_top(dock_label, 0);
        
        if (strcmp(dock_config.position, "left") == 0 || strcmp(dock_config.position, "right") == 0) {
            gtk_widget_set_margin_top(dock_label, y + (alloc.height / 2) - (req.height / 2));
            if (strcmp(dock_config.position, "left") == 0) gtk_widget_set_margin_start(dock_label, x + alloc.width + 12);
            else gtk_widget_set_margin_start(dock_label, x - req.width - 12);
        } else {
            gtk_widget_set_margin_start(dock_label, x + (alloc.width / 2) - (req.width / 2));
            if (strcmp(dock_config.position, "top") == 0) gtk_widget_set_margin_top(dock_label, y + alloc.height + 12);
            else gtk_widget_set_margin_top(dock_label, y - req.height - 12);
        }
        gtk_widget_show(dock_label);
    }
    if (dock_config.autohide) gtk_widget_set_opacity(dock_shelf, 1.0);
    return FALSE;
}

gboolean on_dock_leave(GtkWidget *widget, GdkEventCrossing *event, gpointer user_data) {
    if (dock_label) gtk_widget_hide(dock_label);
    if (dock_config.autohide) gtk_widget_set_opacity(dock_shelf, 0.05);
    return FALSE;
}

void populate_list(const char *query) {
    if (!listbox) return;
    GList *children = gtk_container_get_children(GTK_CONTAINER(listbox));
    for (GList *l = children; l != NULL; l = l->next) gtk_container_remove(GTK_CONTAINER(listbox), GTK_WIDGET(l->data));
    g_list_free(children);
    int count = 0; char *query_lower = query ? g_ascii_strdown(query, -1) : NULL;
    
    char *math_res = try_math(query);
    if (math_res) {
        GtkWidget *row = gtk_list_box_row_new(); g_object_set_data_full(G_OBJECT(row), "math_result", g_strdup(math_res), g_free);
        GtkWidget *hbox = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, config.row_spacing * 2); gtk_container_set_border_width(GTK_CONTAINER(hbox), config.row_spacing);
        GtkWidget *icon = gtk_image_new_from_icon_name("accessories-calculator", GTK_ICON_SIZE_DND);
        gtk_image_set_pixel_size(GTK_IMAGE(icon), config.icon_size); gtk_box_pack_start(GTK_BOX(hbox), icon, FALSE, FALSE, 0);
        char *label_text = g_strdup_printf("%s = %s", query, math_res);
        GtkWidget *label = gtk_label_new(label_text); gtk_widget_set_halign(label, GTK_ALIGN_START);
        gtk_label_set_ellipsize(GTK_LABEL(label), PANGO_ELLIPSIZE_END); gtk_box_pack_start(GTK_BOX(hbox), label, TRUE, TRUE, 0);
        g_free(label_text); gtk_container_add(GTK_CONTAINER(row), hbox); gtk_container_add(GTK_CONTAINER(listbox), row);
        count++; g_free(math_res);
    }

    for (GList *l = apps_list; l != NULL; l = l->next) {
        App *app = (App*)l->data;
        if (!query_lower || strlen(query_lower) == 0 || strstr(app->name_lower, query_lower)) {
            GtkWidget *row = gtk_list_box_row_new(); g_object_set_data(G_OBJECT(row), "app_data", app);
            GtkWidget *hbox = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, config.row_spacing * 2);
            gtk_container_set_border_width(GTK_CONTAINER(hbox), config.row_spacing);
            GtkWidget *icon = gtk_image_new_from_icon_name(app->icon, GTK_ICON_SIZE_DND);
            gtk_image_set_pixel_size(GTK_IMAGE(icon), config.icon_size);
            gtk_box_pack_start(GTK_BOX(hbox), icon, FALSE, FALSE, 0);
            GtkWidget *label = gtk_label_new(app->name); gtk_widget_set_halign(label, GTK_ALIGN_START);
            gtk_label_set_ellipsize(GTK_LABEL(label), PANGO_ELLIPSIZE_END);
            gtk_box_pack_start(GTK_BOX(hbox), label, TRUE, TRUE, 0);
            gtk_container_add(GTK_CONTAINER(row), hbox); gtk_container_add(GTK_CONTAINER(listbox), row);
            if (++count > 100) break;
        }
    }
    if (query_lower) g_free(query_lower);
    gtk_widget_show_all(listbox);
    if (count > 0) gtk_list_box_select_row(GTK_LIST_BOX(listbox), gtk_list_box_get_row_at_index(GTK_LIST_BOX(listbox), 0));
}

void on_search_changed(GtkEditable *e, gpointer user_data) { populate_list(gtk_entry_get_text(GTK_ENTRY(e))); }

void load_dock_apps() {
    for (int i = 0; i < dock_config.apps_count; i++) {
        GList *all = g_app_info_get_all();
        for (GList *l = all; l != NULL; l = l->next) {
            GAppInfo *info = (GAppInfo*)l->data;
            if (g_ascii_strcasecmp(g_app_info_get_name(info), dock_config.apps[i]) == 0) {
                App *app = g_new0(App, 1); app->name = g_strdup(g_app_info_get_name(info));
                app->name_lower = g_ascii_strdown(app->name, -1);
                GIcon *gi = g_app_info_get_icon(info); app->icon = gi ? g_icon_to_string(gi) : g_strdup("system-run");
                app->info = g_object_ref(info); apps_list = g_list_append(apps_list, app); break;
            }
        }
        g_list_free_full(all, g_object_unref);
    }
}

void load_apps() {
    GList *all = g_app_info_get_all();
    for (GList *l = all; l != NULL; l = l->next) {
        GAppInfo *info = (GAppInfo*)l->data;
        if (g_app_info_should_show(info)) {
            App *app = g_new0(App, 1); app->name = g_strdup(g_app_info_get_name(info));
            app->name_lower = g_ascii_strdown(app->name, -1);
            GIcon *gi = g_app_info_get_icon(info); app->icon = gi ? g_icon_to_string(gi) : g_strdup("system-run");
            app->info = g_object_ref(info); apps_list = g_list_append(apps_list, app);
        }
    }
    g_list_free_full(all, g_object_unref);
}

void load_power_menu() {
    struct { char *name; char *icon; char *exec; } items[] = {
        {"Lock", "system-lock-screen", "hyprlock"},         {"Logout", "system-log-out", "hyprctl dispatch 'hl.dsp.exit()'"},
        {"Suspend", "system-suspend", "systemctl suspend"}, {"Hibernate", "system-suspend-hibernate", "systemctl hibernate"},
        {"Reboot", "system-reboot", "systemctl reboot"}, {"Shutdown", "system-shutdown", "systemctl poweroff"},
        {"Power Balanced", "power-profile-balanced", "$HOME/.config/hypr/scripts/power-mode.sh balanced"},
        {"Power High", "power-profile-performance", "$HOME/.config/hypr/scripts/power-mode.sh high"},
        {"Power Auto", "preferences-system-power", "$HOME/.config/hypr/scripts/power-mode.sh auto"},
        {"Power Saver", "power-profile-power-saver", "$HOME/.config/hypr/scripts/power-mode.sh saver"}
    };
    for (int i = 0; i < 10; i++) {
        App *app = g_new0(App, 1); app->name = g_strdup(items[i].name);
        app->name_lower = g_ascii_strdown(app->name, -1); app->icon = g_strdup(items[i].icon);
        app->exec = g_strdup(items[i].exec); apps_list = g_list_append(apps_list, app);
    }
}

void load_custom_items(toml_table_t* table) {
    toml_array_t* items = toml_array_in(table, "items");
    if (!items) return;
    for (int i = 0; i < toml_array_nelem(items); i++) {
        toml_table_t* item = toml_table_at(items, i);
        if (item) {
            App *app = g_new0(App, 1);
            toml_datum_t d;
            d = toml_string_in(item, "name"); if (d.ok) { app->name = g_strdup(d.u.s); app->name_lower = g_ascii_strdown(app->name, -1); free(d.u.s); }
            d = toml_string_in(item, "icon"); if (d.ok) { app->icon = g_strdup(d.u.s); free(d.u.s); }
            d = toml_string_in(item, "exec"); if (d.ok) { app->exec = g_strdup(d.u.s); free(d.u.s); }
            apps_list = g_list_append(apps_list, app);
        }
    }
}

char* extract_color(const char *line) {
    const char *first_space = strchr(line, ' '); if (!first_space) return NULL;
    const char *second_space = strchr(first_space + 1, ' '); if (!second_space) return NULL;
    const char *start = second_space + 1;
    const char *semi = strchr(start, ';'); if (!semi) return NULL;
    return g_strndup(start, semi - start);
}

void load_theme_css() {
    char *path = g_build_filename(g_get_home_dir(), ".config/hypr/themes/current.css", NULL);
    char *content = NULL;
    if (g_file_get_contents(path, &content, NULL, NULL)) {
        char **lines = g_strsplit(content, "\n", -1);
        for (int i = 0; lines[i] != NULL; i++) {
            if (strstr(lines[i], "@define-color theme_wofi_bg_alpha")) {
                g_free(config.bg_color); config.bg_color = extract_color(lines[i]);
                if (strstr(config.bg_color, "#ffffff") || strstr(config.bg_color, "255, 255, 255")) is_dark_mode = 0;
            } else if (strstr(lines[i], "@define-color theme_wofi_fg")) {
                g_free(config.fg_color); config.fg_color = extract_color(lines[i]);
            } else if (strstr(lines[i], "@define-color theme_wofi_sel_bg")) {
                g_free(config.sel_bg_color); config.sel_bg_color = extract_color(lines[i]);
            } else if (strstr(lines[i], "@define-color theme_accent")) {
                char *accent = extract_color(lines[i]);
                g_free(config.border_color); config.border_color = g_strdup(accent);
                g_free(config.glow_color); config.glow_color = g_strdup(accent);
                g_free(config.sel_shadow_color); config.sel_shadow_color = g_strdup(accent);
                g_free(accent);
            }
        }
        g_strfreev(lines); g_free(content);
    }
    g_free(path);
}

void set_default_config() {
    config.width_percent = 70; config.rounding = 24; config.border_size = 1;
    config.bg_color = g_strdup("rgba(20, 20, 20, 0.98)"); config.fg_color = g_strdup("#ffffff");
    config.glow_color = g_strdup("rgba(51, 204, 255, 0.1)"); config.font_size = 24;
    config.icon_size = 32; config.row_spacing = 10;
    config.position = g_strdup("top"); config.margin_top = 100; config.margin_bottom = 50;
    dock_config.enabled = 0; dock_config.autohide = 0; dock_config.icon_size = 48;
    dock_config.bg_color = g_strdup("rgba(20, 20, 20, 0.8)"); dock_config.rounding = 24;
    dock_config.margin = 10; dock_config.padding = 12; dock_config.position = g_strdup("bottom");
}

void apply_table_to_config(toml_table_t* table) {
    if (!table) return;
    toml_datum_t d;
    d = toml_int_in(table, "width_percent"); if (d.ok) config.width_percent = (double)d.u.i;
    d = toml_int_in(table, "rounding"); if (d.ok) config.rounding = d.u.i;
    d = toml_int_in(table, "icon_size"); if (d.ok) config.icon_size = d.u.i;
    d = toml_int_in(table, "font_size"); if (d.ok) config.font_size = d.u.i;
    d = toml_int_in(table, "row_spacing"); if (d.ok) config.row_spacing = d.u.i;
    d = toml_int_in(table, "margin_top"); if (d.ok) config.margin_top = d.u.i;
    d = toml_int_in(table, "margin_bottom"); if (d.ok) config.margin_bottom = d.u.i;
    toml_datum_t s = toml_string_in(table, "position"); if (s.ok) { g_free(config.position); config.position = g_strdup(s.u.s); free(s.u.s); }
}

void load_config() {
    set_default_config(); load_theme_css();
    char *path = custom_config_path ? g_strdup(custom_config_path) : g_build_filename(g_get_home_dir(), ".config/hypr/hyprde.toml", NULL);
    FILE* fp = fopen(path, "r");
    if (fp) {
        char errbuf[200]; toml_table_t* conf = toml_parse_file(fp, errbuf, sizeof(errbuf));
        fclose(fp);
        if (conf) {
            toml_table_t* launcher = toml_table_in(conf, "launcher");
            if (launcher) {
                apply_table_to_config(launcher);
                toml_table_t* mode_table = toml_table_in(launcher, instance_name);
                if (mode_table) {
                    apply_table_to_config(mode_table);
                    load_custom_items(mode_table);
                }
                toml_table_t* dock = toml_table_in(launcher, "dock");
                if (dock) {
                    toml_datum_t d;
                    d = toml_bool_in(dock, "enabled"); if (d.ok) dock_config.enabled = d.u.b;
                    d = toml_bool_in(dock, "autohide"); if (d.ok) dock_config.autohide = d.u.b;
                    d = toml_int_in(dock, "icon_size"); if (d.ok) dock_config.icon_size = d.u.i;
                    d = toml_int_in(dock, "rounding"); if (d.ok) dock_config.rounding = d.u.i;
                    d = toml_int_in(dock, "margin"); if (d.ok) dock_config.margin = d.u.i;
                    d = toml_int_in(dock, "padding"); if (d.ok) dock_config.padding = d.u.i;
                    toml_datum_t ds = toml_string_in(dock, "position"); 
                    if (ds.ok) { 
                        g_free(dock_config.position); 
                        dock_config.position = g_strdup(ds.u.s); 
                        g_message("Loaded dock position: %s", dock_config.position);
                        free(ds.u.s); 
                    } else {
                        g_message("Using default dock position: %s", dock_config.position);
                    }
                    toml_array_t* apps = toml_array_in(dock, "apps");
                    if (apps) {
                        dock_config.apps_count = toml_array_nelem(apps);
                        dock_config.apps = malloc(sizeof(char*) * dock_config.apps_count);
                        for (int i = 0; i < dock_config.apps_count; i++) {
                            toml_datum_t dstr = toml_string_at(apps, i); if (dstr.ok) { dock_config.apps[i] = g_strdup(dstr.u.s); free(dstr.u.s); }
                        }
                    }
                }
            }
            toml_free(conf);
        }
    }
    g_free(path);
}

gboolean on_key_press(GtkWidget *widget, GdkEventKey *event, gpointer user_data) {
    if (event->keyval == GDK_KEY_Escape) { quit_launcher(); return TRUE; }
    if (event->keyval == GDK_KEY_Down || event->keyval == GDK_KEY_Up) {
        GtkListBoxRow *row = gtk_list_box_get_selected_row(GTK_LIST_BOX(listbox));
        int idx = row ? gtk_list_box_row_get_index(row) : -1;
        int new_idx = (event->keyval == GDK_KEY_Down) ? idx + 1 : idx - 1;
        GtkListBoxRow *target = gtk_list_box_get_row_at_index(GTK_LIST_BOX(listbox), new_idx);
        if (target) {
            gtk_list_box_select_row(GTK_LIST_BOX(listbox), target);
            GtkAdjustment *adj = gtk_scrolled_window_get_vadjustment(GTK_SCROLLED_WINDOW(scrolled_window));
            GtkAllocation r_alloc; gtk_widget_get_allocation(GTK_WIDGET(target), &r_alloc);
            int ty; gtk_widget_translate_coordinates(GTK_WIDGET(target), GTK_WIDGET(listbox), 0, 0, NULL, &ty);
            double cv = gtk_adjustment_get_value(adj); double ps = gtk_adjustment_get_page_size(adj);
            if (ty < cv) gtk_adjustment_set_value(adj, ty);
            else if (ty + r_alloc.height > cv + ps) gtk_adjustment_set_value(adj, ty + r_alloc.height - ps);
        }
        return TRUE;
    }
    if (event->keyval == GDK_KEY_Return || event->keyval == GDK_KEY_KP_Enter) {
        if (listbox) {
            GtkListBoxRow *row = gtk_list_box_get_selected_row(GTK_LIST_BOX(listbox));
            if (row) on_row_activated(GTK_LIST_BOX(listbox), row, NULL);
        }
        return TRUE;
    }
    if (entry && !gtk_widget_has_focus(entry)) {
        if ((event->keyval >= 32 && event->keyval <= 126) || event->keyval == GDK_KEY_BackSpace) {
            gtk_widget_grab_focus(entry); return FALSE;
        }
    }
    return FALSE;
}

gboolean on_main_button_press(GtkWidget *widget, GdkEventButton *event, gpointer user_data) {
    if (strcmp(current_mode, "dock") != 0) quit_launcher();
    return FALSE;
}

char* try_math(const char *query) {
    if (!query || strlen(query) < 3) return NULL;
    if (!strpbrk(query, "+-*/^")) return NULL;
    char *cmd = g_strdup_printf("qalc -t '%s'", query);
    char *output = NULL;
    if (g_spawn_command_line_sync(cmd, &output, NULL, NULL, NULL)) {
        g_free(cmd);
        if (output) {
            char *trimmed = g_strstrip(output);
            if (trimmed && strlen(trimmed) > 0 && strchr(trimmed, '=') == NULL) return trimmed;
            if (output) g_free(output);
        }
    } else { g_free(cmd); }
    return NULL;
}

int main(int argc, char *argv[]) {
    gtk_init(&argc, &argv);
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--dock") == 0) { current_mode = "dock"; instance_name = "dock"; }
        else if (strcmp(argv[i], "--pin") == 0) { is_pin_mode = 1; current_mode = "drun"; }
        else if (strcmp(argv[i], "--power-menu") == 0) { current_mode = "power-menu"; instance_name = "power_menu"; }
        else if (strcmp(argv[i], "--dmenu") == 0) { current_mode = "dmenu"; instance_name = "dmenu"; }
        else if (strcmp(argv[i], "--instance") == 0 && i + 1 < argc) instance_name = argv[++i];
        else if (strcmp(argv[i], "--config") == 0 && i + 1 < argc) custom_config_path = argv[++i];
    }
    load_config(); if (strcmp(current_mode, "dock") == 0) load_dock_apps(); 
    else if (strcmp(current_mode, "power-menu") == 0) load_power_menu();
    else load_apps();

    main_window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_layer_init_for_window(GTK_WINDOW(main_window));
    gtk_layer_set_namespace(GTK_WINDOW(main_window), instance_name);
    
    if (strcmp(current_mode, "dock") == 0) {
        gtk_layer_set_layer(GTK_WINDOW(main_window), GTK_LAYER_SHELL_LAYER_TOP);
        gtk_layer_set_keyboard_mode(GTK_WINDOW(main_window), GTK_LAYER_SHELL_KEYBOARD_MODE_NONE);
        if (strcmp(dock_config.position, "left") == 0) {
            gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_LEFT, TRUE);
            gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_TOP, TRUE);
            gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_BOTTOM, TRUE);
        } else if (strcmp(dock_config.position, "right") == 0) {
            gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_RIGHT, TRUE);
            gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_TOP, TRUE);
            gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_BOTTOM, TRUE);
        } else if (strcmp(dock_config.position, "top") == 0) {
            gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_TOP, TRUE);
            gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_LEFT, TRUE);
            gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_RIGHT, TRUE);
        } else {
            gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_BOTTOM, TRUE);
            gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_LEFT, TRUE);
            gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_RIGHT, TRUE);
        }
    } else {
        gtk_layer_set_layer(GTK_WINDOW(main_window), GTK_LAYER_SHELL_LAYER_OVERLAY);
        gtk_layer_set_keyboard_mode(GTK_WINDOW(main_window), GTK_LAYER_SHELL_KEYBOARD_MODE_EXCLUSIVE);
        gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_TOP, TRUE);
        gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_BOTTOM, TRUE);
        gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_LEFT, TRUE);
        gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_RIGHT, TRUE);
        gtk_layer_set_margin(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_TOP, config.margin_top);
        gtk_layer_set_margin(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_BOTTOM, config.margin_bottom);
    }

    centered_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0); 
    gtk_container_add(GTK_CONTAINER(main_window), centered_box);
    g_signal_connect(main_window, "key-press-event", G_CALLBACK(on_key_press), NULL);

    char *css = NULL;
    if (strcmp(current_mode, "dock") == 0) {
        gtk_widget_set_halign(centered_box, GTK_ALIGN_CENTER); gtk_widget_set_valign(centered_box, GTK_ALIGN_CENTER);
        if (strcmp(dock_config.position, "left") == 0) gtk_widget_set_margin_start(centered_box, dock_config.margin);
        else if (strcmp(dock_config.position, "right") == 0) gtk_widget_set_margin_end(centered_box, dock_config.margin);
        else if (strcmp(dock_config.position, "top") == 0) gtk_widget_set_margin_top(centered_box, dock_config.margin);
        else gtk_widget_set_margin_bottom(centered_box, dock_config.margin);

        GtkWidget *overlay = gtk_overlay_new(); gtk_box_pack_start(GTK_BOX(centered_box), overlay, FALSE, FALSE, 0);
        dock_shelf = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 0); gtk_widget_set_name(dock_shelf, "dock-shelf");
        if (dock_config.autohide) gtk_widget_set_opacity(dock_shelf, 0.05);
        
        int buffer = 80;
        if (strcmp(dock_config.position, "left") == 0) gtk_widget_set_margin_end(dock_shelf, buffer);
        else if (strcmp(dock_config.position, "right") == 0) gtk_widget_set_margin_start(dock_shelf, buffer);
        else if (strcmp(dock_config.position, "top") == 0) gtk_widget_set_margin_bottom(dock_shelf, buffer);
        else gtk_widget_set_margin_top(dock_shelf, buffer);

        GtkOrientation orient = (strcmp(dock_config.position, "left") == 0 || strcmp(dock_config.position, "right") == 0) ? GTK_ORIENTATION_VERTICAL : GTK_ORIENTATION_HORIZONTAL;
        GtkWidget *icons_box = gtk_box_new(orient, 10); gtk_container_set_border_width(GTK_CONTAINER(icons_box), dock_config.padding);
        for (GList *l = apps_list; l != NULL; l = l->next) {
            App *app = (App*)l->data;
            GtkWidget *eb = gtk_event_box_new(); gtk_widget_set_name(eb, "dock-item");
            GtkWidget *img = gtk_image_new_from_icon_name(app->icon, GTK_ICON_SIZE_DND);
            gtk_image_set_pixel_size(GTK_IMAGE(img), dock_config.icon_size); gtk_container_add(GTK_CONTAINER(eb), img);
            g_signal_connect(eb, "button-press-event", G_CALLBACK(on_dock_button_press), app);
            g_signal_connect(eb, "enter-notify-event", G_CALLBACK(on_dock_enter), app);
            g_signal_connect(eb, "leave-notify-event", G_CALLBACK(on_dock_leave), app);
            gtk_box_pack_start(GTK_BOX(icons_box), eb, FALSE, FALSE, 0);
        }
        GtkWidget *add_eb = gtk_event_box_new(); gtk_widget_set_name(add_eb, "dock-item-add");
        GtkWidget *add_img = gtk_image_new_from_icon_name("list-add-symbolic", GTK_ICON_SIZE_DND);
        gtk_image_set_pixel_size(GTK_IMAGE(add_img), dock_config.icon_size); gtk_container_add(GTK_CONTAINER(add_eb), add_img);
        g_signal_connect(add_eb, "button-press-event", G_CALLBACK(on_add_button_press), NULL);
        g_signal_connect(add_eb, "enter-notify-event", G_CALLBACK(on_dock_enter), NULL);
        g_signal_connect(add_eb, "leave-notify-event", G_CALLBACK(on_dock_leave), NULL);
        gtk_box_pack_start(GTK_BOX(icons_box), add_eb, FALSE, FALSE, 0);
        gtk_container_add(GTK_CONTAINER(dock_shelf), icons_box); gtk_container_add(GTK_CONTAINER(overlay), dock_shelf);

        dock_label = gtk_label_new(""); gtk_widget_set_name(dock_label, "dock-label");
        gtk_widget_set_no_show_all(dock_label, TRUE); gtk_widget_set_halign(dock_label, GTK_ALIGN_START);
        gtk_widget_set_valign(dock_label, GTK_ALIGN_START); gtk_widget_set_can_focus(dock_label, FALSE);
        gtk_overlay_add_overlay(GTK_OVERLAY(overlay), dock_label);

        const char *transform = "translateY(-20px)";
        if (strcmp(dock_config.position, "left") == 0) transform = "translateX(20px)";
        else if (strcmp(dock_config.position, "right") == 0) transform = "translateX(-20px)";
        const char *highlight = "rgba(255,255,255,0.18)";
        css = g_strdup_printf(
            "window { background-color: transparent; } "
            "#dock-shelf { background-color: rgba(255,255,255,0.15); border-radius: 100px; border: 1px solid rgba(255,255,255,0.2); box-shadow: 0 10px 40px rgba(0,0,0,0.5); transition: all 0.3s ease; }"
            "#dock-item, #dock-item-add { padding: 8px; border-radius: 100px; transition: transform 0.25s cubic-bezier(0.25, 0.8, 0.25, 1), background 0.2s ease; }"
            "#dock-item:hover { transform: scale(2.0) %s; background: %s; } #dock-item-add:hover { transform: scale(1.6); background: %s; }"
            "#dock-label { color: #ffffff; background: rgba(0,0,0,0.85); padding: 6px 14px; border-radius: 10px; font-size: 14px; font-weight: 700; text-shadow: none; box-shadow: 0 5px 15px rgba(0,0,0,0.4); }",
            transform, highlight, highlight
        );
    } else {
        gtk_widget_set_halign(centered_box, GTK_ALIGN_FILL);
        if (strcmp(config.position, "center") == 0) {
            gtk_widget_set_valign(centered_box, GTK_ALIGN_CENTER);
        } else {
            gtk_widget_set_valign(centered_box, GTK_ALIGN_START);
        }

        GtkWidget *search_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0); gtk_widget_set_name(search_box, "main-window");
        gtk_widget_set_halign(search_box, GTK_ALIGN_CENTER);
        GdkDisplay *display = gdk_display_get_default(); GdkMonitor *monitor = NULL;
        int n_monitors = gdk_display_get_n_monitors(display);
        if (n_monitors > 0) monitor = gdk_display_get_monitor(display, 0);
        int width = 1200;
        if (monitor) { GdkRectangle geo; gdk_monitor_get_geometry(monitor, &geo); width = geo.width * (config.width_percent / 100.0); }
        gtk_widget_set_size_request(search_box, width, -1);

        entry = gtk_entry_new(); gtk_widget_set_name(entry, "search-entry");
        gtk_entry_set_placeholder_text(GTK_ENTRY(entry), is_pin_mode ? "Pin App to Dock..." : "Search Apps...");
        g_signal_connect(entry, "changed", G_CALLBACK(on_search_changed), NULL);
        gtk_box_pack_start(GTK_BOX(search_box), entry, FALSE, FALSE, 0);
        scrolled_window = gtk_scrolled_window_new(NULL, NULL);
        gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scrolled_window), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
        gtk_scrolled_window_set_propagate_natural_height(GTK_SCROLLED_WINDOW(scrolled_window), TRUE);
        gtk_box_pack_start(GTK_BOX(search_box), scrolled_window, TRUE, TRUE, 0);
        listbox = gtk_list_box_new(); gtk_list_box_set_selection_mode(GTK_LIST_BOX(listbox), GTK_SELECTION_BROWSE);
        g_signal_connect(listbox, "motion-notify-event", G_CALLBACK(on_list_motion), NULL);
        g_signal_connect(listbox, "button-press-event", G_CALLBACK(on_list_button_press), NULL);
        gtk_widget_add_events(listbox, GDK_POINTER_MOTION_MASK | GDK_BUTTON_PRESS_MASK);
        gtk_container_add(GTK_CONTAINER(scrolled_window), listbox);
        gtk_container_add(GTK_CONTAINER(centered_box), search_box);

        const char *entry_bg = is_dark_mode ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.03)";
        int row_font_size = config.font_size * 0.8;
        if (row_font_size < 12) row_font_size = 12;

        css = g_strdup_printf(
            "window { background-color: transparent; }"
            "#main-window { background-color: %s; border-radius: %dpx; box-shadow: 0 30px 60px rgba(0,0,0,0.5), 0 0 1px 1px rgba(255,255,255,0.08); }"
            "entry { border: none; box-shadow: none; outline: none; background: none; }"
            "#search-entry { font-size: %dpx; font-weight: 300; padding: 28px 50px; background-color: %s; color: %s; border-top-left-radius: %dpx; border-top-right-radius: %dpx; }"
            "list { background: transparent; padding: 8px; }"
            "row { color: %s; border-radius: 12px; margin: 2px 15px; padding: 6px; transition: all 0.15s ease; }"
            "row label { font-size: %dpx; }"
            "row:selected { background-color: %s; color: %s; box-shadow: inset 0 0 0 1px rgba(255,255,255,0.1), 0 4px 12px rgba(0,0,0,0.3); }",
            config.bg_color, config.rounding, config.font_size, entry_bg, config.fg_color, config.rounding, config.rounding, config.fg_color, row_font_size, config.sel_bg_color, config.sel_fg_color
        );
    }

    GtkCssProvider *provider = gtk_css_provider_new(); gtk_css_provider_load_from_data(provider, css, -1, NULL);
    gtk_style_context_add_provider_for_screen(gdk_screen_get_default(), GTK_STYLE_PROVIDER(provider), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    gtk_widget_show_all(main_window);
    if (dock_label) gtk_widget_hide(dock_label);
    if (strcmp(current_mode, "dock") != 0) populate_list("");
    gtk_main(); return 0;
}
