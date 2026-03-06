#include <gtk/gtk.h>
#include <gtk-layer-shell/gtk-layer-shell.h>
#include <gio/gio.h>
#include <string.h>
#include <stdlib.h>

typedef struct {
    char *bg;
    char *fg;
    char *sel_bg;
    char *sel_fg;
    char *entry_bg;
    char *border;
} Theme;

typedef struct {
    char *name;
    char *name_lower;
    char *icon;
    GAppInfo *info;
} App;

GtkWidget *main_window;
GtkWidget *centered_box;
GtkWidget *entry;
GtkWidget *listbox;
GtkWidget *scrolled_window;
GList *apps_list = NULL;
Theme current_theme;

char* extract_color(const char *line) {
    const char *first_space = strchr(line, ' ');
    if (!first_space) return NULL;
    const char *second_space = strchr(first_space + 1, ' ');
    if (!second_space) return NULL;
    const char *start = second_space + 1;
    const char *semi = strchr(start, ';');
    if (!semi) return NULL;
    return g_strndup(start, semi - start);
}

void load_theme() {
    current_theme.bg = g_strdup("rgba(30, 30, 30, 0.95)");
    current_theme.fg = g_strdup("#ffffff");
    current_theme.sel_bg = g_strdup("#33ccff");
    current_theme.sel_fg = g_strdup("#000000");
    current_theme.entry_bg = g_strdup("rgba(255, 255, 255, 0.05)");
    current_theme.border = g_strdup("rgba(255, 255, 255, 0.1)");

    char *path = g_build_filename(g_get_home_dir(), ".config/hypr/themes/current.css", NULL);
    char *content = NULL;
    if (g_file_get_contents(path, &content, NULL, NULL)) {
        char **lines = g_strsplit(content, "\n", -1);
        for (int i = 0; lines[i] != NULL; i++) {
            if (strstr(lines[i], "@define-color theme_wofi_bg_alpha")) {
                g_free(current_theme.bg);
                current_theme.bg = extract_color(lines[i]);
            } else if (strstr(lines[i], "@define-color theme_wofi_fg")) {
                g_free(current_theme.fg);
                current_theme.fg = extract_color(lines[i]);
            } else if (strstr(lines[i], "@define-color theme_wofi_sel_bg")) {
                g_free(current_theme.sel_bg);
                current_theme.sel_bg = extract_color(lines[i]);
            } else if (strstr(lines[i], "@define-color theme_wofi_sel_fg")) {
                g_free(current_theme.sel_fg);
                current_theme.sel_fg = extract_color(lines[i]);
            }
        }
        g_strfreev(lines);
        g_free(content);
    }
    g_free(path);
}

void quit_launcher() {
    gtk_main_quit();
}

void on_row_activated(GtkListBox *lb, GtkListBoxRow *row, gpointer user_data) {
    if (!row) return;
    char *math = g_object_get_data(G_OBJECT(row), "math_result");
    if (math) {
        char *cmd = g_strdup_printf("echo -n '%s' | wl-copy", math);
        system(cmd);
        g_free(cmd);
        system("notify-send -t 2000 'Calculator' 'Copied to clipboard'");
    } else {
        App *app = g_object_get_data(G_OBJECT(row), "app_data");
        if (app && app->info) {
            GdkAppLaunchContext *context = gdk_display_get_app_launch_context(gdk_display_get_default());
            GError *error = NULL;
            if (!g_app_info_launch(app->info, NULL, G_APP_LAUNCH_CONTEXT(context), &error)) {
                g_warning("Launch failed: %s", error->message);
                g_error_free(error);
            }
            g_object_unref(context);
        }
    }
    quit_launcher();
}

gboolean on_list_motion(GtkWidget *widget, GdkEventMotion *event, gpointer user_data) {
    GtkListBoxRow *row = gtk_list_box_get_row_at_y(GTK_LIST_BOX(listbox), (int)event->y);
    if (row) {
        gtk_list_box_select_row(GTK_LIST_BOX(listbox), row);
    }
    return FALSE;
}

gboolean on_list_button_press(GtkWidget *widget, GdkEventButton *event, gpointer user_data) {
    if (event->button == 1) { // Left click
        GtkListBoxRow *row = gtk_list_box_get_row_at_y(GTK_LIST_BOX(listbox), (int)event->y);
        if (row) {
            on_row_activated(GTK_LIST_BOX(listbox), row, NULL);
            return TRUE;
        }
    }
    return FALSE;
}

gboolean on_key_press(GtkWidget *widget, GdkEventKey *event, gpointer user_data) {
    if (event->keyval == GDK_KEY_Escape) {
        quit_launcher();
        return TRUE;
    }
    
    if (event->keyval == GDK_KEY_Down || event->keyval == GDK_KEY_Up) {
        GtkListBoxRow *row = gtk_list_box_get_selected_row(GTK_LIST_BOX(listbox));
        int idx = row ? gtk_list_box_row_get_index(row) : -1;
        int new_idx = (event->keyval == GDK_KEY_Down) ? idx + 1 : idx - 1;
        
        GtkListBoxRow *target = gtk_list_box_get_row_at_index(GTK_LIST_BOX(listbox), new_idx);
        if (target) {
            gtk_list_box_select_row(GTK_LIST_BOX(listbox), target);
            
            GtkAdjustment *adj = gtk_scrolled_window_get_vadjustment(GTK_SCROLLED_WINDOW(scrolled_window));
            GtkAllocation r_alloc;
            gtk_widget_get_allocation(GTK_WIDGET(target), &r_alloc);
            
            int ty;
            gtk_widget_translate_coordinates(GTK_WIDGET(target), GTK_WIDGET(listbox), 0, 0, NULL, &ty);
            
            double current_val = gtk_adjustment_get_value(adj);
            double page_size = gtk_adjustment_get_page_size(adj);
            
            if (ty < current_val) {
                gtk_adjustment_set_value(adj, ty);
            } else if (ty + r_alloc.height > current_val + page_size) {
                gtk_adjustment_set_value(adj, ty + r_alloc.height - page_size);
            }
        }
        return TRUE;
    }

    if (event->keyval == GDK_KEY_Return || event->keyval == GDK_KEY_KP_Enter) {
        GtkListBoxRow *row = gtk_list_box_get_selected_row(GTK_LIST_BOX(listbox));
        if (row) on_row_activated(GTK_LIST_BOX(listbox), row, NULL);
        return TRUE;
    }
    
    if (!gtk_widget_has_focus(entry)) {
        if ((event->keyval >= 32 && event->keyval <= 126) || event->keyval == GDK_KEY_BackSpace) {
            gtk_widget_grab_focus(entry);
            return FALSE;
        }
    }
    return FALSE;
}

gboolean on_main_button_press(GtkWidget *widget, GdkEventButton *event, gpointer user_data) {
    GtkAllocation alloc;
    gtk_widget_get_allocation(centered_box, &alloc);
    if (event->x < alloc.x || event->x > alloc.x + alloc.width ||
        event->y < alloc.y || event->y > alloc.y + alloc.height) {
        quit_launcher();
        return TRUE;
    }
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
            if (strlen(trimmed) > 0 && strchr(trimmed, '=') == NULL) return trimmed;
            g_free(output);
        }
    } else { g_free(cmd); }
    return NULL;
}

void populate_list(const char *query) {
    GList *children = gtk_container_get_children(GTK_CONTAINER(listbox));
    for (GList *l = children; l != NULL; l = l->next) {
        gtk_container_remove(GTK_CONTAINER(listbox), GTK_WIDGET(l->data));
    }
    g_list_free(children);

    int count = 0;
    char *query_lower = query ? g_ascii_strdown(query, -1) : NULL;
    
    char *math_res = try_math(query);
    if (math_res) {
        GtkWidget *row = gtk_list_box_row_new();
        g_object_set_data_full(G_OBJECT(row), "math_result", g_strdup(math_res), g_free);
        GtkWidget *hbox = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 20);
        gtk_container_set_border_width(GTK_CONTAINER(hbox), 12);
        GtkWidget *icon = gtk_image_new_from_icon_name("accessories-calculator", GTK_ICON_SIZE_DND);
        gtk_image_set_pixel_size(GTK_IMAGE(icon), 32);
        gtk_box_pack_start(GTK_BOX(hbox), icon, FALSE, FALSE, 0);
        char *label_text = g_strdup_printf("%s = %s", query, math_res);
        GtkWidget *label = gtk_label_new(label_text);
        gtk_widget_set_halign(label, GTK_ALIGN_START);
        gtk_label_set_ellipsize(GTK_LABEL(label), PANGO_ELLIPSIZE_END);
        gtk_box_pack_start(GTK_BOX(hbox), label, TRUE, TRUE, 0);
        g_free(label_text);
        gtk_container_add(GTK_CONTAINER(row), hbox);
        gtk_container_add(GTK_CONTAINER(listbox), row);
        count++;
        g_free(math_res);
    }

    for (GList *l = apps_list; l != NULL; l = l->next) {
        App *app = (App*)l->data;
        if (!query_lower || strlen(query_lower) == 0 || strstr(app->name_lower, query_lower)) {
            GtkWidget *row = gtk_list_box_row_new();
            g_object_set_data(G_OBJECT(row), "app_data", app);
            GtkWidget *hbox = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 20);
            gtk_container_set_border_width(GTK_CONTAINER(hbox), 12);
            GtkWidget *icon = gtk_image_new_from_icon_name(app->icon, GTK_ICON_SIZE_DND);
            gtk_image_set_pixel_size(GTK_IMAGE(icon), 32);
            gtk_box_pack_start(GTK_BOX(hbox), icon, FALSE, FALSE, 0);
            GtkWidget *label = gtk_label_new(app->name);
            gtk_widget_set_halign(label, GTK_ALIGN_START);
            gtk_label_set_ellipsize(GTK_LABEL(label), PANGO_ELLIPSIZE_END);
            gtk_box_pack_start(GTK_BOX(hbox), label, TRUE, TRUE, 0);
            gtk_container_add(GTK_CONTAINER(row), hbox);
            gtk_container_add(GTK_CONTAINER(listbox), row);
            if (++count > 100) break;
        }
    }
    if (query_lower) g_free(query_lower);
    gtk_widget_show_all(listbox);
    if (count > 0) gtk_list_box_select_row(GTK_LIST_BOX(listbox), gtk_list_box_get_row_at_index(GTK_LIST_BOX(listbox), 0));
}

void on_search_changed(GtkEditable *e, gpointer user_data) {
    populate_list(gtk_entry_get_text(GTK_ENTRY(e)));
}

int main(int argc, char *argv[]) {
    gtk_init(&argc, &argv);
    load_theme();

    GList *all_infos = g_app_info_get_all();
    for (GList *l = all_infos; l != NULL; l = l->next) {
        GAppInfo *info = (GAppInfo*)l->data;
        if (g_app_info_should_show(info)) {
            App *app = g_new0(App, 1);
            app->name = g_strdup(g_app_info_get_name(info));
            app->name_lower = g_ascii_strdown(app->name, -1);
            GIcon *gicon = g_app_info_get_icon(info);
            app->icon = gicon ? g_icon_to_string(gicon) : g_strdup("system-run");
            app->info = g_object_ref(info);
            apps_list = g_list_append(apps_list, app);
        }
    }
    g_list_free_full(all_infos, g_object_unref);

    main_window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_layer_init_for_window(GTK_WINDOW(main_window));
    gtk_layer_set_namespace(GTK_WINDOW(main_window), "hyprde-spotlight");
    gtk_layer_set_layer(GTK_WINDOW(main_window), GTK_LAYER_SHELL_LAYER_OVERLAY);
    gtk_layer_set_keyboard_mode(GTK_WINDOW(main_window), GTK_LAYER_SHELL_KEYBOARD_MODE_EXCLUSIVE);
    gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_TOP, TRUE);
    gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_BOTTOM, TRUE);
    gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_LEFT, TRUE);
    gtk_layer_set_anchor(GTK_WINDOW(main_window), GTK_LAYER_SHELL_EDGE_RIGHT, TRUE);

    GtkWidget *outer = gtk_event_box_new();
    gtk_container_add(GTK_CONTAINER(main_window), outer);
    g_signal_connect(outer, "button-press-event", G_CALLBACK(on_main_button_press), NULL);

    centered_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_widget_set_name(centered_box, "main-window");
    gtk_widget_set_halign(centered_box, GTK_ALIGN_CENTER);
    gtk_widget_set_valign(centered_box, GTK_ALIGN_CENTER);
    
    GdkDisplay *display = gdk_display_get_default();
    GdkMonitor *monitor = gdk_display_get_primary_monitor(display);
    int width = 700, height = 600;
    if (monitor) {
        GdkRectangle geo;
        gdk_monitor_get_geometry(monitor, &geo);
        width = geo.width * 0.4;
        height = geo.height * 0.5;
    }
    gtk_widget_set_size_request(centered_box, width, height);
    gtk_container_add(GTK_CONTAINER(outer), centered_box);

    entry = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(entry), "Search Apps...");
    gtk_widget_set_margin_start(entry, 5);
    gtk_widget_set_margin_end(entry, 5);
    g_signal_connect(entry, "changed", G_CALLBACK(on_search_changed), NULL);
    g_signal_connect(entry, "key-press-event", G_CALLBACK(on_key_press), NULL);
    gtk_box_pack_start(GTK_BOX(centered_box), entry, FALSE, FALSE, 10);

    scrolled_window = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scrolled_window), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    gtk_box_pack_start(GTK_BOX(centered_box), scrolled_window, TRUE, TRUE, 0);
    
    listbox = gtk_list_box_new();
    gtk_list_box_set_selection_mode(GTK_LIST_BOX(listbox), GTK_SELECTION_BROWSE);
    g_signal_connect(listbox, "motion-notify-event", G_CALLBACK(on_list_motion), NULL);
    g_signal_connect(listbox, "button-press-event", G_CALLBACK(on_list_button_press), NULL);
    gtk_widget_add_events(listbox, GDK_POINTER_MOTION_MASK | GDK_BUTTON_PRESS_MASK);
    gtk_container_add(GTK_CONTAINER(scrolled_window), listbox);

    char *css = g_strdup_printf(
        "window { background-color: transparent; }"
        "#main-window { background-color: %s; border-radius: 16px; border: 1px solid rgba(51,204,255,0.3); box-shadow: 0 0 20px rgba(51,204,255,0.4), 0 10px 30px rgba(0,0,0,0.5); }"
        "entry { font-size: 24px; padding: 15px 30px; background: transparent; color: %s; border: none; border-bottom: 1px solid rgba(255,255,255,0.05); margin-bottom: 5px; }"
        "list { background: transparent; padding: 5px; }"
        "row { color: %s; font-size: 16px; border-radius: 8px; margin: 2px 10px; }"
        "row:selected { background-color: %s; color: %s; box-shadow: 0 0 10px %s; }",
        current_theme.bg, current_theme.fg, current_theme.fg, current_theme.sel_bg, current_theme.sel_fg, current_theme.sel_bg
    );
    GtkCssProvider *provider = gtk_css_provider_new();
    gtk_css_provider_load_from_data(provider, css, -1, NULL);
    gtk_style_context_add_provider_for_screen(gdk_screen_get_default(), GTK_STYLE_PROVIDER(provider), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    g_free(css);

    populate_list("");
    gtk_widget_show_all(main_window);
    gtk_main();
    return 0;
}