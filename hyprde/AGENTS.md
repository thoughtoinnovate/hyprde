# Development Guidelines (hyprde context)

## 🛠 Commands

### Installation
- **Install**: `./install.sh`

### Configuration
- **Edit Settings**: Edit `configs/hypr/hyprde.toml`
- **Apply Settings**: `python3 configs/hypr/build_config.py`

### Testing
- **Run Unit Tests**: `./configs/hypr/run_tests.sh`
- **Shell Lint**: `shellcheck configs/hypr/scripts/*.sh`

## 📜 Style

### Shell
- `#!/bin/bash`
- Use `"$variable"` quoting.
- JSON output for Waybar status scripts.

### UI & Icons
- ALL toggles/scripts MUST source `hyprrocket.icons` to define Nerd Font icons.
- Auto modes must use CSS classes (`.auto`, `.auto-theme`) for glow effects.

### TOML
- Follow the schema used by `build_config.py`.
- New sections in TOML must be supported in `build_config.py`.
