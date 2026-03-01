#!/bin/bash

# Function to map file/directory to Nerd Font symbol
get_symbol() {
    local file="$1"
    if [ -d "$file" ]; then
        echo ""  # nf-fa-folder
    else
        local ext="${file##*.}"
        case "$ext" in
            pdf) echo "" ;;  # nf-fa-file_pdf_o
            sh|bash) echo "" ;;  # nf-oct-terminal
            txt|md) echo "" ;;  # nf-fa-file_text_o
            jpg|jpeg|png|gif|bmp|raw|cr2|nef) echo "" ;;  # nf-fa-file_image_o
            mp4|avi|mkv|mov) echo "" ;;  # nf-fa-file_video_o
            mp3|wav|flac|ogg) echo "" ;;  # nf-fa-file_audio_o
            zip|tar|gz|bz2|xz|7z) echo "" ;;  # nf-fa-file_archive_o
            html|htm) echo "" ;;  # nf-fa-globe
            css) echo "" ;;  # nf-fa-css3
            json|xml) echo "" ;;  # nf-fa-file_code_o
            py) echo "" ;;  # nf-dev-python
            js) echo "" ;;  # nf-dev-javascript
            java) echo -e "\ue256" ;;  # nf-dev-java
            scala) echo -e "\ue68e" ;;  # nf-dev-scala
            rs) echo -e "\ue68b" ;;  # nf-dev-rust
            go) echo -e "\udb81\udfd3" ;;  # nf-dev-go
            c|cpp|h) echo -e "\ue771" ;;  # nf-fa-code
            *) echo "" ;;  # nf-fa-file_o
        esac
    fi
}