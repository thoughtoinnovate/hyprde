#!/bin/bash
# Power Mode switcher: balanced / high / saver / auto (CPU speed only, no kills)
# saver  = super power saving: hardware at minimum (cap 30, turbo off, EPP power)
# auto   = AC -> high, battery -> balanced. Boot default: balanced.
# State lives in tmpfs so it never persists across reboot (by design).

# Load Icons (best-effort: keep script functional without them)
if [ -f "$HOME/.config/hypr/scripts/hyprrocket.icons" ]; then
    # shellcheck disable=SC1091
    source "$HOME/.config/hypr/scripts/hyprrocket.icons"
fi
: "${POWER_MODE_BALANCED:=󰾅}"
: "${POWER_MODE_HIGH:=󰐧}"
: "${POWER_MODE_AUTO:=󰑮}"
: "${POWER_ICON_SAVER:=󰈐}"

STATE_DIR="${XDG_RUNTIME_DIR:-/tmp/hyprde-$UID}/hyprde"
STATE_FILE="$STATE_DIR/power-mode"

PSTATE_BASE="/sys/devices/system/cpu/intel_pstate"
# Explicit per-CPU list (no wildcards) so every written path matches the
# hardened sudoers rule 1:1. Adjust range if core count ever changes.
EPP_CPUS="0 1 2 3 4 5 6 7"
epp_node() {
    printf '/sys/devices/system/cpu/cpu%s/cpufreq/energy_performance_preference' "$1"
}

notify() {
    if command -v notify-send >/dev/null 2>&1; then
        notify-send -t 1500 "$1" "$2"
    fi
}

get_mode() {
    if [ -f "$STATE_FILE" ]; then
        local m
        m=$(cat "$STATE_FILE" 2>/dev/null | tr -d '[:space:]')
        case "$m" in
            balanced|high|auto|saver) printf '%s' "$m"; return ;;
        esac
    fi
    printf 'balanced'
}

save_mode() {
    # Private dirs only (umask, since mkdir -p -m covers just the leaf)
    umask 077
    mkdir -p "$STATE_DIR" 2>/dev/null || true
    # Refuse to follow a pre-existing symlink (tmp squatting protection)
    if [ -L "$STATE_FILE" ]; then
        rm -f "$STATE_FILE" 2>/dev/null || return 1
    fi
    printf '%s' "$1" > "$STATE_FILE" 2>/dev/null || true
}

# ac|bat — power source, never drives TLP, display only + auto resolution
detect_source() {
    local online
    for f in /sys/class/power_supply/AC*/online /sys/class/power_supply/ADP*/online; do
        if [ -f "$f" ]; then
            online=$(cat "$f" 2>/dev/null | tr -d '[:space:]')
            if [ "$online" = "1" ]; then
                printf 'ac'
                return
            fi
        fi
    done
    if command -v upower >/dev/null 2>&1; then
        local bat state
        bat=$(upower -e 2>/dev/null | grep -i bat | head -1)
        if [ -n "$bat" ]; then
            state=$(upower -i "$bat" 2>/dev/null | awk -F: '/^[[:space:]]*state/ {gsub(/[[:space:]]/, "", $2); print $2}')
            case "$state" in
                charging|fully-charged|pending-charge)
                    printf 'ac'
                    return
                    ;;
            esac
        fi
    fi
    printf 'bat'
}

# Write one sysfs node. Only ever called with fixed power-control paths/values.
# Returns 0 on success. Respects HYPRDE_POWER_NO_AUTH=1 (state-only mode).
write_node() {
    local node="$1" value="$2"
    [ -n "${HYPRDE_POWER_NO_AUTH:-}" ] && return 1
    if [ -w "$node" ]; then
        printf '%s' "$value" > "$node" 2>/dev/null && return 0
    fi
    # Best-effort via passwordless sudo (non-interactive, silent on failure)
    printf '%s' "$value" | sudo -n tee "$node" >/dev/null 2>&1 && return 0
    return 1
}

# Single privileged batch for all unwritten nodes -> at most ONE auth popup
# per mode switch (never one popup per CPU). No-op when NO_AUTH is set.
privileged_batch() {
    local batch="$1"
    [ -n "$batch" ] || return 0
    [ -n "${HYPRDE_POWER_NO_AUTH:-}" ] && return 1
    printf '%s' "$batch" | sudo -n sh >/dev/null 2>&1 && return 0
    # Last resort: polkit auth dialog (desktop sessions only, never headless)
    if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && command -v pkexec >/dev/null 2>&1; then
        printf '%s' "$batch" | pkexec sh >/dev/null 2>&1 && return 0
    fi
    return 1
}

apply_profile() {
    local profile="$1" cap turbo epp
    if [ "$profile" = "high" ]; then
        cap=100; turbo=0; epp="performance"
    elif [ "$profile" = "saver" ]; then
        cap=30; turbo=1; epp="power"
    else
        cap=70; turbo=1; epp="balance_power"
    fi
    local ok=0 fail=0 i f pending=""
    if [ -f "$PSTATE_BASE/max_perf_pct" ]; then
        write_node "$PSTATE_BASE/max_perf_pct" "$cap" && ok=$((ok+1)) || pending="${pending}printf '%s' '$cap' >'$PSTATE_BASE/max_perf_pct';"
    fi
    if [ -f "$PSTATE_BASE/no_turbo" ]; then
        write_node "$PSTATE_BASE/no_turbo" "$turbo" && ok=$((ok+1)) || pending="${pending}printf '%s' '$turbo' >'$PSTATE_BASE/no_turbo';"
    fi
    for i in $EPP_CPUS; do
        f=$(epp_node "$i")
        [ -f "$f" ] || continue
        # shellcheck disable=SC2016
        write_node "$f" "$epp" && ok=$((ok+1)) || pending="${pending}printf '%s' '$epp' >'$f';"
    done
    # One privileged batch for everything direct write couldn't handle
    if [ -n "$pending" ]; then
        if privileged_batch "$pending"; then
            ok=$((ok+1))
        else
            fail=$((fail+1))
        fi
    fi
    if [ "$fail" -gt 0 ] && [ "$ok" -eq 0 ]; then
        notify "Power Mode" "Could not write CPU nodes (need sudo?). Mode saved, values unchanged."
    fi
}

resolve_auto() {
    if [ "$(detect_source)" = "ac" ]; then
        printf 'high'
    else
        printf 'balanced'
    fi
}

current_values() {
    local cap="?" epp="?" turbo="?"
    [ -f "$PSTATE_BASE/max_perf_pct" ] && cap=$(cat "$PSTATE_BASE/max_perf_pct" 2>/dev/null | tr -d '[:space:]')
    [ -f "$PSTATE_BASE/no_turbo" ] && turbo=$(cat "$PSTATE_BASE/no_turbo" 2>/dev/null | tr -d '[:space:]')
    local first_epp="" i f
    for i in $EPP_CPUS; do
        f=$(epp_node "$i")
        [ -f "$f" ] || continue
        first_epp="$f"
        break
    done
    [ -n "$first_epp" ] && epp=$(cat "$first_epp" 2>/dev/null | tr -d '[:space:]')
    printf '%s|%s|%s' "$cap" "$epp" "$turbo"
}

get_status() {
    local mode profile src icon tooltip class pct vals cap epp
    mode=$(get_mode)
    src=$(detect_source | tr '[:lower:]' '[:upper:]')
    profile="$mode"
    [ "$mode" = "auto" ] && profile=$(resolve_auto)
    vals=$(current_values)
    cap=${vals%%|*}; epp=$(printf '%s' "$vals" | cut -d'|' -f2)
    case "$mode" in
        high)
            icon="$POWER_MODE_HIGH"; class="high"; pct=100
            tooltip="High Performance · cap $cap · $epp · $src"
            ;;
        saver)
            icon="$POWER_ICON_SAVER"; class="saver"; pct=20
            tooltip="Power Saver · cap $cap · $epp · $src"
            ;;
        auto)
            icon="$POWER_MODE_AUTO"; class="auto"; pct=70
            [ "$profile" = "high" ] && pct=100
            tooltip="Automatic ($profile) · cap $cap · $epp · $src"
            ;;
        *)
            icon="$POWER_MODE_BALANCED"; class="balanced"; pct=70
            tooltip="Balanced · cap $cap · $epp · $src"
            ;;
    esac
    echo "{\"text\": \"$icon\", \"alt\": \"$mode\", \"tooltip\": \"$tooltip\", \"class\": \"$class\", \"percentage\": $pct}"
}

set_mode() {
    local mode="$1" profile label
    save_mode "$mode"
    profile="$mode"
    [ "$mode" = "auto" ] && profile=$(resolve_auto)
    apply_profile "$profile"
    case "$mode" in
        high)  label="High Performance $POWER_MODE_HIGH — turbo on, caps off" ;;
        saver) label="Power Saver $POWER_ICON_SAVER — hardware at minimum (cap 30)" ;;
        auto)  label="Automatic $POWER_MODE_AUTO — following power source ($profile)" ;;
        *)     label="Balanced $POWER_MODE_BALANCED — cap 70, turbo off" ;;
    esac
    notify "Power Mode" "$label"
    get_status
}

case "$1" in
    status)
        get_status
        ;;
    balanced|high|auto|saver)
        set_mode "$1"
    pkill -RTMIN+7 waybar || true
        ;;
    cycle)
        case "$(get_mode)" in
            balanced) set_mode "high" ;;
            high)     set_mode "auto" ;;
            auto)     set_mode "saver" ;;
            *)        set_mode "balanced" ;;
        esac
        ;;
    --event)
        # udev / resume / timer hook: only acts in auto mode
        [ "$(get_mode)" = "auto" ] && { apply_profile "$(resolve_auto)"; }
        get_status
        ;;
    install-auto)
        # systemd user timer: re-evaluate auto mode every 60s (AC plug/unplug,
        # resume from suspend). Cheap: two sysfs reads + one upower call.
        unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
        mkdir -p "$unit_dir"
        cat > "$unit_dir/hyprde-power-auto.service" <<'EOF'
[Unit]
Description=HyprDE power-mode auto re-evaluation

[Service]
Type=oneshot
ExecStart=%h/.config/hypr/scripts/power-mode.sh --event
EOF
        cat > "$unit_dir/hyprde-power-auto.timer" <<'EOF'
[Unit]
Description=HyprDE power-mode auto re-evaluation timer

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min

[Install]
WantedBy=timers.target
EOF
        systemctl --user daemon-reload
        systemctl --user enable --now hyprde-power-auto.timer
        notify "Power Mode" "Automatic switching installed (60s poll)"
        ;;
    uninstall-auto)
        systemctl --user disable --now hyprde-power-auto.timer 2>/dev/null || true
        rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/hyprde-power-auto.service" \
              "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/hyprde-power-auto.timer"
        systemctl --user daemon-reload
        notify "Power Mode" "Automatic switching removed"
        ;;
    *)
        echo "{\"text\": \"Usage: $0 {status|balanced|high|auto|saver|cycle|install-auto|uninstall-auto}\", \"class\": \"balanced\"}"
        exit 1
        ;;
esac
