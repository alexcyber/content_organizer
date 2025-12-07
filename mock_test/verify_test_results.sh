#!/bin/bash
# Verify test results against CSV rubric
# Checks that files/folders in "Final" column (where Test=TRUE) exist

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="$SCRIPT_DIR/test_media"
CSV_FILE="$SCRIPT_DIR/mock_test_rubric.csv"
REPORT_FILE="$SCRIPT_DIR/verification_report.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "============================================================================"
echo "CSV-Based Test Result Verification"
echo "============================================================================"
echo ""

# Check if CSV file exists
if [ ! -f "$CSV_FILE" ]; then
    echo -e "${RED}ERROR: CSV rubric file not found at $CSV_FILE${NC}"
    exit 1
fi

# Check if test environment exists
if [ ! -d "$TEST_DIR" ]; then
    echo -e "${RED}ERROR: Test environment not found at $TEST_DIR${NC}"
    echo "Run ./setup_test_environment.sh first"
    exit 1
fi

# Initialize report
{
    echo "Test Result Verification Report"
    echo "Generated: $(date)"
    echo "Test Directory: $TEST_DIR"
    echo "CSV Rubric: $CSV_FILE"
    echo "============================================================================"
    echo ""
} > "$REPORT_FILE"

echo -e "${BLUE}Verifying expected files and folders...${NC}"
echo ""

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Read CSV and verify files/folders from "Final" column (column 2) where Test=TRUE (column 3)
tail -n +2 "$CSV_FILE" | while IFS=, read -r starting final test; do
    # Remove BOM and trim whitespace
    final=$(echo "$final" | sed 's/^\xEF\xBB\xBF//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    test=$(echo "$test" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

    # Skip if final is empty or "Null"
    if [ -z "$final" ] || [ "$final" = "Null" ]; then
        continue
    fi

    # Skip if Test is not TRUE
    if [ "$test" != "TRUE" ] && [ "$test" != "true" ]; then
        continue
    fi

    # Construct full path (relative to test_media)
    full_path="$TEST_DIR/${final#./}"

    # Check if this is a directory - ONLY based on trailing /
    if [[ "$final" == */ ]]; then
        # It's a directory - remove trailing / from path
        full_path="${full_path%/}"

        # Verify directory exists
        if [ -d "$full_path" ]; then
            echo -e "  ${GREEN}✓${NC} Directory exists: $final"
            echo "PASS" >> /tmp/test_results.txt
        else
            echo -e "  ${RED}✗${NC} Directory MISSING: $final"
            echo "FAIL" >> /tmp/test_results.txt
            {
                echo "MISSING DIRECTORY: $final"
                echo "  Expected at: $full_path"
            } >> "$REPORT_FILE"
        fi
    else
        # It's a file
        # Verify file exists
        if [ -f "$full_path" ]; then
            echo -e "  ${GREEN}✓${NC} File exists: $final"
            echo "PASS" >> /tmp/test_results.txt
        else
            echo -e "  ${RED}✗${NC} File MISSING: $final"
            echo "FAIL" >> /tmp/test_results.txt
            {
                echo "MISSING FILE: $final"
                echo "  Expected at: $full_path"
            } >> "$REPORT_FILE"
        fi
    fi
done

# Count results (trim whitespace and ensure single line)
# Note: grep -c always returns a count (even 0), so no need for || echo "0"
TOTAL_TESTS=$(wc -l < /tmp/test_results.txt | tr -d ' \n')
PASSED_TESTS=$(grep -c "PASS" /tmp/test_results.txt 2>/dev/null | tr -d ' \n')
FAILED_TESTS=$(grep -c "FAIL" /tmp/test_results.txt 2>/dev/null | tr -d ' \n')

# Debug: Save test results file for inspection if needed
# cp /tmp/test_results.txt /tmp/test_results_debug.txt 2>/dev/null || true

# Cleanup temp files
rm -f /tmp/test_results.txt

echo ""
echo "============================================================================"
echo "Verification Summary"
echo "============================================================================"
echo ""
echo "Total tests: $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"
echo ""

# Save summary to report
{
    echo ""
    echo "SUMMARY:"
    echo "  Total tests: $TOTAL_TESTS"
    echo "  Passed: $PASSED_TESTS"
    echo "  Failed: $FAILED_TESTS"
    echo ""
} >> "$REPORT_FILE"

if [ "$FAILED_TESTS" -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ SUCCESS: All expected files and folders verified!          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    {
        echo "RESULT: SUCCESS - All tests passed"
    } >> "$REPORT_FILE"
    SUCCESS_CODE=0
else
    echo -e "${RED}╔════════════════════════════════════════════════════════════════╗${NC}"
    printf "${RED}║  ✗ FAILURE: %-3s test(s) failed%33s║${NC}\n" "$FAILED_TESTS" ""
    echo -e "${RED}╚════════════════════════════════════════════════════════════════╝${NC}"
    {
        echo "RESULT: FAILURE - $FAILED_TESTS tests failed"
    } >> "$REPORT_FILE"
    SUCCESS_CODE=1
fi

echo ""
echo "Full report saved to: $REPORT_FILE"
echo ""
echo "============================================================================"

exit $SUCCESS_CODE
