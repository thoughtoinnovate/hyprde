#!/bin/bash
# Sandboxed preview wrapper for Arch, Debian, and macOS

# Clear previous preview
printf '\033[2J\033[H'

file="$1"
[ -z "$file" ] && exit 1
[ ! -e "$file" ] && exit 1

# Find preview script - use absolute paths
script_dir="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$HOME/.config/hypr/scripts/fzf-prev.sh" ]; then
    preview_script="$HOME/.config/hypr/scripts/fzf-prev.sh"
    scripts_dir="$HOME/.config/hypr/scripts"
else
    preview_script="$script_dir/fzf-prev.sh"
    scripts_dir="$script_dir"
fi

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/fzf-pdf-previews"
mkdir -p "$cache_dir" 2>/dev/null

case "$(uname -s)" in
    Linux)
        if command -v firejail >/dev/null 2>&1; then
            firejail --quiet --net=none --nonewprivs --noroot \
                --private-dev \
                --read-only="$HOME" \
                --read-write="$cache_dir" \
                --whitelist="$file" \
                --whitelist="$scripts_dir" \
                --whitelist="$cache_dir" \
                -- "$preview_script" "$file"
        elif command -v bwrap >/dev/null 2>&1; then
            bwrap \
                --ro-bind /usr /usr \
                --ro-bind /bin /bin \
                --ro-bind /lib /lib \
                --ro-bind /lib64 /lib64 2>/dev/null \
                --ro-bind /etc /etc \
                --ro-bind "$file" "$file" \
                --ro-bind "$scripts_dir" "$scripts_dir" \
                --bind "$cache_dir" "$cache_dir" \
                --unshare-net \
                --unshare-pid \
                --die-with-parent \
                -- "$preview_script" "$file"
        else
            "$preview_script" "$file"
        fi
        ;;
    Darwin)
        sandbox-exec -p "(version 1)
(allow default)
(deny network*)
(deny file-write*)
(allow file-write* (subpath \"$cache_dir\"))
(allow file-write* (subpath \"/dev\"))
(allow file-write* (subpath \"/private/var\"))" "$preview_script" "$file"
        ;;
    *)
        "$preview_script" "$file"
        ;;
esac
