# Hyprocket

A Hyprland configuration setup for a productive desktop environment.

## Features

- **File Search**: Press `SUPER + SHIFT + F` to launch an intelligent file and directory search using fzf. It automatically detects case sensitivity (e.g., "HOME" triggers case-sensitive search, "home" is case-insensitive). Files and directories are displayed with Nerd Font icons and open in Yazi file manager via Ghostty terminal.

- **Performance Optimizations**: Uses ripgrep (rg) for fast text searches in scripts, fd for efficient file finding.

- **Custom Scripts**: Various scripts for brightness control, audio, wifi, bluetooth, temperature monitoring, etc.

## Installation

Run `./install.sh` as root to install the configuration.

## Prerequisites

See `config.yml` for required packages.

## Keybinds

- `SUPER + SHIFT + F`: File Search
- Other keybinds defined in `configs/hypr/hyprland.conf`

## Scripts

Located in `configs/hypr/scripts/`:

- `file_search.sh`: Fuzzy file/directory search
- `shortcuts-help.sh`: Display keyboard shortcuts
- And more...