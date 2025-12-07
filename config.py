"""
Configuration management for media file organizer.

Handles paths, thresholds, API keys, and other configuration parameters.
Supports environment variables for sensitive data.
"""

import os
from pathlib import Path
from typing import List

# Directory paths
DOWNLOAD_DIR = os.getenv("MEDIA_DOWNLOAD_DIR", "/mnt/media/TV_Downloads")
MOVIE_DIR = os.getenv("MEDIA_MOVIE_DIR", "/mnt/MediaVaultV3/Movies/Movies")
TV_CURRENT_DIR = os.getenv("MEDIA_TV_CURRENT_DIR", "/mnt/media/TV_Shows/Current")
TV_CONCLUDED_DIR = os.getenv("MEDIA_TV_CONCLUDED_DIR", "/mnt/media/TV_Shows/Concluded")

# API configuration
TVDB_API_KEY = os.getenv("TVDB_API_KEY", "")
TVDB_BASE_URL = "https://api4.thetvdb.com/v4"
TVDB_CACHE_DURATION = 86400 * 7  # 7 days in seconds

# Matching configuration
FUZZY_MATCH_THRESHOLD = int(os.getenv("FUZZY_MATCH_THRESHOLD", "80"))

# Logging configuration
LOG_DIR = os.getenv("MEDIA_LOG_DIR", "/var/log/media_organizer")
LOG_PATH = os.path.join(LOG_DIR, "organizer.log")
CRON_LOG_PATH = os.path.join(LOG_DIR, "cron.log")
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# Runtime configuration
LOCK_FILE = os.getenv("MEDIA_LOCK_FILE", "/tmp/media_organizer.lock")
CACHE_DIR = os.getenv("MEDIA_CACHE_DIR", "/tmp/media_organizer_cache")

# Directories to skip during processing
SKIP_DIRS: List[str] = ["@eaDir", "Movies", "Porn", "TV_Shows"]

# Video file extensions to process
VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv",
    ".webm", ".m4v", ".mpg", ".mpeg", ".m2ts"
}


def validate_config() -> List[str]:
    """
    Validate configuration and return list of warnings/errors.

    Returns:
        List of warning/error messages
    """
    issues = []

    # Check if download directory exists
    if not Path(DOWNLOAD_DIR).exists():
        issues.append(f"Download directory does not exist: {DOWNLOAD_DIR}")

    # Check if destination directories exist
    for dir_name, dir_path in [
        ("Movie", MOVIE_DIR),
        ("TV Current", TV_CURRENT_DIR),
        ("TV Concluded", TV_CONCLUDED_DIR)
    ]:
        if not Path(dir_path).exists():
            issues.append(f"{dir_name} directory does not exist: {dir_path}")

    # Warn if TVDB API key is missing
    if not TVDB_API_KEY:
        issues.append("TVDB_API_KEY not set - will default all shows to 'Current'")

    # Check log directory
    log_dir_path = Path(LOG_DIR)
    if not log_dir_path.exists():
        try:
            log_dir_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            issues.append(f"Cannot create log directory: {LOG_DIR} (permission denied)")

    # Check cache directory
    cache_dir_path = Path(CACHE_DIR)
    if not cache_dir_path.exists():
        try:
            cache_dir_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            issues.append(f"Cannot create cache directory: {CACHE_DIR} (permission denied)")

    return issues
