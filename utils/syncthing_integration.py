"""
Syncthing integration for checking file transfer status.

Provides multiple methods to detect if syncthing is actively transferring files:
1. REST API integration (preferred, most reliable)
2. Temp file detection (fallback)
3. .stfolder markers

This module helps prevent moving files that are still being synced.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any
import requests

from utils.logger import get_logger

logger = get_logger()


class SyncthingIntegration:
    """Integration with Syncthing for detecting active file transfers."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        enabled: bool = True,
        api_timeout: int = 5,
        path_mapping: str = ""
    ):
        """
        Initialize Syncthing integration.

        Args:
            api_url: Syncthing API URL (e.g., 'http://localhost:8384')
            api_key: Syncthing API key
            enabled: If False, skip all syncthing checks
            api_timeout: API request timeout in seconds
            path_mapping: Path mapping string (format: "remote:local,remote2:local2")
        """
        self.api_url = api_url
        self.api_key = api_key
        self.enabled = enabled and bool(api_url and api_key)
        self.api_timeout = api_timeout
        self._folders_cache: Optional[Dict[str, Any]] = None
        self._api_available: Optional[bool] = None

        # Parse path mapping
        self.path_mapping = self._parse_path_mapping(path_mapping)
        if self.path_mapping:
            logger.info(f"Syncthing path mapping configured: {self.path_mapping}")

        if not self.enabled:
            logger.debug("Syncthing integration disabled - will use temp file detection only")
        else:
            logger.debug(f"Syncthing integration enabled - API URL: {api_url}")

    def is_folder_syncing(self, folder_path: Path) -> bool:
        """
        Check if a folder is currently being synced by Syncthing.

        Uses multiple detection methods:
        1. Syncthing REST API (if available)
        2. Presence of .syncthing.*.tmp files
        3. Presence of *.tmp files

        Args:
            folder_path: Path to folder to check

        Returns:
            True if folder is being actively synced, False otherwise
        """
        if not folder_path.exists():
            return False

        # Method 1: Check via Syncthing API (most reliable)
        if self.enabled and self._is_api_available():
            try:
                logger.info(f"Checking Syncthing API for '{folder_path.name}'...")
                folder_id = self._get_folder_id_for_path(folder_path)
                if folder_id:
                    # Check if this specific folder/file has files still downloading
                    files_needed, bytes_needed = self._get_path_sync_status(folder_id, folder_path)

                    if files_needed > 0:
                        logger.info(f"Syncthing API result: '{folder_path.name}' has {files_needed} file(s) still downloading ({bytes_needed:,} bytes needed) - still syncing")
                        return True

                    # Path is fully synced via API
                    logger.info(f"Syncthing API result: '{folder_path.name}' is fully synced (0 files needed) - ready to process")
                    return False
                else:
                    logger.info(f"Syncthing API: Could not map path to Syncthing folder - falling back to temp file detection")

            except Exception as e:
                logger.warning(f"Syncthing API check failed: {e}, falling back to temp file detection")

        # Method 2: Check for syncthing temp files (fallback)
        has_temp = self._has_temp_files(folder_path)
        if not has_temp:
            # No temp files found - folder is ready
            logger.info(f"Temp file detection: No temp files found for '{folder_path.name}' - ready to process")
        return has_temp

    def is_file_syncing(self, file_path: Path) -> bool:
        """
        Check if a specific file is being synced.

        Args:
            file_path: Path to file to check

        Returns:
            True if file is being synced, False otherwise
        """
        if not file_path.exists():
            return False

        # Method 1: Check via Syncthing API (most reliable)
        if self.enabled and self._is_api_available():
            try:
                logger.info(f"Checking Syncthing API for '{file_path.name}'...")
                folder_id = self._get_folder_id_for_path(file_path)
                if folder_id:
                    # Check if this specific file is still downloading
                    files_needed, bytes_needed = self._get_path_sync_status(folder_id, file_path)

                    if files_needed > 0:
                        logger.info(f"Syncthing API result: File '{file_path.name}' is still downloading ({bytes_needed:,} bytes needed) - still syncing")
                        return True

                    # File is fully synced via API
                    logger.info(f"Syncthing API result: File '{file_path.name}' is fully synced - ready to process")
                    return False
                else:
                    logger.info(f"Syncthing API: Could not map path to Syncthing folder - falling back to temp file detection")

            except Exception as e:
                logger.warning(f"Syncthing API check failed: {e}, falling back to temp file detection")

        # Method 2: Check for corresponding temp file (fallback)
        parent = file_path.parent
        filename = file_path.name

        # Check for .syncthing.filename.tmp
        syncthing_tmp = parent / f".syncthing.{filename}.tmp"
        if syncthing_tmp.exists():
            logger.info(f"Temp file detection: Found syncthing temp file '{syncthing_tmp.name}' - still syncing")
            return True

        # Check for filename.tmp
        generic_tmp = parent / f"{filename}.tmp"
        if generic_tmp.exists():
            logger.info(f"Temp file detection: Found generic temp file '{generic_tmp.name}' - still syncing")
            return True

        # No temp files found
        logger.info(f"Temp file detection: No temp files found for '{file_path.name}' - ready to process")
        return False

    def _is_api_available(self) -> bool:
        """
        Check if Syncthing API is available.

        Caches the result to avoid repeated connection attempts.

        Returns:
            True if API is available, False otherwise
        """
        if self._api_available is not None:
            return self._api_available

        if not self.enabled:
            self._api_available = False
            return False

        try:
            headers = {'X-API-Key': self.api_key}
            resp = requests.get(
                f'{self.api_url}/rest/system/ping',
                headers=headers,
                timeout=self.api_timeout
            )
            self._api_available = (resp.status_code == 200)
            if self._api_available:
                logger.info(f"Syncthing API connection successful: {self.api_url}")
            else:
                logger.warning(f"Syncthing API not responding correctly (status {resp.status_code})")
        except Exception as e:
            logger.warning(f"Syncthing API not available: {e}")
            self._api_available = False

        return self._api_available

    def _parse_path_mapping(self, mapping_str: str) -> Dict[str, str]:
        """
        Parse path mapping string into dictionary.

        Args:
            mapping_str: Format "remote:local,remote2:local2"

        Returns:
            Dictionary mapping remote paths to local paths
        """
        if not mapping_str:
            return {}

        mapping = {}
        for pair in mapping_str.split(','):
            pair = pair.strip()
            if ':' not in pair:
                logger.warning(f"Invalid path mapping format: {pair}")
                continue

            remote, local = pair.split(':', 1)
            remote = remote.strip()
            local = local.strip()

            if remote and local:
                mapping[remote] = local
                logger.debug(f"Path mapping: {remote} -> {local}")

        return mapping

    def _map_local_to_remote(self, local_path: Path) -> Path:
        """
        Map a local path to remote Syncthing path.

        Args:
            local_path: Local filesystem path

        Returns:
            Remote path (or original if no mapping)
        """
        if not self.path_mapping:
            return local_path

        local_str = str(local_path.resolve())

        # Check each mapping to see if local path is under a mapped directory
        for remote_path, local_mapped in self.path_mapping.items():
            local_mapped_resolved = str(Path(local_mapped).resolve())
            if local_str.startswith(local_mapped_resolved):
                # Replace local prefix with remote prefix
                relative = local_str[len(local_mapped_resolved):].lstrip('/')
                remote_full = f"{remote_path.rstrip('/')}/{relative}" if relative else remote_path
                logger.debug(f"Mapped local path {local_path} -> {remote_full}")
                return Path(remote_full)

        return local_path

    def _get_folder_id_for_path(self, path: Path) -> Optional[str]:
        """
        Find the Syncthing folder ID that contains the given path.

        Args:
            path: Path to check

        Returns:
            Folder ID if found, None otherwise
        """
        try:
            if self._folders_cache is None:
                headers = {'X-API-Key': self.api_key}
                resp = requests.get(
                    f'{self.api_url}/rest/config/folders',
                    headers=headers,
                    timeout=self.api_timeout
                )
                if resp.status_code == 200:
                    self._folders_cache = {
                        f['id']: Path(f['path']).resolve()
                        for f in resp.json()
                    }
                    logger.debug(f"Syncthing API: Found {len(self._folders_cache)} configured folders")

            # Map local path to remote Syncthing path if mapping configured
            path_to_match = self._map_local_to_remote(path)
            path_resolved = path_to_match.resolve()
            logger.debug(f"Looking for Syncthing folder containing: {path_resolved}")

            for folder_id, folder_path in self._folders_cache.items():
                try:
                    # Check if path is under this folder
                    path_resolved.relative_to(folder_path)
                    logger.debug(f"Matched Syncthing folder '{folder_id}': {folder_path}")
                    return folder_id
                except ValueError:
                    continue

            # If we get here, no folder matched
            logger.debug(f"Path not in any Syncthing folder. Checking: {path_resolved}")
            logger.debug(f"Syncthing folders: {list(self._folders_cache.values())}")

        except Exception as e:
            logger.debug(f"Error getting folder ID: {e}")

        return None

    def _get_path_sync_status(self, folder_id: str, path: Path) -> tuple[int, int]:
        """
        Get sync status for a specific path within a Syncthing folder.

        Checks both files still downloading AND files not yet appeared locally.

        Args:
            folder_id: Syncthing folder ID
            path: Local path to check

        Returns:
            Tuple of (files_count, bytes_needed) for files still downloading or not yet visible
        """
        try:
            # Map local path to remote path
            remote_path = self._map_local_to_remote(path)

            # Get the relative path within the Syncthing folder
            syncthing_folder_path = self._folders_cache.get(folder_id)
            if not syncthing_folder_path:
                logger.debug(f"Could not find folder path for ID {folder_id}")
                return (0, 0)

            try:
                relative_path = remote_path.resolve().relative_to(syncthing_folder_path)
                path_prefix = str(relative_path)
            except ValueError:
                # Path is not under this folder
                logger.debug(f"Path {remote_path} not under folder {syncthing_folder_path}")
                return (0, 0)

            headers = {'X-API-Key': self.api_key}

            # 1. Check for files still being downloaded (in progress)
            resp_need = requests.get(
                f'{self.api_url}/rest/db/need?folder={folder_id}',
                headers=headers,
                timeout=self.api_timeout
            )
            resp_need.raise_for_status()

            data_need = resp_need.json()
            progress_files = data_need.get('progress', [])

            # Filter files in our path that are downloading
            files_downloading = []
            if path.is_dir():
                path_prefix_with_slash = path_prefix + '/'
                files_downloading = [
                    f for f in progress_files
                    if f.get('name', '').startswith(path_prefix_with_slash)
                ]
            else:
                files_downloading = [
                    f for f in progress_files
                    if f.get('name', '') == path_prefix
                ]

            bytes_downloading = sum(f.get('size', 0) for f in files_downloading)

            # 2. For directories, check if all expected files have appeared locally
            files_not_visible = 0
            bytes_not_visible = 0

            if path.is_dir():
                # Get what Syncthing says should be in this directory
                resp_browse = requests.get(
                    f'{self.api_url}/rest/db/browse?folder={folder_id}&prefix={path_prefix}',
                    headers=headers,
                    timeout=self.api_timeout
                )
                resp_browse.raise_for_status()
                expected_files = resp_browse.json()

                # Get what we see locally
                local_files = set()
                if path.exists() and path.is_dir():
                    for item in path.rglob('*'):
                        if item.is_file():
                            local_files.add(item.name)

                # Check for files Syncthing knows about but aren't visible locally yet
                for expected_file in expected_files:
                    if expected_file.get('type') == 'FILE_INFO_TYPE_FILE':
                        filename = expected_file.get('name', '')
                        if filename and filename not in local_files:
                            # File expected but not visible yet
                            file_size = expected_file.get('size', 0)
                            files_not_visible += 1
                            bytes_not_visible += file_size
                            logger.debug(f"File '{filename}' expected but not visible locally yet ({file_size:,} bytes)")

            total_files_pending = len(files_downloading) + files_not_visible
            total_bytes_pending = bytes_downloading + bytes_not_visible

            if total_files_pending > 0:
                logger.debug(f"Path '{path.name}' sync status: {len(files_downloading)} downloading, {files_not_visible} not visible, {total_bytes_pending:,} bytes total")
            else:
                logger.debug(f"Path '{path.name}' is fully synced and all files visible")

            return (total_files_pending, total_bytes_pending)

        except requests.RequestException as e:
            logger.debug(f"Error getting path sync status: {e}")
            return (0, 0)
        except Exception as e:
            logger.debug(f"Unexpected error in path sync status: {e}")
            return (0, 0)

    def _get_folder_completion(self, folder_id: str) -> Optional[float]:
        """
        Get completion percentage for a folder.

        Args:
            folder_id: Syncthing folder ID

        Returns:
            Completion percentage (0-100) or None if unavailable
        """
        try:
            headers = {'X-API-Key': self.api_key}
            resp = requests.get(
                f'{self.api_url}/rest/db/completion?folder={folder_id}',
                headers=headers,
                timeout=self.api_timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get('completion', 100)
        except Exception as e:
            logger.debug(f"Error getting folder completion: {e}")

        return None

    def _has_in_progress_items(self, folder_id: str, path: Path) -> str:
        """
        Check if folder has any in-progress items in Syncthing.

        Args:
            folder_id: Syncthing folder ID
            path: Path to check

        Returns:
            String describing the in-progress status, or empty string if no items in progress
        """
        try:
            headers = {'X-API-Key': self.api_key}
            resp = requests.get(
                f'{self.api_url}/rest/db/status?folder={folder_id}',
                headers=headers,
                timeout=self.api_timeout
            )
            if resp.status_code == 200:
                status = resp.json()
                # Check various in-progress indicators
                if status.get('pullErrors', 0) > 0:
                    return f"pull errors: {status.get('pullErrors', 0)}"

                state = status.get('state', '')
                if state in ['syncing', 'scanning']:
                    return f"state: {state}"

                need_bytes = status.get('needBytes', 0)
                if need_bytes > 0:
                    return f"need {need_bytes:,} bytes"

        except Exception as e:
            logger.debug(f"Error checking in-progress items: {e}")

        return ""

    def _has_temp_files(self, folder_path: Path) -> bool:
        """
        Check for syncthing temporary files (fallback method).

        Checks for:
        - .syncthing.*.tmp files
        - *.tmp files

        Args:
            folder_path: Path to folder to check

        Returns:
            True if temp files found
        """
        if not folder_path.is_dir():
            return False

        try:
            # Iterate through all files and check for temp patterns
            # Using rglob('*') and checking filename patterns is more reliable
            # than using glob patterns with dots
            for item in folder_path.rglob('*'):
                if not item.is_file():
                    continue

                filename = item.name

                # Check for .syncthing.*.tmp pattern
                if filename.startswith('.syncthing.') and filename.endswith('.tmp'):
                    logger.info(f"Temp file detection: Found syncthing temp file '{item.name}' - still syncing")
                    return True

                # Check for any .tmp file
                if filename.endswith('.tmp'):
                    logger.info(f"Temp file detection: Found temp file '{item.name}' - still syncing")
                    return True

        except (OSError, PermissionError) as e:
            logger.debug(f"Error checking for temp files: {e}")

        return False

    def wait_for_sync_complete(self, path: Path, max_wait: int = 300) -> bool:
        """
        Wait for syncthing to complete syncing a path.

        Args:
            path: Path to wait for
            max_wait: Maximum seconds to wait

        Returns:
            True if sync completed, False if timeout
        """
        import time

        start_time = time.time()
        while time.time() - start_time < max_wait:
            if path.is_dir():
                if not self.is_folder_syncing(path):
                    return True
            else:
                if not self.is_file_syncing(path):
                    return True

            time.sleep(2)

        logger.warning(f"Timeout waiting for sync to complete: {path}")
        return False
