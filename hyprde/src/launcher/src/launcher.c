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
    char *icon;
    GAppInfo *info;
    char *math_result;
} App;

GtkWidget *main_window;
GtkWidget *centered_box;
GtkWidget *entry;
GtkWidget *listbox;
GList *apps = NULL;
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

void on_row_activated(GtkListBox *lb, GtkListBoxRow *row, gpointer user_data) {
    char *math = g_object_get_data(G_OBJECT(row), "math_result");
    if (math) {
        char *cmd = g_strdup_printf("echo -n '%s' | wl-copy", math);
        system(cmd);
        g_free(cmd);
        system("notify-send -t 2000 'Calculator' 'Copied to clipboard'");
    } else {
        GAppInfo *info = g_object_get_data(G_OBJECT(row), "app_info");
        if (info) g_app_info_launch(info, NULL, NULL, NULL);
    }
    gtk_main_quit();
}

gboolean on_key_press(GtkWidget *widget, GdkEventKey *event, gpointer user_data) {
    if (event->keyval == GDK_KEY_Escape) {
        gtk_main_quit();
        return TRUE;
    }
    if (!gtk_widget_has_focus(entry)) {
        if (event->keyval != GDK_KEY_Up && event->keyval != GDK_KEY_Down && 
            event->keyval != GDK_KEY_Return && event->keyval != GDK_KEY_KP_Enter) {
            gtk_widget_grab_focus(entry);
            return FALSE;
        }
    } else if (event->keyval == GDK_KEY_Down) {
        gtk_widget_grab_focus(listbox);
        return TRUE;
    }
    return FALSE;
}

gboolean on_button_press(GtkWidget *widget, GdkEventButton *event, gpointer user_data) {
    GtkAllocation alloc;
    gtk_widget_get_allocation(centered_box, &alloc);
    if (event->x < alloc.x || event->x > alloc.x + alloc.width ||
        event->y < alloc.y || event->y > alloc.y + alloc.height) {
        gtk_main_quit();
    }
    return FALSE;
}

char* try_math(const char *query) {
    if (strlen(query) < 3) return NULL;
    if (!strpbrk(query, "+-*/^")) return NULL;
    char *cmd = g_strdup_printf("qalc -t '%s'", query);
    char *output = NULL;
    if (g_spawn_command_line_sync(cmd, &output, NULL, NULL, NULL)) {
        g_free(cmd);
        if (output) {
            char *trimmed = g_strstrip(output);
            if (strlen(trimmed) > 0) return trimmed;
            g_free(output);
        }
    } else {
        g_free(cmd);
    }
    return NULL;
}

void populate_list(const char *query) {
    GList *children = gtk_container_get_children(GTK_CONTAINER(listbox));
    for (GList *l = children; l != NULL; l = l->next) {
        gtk_container_remove(GTK_CONTAINER(listbox), GTK_WIDGET(l->data));
    }
    g_list_free(children);

    int count = 0;
    
    char *math_res = try_math(query);
    if (math_res) {
        GtkWidget *row = gtk_list_box_row_new();
        g_object_set_data_full(G_OBJECT(row), "math_result", g_strdup(math_res), g_free);
        GtkWidget *hbox = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 15);
        gtk_container_set_border_width(GTK_CONTAINER(hbox), 8);
        GtkWidget *icon = gtk_image_new_from_icon_name("accessories-calculator", GTK_ICON_SIZE_DND);
        gtk_image_set_pixel_size(GTK_IMAGE(icon), 28);
        gtk_box_pack_start(GTK_BOX(hbox), icon, FALSE, FALSE, 0);
        char *label_text = g_strdup_printf("%s = %s", query, math_res);
        gtk_box_pack_start(GTK_BOX(hbox), gtk_label_new(label_text), TRUE, TRUE, 0);
        g_free(label_text);
        gtk_container_add(GTK_CONTAINER(row), hbox);
        gtk_container_add(GTK_CONTAINER(listbox), row);
        count++;
        g_free(math_res);
    }

    for (GList *l = apps; l != NULL; l = l->next) {
        App *app = (App*)l->data;
        if (!query || strlen(query) == 0 || g_strrstr(g_ascii_strdown(app->name, -1), g_ascii_strdown(query, -1))) {
            GtkWidget *row = gtk_list_box_row_new();
            g_object_set_data(G_OBJECT(row), "app_info", app->info);
            GtkWidget *hbox = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 15);
            gtk_container_set_border_width(GTK_CONTAINER(hbox), 8);
            GtkWidget *icon = gtk_image_new_from_icon_name(app->icon, GTK_ICON_SIZE_DND);
            gtk_image_set_pixel_size(GTK_IMAGE(icon), 28);
            gtk_box_pack_start(GTK_BOX(hbox), icon, FALSE, FALSE, 0);
            gtk_box_pack_start(GTK_BOX(hbox), gtk_label_new(app->name), TRUE, TRUE, 0);
            gtk_container_add(GTK_CONTAINER(row), hbox);
            gtk_container_add(GTK_CONTAINER(listbox), row);
            if (++count > 100) break;
        }
    }
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
            GIcon *gicon = g_app_info_get_icon(info);
            app->icon = gicon ? g_icon_to_string(gicon) : g_strdup("system-run");
            app->info = g_object_ref(info);
            apps = g_list_append(apps, app);
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
    g_signal_connect(entry, "changed", G_CALLBACK(on_search_changed), NULL);
    g_signal_connect(entry, "activate", G_CALLBACK(gtk_main_quit), NULL);
    gtk_box_pack_start(GTK_BOX(centered_box), entry, FALSE, FALSE, 10);

    GtkWidget *scrolled = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scrolled), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    gtk_box_pack_start(GTK_BOX(centered_box), scrolled, TRUE, TRUE, 0);
    listbox = gtk_list_box_new();
    g_signal_connect(listbox, "row-activated", G_CALLBACK(on_row_activated), NULL);
    gtk_container_add(GTK_CONTAINER(scrolled), listbox);

    g_signal_connect(main_window, "key-press-event", G_CALLBACK(on_key_press), NULL);
    g_signal_connect(main_window, "button-press-event", G_CALLBACK(on_button_press), NULL);

    char *css = g_strdup_printf(
        "window { background-color: transparent; }"
        "#main-window { background-color: %s; border-radius: 10px; }"
        "entry { font-size: 20px; padding: 10px; background: %s; color: %s; border: none; }"
        "row { color: %s; }"
        "row:selected { background-color: %s; color: %s; }",
        current_theme.bg, current_theme.entry_bg, current_theme.fg, current_theme.fg, current_theme.sel_bg, current_theme.sel_fg
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