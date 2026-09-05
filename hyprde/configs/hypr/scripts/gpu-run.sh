#!/bin/bash
# GPU app launcher: run any app on the discrete AMD GPU via PRIME offload.
# Usage: gpu-run.sh [command...]   (no args -> app picker via hyprsearch dmenu)
# Env: DRI_PRIME=1 + AMD_VULKAN_ICD=RADV (Mesa GL + Vulkan radv).

# Load Icons (best-effort: keep script functional without them)
if [ -f "$HOME/.config/hypr/scripts/hyprrocket.icons" ]; then
    # shellcheck disable=SC1091
    source "$HOME/.config/hypr/scripts/hyprrocket.icons"
fi
: "${POWER_MODE_HIGH:=󰐧}"

notify() {
    if command -v notify-send >/dev/null 2>&1; then
        notify-send -t 2000 "$1" "$2"
    fi
}

GPU_ENV="env DRI_PRIME=1 AMD_VULKAN_ICD=RADV"

launch_gpu() {
    # shellcheck disable=SC2086
    nohup $GPU_ENV "$@" >/dev/null 2>&1 &
    disown 2>/dev/null || true
    local renderer
    renderer=$(DRI_PRIME=1 glxinfo -B 2>/dev/null | grep -m1 "renderer string" | cut -d: -f2 | xargs)
    notify "AMD GPU $POWER_MODE_HIGH" "$* ${renderer:+($renderer)}"
}

# Direct mode: bypass picker
if [ $# -gt 0 ]; then
    launch_gpu "$@"
    exit 0
fi

LAUNCHER="$HOME/.config/hypr/scripts/hyprsearch"
if [ ! -x "$LAUNCHER" ]; then
    LAUNCHER="hyprsearch"
fi
if ! command -v "$LAUNCHER" >/dev/null 2>&1 && [ ! -x "$LAUNCHER" ]; then
    notify "Error" "hyprsearch not found"
    exit 1
fi

# Build Name -> Exec map from .desktop files (dedupe by Name, prefer user-local)
declare -A APP_EXEC
while IFS= read -r desktop; do
    name=$(grep -m1 "^Name=" "$desktop" 2>/dev/null | cut -d= -f2-)
    exec_line=$(grep -m1 "^Exec=" "$desktop" 2>/dev/null | cut -d= -f2-)
    [ -z "$name" ] || [ -z "$exec_line" ] && continue
    # Skip entries already seen (user-local dir scanned first, wins)
    # shellcheck disable=SC2034
    if [ -z "${APP_EXEC[$name]+x}" ]; then
        APP_EXEC[$name]="$exec_line"
    fi
done < <(find ~/.local/share/applications /usr/share/applications -maxdepth 1 -name "*.desktop" 2>/dev/null | sort -u)

if [ "${#APP_EXEC[@]}" -eq 0 ]; then
    notify "Error" "No applications found"
    exit 1
fi

selected=$(printf '%s\n' "${!APP_EXEC[@]}" | sort | "$LAUNCHER" --dmenu --prompt "Run on AMD GPU:")
[ -z "$selected" ] && exit 0

exec_line="${APP_EXEC[$selected]}"
# Strip .desktop field codes (%U %F %u %f %i %c %k %d %D %n %N %v %m)
# shellcheck disable=SC2206
cleaned=($exec_line)
cmd=()
for token in "${cleaned[@]}"; do
    case "$token" in
        %*) continue ;;
        *) cmd+=("$token") ;;
    esac
done
if [ "${#cmd[@]}" -eq 0 ]; then
    notify "Error" "Empty Exec for $selected"
    exit 1
fi
launch_gpu "${cmd[@]}"
