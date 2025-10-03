#!/bin/bash

# Test the updated math detection logic
is_math_expression() {
    local input="$1"
    # Remove whitespace and check if it contains only numbers and math operators
    local clean_input=$(echo "$input" | tr -d '[:space:]')
    [[ "$clean_input" =~ ^[0-9+\-*/().]+$ ]] && [[ "$clean_input" =~ [+\-*/] ]]
}

test_input() {
    local input="$1"
    echo "Testing: '$input'"
    if is_math_expression "$input"; then
        echo "✓ Detected as math expression"
        # Test calculation
        result=$(echo "scale=2; $input" | bc -l 2>/dev/null)
        echo "  Result: $result"
    else
        echo "✗ Not a math expression"
    fi
    echo "---"
}

# Test various inputs
test_input "2+2"
test_input "10-3"
test_input "3*4"
test_input "8/2"
test_input "hello"
test_input "firefox"
test_input "2 + 2"
test_input "(5+3)*2"
test_input "sqrt(16)"
test_input ""
