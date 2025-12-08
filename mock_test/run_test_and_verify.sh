#!/bin/bash
# Run test and automatically check for failures
# Combines run_test.sh with failure detection

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
DRY_RUN=""
RESET=false
SFTP_DELETE=""

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
        --sftp-delete)
            SFTP_DELETE="--sftp-delete"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Runs the test and automatically checks for move failures"
            echo ""
            echo "Options:"
            echo "  --dry-run       Run in dry-run mode (no files moved)"
            echo "  --reset         Reset test environment before running"
            echo "  --sftp-delete   Enable SFTP remote file deletion"
            echo "  --help          Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                         # Run and verify"
            echo "  $0 --dry-run               # Dry-run only (no verification)"
            echo "  $0 --reset                 # Reset, run, and verify"
            echo "  $0 --reset --sftp-delete   # Reset, run with SFTP deletion, verify"
            echo ""
            echo "Note: --sftp-delete is usually auto-detected from .env.test configuration"
            exit 0
            ;;
    esac
done

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Media Organizer - Test & Verify                       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Run the test
echo -e "${BLUE}━━━ Step 1: Running Test ━━━${NC}"
echo ""

# Build arguments for run_test.sh
RUN_ARGS=""
if [ "$RESET" = true ]; then
    RUN_ARGS="$RUN_ARGS --reset"
fi
if [ -n "$DRY_RUN" ]; then
    RUN_ARGS="$RUN_ARGS --dry-run"
fi
if [ -n "$SFTP_DELETE" ]; then
    RUN_ARGS="$RUN_ARGS --sftp-delete"
fi

"$SCRIPT_DIR/run_test.sh" $RUN_ARGS
TEST_EXIT_CODE=$?

echo ""

# If dry-run, skip verification
if [ -n "$DRY_RUN" ]; then
    echo -e "${YELLOW}Dry-run mode: Skipping failure verification${NC}"
    echo ""
    echo "To verify actual moves, run: $0 (without --dry-run)"
    exit $TEST_EXIT_CODE
fi

# Step 2: Wait a moment for files to settle
echo -e "${BLUE}━━━ Step 2: Verifying Move Operations ━━━${NC}"
echo ""
sleep 1

# Step 3: Verify against CSV rubric
"$SCRIPT_DIR/verify_test_results.sh"
VERIFY_EXIT_CODE=$?

echo ""

# Final summary
if [ $TEST_EXIT_CODE -eq 0 ] && [ $VERIFY_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ SUCCESS: Test completed with no failures!                  ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    exit 0
elif [ $VERIFY_EXIT_CODE -ne 0 ]; then
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  ⚠ FAILURES DETECTED: Review the report above                 ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════╝${NC}"
    exit 1
else
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  ⚠ Test completed with warnings                               ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════╝${NC}"
    exit $TEST_EXIT_CODE
fi
