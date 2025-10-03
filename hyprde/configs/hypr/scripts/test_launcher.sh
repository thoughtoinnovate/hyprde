#!/bin/bash

# Test version without GUI
echo "Testing wofi_launcher.sh logic..."

# Check dependencies
if ! command -v wofi >/dev/null 2>&1; then
    echo "ERROR: wofi is not installed"
    exit 1
fi

# Check for calculator (prefer bc, fallback to awk)
CALCULATOR=""
if command -v bc >/dev/null 2>&1; then
    CALCULATOR="bc"
    echo "Using bc for calculations"
elif command -v awk >/dev/null 2>&1; then
    CALCULATOR="awk"
    echo "Using awk for calculations"
else
    echo "ERROR: No calculator found (bc or awk)"
    exit 1
fi

# Test math evaluation
test_math() {
    local input="$1"
    echo "Testing input: '$input'"
    
    result=""
    if [ "$CALCULATOR" = "bc" ]; then
        result=$(echo "scale=2; $input" | bc -l 2>/dev/null)
        echo "bc result: '$result'"
    elif [ "$CALCULATOR" = "awk" ]; then
        # Use awk for basic arithmetic
        result=$(echo "$input" | awk -F'+' '{print $1+$2}' 2>/dev/null || echo "$input" | awk -F'-' '{print $1-$2}' 2>/dev/null || echo "$input" | awk -F'*' '{print $1*$2}' 2>/dev/null || echo "$input" | awk -F'/' '{print $1/$2}' 2>/dev/null || echo "error")
        echo "awk result: '$result'"
    fi

    # Check if we got a valid number result
    if [[ -n "$result" && "$result" =~ ^[0-9.-]+$ && "$result" != "error" ]]; then
        echo "✓ Valid math result: $result"
    else
        echo "✗ Not a math expression or invalid result: '$result'"
    fi
    echo "---"
}

# Test various inputs
test_math "2+2"
test_math "10-3"
test_math "3*4"
test_math "8/2"
test_math "hello"
test_math ""

echo "Test completed"
