#!/bin/bash
# Check for failed move operations
# Compares expected moves vs actual results

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="$SCRIPT_DIR/test_media"
LOG_FILE="$TEST_DIR/logs/organizer.log"
REPORT_FILE="$SCRIPT_DIR/move_failures_report.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "============================================================================"
echo "Move Operation Failure Checker"
echo "============================================================================"
echo ""

# Check if test environment exists
if [ ! -d "$TEST_DIR" ]; then
    echo -e "${RED}ERROR: Test environment not found at $TEST_DIR${NC}"
    echo "Run ./setup_test_environment.sh first"
    exit 1
fi

# Function to count files in a directory
count_files() {
    local dir="$1"
    if [ -d "$dir" ]; then
        find "$dir" -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) 2>/dev/null | wc -l
    else
        echo "0"
    fi
}

# Function to count folders
count_folders() {
    local dir="$1"
    if [ -d "$dir" ]; then
        find "$dir" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l
    else
        echo "0"
    fi
}

# Initialize report
{
    echo "Move Operation Failure Report"
    echo "Generated: $(date)"
    echo "Test Directory: $TEST_DIR"
    echo "============================================================================"
    echo ""
} > "$REPORT_FILE"

echo -e "${BLUE}Analyzing test environment...${NC}"
echo ""

# Count files in each location
downloads_files=$(count_files "$TEST_DIR/TV_Downloads")
current_folders=$(count_folders "$TEST_DIR/TV_Shows/Current")
concluded_folders=$(count_folders "$TEST_DIR/TV_Shows/Concluded")
movie_folders=$(count_folders "$TEST_DIR/Movies")

echo "Current State:"
echo "  TV Downloads: $downloads_files video files remaining"
echo "  Current Shows: $current_folders folders"
echo "  Concluded Shows: $concluded_folders folders"
echo "  Movies: $movie_folders folders"
echo ""

# Check if log file exists
if [ ! -f "$LOG_FILE" ]; then
    echo -e "${YELLOW}WARNING: No log file found at $LOG_FILE${NC}"
    echo "This might mean the organizer hasn't been run yet."
    echo ""
    echo "Run ./run_test.sh first to generate logs."
    exit 0
fi

echo -e "${BLUE}Analyzing log file for errors...${NC}"
echo ""

# Extract errors from log
ERRORS_FOUND=0

# Check for explicit error messages
if grep -q "ERROR" "$LOG_FILE"; then
    echo -e "${RED}✗ ERROR messages found in log:${NC}"
    grep "ERROR" "$LOG_FILE" | tail -10
    ERRORS_FOUND=$((ERRORS_FOUND + 1))
    echo ""

    {
        echo "ERRORS FOUND:"
        grep "ERROR" "$LOG_FILE"
        echo ""
    } >> "$REPORT_FILE"
fi

# Check for failed move operations
if grep -q "Failed to move" "$LOG_FILE"; then
    echo -e "${RED}✗ Failed move operations detected:${NC}"
    grep "Failed to move" "$LOG_FILE"
    ERRORS_FOUND=$((ERRORS_FOUND + 1))
    echo ""

    {
        echo "FAILED MOVES:"
        grep "Failed to move" "$LOG_FILE"
        echo ""
    } >> "$REPORT_FILE"
fi

# Check for permission denied errors
if grep -qi "permission denied" "$LOG_FILE"; then
    echo -e "${RED}✗ Permission denied errors found:${NC}"
    grep -i "permission denied" "$LOG_FILE"
    ERRORS_FOUND=$((ERRORS_FOUND + 1))
    echo ""

    {
        echo "PERMISSION ERRORS:"
        grep -i "permission denied" "$LOG_FILE"
        echo ""
    } >> "$REPORT_FILE"
fi

# Check for files that should have been processed but weren't
if [ $downloads_files -gt 3 ]; then
    echo -e "${YELLOW}⚠ Warning: $downloads_files files still in TV_Downloads${NC}"
    echo "   Expected: Most files should be moved (only non-video files should remain)"
    echo ""
    echo "   Remaining files:"
    find "$TEST_DIR/TV_Downloads" -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) -exec basename {} \; | head -10
    echo ""

    {
        echo "UNMOVED FILES (in TV_Downloads):"
        find "$TEST_DIR/TV_Downloads" -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) -exec basename {} \;
        echo ""
    } >> "$REPORT_FILE"
fi

# Extract only the most recent run from log file
# Find the last occurrence of "Media File Organizer - Starting"
TEMP_LOG=$(mktemp)
awk '/Media File Organizer - Starting/ {found=NR} found {lines[NR]=$0} END {for(i=found; i<=NR; i++) print lines[i]}' "$LOG_FILE" > "$TEMP_LOG"

# Analyze move success rate from most recent run only
total_moved=$(grep -c "Moved:" "$TEMP_LOG" 2>/dev/null || echo "0")
total_processed=$(grep -c "Processing:" "$TEMP_LOG" 2>/dev/null || echo "0")

# Remove any leading/trailing whitespace and ensure they're valid integers
total_moved=$(echo "$total_moved" | xargs)
total_processed=$(echo "$total_processed" | xargs)

# Default to 0 if empty
total_moved=${total_moved:-0}
total_processed=${total_processed:-0}

if [ "$total_processed" -gt 0 ] 2>/dev/null; then
    success_rate=$(( total_moved * 100 / total_processed ))

    echo "Move Statistics (Most Recent Run):"
    echo "  Total items processed: $total_processed"
    echo "  Successfully moved: $total_moved"
    echo "  Success rate: $success_rate%"
    echo ""

    {
        echo "STATISTICS:"
        echo "  Total processed: $total_processed"
        echo "  Successfully moved: $total_moved"
        echo "  Success rate: $success_rate%"
        echo ""
    } >> "$REPORT_FILE"

    if [ $success_rate -lt 90 ]; then
        echo -e "${RED}✗ Low success rate detected!${NC}"
        ERRORS_FOUND=$((ERRORS_FOUND + 1))
    elif [ $success_rate -lt 100 ]; then
        echo -e "${YELLOW}⚠ Some operations may have failed${NC}"
    else
        echo -e "${GREEN}✓ All moves successful!${NC}"
    fi
    echo ""
fi

# Check for specific problematic files
echo -e "${BLUE}Checking for common issues...${NC}"
echo ""

ISSUES_FOUND=0

# Check for files with special characters
special_char_files=$(find "$TEST_DIR/TV_Downloads" -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) -name "*[*" 2>/dev/null | wc -l)
if [ $special_char_files -gt 0 ]; then
    echo -e "${YELLOW}⚠ Files with brackets found (may cause issues):${NC}"
    find "$TEST_DIR/TV_Downloads" -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) -name "*[*" -exec basename {} \;
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    echo ""
fi

# Check for duplicate files (same name in multiple locations)
echo "Checking for duplicate file names..."
temp_file=$(mktemp)
find "$TEST_DIR" -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) -exec basename {} \; | sort > "$temp_file"
duplicates=$(uniq -d "$temp_file")
if [ -n "$duplicates" ]; then
    echo -e "${YELLOW}⚠ Duplicate file names found:${NC}"
    echo "$duplicates"
    echo ""

    {
        echo "DUPLICATE FILE NAMES:"
        echo "$duplicates"
        echo ""
    } >> "$REPORT_FILE"
fi
rm "$temp_file"

# Final summary
echo "============================================================================"
echo "Summary"
echo "============================================================================"
echo ""

if [ $ERRORS_FOUND -eq 0 ] && [ $downloads_files -le 3 ]; then
    echo -e "${GREEN}✓ No failures detected!${NC}"
    echo -e "${GREEN}✓ All video files appear to have been moved successfully${NC}"
    {
        echo "RESULT: SUCCESS - No failures detected"
    } >> "$REPORT_FILE"
elif [ $ERRORS_FOUND -gt 0 ]; then
    echo -e "${RED}✗ $ERRORS_FOUND error(s) detected${NC}"
    echo -e "${YELLOW}⚠ See details above and in: $REPORT_FILE${NC}"
    {
        echo "RESULT: FAILURES DETECTED - $ERRORS_FOUND errors"
    } >> "$REPORT_FILE"
else
    echo -e "${YELLOW}⚠ Potential issues detected${NC}"
    echo -e "${YELLOW}⚠ Review details above${NC}"
    {
        echo "RESULT: WARNING - Potential issues"
    } >> "$REPORT_FILE"
fi

echo ""
echo "Full report saved to: $REPORT_FILE"
echo ""

# Suggest next steps
if [ $ERRORS_FOUND -gt 0 ] || [ $downloads_files -gt 3 ]; then
    echo "Suggested next steps:"
    echo "  1. Review the full log: less $LOG_FILE"
    echo "  2. Check file permissions: ls -la $TEST_DIR/TV_Downloads"
    echo "  3. Re-run in dry-run mode: ./run_test.sh --dry-run"
    echo "  4. Reset and try again: ./reset_test_environment.sh"
fi

echo "============================================================================"

# Cleanup temp file
rm -f "$TEMP_LOG"

# Exit with error code if failures found
if [ $ERRORS_FOUND -gt 0 ]; then
    exit 1
else
    exit 0
fi
