## Build/Lint/Test Commands
This is a Hyprland configuration repository with no traditional build system.
- **Install**: `./install.sh` (requires root privileges, installs packages and copies configs)
- **Test single script**: `bash configs/hypr/scripts/<script>.sh <args>` (e.g., `bash configs/hypr/scripts/audio-ctrl.sh --inc`)
- **Validate YAML**: `yq < config.yml` (checks syntax)
- **Shell lint**: `shellcheck configs/hypr/scripts/*.sh` (if shellcheck installed)
- **Validate JSON output**: `bash configs/hypr/scripts/<script>.sh status | jq .` (for Waybar-compatible scripts)

## Code Style Guidelines

### Shell Scripts
- Shebang: `#!/bin/bash`
- Functions: `function_name() { ... }` (lowercase with underscores)
- Variables: lowercase with underscores (`variable_name`), double quotes `"$variable"`
- Arguments: `$1`, `$2`, etc. with case statements for flags
- Error handling: Basic validation with `exit 1`, usage messages for invalid args
- Comments: Minimal, only for complex logic (avoid redundant comments)
- Output: JSON for Waybar modules, notifications via `notify-send` for user feedback

### Configuration Files
- YAML: 2-space indentation, descriptive keys, package arrays for dependencies
- TOML/Conf: Follow tool-specific conventions (Hyprland, Mako, Waybar, Wofi)
- CSS: Standard formatting with tool-specific class names

### General
- No trailing whitespace, LF line endings
- Scripts: Executable (`chmod +x`), configs readable
- File structure: `configs/` for dotfiles, `install.sh` for setup, `config.yml` for dependencies