#!/bin/bash

get_var_value() {
    local var_name="$1"
    local config_file="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../hyprland.conf"
    grep "^${var_name} = " "$config_file" | sed "s/${var_name} = //" | sed 's/ #.*$//' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//'
}

replace_vars() {
    local shortcut="$1"
    shortcut="${shortcut//\$mainMod/$(get_var_value '$mainMod')}"
    echo "$shortcut"
}

echo "Testing variable replacement:"
echo "Original: \$mainMod, Q Kill Window"
replace_vars '$mainMod, Q Kill Window'
