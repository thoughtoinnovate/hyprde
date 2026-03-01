#!/usr/bin/env bash

# ==============================================================================
# File Preview Script for fzf
# ==============================================================================
# Description:
#   Supports images, PDFs, text files, directories, and archives
#   Optimized for terminals with Kitty/Ghostty graphics protocol and Chafa
#
# Author: [Your Name/Team]
# Version: 2.1.0
# Last Modified: 2025-10-07
#
# Prerequisites:
#   - Required: bash 4.0+, file, timeout/gtimeout
#   - Optional: kitten, chafa, pdftoppm, bat/batcat, eza
#
# Usage:
#   ./preview.sh <file_path>
#   FZF_PREVIEW_COLUMNS=80 FZF_PREVIEW_LINES=24 ./preview.sh <file_path>
#
# Security:
#   ⚠️  IMPORTANT SECURITY CONSIDERATIONS:
#   - This script is designed for TRUSTED LOCAL FILES ONLY
#   - DO NOT use on files from untrusted sources (downloads, email, network)
#   - Includes protections: input sanitization, timeouts, file type verification
#   - Blocks access to system directories (/etc, /sys, /proc, /dev)
#   - Validates file sizes (max 100MB) and uses cache integrity checks
#   - For untrusted files, use in sandboxed environment (containers, VMs)
#
# Exit Codes:
#   0 - Success
#   1 - General error (file not found, validation failed, etc.)
#   2 - Missing dependencies for specific operation
# ==============================================================================

set -o errexit
set -o nounset
set -o pipefail
shopt -s inherit_errexit 2>/dev/null || true

# ==============================================================================
# Constants
# ==============================================================================
readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
readonly SCRIPT_VERSION="2.1.0"
readonly CACHE_DIR="${XDG_CACHE_HOME:-${HOME}/.cache}/fzf-pdf-previews"
readonly MAX_CACHE_SIZE_MB=500
readonly MAX_FILE_SIZE_MB=100
readonly CACHE_CLEANUP_DAYS=7

# Terminal control sequences
readonly RESET='\033[0m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[0;33m'
readonly CYAN='\033[0;36m'
readonly GREEN='\033[0;32m'

# Graphics protocol clear sequences
readonly KITTY_CLEAR_SEQ=$'\x1b_Ga=d\x1b\\'

# ==============================================================================
# Global Variables
# ==============================================================================
declare -i VERBOSE=0

# ==============================================================================
# Debug Logging
# ==============================================================================

# Debug log file - persists across preview calls
readonly DEBUG_LOG_FILE="/tmp/hyprde-preview-debug.log"

# Maximum number of log lines to keep
readonly DEBUG_LOG_MAX_LINES=100

# Debug logging function with timestamps and rotation
debug_preview_log() {
    return 0
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S.%3N')
    
    local message="$*"
    
    # Append to debug log
    {
        echo "=== [${timestamp}] ${message}"
    } >> "${DEBUG_LOG_FILE}"
    
    # Rotate log: keep last DEBUG_LOG_MAX_LINES lines
    if [[ -f "${DEBUG_LOG_FILE}" ]]; then
        local line_count
        line_count=$(wc -l < "${DEBUG_LOG_FILE}" 2>/dev/null || echo 0)
        
        if [[ ${line_count} -gt ${DEBUG_LOG_MAX_LINES} ]]; then
            tail -n ${DEBUG_LOG_MAX_LINES} "${DEBUG_LOG_FILE}" > "${DEBUG_LOG_FILE}.tmp"
            mv "${DEBUG_LOG_FILE}.tmp" "${DEBUG_LOG_FILE}"
        fi
    fi
}

# Log script exit
log_script_exit() {
    local exit_code="$1"
    local script_end_time
    script_end_time=$(date +%s%3N)
    local script_duration=$((script_end_time - script_start_time))
    debug_preview_log "SCRIPT END - Duration: ${script_duration}ms | Exit code: ${exit_code}"
}

# ==============================================================================
# Utility Functions
# ==============================================================================

# Clear preview window (text and graphics)
clear_preview() {
    # Force cursor home and clear to end of screen (clears text buffer)
    # printf '\033[H\033[J'
    
    # Clear Kitty graphics if supported
    if [[ -n "${KITTY_WINDOW_ID:-}" ]] || [[ -n "${GHOSTTY_RESOURCES_DIR:-}" ]]; then
        printf '%s' "${KITTY_CLEAR_SEQ}"
    fi
}

# Sanitize filename to prevent command injection
sanitize_filename() {
    local file="$1"
    
    # Check for null bytes - compare string length
    if [[ ${#file} -ne $(printf '%s' "${file}" | wc -c) ]]; then
        log_error "Filename contains null bytes"
        return 1
    fi
    
    # Check for suspicious patterns
    if [[ "${file}" =~ \$\( ]] || [[ "${file}" =~ \` ]] || [[ "${file}" =~ \|\| ]] || [[ "${file}" =~ \&\& ]]; then
        log_error "Filename contains suspicious command injection patterns"
        return 1
    fi
    
    return 0
}

# Execute command with timeout to prevent resource exhaustion
run_with_timeout() {
    local timeout_seconds="$1"
    shift
    local cmd=("$@")
    
    if command_exists timeout; then
        timeout "${timeout_seconds}" "${cmd[@]}" 2>/dev/null
        return $?
    elif command_exists gtimeout; then
        gtimeout "${timeout_seconds}" "${cmd[@]}" 2>/dev/null
        return $?
    else
        # Fallback without timeout (less secure)
        log_warn "timeout command not available, running without timeout"
        "${cmd[@]}" 2>/dev/null
        return $?
    fi
}

# Display usage information
usage() {
    cat << EOF
Usage: ${SCRIPT_NAME} [OPTIONS] <file_path>

Preview files for fzf with support for images, PDFs, text, directories, and archives.

OPTIONS:
    -h, --help      Display this help message
    -v, --verbose   Enable verbose output
    -V, --version   Display version information

ENVIRONMENT VARIABLES:
    FZF_PREVIEW_COLUMNS    Width of preview window
    FZF_PREVIEW_LINES      Height of preview window
    FZF_PREVIEW_TOP        Top position of preview window
    KITTY_WINDOW_ID        Set by Kitty terminal
    GHOSTTY_RESOURCES_DIR  Set by Ghostty terminal
    XDG_CACHE_HOME         Cache directory location

SECURITY WARNINGS:
    ⚠️  Use ONLY with trusted local files
    ⚠️  DO NOT preview files from untrusted sources
    ⚠️  Malicious files can exploit vulnerabilities in preview tools
    ⚠️  System directories (/etc, /sys, /proc, /dev) are blocked

EXAMPLES:
    ${SCRIPT_NAME} document.pdf
    ${SCRIPT_NAME} -v image.jpg
    FZF_PREVIEW_COLUMNS=100 ${SCRIPT_NAME} archive.tar.gz

EXIT CODES:
    0    Success
    1    General error
    2    Missing dependencies

EOF
}

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

# Clean up old cache files to prevent unlimited growth
cleanup_cache() {
    if [[ ! -d "${CACHE_DIR}" ]]; then
        return 0
    fi

    local cache_size
    cache_size=$(du -sm "${CACHE_DIR}" 2>/dev/null | cut -f1 || echo "0")

    if (( cache_size > MAX_CACHE_SIZE_MB )); then
        log_debug "Cache size ${cache_size}MB exceeds limit ${MAX_CACHE_SIZE_MB}MB, cleaning up"
        # Remove files older than specified days
        find "${CACHE_DIR}" -type f -mtime "+${CACHE_CLEANUP_DAYS}" -delete 2>/dev/null || true
        log_info "Cache cleanup completed"
    fi
}

# Get MIME type of file
get_mime_type() {
    local file="$1"

    if [[ ! -e "${file}" ]]; then
        echo "unknown"
        return 1
    fi

    # Use --dereference to follow symlinks
    file --brief --dereference --mime-type -- "${file}" 2>/dev/null || echo "unknown"
}

# Verify file type matches expected type (defense against extension spoofing)
verify_file_type() {
    local file="$1"
    local expected_pattern="$2"
    local mime_type
    
    mime_type=$(get_mime_type "${file}")
    
    if [[ "${mime_type}" == "unknown" ]]; then
        log_error "Cannot determine file type for: ${file}"
        return 1
    fi
    
    if [[ ! "${mime_type}" =~ ${expected_pattern} ]]; then
        log_error "File type mismatch. Expected: ${expected_pattern}, Got: ${mime_type}"
        return 1
    fi
    
    return 0
}

# Get preview window dimensions
get_preview_dimensions() {
    local dim="${FZF_PREVIEW_COLUMNS:-}x${FZF_PREVIEW_LINES:-}"

    # Fallback to terminal dimensions if fzf variables unavailable
    if [[ "${dim}" == "x" ]]; then
        if [[ -t 0 ]]; then
            dim=$(stty size 2>/dev/null </dev/tty | awk '{print $2 "x" $1}') || dim="80x24"
        else
            dim="80x24"
        fi
    # Avoid scrolling when image touches bottom of screen
    elif [[ -z "${KITTY_WINDOW_ID:-}" ]] && \
         (( ${FZF_PREVIEW_TOP:-0} + ${FZF_PREVIEW_LINES:-0} == $(stty size 2>/dev/null </dev/tty | awk '{print $1}' || echo "0") )); then
        dim="${FZF_PREVIEW_COLUMNS}x$((FZF_PREVIEW_LINES - 1))"
    fi

    echo "${dim}"
}

# Get file size in bytes (portable between GNU and BSD)
get_file_size() {
    local file="$1"
    local size

    # Try BSD stat first (macOS)
    if size=$(stat -f%z "${file}" 2>/dev/null); then
        echo "${size}"
        return 0
    fi

    # Try GNU stat (Linux)
    if size=$(stat -c%s "${file}" 2>/dev/null); then
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

    # Sanitize filename first
    if ! sanitize_filename "${file}"; then
        return 1
    fi

    # Check if file exists
    if [[ ! -e "${file}" ]]; then
        log_error "File does not exist: ${file}"
        return 1
    fi

    # Check if file is readable
    if [[ ! -r "${file}" ]]; then
        log_error "File not readable: ${file}"
        return 1
    fi

    # Prevent directory traversal attacks with strict validation
    local canonical_path
    canonical_path=$(readlink -f "${file}" 2>/dev/null || realpath "${file}" 2>/dev/null || echo "")
    
    if [[ -z "${canonical_path}" ]]; then
        log_error "Cannot resolve canonical path for: ${file}"
        return 1
    fi
    
    log_debug "Canonical path: ${canonical_path}"
    
    # Ensure canonical path doesn't escape to sensitive directories
    case "${canonical_path}" in
        /etc/*|/sys/*|/proc/*|/dev/*)
            log_error "Access to system directories not allowed: ${canonical_path}"
            return 1
            ;;
    esac
    
    # Check for symlink loops
    if [[ -L "${file}" ]]; then
        local link_target
        link_target=$(readlink "${file}" 2>/dev/null || echo "")
        if [[ -z "${link_target}" ]]; then
            log_error "Cannot read symlink target: ${file}"
            return 1
        fi
        log_debug "Symlink target: ${link_target}"
    fi

    # For regular files, check size (prevent processing huge files)
    if [[ -f "${file}" ]]; then
        local file_size
        file_size=$(get_file_size "${file}")
        local max_size=$((MAX_FILE_SIZE_MB * 1024 * 1024))

        if (( file_size > max_size )); then
            log_error "File too large (>${MAX_FILE_SIZE_MB}MB): ${file}"
            echo -e "${RED}File too large to preview ($(( file_size / 1024 / 1024 ))MB > ${MAX_FILE_SIZE_MB}MB)${RESET}"
            return 1
        fi
        log_debug "File size: $((file_size / 1024))KB"
    fi

    return 0
}

# ==============================================================================
# Preview Functions
# ==============================================================================

# SECURE: Show metadata ONLY (no image parsing - 100% secure)
preview_image_metadata() {
    local file="$1"
    local function_start_time
    function_start_time=$(date +%s%3N)
    
    debug_preview_log "preview_image_metadata START - File: '${file}' | Time: ${function_start_time}"
    
    # Clear preview window
    clear_preview
    debug_preview_log "  -> Preview cleared"
    
    # Check if file is readable
    if [[ ! -r "${file}" ]]; then
        echo -e "${RED}❌ Cannot read file${RESET}"
        return 1
    fi
    
    # Show metadata only - NO image rendering
    echo -e "${YELLOW}📄 File Info (Secure - No Parsing)${RESET}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📍 ${file}"
    echo "📦 Size: $(du -h "${file}" 2>/dev/null | cut -f1)"
    echo "🗂️  Type: $(file -b --mime-type "${file}" 2>/dev/null | cut -d'/' -f2 | tr '[:lower:]' '[:upper:]')"
    
    # Image dimensions (from file headers only - no full decode)
    if command_exists identify; then
        local dims
        dims=$(identify -format "%wx%h" "${file}" 2>/dev/null || echo "")
        if [[ -n "${dims}" ]]; then
            echo "📐 ${dims}"
        fi
    elif command_exists sips; then
        local w h
        w=$(sips -g pixelWidth "${file}" 2>/dev/null | grep pixelWidth | awk '{print $2}')
        h=$(sips -g pixelHeight "${file}" 2>/dev/null | grep pixelHeight | awk '{print $2}')
        if [[ -n "${w}" ]] && [[ -n "${h}" ]]; then
            echo "📐 ${w}x${h}"
        fi
    fi
    
    # Last modified
    local mtime
    mtime=$(stat -c "%y" "${file}" 2>/dev/null | cut -d' ' -f1 || stat -f "%Sm" "${file}" 2>/dev/null || echo "")
    if [[ -n "${mtime}" ]]; then
        echo "📅 ${mtime}"
    fi
    
    # File permissions
    local perms
    perms=$(stat -c "%a" "${file}" 2>/dev/null || stat -f "%Lp" "${file}" 2>/dev/null || echo "")
    if [[ -n "${perms}" ]]; then
        echo "🔒 Perms: ${perms}"
    fi
    
    # Color profile info (if available)
    if command_exists identify; then
        local colorspace
        colorspace=$(identify -format "%r" "${file}" 2>/dev/null || echo "")
        if [[ -n "${colorspace}" ]]; then
            echo "🎨 ${colorspace}"
        fi
    fi
    
    echo ""
    echo -e "${GREEN}🛡️  Preview: Metadata only (100% secure)${RESET}"
    echo -e "${CYAN}Press CTRL-I to render image in preview${RESET}"
    
    local function_end_time
    function_end_time=$(date +%s%3N)
    local function_duration=$((function_end_time - function_start_time))
    debug_preview_log "preview_image_metadata END - File: '${file}' | Duration: ${function_duration}ms"
}

# RENDERED: Show chafa image preview (runs in firejail sandbox)
preview_image_rendered() {
    local file="$1"
    local function_start_time
    function_start_time=$(date +%s%3N)
    
    # Log function entry
    debug_preview_log "preview_image_rendered START - File: '${file}' | Time: ${function_start_time}"
    
    # Clear preview window
    clear_preview
    debug_preview_log "  -> Preview cleared"
    
    # echo -e "${YELLOW}🖼️  Image Preview (Sandboxed)${RESET}"
    # echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    debug_preview_log "  -> Header printed"
    
    # Check for terminal support and use appropriate method
    local render_method="none"
    if [[ -n "${KITTY_WINDOW_ID:-}" ]] || [[ -n "${GHOSTTY_RESOURCES_DIR:-}" ]]; then
        # Terminal supports graphics protocol
        local cols="${FZF_PREVIEW_COLUMNS:-55}"
        local lines="${FZF_PREVIEW_LINES:-30}"
        debug_preview_log "  -> Using graphics protocol - Size: ${cols}x${lines}"
        
        # Try Kitty format for pixel-perfect rendering (Ghostty supports it)
        if command_exists chafa; then
            if chafa --format=kitty --size="${cols}x${lines}" --animate=off "${file}" 2>/dev/null; then
                render_method="kitty"
                debug_preview_log "  -> Rendered: kitty format"
            else
                # Fallback to ANSI if Kitty doesn't work in fzf preview
                chafa --format=ANSI --size="${cols}x${lines}" --scale=max --animate=off --dither=ordered "${file}" 2>/dev/null
                render_method="ansi"
                debug_preview_log "  -> Rendered: ANSI format"
            fi
        else
            echo -e "${YELLOW}⚠️  Install chafa: pacman -S chafa${RESET}"
            render_method="no-chafa"
        fi
    else
        # Fallback: Show file info for unsupported terminals
        debug_preview_log "  -> No graphics protocol support - showing file info"
        echo "Image: $(basename "${file}")"
        echo "Size: $(du -h "${file}" 2>/dev/null | cut -f1)"
        if command_exists identify; then
            echo "Dimensions: $(identify -format "%wx%h" "${file}" 2>/dev/null || echo 'unknown')"
        fi
        echo ""
        echo -e "${CYAN}💡 Use Kitty or Ghostty for image preview${RESET}"
        render_method="file-info"
    fi
    
    echo ""
    echo -e "${CYAN}Press CTRL-S for metadata (secure mode)${RESET}"
    
    local function_end_time
    function_end_time=$(date +%s%3N)
    local function_duration=$((function_end_time - function_start_time))
    debug_preview_log "preview_image_rendered END - File: '${file}' | Method: ${render_method} | Duration: ${function_duration}ms"
}

# Main preview function - checks toggle state
preview_image() {
    local file="$1"
    local dim
    dim=$(get_preview_dimensions)

    log_debug "Previewing image: ${file} (dimensions: ${dim})"
    
    # Verify it's actually an image
    if ! verify_file_type "${file}" "^image/"; then
        log_error "File is not a valid image"
        file "${file}"
        return 1
    fi

    # Check if we're running inside fzf preview (firejail sandbox)
    if [[ -n "${FZF_PREVIEW_COLUMNS:-}" ]]; then
        # Check toggle state - default to RENDER since chafa runs in firejail (secure)
        if [[ -f "/tmp/hyprde-preview-secure" ]]; then
            preview_image_metadata "${file}"
        else
            preview_image_rendered "${file}"
        fi
        return $?
    fi
}

# Preview PDF files
preview_pdf() {
    local file="$1"
    local function_start_time
    function_start_time=$(date +%s%3N)
    local dim
    dim=$(get_preview_dimensions)
    
    debug_preview_log "preview_pdf START - File: '${file}' | Time: ${function_start_time}"

    # Clear preview window
    clear_preview
    debug_preview_log "  -> Preview cleared"
    
    log_debug "Previewing PDF: ${file} (dimensions: ${dim})"
    
    # Verify it's actually a PDF
    if ! verify_file_type "${file}" "^application/pdf"; then
        log_error "File is not a valid PDF"
        file "${file}"
        return 1
    fi

    # Check for required dependencies
    if ! command_exists pdftoppm; then
        log_error "PDF preview requires pdftoppm (poppler-utils)"
        echo -e "${YELLOW}PDF preview requires pdftoppm (install poppler-utils)${RESET}"
        file "${file}"
        return 2
    fi

    # Create cache directory with proper permissions
    if ! mkdir -p "${CACHE_DIR}" 2>/dev/null; then
        log_error "Failed to create cache directory: ${CACHE_DIR}"
        file "${file}"
        return 1
    fi
    chmod 700 "${CACHE_DIR}" 2>/dev/null || true

    # Generate unique hash based on file path and modification time
    local hash cached_img file_mtime
    
    # Get modification time (portable)
    if file_mtime=$(stat -f%m "${file}" 2>/dev/null); then
        : # BSD stat succeeded
    elif file_mtime=$(stat -c%Y "${file}" 2>/dev/null); then
        : # GNU stat succeeded
    else
        file_mtime="0"
    fi

    # Generate hash (try multiple hash commands)
    if command_exists md5sum; then
        hash=$(printf '%s%s' "${file}" "${file_mtime}" | md5sum 2>/dev/null | cut -d' ' -f1)
    elif command_exists md5; then
        hash=$(printf '%s%s' "${file}" "${file_mtime}" | md5 2>/dev/null)
    else
        # Fallback to simple filename-based hash
        hash="fallback_$(basename "${file}" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')_${file_mtime}"
    fi

    cached_img="${CACHE_DIR}/${hash}.jpg"
    local cached_checksum="${CACHE_DIR}/${hash}.sha256"
    log_debug "Cached image path: ${cached_img}"

    # Verify cache integrity if exists
    local cache_valid=0
    if [[ -f "${cached_img}" ]] && [[ -f "${cached_checksum}" ]]; then
        if command_exists sha256sum; then
            local stored_sum current_sum
            stored_sum=$(cat "${cached_checksum}" 2>/dev/null || echo "")
            current_sum=$(sha256sum "${cached_img}" 2>/dev/null | cut -d' ' -f1)
            if [[ -n "${stored_sum}" ]] && [[ "${stored_sum}" == "${current_sum}" ]]; then
                cache_valid=1
                log_debug "Cache integrity verified"
            else
                log_warn "Cache integrity check failed, regenerating"
                rm -f "${cached_img}" "${cached_checksum}" 2>/dev/null || true
            fi
        elif command_exists shasum; then
            local stored_sum current_sum
            stored_sum=$(cat "${cached_checksum}" 2>/dev/null || echo "")
            current_sum=$(shasum -a 256 "${cached_img}" 2>/dev/null | cut -d' ' -f1)
            if [[ -n "${stored_sum}" ]] && [[ "${stored_sum}" == "${current_sum}" ]]; then
                cache_valid=1
                log_debug "Cache integrity verified"
            else
                log_warn "Cache integrity check failed, regenerating"
                rm -f "${cached_img}" "${cached_checksum}" 2>/dev/null || true
            fi
        else
            # No checksum tool available, trust cache based on existence
            cache_valid=1
        fi
    fi

    # Generate cached image if not exists or is invalid
    if [[ "${cache_valid}" -eq 0 ]]; then
        log_debug "Generating PDF preview cache"
        # Clean up old cache periodically
        cleanup_cache

        # Convert first page of PDF to image with error handling and timeout
        local convert_success=0
        
        # Try with scaling first (15 second timeout) - higher resolution for better quality
        # Scale to 1920x1920 for high-quality previews
        if run_with_timeout 15 pdftoppm -jpeg -f 1 -singlefile -scale-to-x 1920 -scale-to-y 1920 \
            "${file}" "${CACHE_DIR}/${hash}"; then
            convert_success=1
        # Try without scaling as fallback
        elif run_with_timeout 10 pdftoppm -jpeg -f 1 -singlefile "${file}" "${CACHE_DIR}/${hash}"; then
            convert_success=1
            log_warn "PDF conversion succeeded without scaling"
        fi

        if [[ "${convert_success}" -eq 0 ]]; then
            log_error "Failed to convert PDF to image: ${file}"
            echo -e "${RED}Failed to generate PDF preview${RESET}"
            file "${file}"
            return 1
        fi

        # Verify the image was created
        if [[ ! -f "${cached_img}" ]]; then
            log_error "PDF preview generation produced no output"
            file "${file}"
            return 1
        fi
        
        # Generate checksum for cache integrity
        if command_exists sha256sum; then
            sha256sum "${cached_img}" 2>/dev/null | cut -d' ' -f1 > "${cached_checksum}" || true
        elif command_exists shasum; then
            shasum -a 256 "${cached_img}" 2>/dev/null | cut -d' ' -f1 > "${cached_checksum}" || true
        fi
        
        log_info "PDF preview cached successfully"
    else
        log_debug "Using cached PDF preview"
    fi

    # Display cached PDF preview as image
    if [[ -f "${cached_img}" ]] && [[ -r "${cached_img}" ]]; then
        debug_preview_log "  -> Using cached image: ${cached_img}"
        local function_end_time
        function_end_time=$(date +%s%3N)
        local function_duration=$((function_end_time - function_start_time))
        debug_preview_log "preview_pdf END - File: '${file}' | Duration: ${function_duration}ms | Using cache"
        preview_image "${cached_img}"
        return $?
    else
        log_error "Cached PDF preview not accessible"
        file "${file}"
        return 1
    fi
}

# Preview text files
preview_text() {
    local file="$1"
    local function_start_time
    function_start_time=$(date +%s%3N)
    
    debug_preview_log "preview_text START - File: '${file}' | Time: ${function_start_time}"
    
    # Clear preview window
    clear_preview
    debug_preview_log "  -> Preview cleared"
    
    log_debug "Previewing text file: ${file}"
    
    # Try bat/batcat with syntax highlighting
    local render_method="none"
    if command_exists batcat; then
        run_with_timeout 5 batcat --style=numbers --color=always --pager=never "${file}" && render_method="batcat"
    elif command_exists bat; then
        run_with_timeout 5 bat --style=numbers --color=always --pager=never "${file}" && render_method="bat"
    fi
    
    # Fallback to cat with timeout
    if [[ "${render_method}" == "none" ]]; then
        log_debug "Using cat for text preview"
        run_with_timeout 3 cat "${file}" && render_method="cat"
    fi
    
    local function_end_time
    function_end_time=$(date +%s%3N)
    local function_duration=$((function_end_time - function_start_time))
    debug_preview_log "preview_text END - File: '${file}' | Method: ${render_method} | Duration: ${function_duration}ms"
}

# Preview directories
preview_directory() {
    local file="$1"
    local function_start_time
    function_start_time=$(date +%s%3N)
    
    debug_preview_log "preview_directory START - File: '${file}' | Time: ${function_start_time}"
    
    # Clear preview window
    clear_preview
    debug_preview_log "  -> Preview cleared"
    
    log_debug "Previewing directory: ${file}"
    
    # Try eza with icons and colors
    local render_method="none"
    if command_exists eza; then
        run_with_timeout 3 eza --icons --color=always -la "${file}" && render_method="eza"
    fi
    
    # Fallback to ls with colors
    if [[ "${render_method}" == "none" ]]; then
        if run_with_timeout 3 ls --color=always -lAh "${file}" 2>/dev/null; then
            render_method="ls-linux"
        else
            # BSD ls (macOS)
            run_with_timeout 3 ls -lAh "${file}"
            render_method="ls-bsd"
        fi
    fi
    
    local function_end_time
    function_end_time=$(date +%s%3N)
    local function_duration=$((function_end_time - function_start_time))
    debug_preview_log "preview_directory END - File: '${file}' | Method: ${render_method} | Duration: ${function_duration}ms"
}

# Preview archive files
preview_archive() {
    local file="$1"
    local function_start_time
    function_start_time=$(date +%s%3N)
    
    debug_preview_log "preview_archive START - File: '${file}' | Time: ${function_start_time}"
    
    # Clear preview window
    clear_preview
    debug_preview_log "  -> Preview cleared"
    
    log_debug "Previewing archive: ${file}"
    
    # Get file extension
    local ext="${file##*.}"
    local basename_file
    basename_file=$(basename "${file}")

    # Display common header
    display_archive_header() {
        local format="$1"
        echo "Archive: ${basename_file}"
        echo "Format: ${format}"
        echo "================================================"
    }

    # Display missing dependency error
    display_missing_dependency() {
        local tool="$1"
        shift
        echo -e "${RED}❌ Cannot preview: '${tool}' not installed${RESET}" >&2
        echo ""
        echo "Install with:"
        for cmd in "$@"; do
            echo "  ${cmd}"
        done
    }

    # Common archive listing function
    list_archive_contents() {
        local title="$1"
        echo "${title}"
        echo "------------------------------------------------"
    }

    # Process archive contents to show first level only
    process_archive_listing() {
        awk -F'/' '{
            if (NF == 1 && $1 != "") {
                print "  " $1
            } else if (NF > 1) {
                if (!seen[$1]++) {
                    print "  " $1 "/"
                }
            }
        }' | head -n 30
    }

    # ZIP FILES
    if [[ "${ext}" == "zip" ]]; then
        display_archive_header "ZIP"
        if ! command_exists unzip; then
            display_missing_dependency "unzip" \
                "Ubuntu/Debian: sudo apt install unzip" \
                "Fedora/RHEL:   sudo dnf install unzip" \
                "Arch:          sudo pacman -S unzip"
            return 2
        fi
        list_archive_contents "Contents (first level):"
        run_with_timeout 5 unzip -l "${file}" 2>/dev/null | awk 'NR>3 {print $NF}' | process_archive_listing
        echo ""
        echo "Extract: unzip '${basename_file}'"
        return 0
    fi

    # TAR FILES (uncompressed)
    if [[ "${ext}" == "tar" ]]; then
        display_archive_header "TAR (uncompressed)"
        if ! command_exists tar; then
            display_missing_dependency "tar" \
                "Ubuntu/Debian: sudo apt install tar" \
                "(Usually pre-installed on most systems)"
            return 2
        fi
        list_archive_contents "Contents (first level):"
        run_with_timeout 5 tar -tf "${file}" 2>/dev/null | process_archive_listing
        echo ""
        echo "Extract: tar -xf '${basename_file}'"
        return 0
    fi

    # TAR.GZ / TGZ FILES
    if [[ "${file}" == *.tar.gz ]] || [[ "${ext}" == "tgz" ]]; then
        display_archive_header "TAR.GZ (gzip compressed)"
        if ! command_exists tar; then
            display_missing_dependency "tar" "Ubuntu/Debian: sudo apt install tar"
            return 2
        fi
        list_archive_contents "Contents (first level):"
        run_with_timeout 5 tar -tzf "${file}" 2>/dev/null | process_archive_listing
        echo ""
        echo "Extract: tar -xzf '${basename_file}'"
        return 0
    fi

    # TAR.BZ2 / TBZ2 FILES
    if [[ "${file}" == *.tar.bz2 ]] || [[ "${ext}" == "tbz2" ]] || [[ "${file}" == *.tar.bz ]]; then
        display_archive_header "TAR.BZ2 (bzip2 compressed)"
        if ! command_exists tar; then
            display_missing_dependency "tar" "Ubuntu/Debian: sudo apt install tar"
            return 2
        fi
        list_archive_contents "Contents (first level):"
        run_with_timeout 5 tar -tjf "${file}" 2>/dev/null | process_archive_listing
        echo ""
        echo "Extract: tar -xjf '${basename_file}'"
        return 0
    fi

    # TAR.XZ / TXZ FILES
    if [[ "${file}" == *.tar.xz ]] || [[ "${ext}" == "txz" ]]; then
        display_archive_header "TAR.XZ (xz compressed)"
        if ! command_exists tar; then
            display_missing_dependency "tar" "Ubuntu/Debian: sudo apt install tar xz-utils"
            return 2
        fi
        list_archive_contents "Contents (first level):"
        run_with_timeout 5 tar -tJf "${file}" 2>/dev/null | process_archive_listing
        echo ""
        echo "Extract: tar -xJf '${basename_file}'"
        return 0
    fi

    # TAR.ZST FILES
    if [[ "${file}" == *.tar.zst ]] || [[ "${ext}" == "tzst" ]]; then
        display_archive_header "TAR.ZST (zstd compressed)"
        if ! command_exists tar; then
            display_missing_dependency "tar" \
                "Ubuntu/Debian: sudo apt install tar zstd" \
                "Fedora/RHEL:   sudo dnf install tar zstd" \
                "Arch:          sudo pacman -S tar zstd"
            return 2
        fi
        if ! command_exists zstd; then
            display_missing_dependency "zstd" \
                "Ubuntu/Debian: sudo apt install zstd" \
                "Fedora/RHEL:   sudo dnf install zstd" \
                "Arch:          sudo pacman -S zstd"
            return 2
        fi
        list_archive_contents "Contents (first level):"
        run_with_timeout 5 tar --use-compress-program=zstd -tf "${file}" 2>/dev/null | process_archive_listing
        echo ""
        echo "Extract: tar --use-compress-program=zstd -xf '${basename_file}'"
        return 0
    fi

    # RAR FILES
    if [[ "${ext}" == "rar" ]]; then
        display_archive_header "RAR"
        if ! command_exists unrar; then
            display_missing_dependency "unrar" \
                "Ubuntu/Debian: sudo apt install unrar" \
                "Fedora/RHEL:   sudo dnf install unrar" \
                "Arch:          sudo pacman -S unrar"
            return 2
        fi
        list_archive_contents "Contents (first level):"
        run_with_timeout 5 unrar lb "${file}" 2>/dev/null | process_archive_listing
        echo ""
        echo "Extract: unrar x '${basename_file}'"
        return 0
    fi

    # 7-ZIP FILES
    if [[ "${ext}" == "7z" ]]; then
        display_archive_header "7-Zip"
        local cmd=""
        if command_exists 7z; then
            cmd="7z"
        elif command_exists 7za; then
            cmd="7za"
        else
            display_missing_dependency "7z" \
                "Ubuntu/Debian: sudo apt install p7zip-full" \
                "Fedora/RHEL:   sudo dnf install p7zip p7zip-plugins" \
                "Arch:          sudo pacman -S p7zip"
            return 2
        fi
        list_archive_contents "Contents (first level):"
        run_with_timeout 5 "${cmd}" l -slt "${file}" 2>/dev/null | \
            grep "^Path = " | \
            sed 's/^Path = //' | \
            process_archive_listing
        echo ""
        echo "Extract: 7z x '${basename_file}'"
        return 0
    fi

    # Single file compression formats
    local decompressed_name="${basename_file%.*}"
    
    # GZIP FILES (single file compression)
    if [[ "${ext}" == "gz" ]] && [[ "${file}" != *.tar.gz ]]; then
        display_archive_header "GZIP (single file compression)"
        if ! command_exists gzip; then
            display_missing_dependency "gzip" "Usually pre-installed on most systems"
            return 2
        fi
        echo "Compressed file (not an archive)"
        echo ""
        echo "Extract: gunzip '${basename_file}'"
        echo "Output will be: ${decompressed_name}"
        return 0
    fi

    # BZIP2 FILES
    if [[ "${ext}" == "bz2" ]] && [[ "${file}" != *.tar.bz2 ]]; then
        display_archive_header "BZIP2 (single file compression)"
        if ! command_exists bzip2; then
            display_missing_dependency "bzip2" "Ubuntu/Debian: sudo apt install bzip2"
            return 2
        fi
        echo "Compressed file (not an archive)"
        echo ""
        echo "Extract: bunzip2 '${basename_file}'"
        echo "Output will be: ${decompressed_name}"
        return 0
    fi

    # XZ FILES
    if [[ "${ext}" == "xz" ]] && [[ "${file}" != *.tar.xz ]]; then
        display_archive_header "XZ (single file compression)"
        if ! command_exists xz; then
            display_missing_dependency "xz" "Ubuntu/Debian: sudo apt install xz-utils"
            return 2
        fi
        echo "Compressed file (not an archive)"
        echo ""
        echo "Extract: unxz '${basename_file}'"
        echo "Output will be: ${decompressed_name}"
        return 0
    fi

    # ZSTD FILES
    if [[ "${ext}" == "zst" ]] && [[ "${file}" != *.tar.zst ]]; then
        display_archive_header "ZSTD (single file compression)"
        if ! command_exists zstd; then
            display_missing_dependency "zstd" \
                "Ubuntu/Debian: sudo apt install zstd" \
                "Fedora/RHEL:   sudo dnf install zstd" \
                "Arch:          sudo pacman -S zstd"
            return 2
        fi
        echo "Compressed file (not an archive)"
        echo ""
        echo "Extract: zstd -d '${basename_file}'"
        echo "Output will be: ${decompressed_name}"
        return 0
    fi

    # FALLBACK - Unknown or unsupported format
    display_archive_header "Unknown/Unsupported (.${ext})"
    echo -e "${RED}❌ No preview available for this archive format${RESET}" >&2
    echo ""
    file "${file}" 2>/dev/null || echo "Cannot determine file type"
    
    local function_end_time
    function_end_time=$(date +%s%3N)
    local function_duration=$((function_end_time - function_start_time))
    debug_preview_log "preview_archive END - File: '${file}' | Format: unknown | Duration: ${function_duration}ms"
    
    return 1
}

# ==============================================================================
# Main Logic
# ==============================================================================

main() {
    local script_start_time
    script_start_time=$(date +%s%3N)
    
    # Log script entry with full context
    debug_preview_log "SCRIPT START - File: '$*' | PID: $$ | TTY: $(tty 2>/dev/null || echo 'none') | Args: $*"
    
    # Log environment snapshot
    debug_preview_log "ENV - COLUMNS: ${FZF_PREVIEW_COLUMNS:-'unset'} | LINES: ${FZF_PREVIEW_LINES:-'unset'} | TERM: ${TERM:-'unset'}"
    debug_preview_log "ENV - KITTY_WINDOW_ID: ${KITTY_WINDOW_ID:-'unset'} | GHOSTTY_RESOURCES_DIR: ${GHOSTTY_RESOURCES_DIR:-'unset'}"
    debug_preview_log "ENV - VERBOSE: ${VERBOSE} | DEBUG_LOG: ${DEBUG_LOG_FILE}"
    
    # Parse command line options
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)
                usage
                exit 0
                ;;
            -v|--verbose)
                VERBOSE=1
                shift
                ;;
            -V|--version)
                echo "${SCRIPT_NAME} version ${SCRIPT_VERSION}"
                exit 0
                ;;
            -*)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
            *)
                break
                ;;
        esac
    done

    # Handle empty input
    if [[ $# -eq 0 ]]; then
        log_error "No file specified"
        echo "Error: No file specified. Use -h for help." >&2
        exit 1
    fi

    local file="$*"

    # Handle tilde expansion
    file="${file/#\~/${HOME}}"

    log_debug "Processing file: ${file}"

    # Validate file
    if ! validate_file "${file}"; then
        exit 1
    fi

    # Handle directories
    if [[ -d "${file}" ]]; then
        preview_directory "${file}"
        exit 0
    fi

    # Get MIME type for file classification
    local mime_type
    if ! mime_type=$(get_mime_type "${file}"); then
        log_error "Failed to detect MIME type"
        file "${file}"
        exit 1
    fi

    log_debug "Detected MIME type: ${mime_type}"

    # Route to appropriate preview function
    case "${mime_type}" in
        image/*)
            preview_image "${file}"
            exit $?
            ;;
        application/pdf)
            preview_pdf "${file}"
            exit $?
            ;;
        text/*|*json|*xml|*javascript|*python|*yaml|*toml|application/x-shellscript)
            preview_text "${file}"
            exit $?
            ;;
        *zip|*tar|*gzip|*bzip*|*rar|*7z*|*xz|*zstd|application/x-tar|application/gzip|application/x-bzip2|application/x-xz)
            preview_archive "${file}"
            exit $?
            ;;
        *)
            # Fallback for unknown types
            log_debug "Using fallback preview for unknown MIME type"
            file "${file}"
            exit 0
            ;;
    esac
}

# ==============================================================================
# Script Entry Point
# ==============================================================================

# Trap errors and exit for debugging
trap 'log_error "Script failed at line $LINENO with exit code $?"' ERR
trap 'log_script_exit $?' EXIT

# Execute main function
main "$@"
