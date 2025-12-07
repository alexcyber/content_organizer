# Quick Start Guide

Complete workflow for testing the media organizer from setup to verification.

## One-Command Test (Recommended)

```bash
./run_test_and_verify.sh --reset
```

This single command:
- ✅ Resets the test environment
- ✅ Runs the organizer
- ✅ Automatically verifies all moves succeeded
- ✅ Reports any issues found

## Step-by-Step Workflow

### 1. Setup Environment

```bash
# First time only (creates test_media/ with 30+ sample files)
./setup_test_environment.sh
```

Creates:
- **26 video files** in `TV_Downloads/`
- **4 video folders** (scene releases)
- **4 existing Current TV show folders** (for fuzzy matching tests)
- **2 existing Concluded TV show folders**
- **3 existing Movie folders**

### 2. Preview Environment (Before)

```bash
# See what files are waiting to be organized
./inspect_test_environment.sh
```

Shows:
- All files in TV_Downloads
- Existing destination folders with file counts
- Expected fuzzy matches

### 3. Preview What Will Happen

```bash
# Dry-run mode - NO files are moved
./run_test.sh --dry-run
```

Output shows:
- Which files will be processed
- Where each file will be moved
- Fuzzy match scores
- New folders that will be created

### 4. Run The Organizer

```bash
# Actually move the files
./run_test.sh
```

Processes all files and moves them to appropriate destinations.

### 5. View Environment (After)

```bash
# See where files ended up
./inspect_test_environment.sh
```

Shows:
- Files remaining in TV_Downloads (should be 0-3 non-video files)
- All TV show folders with episode counts
- All movie folders

### 6. Verify Moves Succeeded

```bash
# Check for any failures
./check_move_failures.sh
```

Analyzes:
- ✅ Log file for ERROR messages
- ✅ Move success rate (should be 100%)
- ✅ Files remaining in downloads
- ✅ Permission issues
- ✅ Failed operations

**Exit codes:**
- `0` = All moves successful
- `1` = Failures detected

**Output includes:**
- Console report (color-coded)
- Detailed report saved to `move_failures_report.txt`

### 7. Reset For Next Test

```bash
# Wipe and recreate environment
./reset_test_environment.sh
```

Removes:
- Entire `test_media/` directory
- Cache and lock files

Then recreates fresh test environment.

---

## Common Workflows

### Quick Test Cycle
```bash
# All-in-one: reset + run + verify
./run_test_and_verify.sh --reset
```

### Preview Only
```bash
# Just see what would happen (no actual moves, no verification)
./run_test_and_verify.sh --dry-run
```

### Development Workflow
```bash
# 1. Make code changes
nano ../parsers/filename_parser.py

# 2. Test with preview
./run_test.sh --reset --dry-run

# 3. If looks good, run for real with verification
./run_test_and_verify.sh --reset

# 4. Check results
cat move_failures_report.txt
```

### Inspect Current State
```bash
# See current environment without running anything
./inspect_test_environment.sh
```

### Manual Verification
```bash
# Run test
./run_test.sh

# Then separately verify
./check_move_failures.sh

# Review detailed report
cat move_failures_report.txt
```

---

## Understanding Results

### Successful Test Output

```
✓ No failures detected!
✓ All video files appear to have been moved successfully

Move Statistics (Most Recent Run):
  Total items processed: 25
  Successfully moved: 25
  Success rate: 100%
```

### Failed Test Output

```
✗ ERROR messages found in log
✗ Permission denied errors found
✗ Low success rate detected!

Move Statistics (Most Recent Run):
  Total items processed: 25
  Successfully moved: 18
  Success rate: 72%

⚠ Warning: 7 files still in TV_Downloads
```

When failures occur, the report will include:
- Specific error messages from logs
- List of unmoved files
- Permission errors
- Suggested troubleshooting steps

---

## Script Reference

| Script | Purpose | When To Use |
|--------|---------|-------------|
| `setup_test_environment.sh` | Create test environment | First time only |
| `inspect_test_environment.sh` | Show current state | Before/after testing |
| `run_test.sh --dry-run` | Preview operations | Before actual run |
| `run_test.sh` | Run organizer | To actually move files |
| `check_move_failures.sh` | Verify success | After running test |
| `run_test_and_verify.sh` | Run + verify | Easiest complete test |
| `reset_test_environment.sh` | Wipe and recreate | Between tests |

### Script Options

**`run_test.sh` options:**
- `--dry-run` - Preview only, no files moved
- `--reset` - Reset environment before running

**`run_test_and_verify.sh` options:**
- `--dry-run` - Preview only (skips verification)
- `--reset` - Reset environment before running

---

## Troubleshooting

### Files Not Moving

**Check:**
1. Are they video files? (`.mkv`, `.mp4`, `.avi`)
2. Run with `--dry-run` to see what organizer detects
3. Check `test_media/logs/organizer.log` for errors

### Permission Errors

```bash
# Fix script permissions
chmod +x *.sh

# Fix directory permissions
chmod -R 755 test_media/
```

### Test Environment Missing

```bash
# Create it
./setup_test_environment.sh

# Or reset it
./reset_test_environment.sh
```

### Want Fresh Start

```bash
# Nuclear option - delete everything and start over
rm -rf test_media/ move_failures_report.txt
./setup_test_environment.sh
```

### Verification Showing Old Results

```bash
# Reset clears logs and creates fresh environment
./reset_test_environment.sh
./run_test_and_verify.sh
```

---

## What's Being Tested

### Filename Parsing
- ✅ Site prefixes: `www.UIndex.org -`, `[eztv.re]`
- ✅ Episode patterns: `S01E01`, `1x01`, `4x03`
- ✅ Year in title: `1917.2019.mkv`
- ✅ Multiple years: `Back.to.the.Future.1985.2015.mkv`
- ✅ Episode titles: `Mr.Robot.S01E01.eps1.0_hellofriend.mov.1080p.mkv`

### Fuzzy Matching (80% threshold)
- ✅ Exact: `The Pitt` → `The Pitt` (100%)
- ✅ With year: `Severance` → `Severance (2022)` (~83%)
- ✅ Case insensitive: `severance` → `Severance (2022)`
- ✅ New folder creation when no match

### Content Classification
- ✅ TV Shows vs Movies
- ✅ Current vs Concluded (with TMDB API)
- ✅ Folder structures (scene releases)

### File Operations
- ✅ Standalone files moved correctly
- ✅ Folders moved as complete units
- ✅ Non-video files skipped

---

## Expected Results

**After successful run:**
- `TV_Downloads/`: 0-3 files (only non-video files like .txt, .jpg)
- `TV_Shows/Current/`: ~16 folders
- `TV_Shows/Concluded/`: ~2 folders
- `Movies/`: ~9 folders

---

## Quick Reference

```bash
# First time
./setup_test_environment.sh
./inspect_test_environment.sh
./run_test.sh --dry-run
./run_test.sh
./check_move_failures.sh

# Easiest way
./run_test_and_verify.sh --reset

# Development cycle
./run_test.sh --reset --dry-run  # Preview
./run_test_and_verify.sh --reset  # Run + verify

# Reset between tests
./reset_test_environment.sh
```

---

**Need more details?** See [TESTING_GUIDE.md](TESTING_GUIDE.md) for comprehensive documentation.
