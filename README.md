# Developer Purpose
This project was 100% written by AI.  The only section that wasn't, is this this one right here.  The purpose of this project was to understand how "Vibe Coding" works and to see how "production code" could be written with it to solve a problem for a friend.

# Media File Organizer

Automated media file organizer that monitors your download directory and routes files to appropriate destinations based on content type. Intelligently determines if TV shows are currently airing or concluded using TMDB API.

## Features

- **Intelligent Parsing**: Handles inconsistent naming conventions (dot/space separators, quality tags, site prefixes)
- **TMDB Integration**: Automatically determines if TV shows are current or concluded
- **Fuzzy Matching**: Finds existing destination folders using similarity matching
- **Dry-Run Mode**: Preview all operations before committing
- **Comprehensive Logging**: Structured logs to both console and rotating files
- **Cron-Compatible**: Designed for automated scheduling with lockfile support
- **Syncthing Integration**: Automatically detects and waits for Syncthing file synchronization to complete
- **File Stability Detection**: Dual-method verification using both file size monitoring and Syncthing temporary file detection
- **Minimal Dependencies**: Uses stdlib where possible

## Content Routing

| Content Type | Destination |
|-------------|-------------|
| Movies | `/mnt/MediaVaultV3/Movies/Movies` |
| Currently Airing TV Shows | `/mnt/media/TV_Shows/Current/` |
| Concluded TV Shows | `/mnt/media/TV_Shows/Concluded/` |

## Installation

### Requirements

- Python 3.8 or higher
- pip

### Setup

1. Clone or download this repository:
```bash
cd /opt
git clone <repository-url> media_organizer
cd media_organizer
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
nano .env  # Edit with your settings
```

4. Create necessary directories:
```bash
sudo mkdir -p /var/log/media_organizer
sudo chown $USER:$USER /var/log/media_organizer
```

## Configuration

Configuration can be done via environment variables (recommended) or by editing `config.py`.

### Required Paths

```bash
MEDIA_DOWNLOAD_DIR=/mnt/media/TV_Downloads
MEDIA_MOVIE_DIR=/mnt/MediaVaultV3/Movies/Movies
MEDIA_TV_CURRENT_DIR=/mnt/media/TV_Shows/Current
MEDIA_TV_CONCLUDED_DIR=/mnt/media/TV_Shows/Concluded
```

### Optional Settings

```bash
# TMDB API key (recommended for accurate show status)
# Get free key from: https://www.themoviedb.org/settings/api
TMDB_API_KEY=your_api_key_here

# Fuzzy matching threshold (0-100, higher = stricter)
FUZZY_MATCH_THRESHOLD=85

# Log directory
MEDIA_LOG_DIR=/var/log/media_organizer
```

### TMDB API Key

While optional, a TMDB API key is recommended for accurate show status detection:

1. Create free account at [TMDB](https://www.themoviedb.org/signup)
2. Go to Settings > API > Request API Key
3. Choose "Developer" option
4. Add key to `.env` file

Without TMDB API key, all TV shows default to "Current" status.

### File Transfer Completion Verification

The organizer uses a dual-method approach to ensure files are fully transferred before processing:

#### 1. File Size Stability Detection (Traditional Method)

Monitors file sizes over time to detect active transfers:
- Checks file sizes at configurable intervals
- Compares sizes between checks
- Only processes files when sizes remain stable

Configure via environment variables:
```bash
# Seconds between stability checks (default: 10)
FILE_STABILITY_CHECK_INTERVAL=10

# Number of checks to perform (default: 2)
FILE_STABILITY_CHECK_RETRIES=2
```

#### 2. Syncthing Integration

The organizer provides comprehensive Syncthing integration using two methods:

**A. Syncthing REST API (Recommended)**

For the most reliable sync detection, configure the Syncthing REST API:

```bash
# Syncthing API settings (optional but recommended)
SYNCTHING_URL=http://localhost:8384
SYNCTHING_API_KEY=your_syncthing_api_key_here
SYNCTHING_API_TIMEOUT=5  # API request timeout in seconds
```

To get your Syncthing API key:
1. Open Syncthing web interface (usually http://localhost:8384)
2. Go to Settings > General
3. Copy the "API Key" value
4. Add to your `.env` file

**Benefits of API integration:**
- Real-time sync status checking (completion percentage)
- Detection of in-progress items (syncing/scanning states)
- Accurate folder mapping
- Handles edge cases where temp files might not be present

**B. Temporary File Detection (Fallback)**

**Enabled by default**. If API is not configured, falls back to temp file detection:
- `.syncthing.<filename>.tmp` - Standard Syncthing pattern
- `<filename>.tmp` - Generic temporary files

The organizer automatically:
- Detects these temporary files in both single files and nested folder structures
- Waits for Syncthing to complete synchronization
- Only processes files/folders when no `.tmp` files are present

**Disable all Syncthing detection** (if not using Syncthing):
```bash
SYNCTHING_ENABLED=false
```

**How It Works:**

For **single files** (e.g., `The.Pitt.S01E10.1080p.WEB.h264-ETHEL.mkv`):
- Checks for `.syncthing.The.Pitt.S01E10.1080p.WEB.h264-ETHEL.mkv.tmp`
- Waits until temp file is removed before processing

For **folder structures** (e.g., `Breaking.Bad.S05E16.Felina.1080p.BluRay.x264-ROVERS/`):
- Recursively scans all subdirectories
- Detects any `.tmp` files at any nesting level
- Waits until all files in the folder structure are synced

**Example Folder Structure:**
```
Spartacus.House.of.Ashur.S01E01.1080p.WEB.H264-SYLiX/
├── spartacus.house.of.ashur.s01e01.1080p.web.h264-sylix.mkv  ✓ Complete
├── spartacus.house.of.ashur.s01e01.1080p.web.h264-sylix.nfo  ✓ Complete
└── Sample/
    ├── sample.mkv  ⏳ Syncing
    └── .syncthing.sample.mkv.tmp  ← Detected
```
→ Entire folder marked as unstable until Sample/sample.mkv completes

**Race Condition Protection:**

The organizer performs a final sync check immediately before moving files:
- Prevents the race condition where files get added between initial stability check and move
- Uses Syncthing API if configured (most reliable)
- Falls back to temp file detection
- Skips move if sync activity detected, preventing split files across duplicate folders

**Benefits:**
- Works seamlessly with Syncthing file synchronization
- Prevents partial file processing and duplicate folder creation
- Handles complex nested folder structures
- Dual-layer protection: initial stability check + pre-move verification
- Can be disabled if not using Syncthing (falls back to file size detection only)

## Usage

### Basic Usage

Process all files in download directory:
```bash
python3 main.py
```

### Dry-Run Mode

Preview what would be moved without actually moving files:
```bash
python3 main.py --dry-run
```

### Example Output

```
==============================================================
Media File Organizer - Starting
==============================================================
Found 3 items to process

Processing: The.Pitt.S01E10.1080p.WEB.h264-ETHEL.mkv
Classified: TV Show - "The Pitt" S01E10
Status: CURRENT
Matched existing folder: /mnt/media/TV_Shows/Current/The.Pitt/
Moved: The.Pitt.S01E10.1080p.WEB.h264-ETHEL.mkv -> /mnt/media/TV_Shows/Current/The.Pitt/

Processing: Breaking.Bad.S05E16.1080p.BluRay.mkv
Classified: TV Show - "Breaking Bad" S05E16
Status: CONCLUDED
Creating new folder: /mnt/media/TV_Shows/Concluded/Breaking Bad
Moved: Breaking.Bad.S05E16.1080p.BluRay.mkv -> /mnt/media/TV_Shows/Concluded/Breaking Bad/

Processing: 1917.2019.1080p.AMZN.WEB-DL.mkv
Classified: Movie - "1917" (2019)
Creating new folder: /mnt/MediaVaultV3/Movies/Movies/1917
Moved: 1917.2019.1080p.AMZN.WEB-DL.mkv -> /mnt/MediaVaultV3/Movies/Movies/1917/

==============================================================
Processing Summary
==============================================================
Items processed: 3
Items moved:     3
Items skipped:   0
Errors:          0
==============================================================
```

## Automated Scheduling (Cron)

### Setup Cron Job

1. Open crontab:
```bash
crontab -e
```

2. Add entry (runs every 2 hours):
```cron
0 */2 * * * /usr/bin/python3 /opt/media_organizer/main.py >> /var/log/media_organizer/cron.log 2>&1
```

### Alternative: Systemd Timer

1. Create service file `/etc/systemd/system/media-organizer.service`:
```ini
[Unit]
Description=Media File Organizer
After=network.target

[Service]
Type=oneshot
User=your_username
ExecStart=/usr/bin/python3 /opt/media_organizer/main.py
StandardOutput=append:/var/log/media_organizer/cron.log
StandardError=append:/var/log/media_organizer/cron.log

[Install]
WantedBy=multi-user.target
```

2. Create timer file `/etc/systemd/system/media-organizer.timer`:
```ini
[Unit]
Description=Run Media File Organizer every 2 hours
Requires=media-organizer.service

[Timer]
OnCalendar=*:0/2:0
Persistent=true

[Install]
WantedBy=timers.target
```

3. Enable and start timer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable media-organizer.timer
sudo systemctl start media-organizer.timer
```

## Project Structure

```
media_organizer/
├── main.py                 # Entry point, CLI interface
├── config.py               # Configuration management
├── parsers/
│   ├── filename_parser.py  # Extract title, season, episode
│   └── content_classifier.py  # Movie vs TV, status lookup
├── matchers/
│   └── folder_matcher.py   # Fuzzy matching logic
├── operations/
│   └── file_mover.py       # File move operations
├── utils/
│   ├── logger.py           # Logging configuration
│   └── cache.py            # API response caching
└── tests/
    ├── test_parser.py      # Parser tests
    ├── test_matcher.py     # Matcher tests
    ├── test_classifier.py  # Classifier tests
    └── fixtures/           # Sample filenames
```

## Testing

### Unit Tests

Run unit tests (43 tests):
```bash
.venv/bin/pytest
```

Run tests with coverage:
```bash
.venv/bin/pytest --cov=. --cov-report=html
```

Run specific test file:
```bash
.venv/bin/pytest tests/test_parser.py
```

### Integration Testing with Sample Files

A complete test environment with 30+ sample files is included in `mock_test/`:

```bash
# Navigate to test directory
cd mock_test

# Preview what would happen with sample files
./run_test.sh --dry-run

# Inspect test environment
./inspect_test_environment.sh

# Run organizer on test files
./run_test.sh

# Reset and start over
./reset_test_environment.sh
```

See `mock_test/README.md` for overview and `mock_test/TESTING.md` for detailed testing documentation.

## Troubleshooting

### Permission Denied Errors

Ensure user has write permissions to destination directories:
```bash
sudo chown -R $USER:$USER /mnt/media/TV_Shows
sudo chown -R $USER:$USER /mnt/MediaVaultV3/Movies
```

### Lock File Exists

If you see "Lock file exists" error:
```bash
rm /tmp/media_organizer.lock
```

### TMDB API Not Working

1. Verify API key is correct in `.env`
2. Check internet connectivity
3. Verify TMDB service status
4. System will default to "Current" for all shows if API unavailable

### Files Not Being Processed

1. Check that files are in the correct directory (`MEDIA_DOWNLOAD_DIR`)
2. Verify files have video extensions (`.mkv`, `.mp4`, `.avi`, etc.)
3. Check that directories don't match `SKIP_DIRS` in config
4. Run with `--dry-run` to see what would be processed

## Supported File Formats

Video files: `.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`, `.mpg`, `.mpeg`, `.m2ts`

## Exit Codes

- `0`: Success
- `1`: Errors occurred during processing (check logs)

## Logs

Logs are written to:
- Console output (STDOUT)
- `/var/log/media_organizer/organizer.log` (rotating, max 10MB, 5 backups)
- `/var/log/media_organizer/cron.log` (when run via cron)

## License

MIT License - Feel free to modify and distribute

## Contributing

Contributions welcome! Please ensure tests pass before submitting pull requests.
