#!/usr/bin/env bash
#
# File Preview Script for fzf
# Supports images, PDFs, text files, directories, and archives
# Optimized for terminals with Kitty/Ghostty graphics protocol and Chafa

set -o errexit
set -o nounset
set -o pipefail

# ============================================================================
# Constants
# ============================================================================

readonly CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/fzf-pdf-previews"
readonly CLEAR_IMAGE_SEQ=$'\x1b_Ga=d,d=A\x1b\\'

# ============================================================================
# Helper Functions
# ============================================================================

get_mime_type() {
    local file="$1"
    file --brief --dereference --mime-type -- "$file" 2>/dev/null || echo "unknown"
}

get_preview_dimensions() {
    local dim="${FZF_PREVIEW_COLUMNS:-}x${FZF_PREVIEW_LINES:-}"
    
    # Fallback to terminal dimensions if fzf variables unavailable
    if [[ "$dim" == "x" ]]; then
        dim=$(stty size < /dev/tty | awk '{print $2 "x" $1}')
    # Avoid scrolling when image touches bottom of screen
    elif [[ ! ${KITTY_WINDOW_ID:-} ]] && \
         (( ${FZF_PREVIEW_TOP:-0} + ${FZF_PREVIEW_LINES:-0} == $(stty size < /dev/tty | awk '{print $1}') )); then
        dim="${FZF_PREVIEW_COLUMNS}x$((FZF_PREVIEW_LINES - 1))"
    fi
    
    echo "$dim"
}

# ============================================================================
# Preview Functions
# ============================================================================

preview_image() {
    local file="$1"
    local dim
    dim=$(get_preview_dimensions)
    
    # Use Kitty/Ghostty graphics protocol for highest quality
    if [[ ${KITTY_WINDOW_ID:-} || ${GHOSTTY_RESOURCES_DIR:-} ]] && command -v kitten &> /dev/null; then
        kitten icat \
            --clear \
            --transfer-mode=memory \
            --stdin=no \
            --align center \
            --place "${FZF_PREVIEW_COLUMNS}x${FZF_PREVIEW_LINES}@0x0" \
            "$file"
    # Fallback to Chafa
    elif command -v chafa &> /dev/null; then
        chafa --format=sixels --size="$dim" --animate=off "$file" 2>/dev/null || \
        chafa --format=symbols --symbols=all --size="$dim" --dither=ordered "$file"
        echo  # Newline for proper fzf rendering
    else
        echo "No image preview available. Install chafa or kitten." >&2
        file "$file"
    fi
}

preview_pdf() {
    local file="$1"
    local dim
    dim=$(get_preview_dimensions)
    
    if ! command -v pdftoppm &> /dev/null; then
        echo "PDF preview requires pdftoppm (poppler-utils)" >&2
        file "$file"
        return 1
    fi
    
    mkdir -p "$CACHE_DIR"
    
    local hash cached_img
    hash=$(echo -n "$file" | md5sum | cut -d' ' -f1)
    cached_img="$CACHE_DIR/$hash.jpg"
    
    # Generate cached image if not exists
    if [[ ! -f "$cached_img" ]]; then
        pdftoppm -jpeg -f 1 -singlefile "$file" "$CACHE_DIR/$hash" 2>/dev/null || return 1
    fi
    
    # Display cached PDF preview as image
    if [[ -f "$cached_img" ]]; then
        if [[ ${KITTY_WINDOW_ID:-} ]] && command -v kitten &> /dev/null; then
            kitten icat \
                --clear \
                --transfer-mode=memory \
                --stdin=no \
                --place="${dim}@0x0" \
                "$cached_img"
        elif command -v chafa &> /dev/null; then
            chafa --format=sixels --size="$dim" "$cached_img" 2>/dev/null || \
            chafa --format=symbols --symbols=all --size="$dim" "$cached_img"
        fi
    else
        echo "PDF preview generation failed" >&2
        file "$file"
        return 1
    fi
}

preview_text() {
    local file="$1"
    
    printf "%s" "$CLEAR_IMAGE_SEQ"
    
    if command -v batcat &> /dev/null; then
        batcat --style=numbers --color=always --pager=never "$file"
    elif command -v bat &> /dev/null; then
        bat --style=numbers --color=always --pager=never "$file"
    else
        cat "$file"
    fi
}

preview_directory() {
    local file="$1"
    
    printf "%s" "$CLEAR_IMAGE_SEQ"
    
    if command -v eza &> /dev/null; then
        eza --icons --color=always -la "$file"
    elif command -v ls &> /dev/null; then
        ls --color=always -lAh "$file" 2>/dev/null || ls -lAh "$file"
    fi
}

preview_archive() {
    local file="$1"
    
    printf "%s" "$CLEAR_IMAGE_SEQ"
    
    if command -v lesspipe &> /dev/null; then
        lesspipe "$file" 2>/dev/null
    else
        file "$file"
    fi
}

# ============================================================================
# Main Logic
# ============================================================================

main() {
    local file="$*"
    
    # Handle tilde expansion
    file="${file/#\~/$HOME}"
    
    # Validate file exists and is readable
    if [[ ! -r "$file" ]]; then
        echo "Error: File not readable: $file" >&2
        exit 1
    fi
    
    # Handle directories
    if [[ -d "$file" ]]; then
        preview_directory "$file"
        exit 0
    fi
    
    # Get MIME type for file classification
    local mime_type
    mime_type=$(get_mime_type "$file")
    
    # Route to appropriate preview function
    case "$mime_type" in
        image/*)
            preview_image "$file"
            ;;
        application/pdf)
            preview_pdf "$file"
            ;;
        text/*|*json|*xml|*javascript|*python)
            preview_text "$file"
            ;;
        *zip|*tar|*gzip|*rar|*7z*)
            preview_archive "$file"
            ;;
        *)
            file "$file"
            ;;
    esac
}

main "$@"
