"""
RuTorrent integration for checking torrent completion status.

Provides methods to:
1. Check if a torrent is complete on the remote seedbox
2. Identify the parent folder for a download
3. Get expected file count and size for verification

This module helps prevent moving files before the torrent download is complete.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
from requests.auth import HTTPDigestAuth

from utils.logger import get_logger

logger = get_logger()


@dataclass
class TorrentInfo:
    """Information about a torrent from RuTorrent."""
    hash_id: str
    name: str
    size_bytes: int
    size_chunks: int
    completed_chunks: int
    bytes_done: int
    base_path: str
    label: str
    is_complete: bool
    progress: float

    @property
    def folder_name(self) -> str:
        """Extract the folder name from the base path."""
        return Path(self.base_path).name


class RuTorrentClient:
    """Client for interacting with RuTorrent's HTTPRPC API."""

    # Field indices in RuTorrent's torrent list response
    IDX_IS_OPEN = 0
    IDX_IS_HASH_CHECKING = 1
    IDX_IS_HASH_CHECKED = 2
    IDX_STATE = 3
    IDX_NAME = 4
    IDX_SIZE_BYTES = 5
    IDX_SIZE_CHUNKS = 6
    IDX_COMPLETED_CHUNKS = 7
    IDX_BYTES_DONE = 8
    IDX_LABEL = 14
    IDX_BASE_PATH = 25

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        base_path: str,
        subfolders: List[str],
        enabled: bool = True,
        timeout: int = 30
    ):
        """
        Initialize RuTorrent client.

        Args:
            url: RuTorrent base URL (e.g., 'https://host/rutorrent/')
            username: RuTorrent username
            password: RuTorrent password
            base_path: Base download path on remote (e.g., '/home/user/downloads/manual')
            subfolders: List of subfolders to check (e.g., ['TV_Shows', 'Movies'])
            enabled: If False, skip all RuTorrent checks
            timeout: Request timeout in seconds
        """
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.base_path = base_path.rstrip('/')
        self.subfolders = subfolders
        self.enabled = enabled and bool(url and username and password)
        self.timeout = timeout

        # Cache for torrent data
        self._torrents_cache: Optional[Dict[str, TorrentInfo]] = None
        self._torrents_by_path: Optional[Dict[str, TorrentInfo]] = None
        self._torrents_by_folder: Optional[Dict[str, TorrentInfo]] = None
        self._api_available: Optional[bool] = None

        if not self.enabled:
            logger.debug("RuTorrent integration disabled")
        else:
            logger.debug(f"RuTorrent integration enabled - URL: {url}")

    def is_available(self) -> bool:
        """
        Check if RuTorrent API is available.

        Returns:
            True if API is accessible, False otherwise
        """
        if not self.enabled:
            return False

        if self._api_available is not None:
            return self._api_available

        try:
            # Test API with a simple list request
            response = requests.post(
                f"{self.url}/plugins/httprpc/action.php",
                data={"mode": "list"},
                auth=HTTPDigestAuth(self.username, self.password),
                timeout=self.timeout
            )
            self._api_available = response.status_code == 200

            if self._api_available:
                logger.info(f"RuTorrent API connection successful: {self.url}")
            else:
                logger.warning(f"RuTorrent API returned status {response.status_code}")

        except requests.RequestException as e:
            logger.warning(f"RuTorrent API not available: {e}")
            self._api_available = False

        return self._api_available

    def refresh_cache(self) -> bool:
        """
        Refresh the torrent cache from RuTorrent.

        Returns:
            True if cache was refreshed successfully, False otherwise
        """
        if not self.enabled:
            return False

        try:
            response = requests.post(
                f"{self.url}/plugins/httprpc/action.php",
                data={"mode": "list"},
                auth=HTTPDigestAuth(self.username, self.password),
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            torrents_raw = data.get('t', {})

            self._torrents_cache = {}
            self._torrents_by_path = {}
            self._torrents_by_folder = {}

            for hash_id, values in torrents_raw.items():
                try:
                    torrent = self._parse_torrent(hash_id, values)
                    self._torrents_cache[hash_id] = torrent

                    # Index by full path (normalized)
                    normalized_path = torrent.base_path.lower()
                    self._torrents_by_path[normalized_path] = torrent

                    # Index by folder name (for fallback search)
                    folder_name = torrent.folder_name.lower()
                    # If multiple torrents have same folder name, keep the most recent
                    if folder_name not in self._torrents_by_folder:
                        self._torrents_by_folder[folder_name] = torrent

                except (IndexError, ValueError) as e:
                    logger.debug(f"Error parsing torrent {hash_id}: {e}")
                    continue

            logger.debug(f"RuTorrent cache refreshed: {len(self._torrents_cache)} torrents")
            return True

        except requests.RequestException as e:
            logger.warning(f"Failed to refresh RuTorrent cache: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error refreshing RuTorrent cache: {e}")
            return False

    def _parse_torrent(self, hash_id: str, values: List) -> TorrentInfo:
        """
        Parse torrent data from RuTorrent response.

        Args:
            hash_id: Torrent hash ID
            values: List of field values from RuTorrent

        Returns:
            TorrentInfo object
        """
        size_bytes = int(values[self.IDX_SIZE_BYTES])
        size_chunks = int(values[self.IDX_SIZE_CHUNKS])
        completed_chunks = int(values[self.IDX_COMPLETED_CHUNKS])
        bytes_done = int(values[self.IDX_BYTES_DONE])

        is_complete = (size_chunks == completed_chunks) and (size_bytes == bytes_done)
        progress = (completed_chunks / size_chunks * 100) if size_chunks > 0 else 0

        return TorrentInfo(
            hash_id=hash_id,
            name=values[self.IDX_NAME],
            size_bytes=size_bytes,
            size_chunks=size_chunks,
            completed_chunks=completed_chunks,
            bytes_done=bytes_done,
            base_path=values[self.IDX_BASE_PATH],
            label=values[self.IDX_LABEL] or "",
            is_complete=is_complete,
            progress=progress
        )

    def find_torrent_by_folder(self, folder_name: str) -> Optional[TorrentInfo]:
        """
        Find a torrent by folder name.

        First tries direct path lookup using configured subfolders,
        then falls back to searching by folder name.

        Args:
            folder_name: Name of the folder to find

        Returns:
            TorrentInfo if found, None otherwise
        """
        if not self.enabled:
            return None

        # Refresh cache if needed
        if self._torrents_cache is None:
            if not self.refresh_cache():
                return None

        # Method 1: Direct path lookup (preferred)
        for subfolder in self.subfolders:
            expected_path = f"{self.base_path}/{subfolder}/{folder_name}"
            normalized = expected_path.lower()

            if normalized in self._torrents_by_path:
                torrent = self._torrents_by_path[normalized]
                logger.debug(f"Found torrent by direct path: {expected_path}")
                return torrent

        # Method 2: Fallback to folder name search
        normalized_folder = folder_name.lower()
        if normalized_folder in self._torrents_by_folder:
            torrent = self._torrents_by_folder[normalized_folder]
            logger.debug(f"Found torrent by folder name search: {folder_name}")
            return torrent

        logger.debug(f"No torrent found for folder: {folder_name}")
        return None

    def is_torrent_complete(self, folder_name: str) -> Tuple[bool, Optional[str], Optional[TorrentInfo]]:
        """
        Check if a torrent is complete.

        Args:
            folder_name: Name of the folder to check

        Returns:
            Tuple of (is_complete, reason, torrent_info)
            - is_complete: True if complete or not found (non-torrent), False if incomplete
            - reason: Human-readable status message
            - torrent_info: TorrentInfo if found, None if not a torrent
        """
        if not self.enabled:
            return (True, "RuTorrent integration disabled", None)

        if not self.is_available():
            return (True, "RuTorrent API not available (skipping check)", None)

        torrent = self.find_torrent_by_folder(folder_name)

        if torrent is None:
            # Not found in RuTorrent - might be a manual copy or already removed
            return (True, "Not found in RuTorrent (manual copy or removed)", None)

        if torrent.is_complete:
            return (True, f"Torrent complete ({torrent.progress:.1f}%)", torrent)
        else:
            return (
                False,
                f"Torrent incomplete: {torrent.progress:.1f}% ({torrent.completed_chunks}/{torrent.size_chunks} chunks)",
                torrent
            )

    def get_all_torrents(self) -> Dict[str, TorrentInfo]:
        """
        Get all torrents from RuTorrent.

        Returns:
            Dictionary mapping hash IDs to TorrentInfo objects
        """
        if not self.enabled:
            return {}

        if self._torrents_cache is None:
            self.refresh_cache()

        return self._torrents_cache or {}

    def clear_cache(self) -> None:
        """Clear the torrent cache to force a refresh on next query."""
        self._torrents_cache = None
        self._torrents_by_path = None
        self._torrents_by_folder = None
        self._api_available = None
