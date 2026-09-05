#!/bin/bash
# Power Mode switcher: balanced / high / auto (CPU speed only, no kills)
# auto = AC -> high, battery -> balanced. Boot default: balanced.
# State lives in tmpfs so it never persists across reboot (by design).

# Load Icons (best-effort: keep script functional without them)
if [ -f "$HOME/.config/hypr/scripts/hyprrocket.icons" ]; then
    # shellcheck disable=SC1091
    source "$HOME/.config/hypr/scripts/hyprrocket.icons"
fi
: "${POWER_MODE_BALANCED:=󰾅}"
: "${POWER_MODE_HIGH:=󰐧}"
: "${POWER_MODE_AUTO:=󰑮}"

STATE_DIR="${XDG_RUNTIME_DIR:-/tmp}/hyprde"
STATE_FILE="$STATE_DIR/power-mode"

PSTATE_BASE="/sys/devices/system/cpu/intel_pstate"
EPP_GLOB="/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference"

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
            balanced|high|auto) printf '%s' "$m"; return ;;
        esac
    fi
    printf 'balanced'
}

save_mode() {
    mkdir -p "$STATE_DIR" 2>/dev/null || true
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

write_node() {
    local node="$1" value="$2"
    if [ -w "$node" ]; then
        printf '%s' "$value" > "$node" 2>/dev/null && return 0
    fi
    # Best-effort via passwordless sudo (non-interactive, silent on failure)
    printf '%s' "$value" | sudo -n tee "$node" >/dev/null 2>&1 && return 0
    return 1
}

apply_profile() {
    local profile="$1" cap turbo epp
    if [ "$profile" = "high" ]; then
        cap=100; turbo=0; epp="performance"
    else
        cap=70; turbo=1; epp="balance_power"
    fi
    local ok=0 fail=0
    if [ -f "$PSTATE_BASE/max_perf_pct" ]; then
        write_node "$PSTATE_BASE/max_perf_pct" "$cap" && ok=$((ok+1)) || fail=$((fail+1))
    fi
    if [ -f "$PSTATE_BASE/no_turbo" ]; then
        write_node "$PSTATE_BASE/no_turbo" "$turbo" && ok=$((ok+1)) || fail=$((fail+1))
    fi
    local f
    for f in $EPP_GLOB; do
        [ -f "$f" ] || continue
        write_node "$f" "$epp" && ok=$((ok+1)) || fail=$((fail+1))
    done
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
    local first_epp=""
    for f in $EPP_GLOB; do
        # shellcheck disable=SC2231
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
        high) label="High Performance 🔥 — turbo on, caps off" ;;
        auto) label="Automatic 🤖 — following power source ($profile)" ;;
        *)    label="Balanced ⚖️ — cap 70, turbo off" ;;
    esac
    notify "Power Mode" "$label"
    get_status
}

case "$1" in
    status)
        get_status
        ;;
    balanced|high|auto)
        set_mode "$1"
        ;;
    cycle)
        case "$(get_mode)" in
            balanced) set_mode "high" ;;
            high)     set_mode "auto" ;;
            *)        set_mode "balanced" ;;
        esac
        ;;
    --event)
        # udev / resume / timer hook: only acts in auto mode
        [ "$(get_mode)" = "auto" ] && { apply_profile "$(resolve_auto)"; }
        get_status
        ;;
    *)
        echo "{\"text\": \"Usage: $0 {status|balanced|high|auto|cycle}\", \"class\": \"balanced\"}"
        exit 1
        ;;
esac
