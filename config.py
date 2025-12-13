"""
Configuration management for media file organizer.

Handles paths, thresholds, API keys, and other configuration parameters.
Supports environment variables for sensitive data.
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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

# Directories to completely skip during processing
SKIP_DIRS: List[str] = ["@eaDir", "Porn", ".stfolder"]

# Parent directories to process children from (not the directory itself)
PARENT_DIRS: List[str] = ["TV_Shows", "Movies"]

# Video file extensions to process
VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv",
    ".webm", ".m4v", ".mpg", ".mpeg", ".m2ts"
}

# SFTP configuration for remote file deletion
SFTP_HOST = os.getenv("SFTP_HOST", "")
SFTP_PORT = int(os.getenv("SFTP_PORT", "22"))
SFTP_USER = os.getenv("SFTP_USER", "")
SFTP_PASSWORD = os.getenv("SFTP_PASSWORD", "")
SFTP_REMOTE_DIR = os.getenv("SFTP_REMOTE_DIR", "")
SFTP_TIMEOUT = int(os.getenv("SFTP_TIMEOUT", "30"))

# File transfer completion verification
# Ensures all files are fully transferred before processing
FILE_STABILITY_CHECK_INTERVAL = int(os.getenv("FILE_STABILITY_CHECK_INTERVAL", "10"))  # seconds between checks
FILE_STABILITY_CHECK_RETRIES = int(os.getenv("FILE_STABILITY_CHECK_RETRIES", "2"))  # number of checks to perform

# Allow 0-byte files to be processed (default: false - 0-byte files are considered still downloading)
ALLOW_ZERO_BYTE_FILES = os.getenv("ALLOW_ZERO_BYTE_FILES", "false").lower() in ("true", "1", "yes")

# Use hash verification for untracked files (files not synced via Syncthing)
# This provides extra assurance that files are stable before moving
HASH_CHECK_FOR_UNTRACKED = os.getenv("HASH_CHECK_FOR_UNTRACKED", "true").lower() in ("true", "1", "yes")

# Syncthing integration
# Enable Syncthing temporary file detection (files with .tmp suffix or .syncthing. prefix)
SYNCTHING_ENABLED = os.getenv("SYNCTHING_ENABLED", "true").lower() in ("true", "1", "yes")
SYNCTHING_TMP_PATTERNS = [
    ".syncthing.*.tmp",  # Standard syncthing temporary files
    "*.tmp",             # Generic temporary files
]

# Syncthing REST API integration (optional, for advanced sync detection)
# If provided, will use API to detect active syncing in addition to temp file detection
SYNCTHING_URL = os.getenv("SYNCTHING_URL", "")  # e.g., "http://localhost:8384"
SYNCTHING_API_KEY = os.getenv("SYNCTHING_API_KEY", "")
SYNCTHING_API_TIMEOUT = int(os.getenv("SYNCTHING_API_TIMEOUT", "5"))  # API request timeout in seconds
SYNCTHING_API_ENABLED = bool(SYNCTHING_URL and SYNCTHING_API_KEY)

# Syncthing path mapping (for remote Syncthing or containerized setups)
# Maps Syncthing's reported paths to local paths
# Format: "remote_path:local_path,remote_path2:local_path2"
SYNCTHING_PATH_MAPPING = os.getenv("SYNCTHING_PATH_MAPPING", "")


def validate_config() -> List[str]:
    """
    Validate configuration and return list of warnings/errors.
    Creates directories if they don't exist.

    Returns:
        List of warning/error messages
    """
    issues = []

    # Check and create download directory
    download_path = Path(DOWNLOAD_DIR)
    if not download_path.exists():
        try:
            download_path.mkdir(parents=True, exist_ok=True)
            issues.append(f"Created download directory: {DOWNLOAD_DIR}")
        except PermissionError:
            issues.append(f"Cannot create download directory: {DOWNLOAD_DIR} (permission denied)")
        except Exception as e:
            issues.append(f"Error creating download directory: {DOWNLOAD_DIR} ({e})")

    # Check and create destination directories
    for dir_name, dir_path in [
        ("Movie", MOVIE_DIR),
        ("TV Current", TV_CURRENT_DIR),
        ("TV Concluded", TV_CONCLUDED_DIR)
    ]:
        path = Path(dir_path)
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
                issues.append(f"Created {dir_name} directory: {dir_path}")
            except PermissionError:
                issues.append(f"Cannot create {dir_name} directory: {dir_path} (permission denied)")
            except Exception as e:
                issues.append(f"Error creating {dir_name} directory: {dir_path} ({e})")

    # Warn if TVDB API key is missing
    if not TVDB_API_KEY:
        issues.append("TVDB_API_KEY not set - will default all shows to 'Current'")

    # Check and create log directory
    log_dir_path = Path(LOG_DIR)
    if not log_dir_path.exists():
        try:
            log_dir_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            issues.append(f"Cannot create log directory: {LOG_DIR} (permission denied)")
        except Exception as e:
            issues.append(f"Error creating log directory: {LOG_DIR} ({e})")

    # Check and create cache directory
    cache_dir_path = Path(CACHE_DIR)
    if not cache_dir_path.exists():
        try:
            cache_dir_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            issues.append(f"Cannot create cache directory: {CACHE_DIR} (permission denied)")
        except Exception as e:
            issues.append(f"Error creating cache directory: {CACHE_DIR} ({e})")

    return issues
