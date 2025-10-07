#!/usr/bin/env bash

# ==============================================================================
# File Preview Script for fzf
# ==============================================================================
# Description:
#   Supports images, PDFs, text files, directories, and archives
#   Optimized for terminals with Kitty/Ghostty graphics protocol and Chafa
#
# Author: [Your Name/Team]
# Version: 2.0.0
# Last Modified: 2025-10-07
#
# Prerequisites:
#   - Required: bash 4.0+, file
#   - Optional: kitten, chafa, pdftoppm, bat/batcat, eza
#
# Usage:
#   ./preview.sh <file_path>
#   FZF_PREVIEW_COLUMNS=80 FZF_PREVIEW_LINES=24 ./preview.sh <file_path>
#
# Exit Codes:
#   0 - Success
#   1 - General error (file not found, validation failed, etc.)
#   2 - Missing dependencies for specific operation
# ==============================================================================

set -o errexit
set -o nounset
set -o pipefail
${BASH_VERSION:+shopt -s inherit_errexit}

# ==============================================================================
# Constants
# ==============================================================================
readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
readonly SCRIPT_VERSION="2.0.0"
readonly CACHE_DIR="${XDG_CACHE_HOME:-${HOME}/.cache}/fzf-pdf-previews"
readonly MAX_CACHE_SIZE_MB=500
readonly MAX_FILE_SIZE_MB=100
readonly CACHE_CLEANUP_DAYS=7
readonly CLEAR_IMAGE_SEQ=$'\x1b_Ga=d,d=A\x1b\\'

# Terminal control sequences
readonly RESET='\033[0m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[0;33m'

# ==============================================================================
# Global Variables
# ==============================================================================
declare -i VERBOSE=0

# ==============================================================================
# Utility Functions
# ==============================================================================

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

    # Prevent directory traversal attacks
    local canonical_path
    canonical_path=$(readlink -f "${file}" 2>/dev/null || realpath "${file}" 2>/dev/null || echo "${file}")
    log_debug "Canonical path: ${canonical_path}"

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

# Preview image files
preview_image() {
    local file="$1"
    local dim
    dim=$(get_preview_dimensions)

    log_debug "Previewing image: ${file} (dimensions: ${dim})"

    # Use Kitty/Ghostty graphics protocol for highest quality
    if [[ -n "${KITTY_WINDOW_ID:-}" ]] || [[ -n "${GHOSTTY_RESOURCES_DIR:-}" ]]; then
        if command_exists kitten; then
            log_debug "Using kitten for image display"
            if kitten icat \
                --clear \
                --transfer-mode=memory \
                --stdin=no \
                --align center \
                --place "${FZF_PREVIEW_COLUMNS:-80}x${FZF_PREVIEW_LINES:-24}@0x0" \
                "${file}" 2>/dev/null; then
                return 0
            else
                log_warn "kitten failed, falling back"
            fi
        fi
    fi

    # Fallback to Chafa
    if command_exists chafa; then
        log_debug "Using chafa for image display"
        # Try sixel format first
        if chafa --format=sixels --size="${dim}" --animate=off "${file}" 2>/dev/null; then
            echo  # Newline for proper fzf rendering
            return 0
        fi
        # Fallback to symbol format
        if chafa --format=symbols --symbols=all --size="${dim}" --dither=ordered "${file}" 2>/dev/null; then
            echo  # Newline for proper fzf rendering
            return 0
        fi
        log_warn "chafa failed for ${file}"
    fi

    # Last resort: show file info
    log_error "No image preview available. Install chafa or kitten."
    file "${file}"
    return 2
}

# Preview PDF files
preview_pdf() {
    local file="$1"
    local dim
    dim=$(get_preview_dimensions)

    log_debug "Previewing PDF: ${file} (dimensions: ${dim})"

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
    log_debug "Cached image path: ${cached_img}"

    # Generate cached image if not exists or is stale
    if [[ ! -f "${cached_img}" ]]; then
        log_debug "Generating PDF preview cache"
        # Clean up old cache periodically
        cleanup_cache

        # Convert first page of PDF to image with error handling
        local convert_success=0
        
        # Try with scaling first
        if pdftoppm -jpeg -f 1 -singlefile -scale-to-x 1920 -scale-to-y -1 \
            "${file}" "${CACHE_DIR}/${hash}" 2>/dev/null; then
            convert_success=1
        # Try without scaling as fallback
        elif pdftoppm -jpeg -f 1 -singlefile "${file}" "${CACHE_DIR}/${hash}" 2>/dev/null; then
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
        
        log_info "PDF preview cached successfully"
    else
        log_debug "Using cached PDF preview"
    fi

    # Display cached PDF preview as image
    if [[ -f "${cached_img}" ]] && [[ -r "${cached_img}" ]]; then
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
    printf '%s' "${CLEAR_IMAGE_SEQ}"

    log_debug "Previewing text file: ${file}"

    # Try bat/batcat with syntax highlighting
    if command_exists batcat; then
        batcat --style=numbers --color=always --pager=never "${file}" 2>/dev/null && return 0
    elif command_exists bat; then
        bat --style=numbers --color=always --pager=never "${file}" 2>/dev/null && return 0
    fi

    # Fallback to cat
    log_debug "Using cat for text preview"
    cat "${file}"
}

# Preview directories
preview_directory() {
    local file="$1"
    printf '%s' "${CLEAR_IMAGE_SEQ}"

    log_debug "Previewing directory: ${file}"

    # Try eza with icons and colors
    if command_exists eza; then
        eza --icons --color=always -la "${file}" 2>/dev/null && return 0
    fi

    # Fallback to ls with colors
    if ls --color=always -lAh "${file}" 2>/dev/null; then
        return 0
    else
        # BSD ls (macOS)
        ls -lAh "${file}"
    fi
}

# Preview archive files
preview_archive() {
    local file="$1"
    printf '%s' "${CLEAR_IMAGE_SEQ}"

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
        unzip -l "${file}" 2>/dev/null | awk 'NR>3 {print $NF}' | process_archive_listing
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
        tar -tf "${file}" 2>/dev/null | process_archive_listing
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
        tar -tzf "${file}" 2>/dev/null | process_archive_listing
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
        tar -tjf "${file}" 2>/dev/null | process_archive_listing
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
        tar -tJf "${file}" 2>/dev/null | process_archive_listing
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
        tar --use-compress-program=zstd -tf "${file}" 2>/dev/null | process_archive_listing
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
        unrar lb "${file}" 2>/dev/null | process_archive_listing
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
        "${cmd}" l -slt "${file}" 2>/dev/null | \
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
    return 1
}

# ==============================================================================
# Main Logic
# ==============================================================================

main() {
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

# Trap errors for better debugging
trap 'log_error "Script failed at line $LINENO with exit code $?"' ERR

# Execute main function
main "$@"

