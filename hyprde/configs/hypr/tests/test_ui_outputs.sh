#!/bin/bash

# Test script for HyprDE UI Outputs
# Verifies that scripts return the expected JSON for Waybar

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Adjust paths to point to the correct directories
BASE_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"
SCRIPTS_DIR="$BASE_DIR/scripts"
MAKO_DIR="$(dirname "$BASE_DIR")/mako"

errors=0

echo "Running HyprDE UI Output Tests..."

# 1. Test wifi.sh status
# Since we are running in a shell that doesn't 'source' the icons for bash output, 
# it will either show the literal variable name or the resolved icon.
# On this system, it seems to resolve to the icon.
echo -n "Testing wifi.sh status output... "
wifi_out=$(bash "$SCRIPTS_DIR/wifi.sh" status)
if echo "$wifi_out" | grep -q '"text": "'; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
    echo "  Expected icon in 'text' field, got: $wifi_out"
    errors=$((errors + 1))
fi

# 2. Test screen-record.sh status main (idle)
echo -n "Testing screen-record.sh status main (idle)... "
record_out=$(bash "$SCRIPTS_DIR/screen-record.sh" status main)
if [ "$record_out" == "{}" ]; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
    echo "  Expected empty JSON {}, got: $record_out"
    errors=$((errors + 1))
fi

# 3. Test screen-record.sh status (idle, control center)
echo -n "Testing screen-record.sh status (idle, control center)... "
record_out=$(bash "$SCRIPTS_DIR/screen-record.sh" status)
if echo "$record_out" | grep -q '"text": "'; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
    echo "  Expected idle icon, got: $record_out"
    errors=$((errors + 1))
fi

# 4. Test Mako Config (Dark)
echo -n "Testing Mako Dark config properties... "
if [ -f "$MAKO_DIR/config.dark" ] && grep -q "default-timeout=3000" "$MAKO_DIR/config.dark" && grep -q "border-radius=15" "$MAKO_DIR/config.dark"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
    echo "  Mako dark config missing or incorrect (timeout=3000, radius=15)"
    [ ! -f "$MAKO_DIR/config.dark" ] && echo "  File not found: $MAKO_DIR/config.dark"
    errors=$((errors + 1))
fi

# 5. Test Mako Config (Light)
echo -n "Testing Mako Light config properties... "
if [ -f "$MAKO_DIR/config.light" ] && grep -q "default-timeout=3000" "$MAKO_DIR/config.light" && grep -q "border-radius=15" "$MAKO_DIR/config.light"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
    echo "  Mako light config missing or incorrect (timeout=3000, radius=15)"
    [ ! -f "$MAKO_DIR/config.light" ] && echo "  File not found: $MAKO_DIR/config.light"
    errors=$((errors + 1))
fi

echo "---------------------------------------"
if [ $errors -eq 0 ]; then
    echo -e "${GREEN}ALL TESTS PASSED${NC}"
    exit 0
else
    echo -e "${RED}$errors TESTS FAILED${NC}"
    exit 1
fi
