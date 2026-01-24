# hyprde

An out-of-the-box, highly productive, and visually polished Hyprland desktop environment for Arch Linux and Debian-based distributions.

## 🚀 Features

- **Dynamic Configuration**: Automatically merges latest upstream Hyprland defaults with your custom settings via a TOML-based overrides system.
- **Intelligent File Search**: `SUPER + SHIFT + F` for fuzzy search with Nerd Font icons, opening in Yazi/Ghostty.
- **Pre-configured Tools**: Waybar, Mako (notifications), Wofi (launcher), Hypridle, and Hyprlock integration.
- **System Control Scripts**: Specialized scripts for brightness, audio, wifi, bluetooth, and power management.
- **Multi-OS Support**: Native support for Arch Linux and Debian/Ubuntu derivatives.
- **Robust Testing**: Built-in Python unit tests and Docker-based headless integration testing.

## 🛠 Architecture

This project uses a "Base + Overrides" model for its configuration:

1. **`hyprde.toml`**: Your single source of truth. Define your monitors, keybinds, and programs here.
2. **`build_config.py`**: A Python engine that downloads the official Hyprland example config, cleans it (removes conflicts), and applies your TOML settings.
3. **`hyprland.conf`**: The final generated config sourced by Hyprland.

## 📥 Installation

```bash
git clone https://github.com/thoughtoinnovate/hyprde.git
cd hyprde
chmod +x hyprde/install.sh
sudo ./hyprde/install.sh
```

The installation script will:
1. Detect your OS and install required packages from `config.yml`.
2. Back up your existing `~/.config/hypr` settings.
3. Generate a fresh, conflict-free configuration using the latest upstream defaults.

## ⚙️ Configuration

To customize your environment, edit:
`~/.config/hypr/hyprde.toml` (locally) or `hyprde/configs/hypr/hyprde.toml` (in the repo).

After editing, you can regenerate the config by running:
```bash
python3 ~/.config/hypr/build_config.py
```

## 🧪 Testing

### Local Unit Tests
Verifies the configuration builder logic:
```bash
./hyprde/configs/hypr/run_tests.sh
```

### Docker Integration Test
Launches a headless Hyprland session in a container to verify full syntax validity:
```bash
docker build -t hyprde-test -f test/Dockerfile.arch .
docker run --rm hyprde-test ./test/validate_config_headless.sh
```

## ⌨️ Keybindings (Highlights)

- `SUPER + T`: Terminal (Ghostty)
- `SUPER + E`: File Manager (Thunar)
- `SUPER + SPACE`: Launcher (Wofi)
- `SUPER + SHIFT + F`: Fuzzy File Search
- `SUPER + L`: Lock Screen
- `SUPER + Q`: Kill Active Window

---
*Maintained by the HyprDE team.*
