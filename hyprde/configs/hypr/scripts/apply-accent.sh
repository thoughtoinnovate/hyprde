#!/bin/bash
# apply-accent.sh — fan out the accent color to every component.
#
# Usage: apply-accent.sh "#007aff" | "rgba(0, 122, 255, 1.0)"
#
# The settings accent picker only used to rewrite `@define-color
# theme_accent`, which almost nothing consumes — toggles, selections,
# notification borders and Mako all run on other variables / hardcoded
# colors, so accent changes appeared to do nothing. This script updates
# every accent-tracking definition in both theme files plus the Mako
# configs. Callers (settings Apply, theme-ctrl.sh) handle reload/restart.
#
# Accent-tracking definitions (all #007aff by default in both themes):
#   theme_accent, theme_active_bg, theme_success_bg, theme_wofi_sel_bg,
#   theme_notif_border (rgba form), Mako border-color (hex + alpha suffix)

ACCENT_RAW="${1:-}"
if [ -z "$ACCENT_RAW" ]; then
    echo "Usage: $0 <color>" >&2
    exit 1
fi

# Normalize any CSS color to #RRGGBB + "R G B" decimals (stdlib only).
read -r ACCENT_HEX ACCENT_R ACCENT_G ACCENT_B _ALPHA <<<"$($(
    command -v /usr/bin/python3 || command -v python3
) - "$ACCENT_RAW" <<'PYEOF' 2>/dev/null
import re
import sys
raw = sys.argv[1].strip()
r = g = b = 0
m = re.match(r'#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$', raw)
if m:
    r, g, b = (int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
else:
    m = re.match(
        r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*'
        r'(?:,\s*([0-9.]+)\s*)?\)', raw)
    if not m:
        raise SystemExit(f"cannot parse color: {raw}")
    r, g, b = (max(0, min(255, int(m.group(i)))) for i in (1, 2, 3))
print(f"#{r:02x}{g:02x}{b:02x} {r} {g} {b} x")
PYEOF
)"
if [ -z "$ACCENT_HEX" ]; then
    echo "apply-accent.sh: cannot parse color '$ACCENT_RAW'" >&2
    exit 1
fi

THEMES_DIR="$HOME/.config/hypr/themes"
FAILED=0

for css_file in "$THEMES_DIR/dark.css" "$THEMES_DIR/light.css"; do
    [ -f "$css_file" ] || continue
    # Snapshot alpha of the current notif border so we preserve it.
    old_rgba=$(grep -o '@define-color theme_notif_border [^;]*;' "$css_file" | head -1 || true)
    old_alpha=$(printf '%s' "$old_rgba" | grep -o '[0-9.]*)\s*$' | tr -d ') ' || true)
    [ -n "$old_alpha" ] || old_alpha="0.9"
    notif_rgba="rgba(${ACCENT_R}, ${ACCENT_G}, ${ACCENT_B}, ${old_alpha})"
    sed -i \
        -e "s/@define-color theme_accent [^;]*;/@define-color theme_accent ${ACCENT_HEX};/" \
        -e "s/@define-color theme_active_bg [^;]*;/@define-color theme_active_bg ${ACCENT_HEX};/" \
        -e "s/@define-color theme_success_bg [^;]*;/@define-color theme_success_bg ${ACCENT_HEX};/" \
        -e "s/@define-color theme_wofi_sel_bg [^;]*;/@define-color theme_wofi_sel_bg ${ACCENT_HEX};/" \
        -e "s|@define-color theme_notif_border [^;]*;|@define-color theme_notif_border ${notif_rgba};|" \
        "$css_file" || FAILED=1
done

# Mako: border-color=#RRGGBBAA — replace the RGB part, keep file's alpha.
for mako_cfg in "$HOME/.config/mako/config.dark" "$HOME/.config/mako/config.light"; do
    [ -f "$mako_cfg" ] || continue
    old_aa=$(grep -o '^border-color=#[0-9a-fA-F]*' "$mako_cfg" | head -1 | grep -o '[0-9a-fA-F]\{2\}$' || true)
    [ -n "$old_aa" ] || old_aa="4d"
    sed -i "s|^border-color=#[0-9a-fA-F]*|border-color=${ACCENT_HEX}${old_aa}|" "$mako_cfg" || FAILED=1
done

# Apply to GTK3 and GTK4 apps
for GTK_DIR in "$HOME/.config/gtk-3.0" "$HOME/.config/gtk-4.0"; do
    mkdir -p "$GTK_DIR"
    GTK_CSS="$GTK_DIR/gtk.css"
    if [ ! -f "$GTK_CSS" ]; then
        touch "$GTK_CSS"
    fi
    
    # If the variables don't exist, append them
    if ! grep -q "@define-color accent_bg_color" "$GTK_CSS"; then
        echo "@define-color accent_color ${ACCENT_HEX};" >> "$GTK_CSS"
        echo "@define-color accent_bg_color ${ACCENT_HEX};" >> "$GTK_CSS"
        echo "@define-color accent_fg_color #ffffff;" >> "$GTK_CSS"
    else
        # Otherwise replace them inline
        sed -i -e "s/@define-color accent_color .*/@define-color accent_color ${ACCENT_HEX};/" \
               -e "s/@define-color accent_bg_color .*/@define-color accent_bg_color ${ACCENT_HEX};/" \
               -e "s/@define-color accent_fg_color .*/@define-color accent_fg_color #ffffff;/" \
               "$GTK_CSS"
    fi
done

# Force GTK apps to live-reload CSS by briefly toggling theme states
CURRENT_THEME=$(gsettings get org.gnome.desktop.interface gtk-theme 2>/dev/null || echo "'Adwaita-dark'")
CURRENT_SCHEME=$(gsettings get org.gnome.desktop.interface color-scheme 2>/dev/null || echo "'prefer-dark'")

if [[ "$CURRENT_THEME" == *"'Adwaita-dark'"* ]]; then
    gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita'
else
    gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita-dark'
fi

if [[ "$CURRENT_SCHEME" == *"'prefer-dark'"* ]]; then
    gsettings set org.gnome.desktop.interface color-scheme 'prefer-light'
else
    gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
fi

# Restore settings immediately
gsettings set org.gnome.desktop.interface gtk-theme "$CURRENT_THEME"
gsettings set org.gnome.desktop.interface color-scheme "$CURRENT_SCHEME"

exit $FAILED
