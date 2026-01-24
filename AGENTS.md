# Development Guidelines (AGENTS.md)

## 🛠 Build & Test Commands

### Installation
- **Full Install**: `sudo ./hyprde/install.sh`

### Configuration Building
- **Rebuild Config**: `python3 hyprde/configs/hypr/build_config.py`
- **Verify Syntax**: `./test/validate_config_headless.sh` (Requires Hyprland installed)

### Testing
- **Run Unit Tests**: `./hyprde/configs/hypr/run_tests.sh`
- **Docker Integration Test**: 
  ```bash
  docker build -t hyprde-test -f test/Dockerfile.arch .
  docker run --rm hyprde-test ./test/validate_config_headless.sh
  ```

## 📜 Code Style Guidelines

### Python (Config Builder)
- Use standard library as much as possible (e.g., `tomllib`, `urllib`).
- Maintain compatibility with Python 3.11+.
- Use `unittest` for all logic verification.

### Shell Scripts
- Use `#!/bin/bash` shebang.
- Functions: `function_name() { ... }`.
- Variables: lowercase with underscores (`variable_name`).
- Quotes: Always double-quote variables `"$var"`.

### Configuration (TOML)
- Keep `hyprde.toml` clean and well-commented.
- Use the `[custom]` block for raw lines that don't fit the schema.

### Git Workflow
- Atomic commits preferred.
- Use conventional commit messages (`feat:`, `fix:`, `test:`, `docs:`).
