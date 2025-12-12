#!/bin/bash
# Setup test environment from CSV rubric
# Reads mock_test_rubric.csv and creates files/folders based on "Starting" and "Remote" columns
# Usage: ./setup_test_environment.sh [--sftp-delete]

set -e

# Get the directory where this script is located (mock_test/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="$SCRIPT_DIR/test_media"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CSV_FILE="$SCRIPT_DIR/mock_test_rubric.csv"

# Source SFTP helper functions
source "$SCRIPT_DIR/sftp_helper.sh"

# Parse arguments
USE_SFTP=false
for arg in "$@"; do
    if [ "$arg" = "--sftp-delete" ]; then
        USE_SFTP=true
    fi
done

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

# Check if SFTP should be used (only if --sftp-delete was passed)
if [ "$USE_SFTP" = true ] && is_sftp_enabled; then
    echo "SFTP Configuration detected:"
    echo "  Host: $SFTP_HOST:$SFTP_PORT"
    echo "  Remote Dir: $SFTP_REMOTE_DIR"
    echo ""

    # Test SFTP connection
    if ! sftp_test_connection; then
        echo ""
        echo "WARNING: SFTP connection failed. Remote files will not be created."
        echo "         Local test environment will still be set up."
        echo ""
        SFTP_ENABLED=false
    else
        SFTP_ENABLED=true
        echo ""
        # Clean up remote directory
        echo "Cleaning up remote SFTP directory..."
        sftp_cleanup_all
        echo ""
    fi
else
    if [ "$USE_SFTP" = true ]; then
        echo "WARNING: --sftp-delete specified but SFTP not configured in .env.test"
        echo ""
    else
        echo "SFTP disabled (use --sftp-delete to enable remote file creation)"
        echo ""
    fi
    SFTP_ENABLED=false
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
REMOTE_DIRS_CREATED=0
while IFS=, read -r remote starting final test || [ -n "$remote" ]; do
    # Remove BOM and trim whitespace
    remote=$(echo "$remote" | sed 's/^\xEF\xBB\xBF//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    starting=$(echo "$starting" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

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

        # Create remote directory if specified and SFTP is enabled
        if [ "$SFTP_ENABLED" = true ] && [ -n "$remote" ] && [ "$remote" != "Null" ]; then
            if [[ "$remote" == */ ]]; then
                echo "    Creating remote directory: $remote"
                sftp_create_directory "$remote" || echo "      WARNING: Failed to create remote directory"
                REMOTE_DIRS_CREATED=$((REMOTE_DIRS_CREATED + 1))
            fi
        fi
    fi
done < <(tail -n +2 "$CSV_FILE")

echo ""
echo "Creating files from CSV..."

# Create files - ONLY entries that do NOT end with /
REMOTE_FILES_CREATED=0
while IFS=, read -r remote starting final test || [ -n "$remote" ]; do
    # Remove BOM and trim whitespace
    remote=$(echo "$remote" | sed 's/^\xEF\xBB\xBF//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    starting=$(echo "$starting" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

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

    # Create file with content (100 bytes, matching remote file size)
    # Note: Video files must be non-zero bytes to pass stability checks
    if [ ! -f "$full_path" ]; then
        echo "  Creating file: $starting"
        dd if=/dev/zero of="$full_path" bs=100 count=1 2>/dev/null
    fi

    # Create remote file if specified and SFTP is enabled
    if [ "$SFTP_ENABLED" = true ] && [ -n "$remote" ] && [ "$remote" != "Null" ]; then
        if [[ "$remote" != */ ]]; then
            echo "    Creating remote file: $remote"
            sftp_create_file "$remote" 100 || echo "      WARNING: Failed to create remote file"
            REMOTE_FILES_CREATED=$((REMOTE_FILES_CREATED + 1))
        fi
    fi
done < <(tail -n +2 "$CSV_FILE")

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
echo "  Local files created: $(find "$TEST_DIR" -type f | wc -l)"
echo "  Local directories created: $(find "$TEST_DIR" -type d | wc -l)"

if [ "$SFTP_ENABLED" = true ]; then
    echo ""
    echo "Remote SFTP Statistics:"
    echo "  Remote files created: $REMOTE_FILES_CREATED"
    echo "  Remote directories created: $REMOTE_DIRS_CREATED"
fi
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
