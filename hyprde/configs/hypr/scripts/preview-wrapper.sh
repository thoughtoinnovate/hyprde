#!/bin/bash
# Secure preview wrapper using firejail for untrusted files
# Provides namespace isolation, no network, minimal filesystem access
# 
# SECURITY WARNING:
# - With firejail: Preview runs in sandbox (safe for untrusted files)
# - Without firejail: Preview runs unsandboxed (only safe for trusted files)
# 
# Install firejail for secure previews: sudo pacman -S firejail

set -e

# Debug log file for wrapper
readonly WRAPPER_DEBUG_LOG="/tmp/hyprde-wrapper-debug.log"

# Debounce configuration
readonly DEBOUNCE_MS=500
readonly DEBOUNCE_STATE_FILE="/tmp/hyprde-preview-debounce"

# Wrapper debug logging function
wrapper_debug_log() {
    return 0
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S.%3N')
    
    local message="$*"
    
    # Append to debug log
    {
        echo "=== [${timestamp}] WRAPPER - ${message}"
    } >> "${WRAPPER_DEBUG_LOG}"
    
    # Keep last 50 lines
    if [[ -f "${WRAPPER_DEBUG_LOG}" ]]; then
        local line_count
        line_count=$(wc -l < "${WRAPPER_DEBUG_LOG}" 2>/dev/null || echo 0)
        if [[ ${line_count} -gt 50 ]]; then
            tail -n 50 "${WRAPPER_DEBUG_LOG}" > "${WRAPPER_DEBUG_LOG}.tmp"
            mv "${WRAPPER_DEBUG_LOG}.tmp" "${WRAPPER_DEBUG_LOG}"
        fi
    fi
}

# Debounce: skip duplicate calls for same file within DEBOUNCE_MS
check_debounce() {
    local file="$1"
    local current_time
    current_time=$(date +%s%3N)
    
    if [[ -f "${DEBOUNCE_STATE_FILE}" ]]; then
        local last_file last_time time_diff
        last_file=$(cat "${DEBOUNCE_STATE_FILE}" 2>/dev/null | cut -d'|' -f1)
        last_time=$(cat "${DEBOUNCE_STATE_FILE}" 2>/dev/null | cut -d'|' -f2)
        time_diff=$((current_time - last_time))
        
        # Skip if same file previewed too recently
        if [[ "$last_file" == "$file" ]] && [[ $time_diff -lt $DEBOUNCE_MS ]]; then
            wrapper_debug_log "DEBOUNCE: Skipping duplicate for '${file}' (gap: ${time_diff}ms)"
            echo "" > /dev/null
            return 0
        fi
    fi
    
    # Record this preview
    echo "${file}|${current_time}" > "${DEBOUNCE_STATE_FILE}"
    wrapper_debug_log "DEBOUNCE: Processing '${file}' | Gap since last: $((current_time - last_time))ms"
    return 1
}

# Track wrapper start
script_start_time=$(date +%s%3N)
wrapper_debug_log "START - File: '$1' | PID: $$ | Firejail: $(command -v firejail >/dev/null 2>&1 && echo 'yes' || echo 'no')"

file="$1"
[ -z "$file" ] && exit 1
[ ! -e "$file" ] && exit 1

# Resolve absolute path for firejail whitelist
if command -v realpath >/dev/null 2>&1; then
    abs_file=$(realpath "$file")
else
    abs_file=$(readlink -f "$file")
fi

# Check debounce BEFORE processing file
# check_debounce "$abs_file" && exit 0

# Find preview script
script_dir="$(cd "$(dirname "$0")" && pwd)"
preview_script="$script_dir/fzf-prev.sh"
cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/fzf-pdf-previews"

# Verify preview script exists
if [ ! -f "$preview_script" ]; then
    echo "Error: Preview script not found at $preview_script" >&2
    exit 1
fi

# Create cache if needed
mkdir -p "$cache_dir" 2>/dev/null || true

if command -v firejail >/dev/null 2>&1; then
    # SECURE: Run with firejail isolation
    # This creates a secure sandbox for previewing untrusted files
    # Security features:
    #   - Network isolation (--net=none)
    #   - No device access (--nosound, --novideo, --private-dev)
    #   - Syscall filtering (--seccomp)
    #   - Capability dropping (--caps.drop=all)
    #   - Namespace restrictions (--restrict-namespaces)
    #   - Isolated /tmp (--private-tmp)
    # Note: File access is still broad due to whitelist behavior,
    # but the above prevents privilege escalation and most attacks
    sleep 0.05
    exec firejail \
        --quiet \
        --noprofile \
        --private-tmp \
        --private-dev \
        --net=none \
        --nosound \
        --novideo \
        --seccomp \
        --caps.drop=all \
        --restrict-namespaces \
        --whitelist="$abs_file" \
        --whitelist="$preview_script" \
        --whitelist="$cache_dir" \
        --whitelist=/tmp/hyprde-preview-secure \
        --env=FZF_PREVIEW_COLUMNS="${FZF_PREVIEW_COLUMNS:-80}" \
        --env=FZF_PREVIEW_LINES="${FZF_PREVIEW_LINES:-24}" \
        --env=TERM="${TERM:-xterm-256color}" \
        -- "$preview_script" "$abs_file" 2>/dev/null
else
    # UNSANDBOXED: Direct execution
    # WARNING: Only safe for trusted files!
    # For secure previewing of downloaded files, install firejail:
    #   sudo pacman -S firejail
    sleep 0.05
    exec "$preview_script" "$abs_file" 2>/dev/null
fi

# Trap for exit logging
trap 'log_wrapper_exit $?' EXIT
