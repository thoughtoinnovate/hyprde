#!/bin/bash

# Manual test of the launcher logic
echo "Testing wofi_launcher.sh manually..."

# Simulate user input
echo "Enter input (or press Ctrl+C to exit):"
read -r input

if [ -z "$input" ]; then
    echo "No input, exiting"
    exit 0
fi

echo "Input received: '$input'"

# Check dependencies
if ! command -v bc >/dev/null 2>&1 && ! command -v awk >/dev/null 2>&1; then
    echo "ERROR: No calculator found"
    exit 1
fi

# Check for calculator
CALCULATOR=""
if command -v bc >/dev/null 2>&1; then
    CALCULATOR="bc"
    echo "Using calculator: $CALCULATOR"
elif command -v awk >/dev/null 2>&1; then
    CALCULATOR="awk"
    echo "Using calculator: $CALCULATOR"
fi

# Check if input looks like a math expression
is_math_expression() {
    local input="$1"
    local clean_input=$(echo "$input" | tr -d '[:space:]')
    [[ "$clean_input" =~ [0-9] ]] && ([[ "$clean_input" =~ [+*/-] ]] || [[ "$clean_input" =~ [a-zA-Z] ]])
}

# Remove leading/trailing whitespace
input=$(echo "$input" | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
echo "Cleaned input: '$input'"

# Try to evaluate as a math expression
result=""
is_math=false

if is_math_expression "$input"; then
    echo "Detected as math expression"
    is_math=true
    if [ "$CALCULATOR" = "bc" ]; then
        result=$(echo "scale=2; $input" | bc -l 2>/dev/null)
    elif [ "$CALCULATOR" = "awk" ]; then
        result=$(echo "$input" | awk -F'+' '{print $1+$2}' 2>/dev/null || echo "$input" | awk -F'-' '{print $1-$2}' 2>/dev/null || echo "$input" | awk -F'*' '{print $1*$2}' 2>/dev/null || echo "$input" | awk -F'/' '{print $1/$2}' 2>/dev/null || echo "error")
    fi
    echo "Calculation result: '$result'"
else
    echo "Not detected as math expression"
fi

# Check result
if $is_math && [[ -n "$result" && "$result" =~ ^[0-9.-]+$ && "$result" != "error" ]]; then
    echo "✓ Would show calculator result: $result"
else
    echo "Checking if '$input' is a command..."
    if command -v "$input" >/dev/null 2>&1; then
        echo "✓ Would run command: $input"
    else
        echo "✓ Would show application launcher"
    fi
fi

echo "Test completed"
