# Hyprocket (HyprDE Core)

Hyprocket is the core configuration engine of the HyprDE project. It provides a modular, maintainable, and robust way to manage Hyprland dotfiles.

## 🌟 Core Philosophy

Instead of maintaining a massive, fragile `hyprland.conf` that breaks with every Hyprland update, Hyprocket uses a **TOML-based configuration** that is dynamically merged with upstream defaults.

## 📂 Structure

- `hyprde.toml`: Define your preferences here.
- `build_config.py`: The build engine that creates the actual Hyprland config.
- `scripts/`: A collection of high-quality bash scripts for system integration.
- `applications/`: Custom desktop entries for power management (reboot, shutdown, etc.).

## 🔧 The `hyprde.toml` File

The configuration is split into logical sections:

- **`[monitors]`**: Define monitor resolutions and scaling.
- **`[programs]`**: Define your preferred terminal, file manager, etc.
- **`[binds]`**: Manage your keyboard shortcuts cleanly.
- **`[rules]`**: Define window-specific behaviors (floating, pinning, opacity).
- **`[env]`**: Set environment variables.

## ⌨️ Advanced Scripting

Many features are powered by custom scripts in `scripts/`:

- **File Search**: Uses `fzf`, `fd`, and `bat` for a powerful terminal-based search experience.
- **Dynamic Wallpapers**: Automatically rotates wallpapers based on time of day.
- **Brightness/Audio**: Smooth OSD-compatible controls.

## 🚀 Updating

To pull upstream defaults matching your local Hyprland version without losing your settings:
```bash
python3 build_config.py
```
This will automatically detect your local Hyprland version, download the corresponding `hyprland.base.conf` from GitHub, and rebuild your `hyprland.conf`.
