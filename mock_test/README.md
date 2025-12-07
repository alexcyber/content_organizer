# Mock Test Environment

CSV-driven testing environment for the media file organizer with automated setup and verification.

## Quick Start

**Easiest way to test:**
```bash
./run_test_and_verify.sh --reset
```

This resets the environment, runs the organizer, and automatically verifies success against the CSV rubric.

**See [QUICK_START.md](QUICK_START.md) for complete step-by-step workflow.**

## CSV-Driven Testing

The test environment is now driven by `mock_test_rubric.csv`, which defines:
- **Starting**: Files/folders that should exist before running the organizer
- **Final**: Expected location after the organizer runs
- **Test**: Whether to verify this in automated testing (TRUE/FALSE)

This approach allows you to:
- Easily add/modify test cases by editing the CSV
- Track exactly what should happen for each file
- Automatically verify all expected outcomes

## What's Here

| File/Directory | Purpose |
|----------------|---------|
| **`mock_test_rubric.csv`** | **Test specification (defines all test cases)** |
| **`QUICK_START.md`** | **Step-by-step testing workflow** |
| **`TESTING_GUIDE.md`** | **Comprehensive testing documentation** |
| `setup_test_environment.sh` | Creates test environment from CSV rubric |
| `run_test_and_verify.sh` | Runs test and verifies against CSV |
| `verify_test_results.sh` | CSV-based verification script |
| `run_test.sh` | Runs the organizer on test files |
| `inspect_test_environment.sh` | Shows current state (before/after) |
| `check_move_failures.sh` | Analyzes logs (legacy, for detailed debugging) |
| `reset_test_environment.sh` | Wipes and recreates test environment |
| `.env.test` | Test configuration (paths, settings) |
| `test_media/` | Test directory (created by setup script) |

## Common Commands

```bash
# Easiest: reset + run + verify in one command
./run_test_and_verify.sh --reset

# Step-by-step workflow:
./setup_test_environment.sh    # 1. Create environment from CSV (first time)
./inspect_test_environment.sh  # 2. Preview files before
./run_test.sh --dry-run         # 3. Preview what will happen
./run_test.sh                   # 4. Run the organizer
./inspect_test_environment.sh  # 5. View results after
./verify_test_results.sh        # 6. Verify against CSV rubric

# Reset between tests
./reset_test_environment.sh
```

## Documentation

- **[QUICK_START.md](QUICK_START.md)** - Complete workflow from setup to verification
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Comprehensive testing reference

## Test Coverage

The CSV rubric defines 58 test cases covering:
- ✅ TV Shows: Current and Concluded status
- ✅ Movies: Various naming patterns and formats
- ✅ Fuzzy folder matching (exact vs. close matches)
- ✅ Site prefix removal (`www.`, `[eztv.re]`, `[EZTVx.to]`)
- ✅ Various episode patterns (S01E01, 1x01, 4x03)
- ✅ Edge cases (year in title, multiple years, special characters)
- ✅ Folder structures (scene releases with multiple files)
- ✅ Non-video files (should remain in downloads)
- ✅ Automatic verification of all expected outcomes

## Important Notes

1. **All scripts must be run from this directory** (`mock_test/`)
2. **Test environment is isolated** - only affects files in `test_media/`
3. **CSV-driven** - edit `mock_test_rubric.csv` to add/modify test cases
4. **Safe to experiment** - reset script recreates everything from CSV
5. **Add TheTVDB API key** to `.env.test` for realistic show status detection (Current vs Concluded)

## Example Workflow

```bash
# 1. Navigate to mock_test
cd mock_test

# 2. Create test environment (first time only)
./setup_test_environment.sh

# 3. Preview what would happen
./run_test.sh --dry-run

# 4. Reset and test again with verification
./run_test_and_verify.sh --reset
```

For detailed documentation, see **[TESTING_GUIDE.md](TESTING_GUIDE.md)**.
