# AGENTS.md

## Build/Lint/Test Commands
This is a configuration repository with no traditional build system.
- **Install**: `./hyprde/install.sh` (requires root privileges)
- **Test single script**: `bash hyprde/configs/hypr/scripts/<script>.sh <args>`
- **Validate YAML**: `yq < hyprde/config.yml` (checks syntax)
- **Shell lint**: `shellcheck hyprde/configs/hypr/scripts/*.sh` (if shellcheck installed)

## Code Style Guidelines

### Shell Scripts
- Use `#!/bin/bash` shebang
- Functions: `function_name() { ... }`
- Variables: lowercase with underscores (`variable_name`)
- Arguments: Use `$1`, `$2`, etc. with case statements for flags
- Error handling: Basic checks with `exit 1` for missing args
- Comments: Minimal, only for complex logic
- Quotes: Double quotes for variables `"$variable"`

### Configuration Files
- YAML: 2-space indentation, descriptive keys
- TOML/Conf: Follow tool-specific conventions
- CSS: Standard CSS formatting

### General
- No trailing whitespace
- LF line endings
- Executable scripts: `chmod +x` after creation
- File permissions: Scripts executable, configs readable