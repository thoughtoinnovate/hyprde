#!/usr/bin/env bash

FILE="$1"

[[ -z "$FILE" ]] && exit 1
[[ ! -e "$FILE" ]] && exit 1

# Preview directories
if [ -d "$FILE" ]; then
    ls -lah --color=always "$FILE" 2>/dev/null
    exit 0
fi

# Preview files
if [ -f "$FILE" ]; then
    mime_type=$(file --mime-type -b "$FILE" 2>/dev/null)
    
    if [[ "$mime_type" =~ ^image/ ]]; then
        # Use chafa with symbols format - this worked
        if command -v chafa >/dev/null 2>&1; then
            clear
            chafa --format=symbols --size="${FZF_PREVIEW_COLUMNS:-80}x${FZF_PREVIEW_LINES:-40}" \
                --animate=off "$FILE" 2>/dev/null
        else
            echo "Image: $FILE (chafa not installed)"
        fi
    else
        # Text file preview
        if command -v bat >/dev/null 2>&1; then
            bat --color=always --style=numbers --line-range=:500 "$FILE" 2>/dev/null
        else
            head -n 500 "$FILE" 2>/dev/null
        fi
    fi
fi

