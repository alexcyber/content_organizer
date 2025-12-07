# Media File Organizer - Project Summary

## Overview
Complete implementation of an automated media file organizer that routes TV shows and movies to appropriate destinations based on content type and airing status.

## Implementation Status
✅ **COMPLETE** - All components implemented and tested (43/43 tests passing)

## Key Features Implemented

### 1. Intelligent Filename Parsing
- Handles multiple naming conventions (dots, spaces, underscores)
- Extracts: title, season, episode, year, quality, release group
- Special handling for edge cases:
  - Movies with years in title (e.g., "1917")
  - Multiple years in filename (uses smart detection)
  - Site prefixes/suffixes removal
  - Episode titles and quality tags cleanup

### 2. Content Classification
- TV Show vs Movie detection via season/episode patterns
- TMDB API integration for show status (Current vs Concluded)
- Caching system to minimize API calls
- Graceful fallback when API unavailable

### 3. Fuzzy Folder Matching
- 80% similarity threshold (configurable)
- Case-insensitive matching
- Handles variations in folder names (years, special chars)
- Automatic folder creation when no match found

### 4. File Operations
- Dry-run mode for safe testing
- Duplicate handling with unique naming
- Preserves folder structures for releases
- Lockfile prevents concurrent runs

### 5. Logging & Monitoring
- Structured console and file logging
- Rotating log files (10MB, 5 backups)
- Detailed operation tracking
- Cron-compatible output

## Project Structure
```
content_organizer/
├── main.py                      # CLI entry point
├── config.py                    # Configuration management
├── parsers/
│   ├── filename_parser.py       # Metadata extraction
│   └── content_classifier.py    # TMDB integration
├── matchers/
│   └── folder_matcher.py        # Fuzzy matching
├── operations/
│   └── file_mover.py            # File operations
├── utils/
│   ├── logger.py                # Logging setup
│   └── cache.py                 # API response caching
└── tests/                       # 43 unit tests
    ├── test_parser.py
    ├── test_matcher.py
    └── test_classifier.py
```

## Test Coverage

### Parser Tests (19 tests)
- ✅ Various TV show naming conventions
- ✅ Movie title extraction
- ✅ Year detection (including edge cases)
- ✅ Quality and release group extraction
- ✅ Title normalization for fuzzy matching

### Matcher Tests (12 tests)
- ✅ Exact and fuzzy matching
- ✅ Case insensitivity
- ✅ Folder creation
- ✅ Name sanitization

### Classifier Tests (12 tests)
- ✅ TMDB API integration
- ✅ Show status detection
- ✅ Caching functionality
- ✅ Graceful degradation

## Configuration

### Default Settings
- Download Directory: `/mnt/media/TV_Downloads`
- Movie Destination: `/mnt/MediaVaultV3/Movies/Movies`
- TV Current: `/mnt/media/TV_Shows/Current`
- TV Concluded: `/mnt/media/TV_Shows/Concluded`
- Fuzzy Match Threshold: 80%

### Environment Variables
All settings configurable via `.env` file (see `.env.example`)

## Usage

### Basic
```bash
python3 main.py
```

### Dry-Run (Preview Only)
```bash
python3 main.py --dry-run
```

### Automated (Cron)
```cron
0 */2 * * * /usr/bin/python3 /opt/media_organizer/main.py >> /var/log/media_organizer/cron.log 2>&1
```

## Dependencies
- `rapidfuzz>=3.0.0` - Fuzzy string matching
- `requests>=2.31.0` - TMDB API calls
- `pytest>=7.4.0` - Testing framework

## Example Processing

### Input
```
TV_Downloads/
├── The.Pitt.S01E10.1080p.WEB.h264-ETHEL[EZTVx.to].mkv
├── Breaking.Bad.S05E16.Felina.1080p.BluRay.mkv
└── 1917.2019.1080p.AMZN.WEB-DL.DDP5.1.H.264-TEPES.mkv
```

### Output
```
Processing: The.Pitt.S01E10.1080p.WEB.h264-ETHEL.mkv
Classified: TV Show - "The Pitt" S01E10
Status: CURRENT
Matched existing folder: /mnt/media/TV_Shows/Current/The.Pitt/
Moved to: /mnt/media/TV_Shows/Current/The.Pitt/...

Processing: Breaking.Bad.S05E16.Felina.1080p.BluRay.mkv
Classified: TV Show - "Breaking Bad" S05E16
Status: CONCLUDED
Creating new folder: /mnt/media/TV_Shows/Concluded/Breaking Bad
Moved to: /mnt/media/TV_Shows/Concluded/Breaking Bad/...

Processing: 1917.2019.1080p.AMZN.WEB-DL.mkv
Classified: Movie - "1917" (2019)
Creating new folder: /mnt/MediaVaultV3/Movies/Movies/1917
Moved to: /mnt/MediaVaultV3/Movies/Movies/1917/...
```

## Next Steps for Deployment

1. **Install on target system:**
   ```bash
   cd /opt
   git clone <repo> media_organizer
   cd media_organizer
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure:**
   ```bash
   cp .env.example .env
   nano .env  # Add TMDB API key, adjust paths
   ```

3. **Create directories:**
   ```bash
   sudo mkdir -p /var/log/media_organizer
   sudo chown $USER:$USER /var/log/media_organizer
   ```

4. **Test:**
   ```bash
   python3 main.py --dry-run
   ```

5. **Schedule:**
   ```bash
   crontab -e
   # Add: 0 */2 * * * /opt/media_organizer/venv/bin/python3 /opt/media_organizer/main.py >> /var/log/media_organizer/cron.log 2>&1
   ```

## License
MIT License
