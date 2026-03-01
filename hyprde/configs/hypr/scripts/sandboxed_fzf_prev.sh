#!/bin/bash

# ==============================================================================
# Sandboxed File Preview Script for fzf
# ==============================================================================
# Description:
#   Cross-platform sandboxed preview using platform-specific sandbox technologies
#   Wraps existing fzf-prev.sh functionality in secure isolation
#
# Author: Hyprland Configuration Team
# Version: 1.0.0
# Last Modified: 2025-12-06
#
# Prerequisites:
#   - Required: bash 4.0+, file, timeout/gtimeout
#   - Linux: bubblewrap (bwrap) or firejail
#   - macOS: sandbox-exec (built-in)
#   - Optional: Existing fzf-prev.sh for preview functions
#
# Usage:
#   ./sandboxed_fzf_prev.sh <file_path>
#   FZF_PREVIEW_COLUMNS=80 FZF_PREVIEW_LINES=24 ./sandboxed_fzf_prev.sh <file_path>
#
# Security:
#   ✅ Platform-specific sandbox isolation
#   ✅ Risk-based file type assessment
#   ✅ Configurable security levels
#   ✅ Graceful fallback to unsandboxed execution
#
# Environment Variables:
#   SANDBOX_PREVIEW_LEVEL: strict|medium|permissive (default: strict)
#   SANDBOX_FORCE_DISABLE: Set to 1 to disable sandboxing
#   SANDBOX_CACHE_DISABLE: Set to 1 to disable caching in sandbox
#
# Exit Codes:
#   0 - Success
#   1 - General error
#   2 - Missing dependencies
# ==============================================================================

set -o errexit
set -o nounset
set -o pipefail
shopt -s inherit_errexit 2>/dev/null || true

# ==============================================================================
# Constants
# ==============================================================================
readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
readonly SCRIPT_VERSION="1.0.0"
readonly PREVIEW_TIMEOUT="${SANDBOX_PREVIEW_TIMEOUT:-10}"
readonly ORIGINAL_PREVIEW_SCRIPT="${HOME}/.config/hypr/scripts/fzf-prev.sh"

# Security levels
readonly SECURITY_LEVEL_STRICT="strict"
readonly SECURITY_LEVEL_MEDIUM="medium"
readonly SECURITY_LEVEL_PERMISSIVE="permissive"

# Terminal control sequences
readonly RESET='\033[0m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[0;33m'
readonly GREEN='\033[0;32m'

# ==============================================================================
# Global Variables
# ==============================================================================
declare -i VERBOSE=0
declare SANDBOX_TYPE="none"
declare SECURITY_LEVEL="${SANDBOX_PREVIEW_LEVEL:-$SECURITY_LEVEL_STRICT}"

# ==============================================================================
# Utility Functions
# ==============================================================================

# Log messages to stderr with timestamp
log_message() {
    local level="$1"
    shift
    if [[ "${VERBOSE}" -eq 1 ]] || [[ "${level}" == "ERROR" ]] || [[ "${level}" == "WARN" ]]; then
        printf '%s [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${level}" "$*" >&2
    fi
}

log_error() {
    log_message "ERROR" "$@"
}

log_warn() {
    log_message "WARN" "$@"
}

log_info() {
    log_message "INFO" "$@"
}

log_debug() {
    if [[ "${VERBOSE}" -eq 1 ]]; then
        log_message "DEBUG" "$@"
    fi
}

# Check if command exists
command_exists() {
    command -v "$1" &>/dev/null
}

# Detect platform and available sandbox type
detect_sandbox_type() {
    # Check for forced disable
    if [[ "${SANDBOX_FORCE_DISABLE:-}" == "1" ]]; then
        SANDBOX_TYPE="none"
        log_warn "Sandboxing disabled by environment variable"
        return 0
    fi

    # macOS detection
    if [[ "$OSTYPE" == "darwin"* ]] || [[ "$(uname)" == "Darwin" ]]; then
        if command_exists sandbox-exec; then
            SANDBOX_TYPE="macos_sandbox_exec"
            log_debug "Using macOS sandbox-exec"
            return 0
        else
            log_warn "macOS detected but sandbox-exec not available"
            SANDBOX_TYPE="none"
            return 0
        fi
    fi

    # Linux detection
    if [[ "$OSTYPE" == "linux-gnu"* ]] || [[ "$(uname)" == "Linux" ]]; then
        # Try bubblewrap first (lighter, more flexible)
        if command_exists bwrap; then
            SANDBOX_TYPE="linux_bubblewrap"
            log_debug "Using Linux bubblewrap"
            return 0
        fi
        
        # Try firejail as fallback
        if command_exists firejail; then
            SANDBOX_TYPE="linux_firejail"
            log_debug "Using Linux firejail"
            return 0
        fi
        
        log_warn "Linux detected but no sandbox tools available"
        SANDBOX_TYPE="none"
        return 0
    fi

    # Unknown platform
    log_warn "Unknown platform, no sandbox available"
    SANDBOX_TYPE="none"
    return 0
}

# Assess file risk level
assess_file_risk() {
    local file="$1"
    local mime_type
    
    if [[ ! -f "$file" ]]; then
        echo "low"
        return 0
    fi
    
    mime_type=$(file --brief --mime-type "$file" 2>/dev/null || echo "unknown")
    
    case "$mime_type" in
        # High risk - executables and scripts
        application/x-executable|application/x-shellscript|application/x-msdownload|application/x-msdos-program)
            echo "high"
            ;;
        # High risk - archives (can contain malicious content)
        application/zip|application/x-tar|application/gzip|application/x-bzip2|application/x-xz|application/x-7z-compressed)
            echo "high"
            ;;
        # Medium risk - office documents, PDFs
        application/pdf|application/msword|application/vnd.openxmlformats-officedocument*|application/vnd.ms-*|application/vnd.oasis.opendocument*)
            echo "medium"
            ;;
        # Low risk - images, text, media
        image/*|text/*|audio/*|video/*)
            echo "low"
            ;;
        # Default to medium for unknown types
        *)
            echo "medium"
            ;;
    esac
}

# Determine if file should be sandboxed based on security level and risk
should_sandbox_file() {
    local file="$1"
    local risk_level
    risk_level=$(assess_file_risk "$file")
    
    case "$SECURITY_LEVEL" in
        "$SECURITY_LEVEL_STRICT")
            # Always sandbox
            return 0
            ;;
        "$SECURITY_LEVEL_MEDIUM")
            # Sandbox high and medium risk files
            if [[ "$risk_level" == "high" ]] || [[ "$risk_level" == "medium" ]]; then
                return 0
            else
                return 1
            fi
            ;;
        "$SECURITY_LEVEL_PERMISSIVE")
            # Only sandbox high risk files
            if [[ "$risk_level" == "high" ]]; then
                return 0
            else
                return 1
            fi
            ;;
        *)
            # Default to strict
            return 0
            ;;
    esac
}

# Get file size in bytes (portable between GNU and BSD)
get_file_size() {
    local file="$1"
    local size

    # Try BSD stat first (macOS)
    if size=$(stat -f%z "$file" 2>/dev/null); then
        echo "${size}"
        return 0
    fi

    # Try GNU stat (Linux)
    if size=$(stat -c%s "$file" 2>/dev/null); then
        echo "${size}"
        return 0
    fi

    # Fallback
    echo "0"
    return 1
}

# Validate file is safe to process
validate_file() {
    local file="$1"

    # Check if file exists
    if [[ ! -e "$file" ]]; then
        log_error "File does not exist: $file"
        return 1
    fi

    # Check if file is readable
    if [[ ! -r "$file" ]]; then
        log_error "File not readable: $file"
        return 1
    fi

    # Check file size (limit to 50MB for sandboxed preview)
    local file_size
    file_size=$(get_file_size "$file")
    local max_size=$((50 * 1024 * 1024))  # 50MB

    if (( file_size > max_size )); then
        log_error "File too large for sandboxed preview (>$((file_size / 1024 / 1024))MB): $file"
        echo -e "${RED}File too large for sandboxed preview ($((file_size / 1024 / 1024))MB > 50MB)${RESET}"
        return 1
    fi

    return 0
}

# ==============================================================================
# Sandbox Execution Functions
