"""
Simple file-based caching for API responses.

Stores JSON responses with expiration timestamps to minimize API calls.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional

import config


class SimpleCache:
    """File-based cache with TTL support."""

    def __init__(self, cache_dir: str = config.CACHE_DIR):
        """
        Initialize cache with specified directory.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        """
        Get file path for cache key.

        Args:
            key: Cache key

        Returns:
            Path to cache file
        """
        # Sanitize key for filename
        safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str, ttl: int = config.TVDB_CACHE_DURATION) -> Optional[Any]:
        """
        Retrieve value from cache if not expired.

        Args:
            key: Cache key
            ttl: Time-to-live in seconds

        Returns:
            Cached value or None if expired/missing
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r") as f:
                data = json.load(f)

            # Check expiration
            if time.time() - data.get("timestamp", 0) > ttl:
                cache_path.unlink()  # Remove expired cache
                return None

            return data.get("value")
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, key: str, value: Any) -> None:
        """
        Store value in cache with current timestamp.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
        """
        cache_path = self._get_cache_path(key)

        try:
            with open(cache_path, "w") as f:
                json.dump({
                    "timestamp": time.time(),
                    "value": value
                }, f)
        except (OSError, TypeError) as e:
            # Silently fail on cache write errors
            pass

    def clear(self) -> None:
        """Remove all cached files."""
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except OSError:
                pass
