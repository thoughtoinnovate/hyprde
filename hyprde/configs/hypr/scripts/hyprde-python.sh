# hyprde-python.sh — source this from HyprDE shell scripts.
#
# Problem: on some machines the first `python3` on PATH is a Nix/home-weave
# interpreter without tomlkit/pygobject, while the system /usr/bin/python3
# has everything install.sh deployed. Symptoms: "ModuleNotFoundError:
# No module named 'tomlkit'" (settings), dead toggles (redglow, theme...).
#
# Effect: defines a `python3` shell function routing to the first interpreter
# that can `import tomlkit`. Zero call-site changes needed; heredocs
# (`python3 - <<'EOF'`) and pipes (`... | python3 -c ...`) keep working.
# If no interpreter has tomlkit, falls back to plain `python3` (and the
# settings_manager.py pre-flight will report exactly what to install).
#
# Idempotent: safe to source multiple times (guarded by _HYPRDE_PYTHON_BIN).

if [ -z "${_HYPRDE_PYTHON_BIN:-}" ]; then
    _HYPRDE_PYTHON_BIN=""
    for _c in /usr/bin/python3 python3; do
        _resolved="$(command -v "$_c" 2>/dev/null || echo "$_c")"
        case "$_resolved" in
            *python3*|*python3.*)
                if "$_resolved" -c "import tomlkit" 2>/dev/null; then
                    _HYPRDE_PYTHON_BIN="$_resolved"
                    break
                fi
                ;;
        esac
    done
    unset _c _resolved
    [ -n "$_HYPRDE_PYTHON_BIN" ] || _HYPRDE_PYTHON_BIN="python3"
fi

if [ "$_HYPRDE_PYTHON_BIN" != "python3" ]; then
    python3() { "$_HYPRDE_PYTHON_BIN" "$@"; }
    export -f python3 2>/dev/null || true
fi
