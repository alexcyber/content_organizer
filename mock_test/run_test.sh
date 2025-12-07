#!/bin/bash
# Convenient test runner for media organizer
# Usage: ./run_test.sh [--dry-run] [--reset]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_DIR="$SCRIPT_DIR/test_media"

cd "$PROJECT_ROOT"

# Parse arguments
DRY_RUN=""
RESET=false

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --reset)
            RESET=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run    Run in dry-run mode (no files moved)"
            echo "  --reset      Reset test environment before running"
            echo "  --help       Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Run organizer on test data"
            echo "  $0 --dry-run          # Preview without moving files"
            echo "  $0 --reset --dry-run  # Reset environment and preview"
            exit 0
            ;;
    esac
done

# Check if test environment exists
if [ ! -d "$TEST_DIR" ] || [ "$RESET" = true ]; then
    if [ "$RESET" = true ]; then
        echo "Resetting test environment..."
        bash "$SCRIPT_DIR/reset_test_environment.sh"
    else
        echo "Test environment not found. Creating..."
        bash "$SCRIPT_DIR/setup_test_environment.sh"
    fi
    echo ""
fi

# Load test environment variables
if [ -f "$SCRIPT_DIR/.env.test" ]; then
    echo "Loading test configuration from .env.test"
    export $(cat "$SCRIPT_DIR/.env.test" | grep -v '^#' | xargs)
else
    echo "ERROR: .env.test not found in $SCRIPT_DIR"
    exit 1
fi

echo ""
echo "============================================================================"
echo "Running Media Organizer in TEST MODE"
echo "============================================================================"
echo ""
echo "Configuration:"
echo "  Download Dir:    $MEDIA_DOWNLOAD_DIR"
echo "  Movie Dir:       $MEDIA_MOVIE_DIR"
echo "  TV Current Dir:  $MEDIA_TV_CURRENT_DIR"
echo "  TV Concluded Dir: $MEDIA_TV_CONCLUDED_DIR"
echo ""

if [ -n "$DRY_RUN" ]; then
    echo "MODE: DRY-RUN (no files will be moved)"
else
    echo "MODE: LIVE (files will be moved)"
fi

echo ""
echo "============================================================================"
echo ""

# Show what's in the download directory
echo "Files to process:"
find "$MEDIA_DOWNLOAD_DIR" -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) 2>/dev/null | wc -l | xargs echo "  Video files:"
find "$MEDIA_DOWNLOAD_DIR" -mindepth 1 -type d 2>/dev/null | wc -l | xargs echo "  Folders:"
echo ""

# Run the organizer
.venv/bin/python3 main.py $DRY_RUN

# Show summary if not dry-run
if [ -z "$DRY_RUN" ]; then
    echo ""
    echo "============================================================================"
    echo "Post-Run Summary"
    echo "============================================================================"
    echo ""
    echo "Remaining in Downloads:"
    find "$MEDIA_DOWNLOAD_DIR" -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) 2>/dev/null | wc -l | xargs echo "  Video files:"
    echo ""
    echo "Current Shows:"
    find "$MEDIA_TV_CURRENT_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | xargs echo "  Folders:"
    echo ""
    echo "Concluded Shows:"
    find "$MEDIA_TV_CONCLUDED_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | xargs echo "  Folders:"
    echo ""
    echo "Movies:"
    find "$MEDIA_MOVIE_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | xargs echo "  Folders:"
    echo ""
fi

echo "============================================================================"
echo "Test Complete!"
echo ""
echo "To reset and run again: $0 --reset"
echo "============================================================================"
