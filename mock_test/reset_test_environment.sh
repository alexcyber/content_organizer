#!/bin/bash
# Reset test environment - Wipes and recreates test directory
# Safe to run multiple times
# Usage: ./reset_test_environment.sh [--sftp-delete]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="$SCRIPT_DIR/test_media"

# Parse arguments to pass through to setup script
SETUP_ARGS=""
for arg in "$@"; do
    if [ "$arg" = "--sftp-delete" ]; then
        SETUP_ARGS="$SETUP_ARGS --sftp-delete"
    fi
done

echo "============================================================================"
echo "Resetting Test Environment"
echo "============================================================================"

# Remove existing test directory
if [ -d "$TEST_DIR" ]; then
    echo "Removing existing test directory: $TEST_DIR"
    rm -rf "$TEST_DIR"
    echo "  ✓ Removed"
else
    echo "No existing test directory found"
fi

# Clear cache if it exists
CACHE_DIR="$TEST_DIR/.cache"
if [ -d "$CACHE_DIR" ]; then
    echo "Clearing cache: $CACHE_DIR"
    rm -rf "$CACHE_DIR"
    echo "  ✓ Cleared"
fi

# Remove lock file if it exists
LOCK_FILE="$TEST_DIR/.lock"
if [ -f "$LOCK_FILE" ]; then
    echo "Removing lock file: $LOCK_FILE"
    rm -f "$LOCK_FILE"
    echo "  ✓ Removed"
fi

echo ""
echo "Recreating test environment..."
echo ""

# Run setup script with arguments
bash "$SCRIPT_DIR/setup_test_environment.sh" $SETUP_ARGS
