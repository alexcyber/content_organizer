# Testing Guide

This guide covers everything you need to test the media organizer using the mock test environment.

## Table of Contents
1. [Initial Setup](#initial-setup)
2. [Available Tests](#available-tests)
3. [Verifying Output](#verifying-output)

---

## Initial Setup

### First-Time Setup

All test scripts must be run from the `mock_test` directory.

```bash
# Navigate to mock_test directory
cd /home/amolina/programming_projects/content_organizer/mock_test

# Create the test environment (one time)
./setup_test_environment.sh
```

This creates `test_media/` with:
- **30+ sample video files** in `TV_Downloads/`
- **Existing destination folders** to test fuzzy matching
- Various naming conventions and edge cases
- Mix of TV shows (current & concluded) and movies

### Test Environment Structure

```
test_media/
├── TV_Downloads/          # Source files (simulates downloads)
│   ├── The.Pitt.S01E10.1080p.WEB.h264-ETHEL.mkv
│   ├── Breaking.Bad.S05E16.Felina.1080p.BluRay.x264/
│   ├── 1917.2019.1080p.AMZN.WEB-DL.mkv
│   └── ... (30+ files and folders)
│
├── TV_Shows/
│   ├── Current/           # Existing current shows
│   │   ├── The Pitt/
│   │   ├── Severance (2022)/
│   │   └── The Mandalorian/
│   │
│   └── Concluded/         # Existing concluded shows
│       ├── Breaking Bad/
│       └── Game of Thrones (2011-2019)/
│
├── Movies/                # Existing movies
│   ├── The Matrix Collection/
│   ├── Inception/
│   └── 12 Angry Men/
│
└── logs/
    └── organizer.log      # Test run logs
```

### Configuration

The test environment uses `.env.test` with isolated paths:
- `MEDIA_DOWNLOAD_DIR=./mock_test/test_media/TV_Downloads`
- `MEDIA_TV_CURRENT_DIR=./mock_test/test_media/TV_Shows/Current`
- `MEDIA_TV_CONCLUDED_DIR=./mock_test/test_media/TV_Shows/Concluded`
- `MEDIA_MOVIE_DIR=./mock_test/test_media/Movies`

**Optional: TheTVDB API**
Add TheTVDB API key to `.env.test` for realistic show status detection:
```bash
TVDB_API_KEY=your_key_here
```
Get a free key at: https://thetvdb.com/dashboard/account/apikeys

**Optional: SFTP Remote File Deletion Testing**
Add SFTP credentials to `.env.test` to test remote file deletion:
```bash
SFTP_HOST=your.server.com
SFTP_PORT=22
SFTP_USER=your_username
SFTP_PASSWORD=your_password
SFTP_REMOTE_DIR=/path/to/remote/test/directory/
```

When SFTP is configured:
- Setup script creates files on the remote server based on CSV "Remote" column
- Test script automatically uses `--sftp-delete` flag
- Verification script checks that remote files were deleted
- Gracefully disables SFTP if connection fails (falls back to local-only testing)

---

## Available Tests

### Basic Testing Workflow

```bash
# 1. Preview what would happen (ALWAYS START HERE)
./run_test.sh --dry-run

# 2. Inspect the test environment state
./inspect_test_environment.sh

# 3. Run for real (moves files within test_media/)
./run_test.sh

# 4. Reset and start fresh
./reset_test_environment.sh
```

### Test Scripts Reference

#### `setup_test_environment.sh`
Creates the complete test environment with sample files.

**What it creates:**
- 30+ video files with various naming patterns
- Existing destination folders
- Edge cases (year in title, site prefixes, etc.)

**When to use:** First time only, or after manual deletion of `test_media/`

#### `run_test.sh`
Runs the organizer on test files.

**Options:**
```bash
./run_test.sh                    # Run organizer on test files
./run_test.sh --dry-run          # Preview only (no changes)
./run_test.sh --reset            # Reset environment first
./run_test.sh --reset --dry-run  # Reset and preview
```

**What it does:**
- Loads `.env.test` configuration
- Runs main.py on test environment
- Shows before/after statistics
- Creates logs in `test_media/logs/`

#### `inspect_test_environment.sh`
Shows the current state of the test environment.

**Output includes:**
- Files remaining in TV_Downloads
- Existing destination folders
- File counts per location
- Expected fuzzy matches

**When to use:**
- Before running tests (see initial state)
- After running tests (verify results)
- Debugging matching issues

#### `reset_test_environment.sh`
Wipes and recreates the entire test environment.

**What it does:**
- Deletes `test_media/` directory
- Clears cache and lock files
- Runs `setup_test_environment.sh`

**When to use:**
- Between test runs for clean state
- After making code changes
- When test environment gets messy

### Test Coverage

The test environment covers:

**Filename Parsing:**
- ✅ Various separators (dots, spaces)
- ✅ Site prefixes (`www.UIndex.org -`, `[eztv.re]`)
- ✅ Different episode patterns (S01E01, 1x01, 4x03)
- ✅ Quality tags (1080p, 2160p, BluRay, WEB)
- ✅ Release groups (ETHEL, CAKES, ROVERS)
- ✅ Edge cases (year as title, multiple years)

**Fuzzy Matching (80% threshold):**
- ✅ Exact matches
- ✅ Case insensitive matching
- ✅ Matching with year in folder name
- ✅ Partial matches
- ✅ New folder creation when no match

**Content Classification:**
- ✅ TV shows vs Movies
- ✅ Current vs Concluded (with TheTVDB API)
- ✅ Season/episode detection

**File Operations:**
- ✅ Standalone files
- ✅ Folder structures (scene releases)
- ✅ Multiple files per show
- ✅ Non-video files (ignored)

**SFTP Remote File Deletion (optional):**
- ✅ Remote file creation during setup
- ✅ Automatic deletion after successful local move
- ✅ Verification of remote deletion
- ✅ Graceful fallback when SFTP unavailable

### Expected Test Results

**After dry-run:**
- Shows planned operations
- No actual file changes
- Displays fuzzy match scores
- Identifies new vs existing folders

**After real run (without TMDB):**
- TV_Downloads: Nearly empty (only non-video files remain)
- TV_Shows/Current: ~15 folders (all TV shows default to Current)
- TV_Shows/Concluded: 2-3 folders (based on folder names)
- Movies: ~10 folders

**With TMDB API configured:**
- Breaking Bad → Concluded
- Game of Thrones → Concluded
- The Last of Us → Current
- Other shows properly classified

---

## Verifying Output

### CSV-Based Verification (Recommended)

After running a test, use the CSV-based verification script:

```bash
# Verify against CSV rubric
./verify_test_results.sh
```

This script:
1. Verifies all files are in expected final locations (from CSV)
2. Checks remote SFTP files were deleted (if SFTP configured)
3. Reports local and remote verification results
4. Generates detailed report

**Verification includes:**
- Local file/directory existence checks
- Remote SFTP deletion checks (when enabled)
- Separate pass/fail counts for local and remote tests
- Combined success/failure reporting

### Quick Test + Verify

```bash
# Run test and automatically verify
./run_test_and_verify.sh

# With reset
./run_test_and_verify.sh --reset
```

This script runs the test then calls `verify_test_results.sh` for verification.

### Legacy Log Analysis

For detailed log analysis (debugging specific issues):

```bash
./check_move_failures.sh
```

This analyzes logs for:
1. ERROR messages
2. Failed move operations
3. Permission issues
4. Low success rates

### Manual Verification

#### Check Logs
```bash
# View full log
less test_media/logs/organizer.log

# Check for errors
grep ERROR test_media/logs/organizer.log

# Check move operations
grep "Moved:" test_media/logs/organizer.log
```

#### Verify File Locations
```bash
# Inspect current state
./inspect_test_environment.sh

# Count remaining files in downloads
find test_media/TV_Downloads -type f \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" \) | wc -l

# List files in a specific show folder
ls -lh "test_media/TV_Shows/Current/The Pitt/"
```

### Verification Output

**CSV-based verification (`verify_test_results.sh`):**
- Checks each file/directory from CSV "Final" column
- Verifies remote SFTP deletion for items with "Remote" column
- Color-coded results (✓ green for pass, ✗ red for fail)
- Separate statistics for local and remote verification
- Exit code 0 (success) or 1 (failures detected)
- Detailed report saved to `verification_report.txt`

**Legacy log analysis (`check_move_failures.sh`):**
- Analyzes log files for ERROR messages
- Checks for "Failed to move" operations
- Detects permission denied errors
- Calculates success rate
- Lists unmoved files
- Exit code 0 (success) or 1 (failures detected)
- Detailed report saved to `move_failures_report.txt`

**Example - Successful Run:**
```
✓ No failures detected!
✓ All video files appear to have been moved successfully

Statistics:
  Total processed: 25
  Successfully moved: 25
  Success rate: 100%
```

**Example - Failed Run:**
```
✗ ERROR messages found in log
✗ Permission denied errors found

Statistics:
  Total processed: 25
  Successfully moved: 18
  Success rate: 72%

⚠ Warning: 7 files still in TV_Downloads
```

### Verification Reports

**Console Report:**
- Real-time colored output
- Current environment state
- Errors found (if any)
- Statistics and success rate
- Suggested next steps

**File Report (`move_failures_report.txt`):**
- Timestamp
- All errors with context
- Failed moves list
- Permission errors
- Unmoved files
- Statistics
- Final result

### Success Criteria

**100% Success:**
- All video files moved from TV_Downloads to expected final locations
- All remote SFTP files deleted (if SFTP configured)
- No ERROR messages in logs
- All CSV verification tests passed
- Only non-video files remain in downloads

**Partial Success:**
- Most files moved successfully (local verification passes)
- Minor remote deletion failures (if SFTP enabled)
- Check verification report for specific issues

**Failure:**
- Significant number of local files not in expected locations
- Remote files not deleted (if SFTP was enabled)
- Multiple errors in logs
- Review verification_report.txt for details

---

## Common Workflows

### Testing a Code Change
```bash
# 1. Make your changes
nano ../parsers/filename_parser.py

# 2. Reset test environment
./reset_test_environment.sh

# 3. Preview results
./run_test.sh --dry-run

# 4. If good, run for real
./run_test.sh

# 5. Verify success
./check_move_failures.sh
```

### Quick Test Iteration
```bash
# All-in-one: reset, run, and verify
./run_test_and_verify.sh --reset
```

### Debugging a Specific Issue
```bash
# 1. Inspect current state
./inspect_test_environment.sh

# 2. Check what would happen
./run_test.sh --dry-run

# 3. Review logs
less test_media/logs/organizer.log

# 4. Check for failures
./check_move_failures.sh

# 5. Review detailed report
cat move_failures_report.txt
```

---

## Troubleshooting

### Permission Denied Errors
```bash
# Make scripts executable
chmod +x *.sh

# Check directory permissions
ls -la test_media/TV_Shows/Current/
```

### Test Environment Not Found
```bash
# Create it
./setup_test_environment.sh
```

### Want Completely Fresh Start
```bash
# Remove everything and recreate
rm -rf test_media move_failures_report.txt
./setup_test_environment.sh
```

### Files Not Being Processed
- Check files have video extensions (.mkv, .mp4, .avi)
- Run `./inspect_test_environment.sh` to see what exists
- Use `--dry-run` to see what would be processed
- Check logs for parsing errors

### Fuzzy Matching Not Working
- Check match score in dry-run output
- Lower `FUZZY_MATCH_THRESHOLD` in `.env.test` (default 80)
- Or rename existing folder to match closer

### Shows Going to Wrong Destination
**Without TheTVDB API:** All shows default to "Current"
**Solution:** Add TheTVDB API key to `.env.test`

### SFTP Connection Failures
If SFTP is configured but verification shows "SFTP Verification: DISABLED":
- Check SFTP credentials in `.env.test`
- Verify SFTP server is accessible
- Test connection manually: `lftp -u user,pass sftp://host:port`
- Check firewall/network settings
- Review setup script output for connection errors

**Note:** SFTP is optional - tests will run with local-only verification if SFTP is unavailable

---

## Summary

**Setup:** `./setup_test_environment.sh`
**Test:** `./run_test.sh --dry-run` then `./run_test.sh`
**Verify:** `./run_test_and_verify.sh` or `./check_move_failures.sh`
**Reset:** `./reset_test_environment.sh`

The test environment is completely isolated and safe to experiment with. All operations only affect files in `test_media/`.
