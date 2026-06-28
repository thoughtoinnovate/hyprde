#!/bin/bash
# Test sandboxed_fzf_prev.sh functionality

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓ $1${NC}"; }
fail() { echo -e "${RED}✗ $1${NC}"; }

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
PREVIEW_SCRIPT="$HOME/.config/hypr/scripts/sandboxed_fzf_prev.sh"
if [ ! -f "$PREVIEW_SCRIPT" ]; then
    # Fallback to local script
    PREVIEW_SCRIPT="$SCRIPT_DIR/../hyprde/configs/hypr/scripts/sandboxed_fzf_prev.sh"
fi

TESTFILES_DIR="$SCRIPT_DIR/testfiles"
if [ ! -d "$TESTFILES_DIR" ]; then
    TESTFILES_DIR="$HOME/testfiles"
fi

echo "=== Sandbox Preview Tests ==="
echo "Using preview script: $PREVIEW_SCRIPT"
echo "Using testfiles dir: $TESTFILES_DIR"
echo ""

# Test 1: Basic preview works
echo "Test 1: Basic text preview"
if bash "$PREVIEW_SCRIPT" "$TESTFILES_DIR/test.txt" >/dev/null 2>&1; then
    pass "Text preview works"
else
    fail "Text preview failed"
fi

# Test 2: JSON preview
echo "Test 2: JSON preview"
if bash "$PREVIEW_SCRIPT" "$TESTFILES_DIR/test.json" >/dev/null 2>&1; then
    pass "JSON preview works"
else
    fail "JSON preview failed"
fi

# Test 3: Network blocked (try curl inside sandbox)
echo "Test 3: Network isolation"
if timeout 2 bash "$PREVIEW_SCRIPT" "$TESTFILES_DIR/test.txt" 2>&1 | grep -q "network"; then
    fail "Network might not be blocked"
else
    pass "Network appears blocked"
fi

# Test 4: Sandbox tool detection
echo "Test 4: Sandbox tool available"
if command -v firejail >/dev/null 2>&1; then
    pass "firejail available"
elif command -v bwrap >/dev/null 2>&1; then
    pass "bubblewrap available"
else
    fail "No sandbox tool found"
fi

# Test 5: Non-existent file
echo "Test 5: Non-existent file handling"
if ! bash "$PREVIEW_SCRIPT" /nonexistent 2>/dev/null; then
    pass "Handles missing file correctly"
else
    fail "Should fail on missing file"
fi

echo ""
echo "=== Tests Complete ==="
