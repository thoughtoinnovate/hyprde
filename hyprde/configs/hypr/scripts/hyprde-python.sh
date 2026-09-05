if [ -z "${_HYPRDE_PYTHON_BIN:-}" ]; then
    if [ -f "/tmp/hyprde_python_bin" ]; then
        _HYPRDE_PYTHON_BIN=$(cat /tmp/hyprde_python_bin)
    else
        _HYPRDE_PYTHON_BIN=""
        for _c in /usr/bin/python3 python3; do
            _resolved="$(command -v "$_c" 2>/dev/null || echo "$_c")"
            case "$_resolved" in
                *python3*|*python3.*)
                    if "$_resolved" -c "import tomlkit" 2>/dev/null; then
                        _HYPRDE_PYTHON_BIN="$_resolved"
                        echo "$_resolved" > /tmp/hyprde_python_bin
                        break
                    fi
                    ;;
            esac
        done
        unset _c _resolved
        [ -n "$_HYPRDE_PYTHON_BIN" ] || _HYPRDE_PYTHON_BIN="python3"
    fi
fi

if [ "$_HYPRDE_PYTHON_BIN" != "python3" ]; then
    python3() { "$_HYPRDE_PYTHON_BIN" "$@"; }
    export -f python3 2>/dev/null || true
fi
