#!/bin/bash
# Setup test environment from CSV rubric
# Reads mock_test_rubric.csv and creates files/folders based on "Starting" column

set -e

# Get the directory where this script is located (mock_test/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="$SCRIPT_DIR/test_media"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CSV_FILE="$SCRIPT_DIR/mock_test_rubric.csv"

echo "============================================================================"
echo "Setting up test environment from CSV rubric"
echo "============================================================================"
echo "CSV File: $CSV_FILE"
echo "Test Directory: $TEST_DIR"
echo "Project Root: $PROJECT_ROOT"
echo ""

# Check if CSV file exists
if [ ! -f "$CSV_FILE" ]; then
    echo "ERROR: CSV rubric file not found at $CSV_FILE"
    exit 1
fi

# Clean up existing test directory
if [ -d "$TEST_DIR" ]; then
    echo "Removing existing test directory..."
    rm -rf "$TEST_DIR"
fi

# Create base directory structure
echo "Creating base directory structure..."
mkdir -p "$TEST_DIR/TV_Downloads"
mkdir -p "$TEST_DIR/Movies"
mkdir -p "$TEST_DIR/TV_Shows/Current"
mkdir -p "$TEST_DIR/TV_Shows/Concluded"
mkdir -p "$TEST_DIR/logs"
echo ""

echo "Creating directories from CSV (entries ending with /)..."

# Create directories - ONLY entries that end with /
tail -n +2 "$CSV_FILE" | while IFS=, read -r starting final test; do
    # Remove BOM and trim whitespace
    starting=$(echo "$starting" | sed 's/^\xEF\xBB\xBF//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

    # Skip if starting is empty or "Null"
    if [ -z "$starting" ] || [ "$starting" = "Null" ]; then
        continue
    fi

    # ONLY create directory if it explicitly ends with /
    if [[ "$starting" == */ ]]; then
        dir_path="${starting%/}"
        full_path="$TEST_DIR/${dir_path#./}"
        if [ ! -d "$full_path" ]; then
            echo "  Creating directory: $dir_path"
            mkdir -p "$full_path"
        fi
    fi
done

echo ""
echo "Creating files from CSV..."

# Create files - ONLY entries that do NOT end with /
tail -n +2 "$CSV_FILE" | while IFS=, read -r starting final test; do
    # Remove BOM and trim whitespace
    starting=$(echo "$starting" | sed 's/^\xEF\xBB\xBF//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

    # Skip if starting is empty or "Null"
    if [ -z "$starting" ] || [ "$starting" = "Null" ]; then
        continue
    fi

    # Skip if it ends with / (it's a directory, not a file)
    if [[ "$starting" == */ ]]; then
        continue
    fi

    # Construct full path (relative to test_media)
    full_path="$TEST_DIR/${starting#./}"

    # Create parent directory if needed
    dir_path=$(dirname "$full_path")
    if [ ! -d "$dir_path" ]; then
        mkdir -p "$dir_path"
    fi

    # Create empty file
    if [ ! -f "$full_path" ]; then
        echo "  Creating file: $starting"
        touch "$full_path"
    fi
done

echo ""
echo "============================================================================"
echo "Test Environment Setup Complete!"
echo "============================================================================"
echo ""
echo "Test Directory: $TEST_DIR"
echo ""

# Show statistics
echo "Statistics:"
echo "  Total entries in CSV: $(tail -n +2 "$CSV_FILE" | wc -l)"
echo "  Files created: $(find "$TEST_DIR" -type f | wc -l)"
echo "  Directories created: $(find "$TEST_DIR" -type d | wc -l)"
echo ""

# Show directory structure
echo "Directory Structure:"
if command -v tree &> /dev/null; then
    tree -L 2 "$TEST_DIR"
else
    find "$TEST_DIR" -maxdepth 2 -type d | sort
fi
echo ""

echo "To use this test environment:"
echo "  cd $SCRIPT_DIR"
echo "  ./run_test.sh --dry-run"
echo "============================================================================"
