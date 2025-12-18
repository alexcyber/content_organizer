"""
File stability checker to verify files are fully transferred.

Ensures files/directories are completely copied before processing by checking:
1. RuTorrent API (if configured) - is torrent complete on remote seedbox?
2. Syncthing temporary file detection - quick local check
3. Syncthing API status (if configured) - is sync complete locally?
4. File sizes remain stable over time (fallback for non-torrent items)
5. File hash verification for untracked files (extra assurance)

The multi-source approach ensures we don't move files until:
- The torrent download is complete on the seedbox (RuTorrent)
- The sync to local storage is complete (Syncthing)
- All files are stable and not changing (fallback checks)
"""

import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import config
from utils.logger import get_logger
from utils.syncthing_integration import SyncthingIntegration
from utils.rutorrent_client import RuTorrentClient

logger = get_logger()


class FileStabilityChecker:
    """Checks if files/directories are fully transferred and stable."""

    def __init__(
        self,
        check_interval: int = config.FILE_STABILITY_CHECK_INTERVAL,
        retries: int = config.FILE_STABILITY_CHECK_RETRIES,
        syncthing_enabled: bool = config.SYNCTHING_ENABLED,
        allow_zero_byte_files: bool = config.ALLOW_ZERO_BYTE_FILES,
        hash_check_for_untracked: bool = config.HASH_CHECK_FOR_UNTRACKED,
        rutorrent_enabled: bool = None,
        quiet: bool = False,
    ):
        """
        Initialize stability checker.

        Args:
            check_interval: Seconds to wait between stability checks
            retries: Number of times to verify stability
            syncthing_enabled: Enable Syncthing temporary file detection
            allow_zero_byte_files: Allow 0-byte files to be considered stable
            hash_check_for_untracked: Use hash verification for untracked files
            rutorrent_enabled: Enable RuTorrent integration (None = use config)
            quiet: If True, collect logs for deferred output instead of logging immediately
        """
        self.check_interval = check_interval
        self.retries = retries
        self.syncthing_enabled = syncthing_enabled
        self.allow_zero_byte_files = allow_zero_byte_files
        self.hash_check_for_untracked = hash_check_for_untracked
        self.quiet = quiet

        # Collected logs for deferred output in quiet mode
        self.stability_logs: List[str] = []

        # Initialize RuTorrent integration for torrent completion detection
        # RuTorrent checks if the torrent is complete on the remote seedbox
        rutorrent_enabled = rutorrent_enabled if rutorrent_enabled is not None else getattr(config, 'RUTORRENT_ENABLED', False)
        self.rutorrent = RuTorrentClient(
            url=getattr(config, 'RUTORRENT_URL', ''),
            username=getattr(config, 'RUTORRENT_USERNAME', ''),
            password=getattr(config, 'RUTORRENT_PASSWORD', ''),
            base_path=getattr(config, 'RUTORRENT_BASE_PATH', ''),
            subfolders=getattr(config, 'RUTORRENT_SUBFOLDERS', []),
            enabled=rutorrent_enabled,
            timeout=getattr(config, 'RUTORRENT_TIMEOUT', 30)
        )

        if rutorrent_enabled:
            logger.debug("RuTorrent integration enabled - will check torrent completion status")

        # Initialize Syncthing integration for API-based sync detection
        # Use the syncthing_enabled parameter to control both temp file checks
        # and API-based sync detection consistently
        self.syncthing = SyncthingIntegration(
            api_url=config.SYNCTHING_URL,
            api_key=config.SYNCTHING_API_KEY,
            enabled=syncthing_enabled and config.SYNCTHING_API_ENABLED,
            api_timeout=config.SYNCTHING_API_TIMEOUT,
            path_mapping=config.SYNCTHING_PATH_MAPPING
        )

        if syncthing_enabled:
            logger.debug("Syncthing integration enabled - will check for temporary files")

    def _log(self, message: str, level: str = "info") -> None:
        """Log a message, collecting it for deferred output in quiet mode.

        Args:
            message: The message to log
            level: Log level (info, debug, warning)
        """
        # Always collect INFO level logs for potential deferred output
        if level == "info":
            self.stability_logs.append(message)

        # Log immediately if not in quiet mode
        if not self.quiet:
            if level == "debug":
                logger.debug(message)
            elif level == "warning":
                logger.warning(message)
            else:
                logger.info(message)

    def get_stability_logs(self) -> List[str]:
        """Get collected stability logs for deferred output.

        Returns:
            List of log messages from the last stability check
        """
        return self.stability_logs

    def clear_stability_logs(self) -> None:
        """Clear collected stability logs."""
        self.stability_logs = []

    def get_stable_items(self, items: List[Path]) -> List[Path]:
        """
        Check multiple items and return only those that are stable.

        Performs a multi-stage check:
        1. RuTorrent check - is torrent complete on remote seedbox?
        2. Syncthing temp file check - quick local check for .tmp files
        3. Syncthing API check - is sync complete locally?
        4. File stability checks - size/hash verification for untracked items

        Args:
            items: List of file/directory paths to check

        Returns:
            List of items that are stable and ready to process
        """
        if not items:
            return []

        # Clear previous logs and start fresh
        self.clear_stability_logs()

        self._log(f"Checking stability of {len(items)} item(s):")
        for item in items:
            self._log(f"  • {item.name}")

        # Build maps for tracking
        item_files_map: Dict[Path, List[Path]] = {}
        untracked_items: Set[Path] = set()  # Items not tracked by Syncthing
        unstable_items: List[Path] = []
        unstable_reasons: Dict[Path, str] = {}  # Track why each item is unstable

        # Refresh RuTorrent cache once at the start (if enabled)
        if self.rutorrent.enabled:
            self.rutorrent.refresh_cache()

        for item in items:
            if not item.exists():
                self._log(f"Item does not exist: {item}", "warning")
                continue

            # Step 1: Check RuTorrent (if enabled) - is torrent complete on remote?
            if self.rutorrent.enabled:
                is_complete, reason, torrent_info = self.rutorrent.is_torrent_complete(item.name)

                if torrent_info is not None:
                    # This is a tracked torrent
                    if not is_complete:
                        unstable_items.append(item)
                        unstable_reasons[item] = f"RuTorrent: {reason}"
                        continue
                    else:
                        self._log(f"'{item.name}' - RuTorrent: {reason}", "debug")
                # If torrent_info is None, it's not a torrent (manual copy) - continue to other checks

            # Step 2: Check for Syncthing temporary files (quick local check)
            if self.syncthing_enabled and self._has_syncthing_tmp_files(item):
                unstable_items.append(item)
                unstable_reasons[item] = "has Syncthing temporary files - still syncing"
                continue

            # Step 3: Get detailed Syncthing sync status (is_syncing, is_tracked)
            is_syncing, is_tracked = self.syncthing.get_sync_status(item)

            if is_syncing:
                unstable_items.append(item)
                unstable_reasons[item] = "actively syncing via Syncthing"
                continue

            if not is_tracked:
                self._log(f"'{item.name}' is not tracked by Syncthing - will use enhanced stability checks", "debug")
                untracked_items.add(item)

            # Collect files for stability checking
            if item.is_file():
                item_files_map[item] = [item]
            else:
                files = self._get_all_files(item)
                if not files:
                    # Empty directory is considered stable
                    item_files_map[item] = []
                else:
                    item_files_map[item] = files

        if not item_files_map:
            # All items were unstable - log summary
            self._log_stability_summary([], unstable_items, unstable_reasons)
            return []

        # Get all unique files across all items
        all_files: List[Path] = []
        for files in item_files_map.values():
            all_files.extend(files)

        if not all_files:
            # All items are empty directories
            stable_items = list(item_files_map.keys())
            self._log(f"All {len(item_files_map)} item(s) are empty directories (stable)")
            self._log_stability_summary(stable_items, unstable_items, unstable_reasons)
            return stable_items

        # Perform stability checks with enhanced verification for untracked items
        stable_items = self._perform_stability_checks(
            item_files_map, all_files, untracked_items, unstable_items, unstable_reasons
        )

        # Log final summary
        self._log_stability_summary(stable_items, unstable_items, unstable_reasons)

        return stable_items

    def _log_stability_summary(
        self,
        stable_items: List[Path],
        unstable_items: List[Path],
        unstable_reasons: Dict[Path, str]
    ) -> None:
        """Log a summary of stable and unstable items.

        Args:
            stable_items: Items that passed stability checks
            unstable_items: Items that failed stability checks
            unstable_reasons: Reasons why each unstable item failed
        """
        self._log("")  # Blank line for readability

        if stable_items:
            self._log(f"Stable items ready for processing ({len(stable_items)}):")
            for item in stable_items:
                self._log(f"  ✓ {item.name}")

        if unstable_items:
            self._log(f"Unstable items skipped ({len(unstable_items)}):")
            for item in unstable_items:
                reason = unstable_reasons.get(item, "unknown reason")
                self._log(f"  ✗ {item.name} - {reason}")

    def _perform_stability_checks(
        self,
        item_files_map: Dict[Path, List[Path]],
        all_files: List[Path],
        untracked_items: Set[Path],
        unstable_items: List[Path],
        unstable_reasons: Dict[Path, str]
    ) -> List[Path]:
        """
        Perform stability checks on files.

        For untracked items, performs additional hash verification.

        Args:
            item_files_map: Map of items to their files
            all_files: All files to check
            untracked_items: Items not tracked by Syncthing
            unstable_items: List to append unstable items to
            unstable_reasons: Dict to store reasons for instability

        Returns:
            List of stable items
        """
        stable_items: List[Path] = []

        # Get files that belong to untracked items (need hash verification)
        untracked_files: Set[Path] = set()
        for item in untracked_items:
            for file_path in item_files_map.get(item, []):
                untracked_files.add(file_path)

        # Initial hashes for untracked files (if hash checking enabled)
        previous_hashes: Dict[Path, str] = {}
        if self.hash_check_for_untracked and untracked_files:
            self._log(f"Computing initial hashes for {len(untracked_files)} untracked file(s)...", "debug")
            previous_hashes = self._get_file_hashes(list(untracked_files))

        for attempt in range(self.retries):
            # Get current sizes
            current_sizes = self._get_file_sizes(all_files)

            if current_sizes is None:
                self._log("Failed to get file sizes during batch check", "warning")
                return []

            # On first check, just record sizes
            if attempt == 0:
                previous_sizes = current_sizes
                total_bytes = sum(current_sizes.values())
                self._log(f"Verifying file stability: {len(all_files)} file(s), {total_bytes:,} bytes total", "debug")
            else:
                # Compare with previous sizes
                size_changed = False
                for item, files in item_files_map.items():
                    for file_path in files:
                        prev_size = previous_sizes.get(file_path, 0)
                        curr_size = current_sizes.get(file_path, 0)
                        if prev_size != curr_size:
                            if item not in unstable_items:
                                unstable_items.append(item)
                                reason = f"still transferring ({file_path.name}: {prev_size:,} -> {curr_size:,} bytes)"
                                unstable_reasons[item] = reason
                                size_changed = True
                            break

                if size_changed:
                    # Return only stable items (those not in unstable list)
                    for item in item_files_map.keys():
                        if item not in unstable_items:
                            stable_items.append(item)
                    return stable_items
                else:
                    self._log(f"Size check {attempt + 1}/{self.retries} passed", "debug")

                previous_sizes = current_sizes

            # Wait before next check (except on last iteration)
            if attempt < self.retries - 1:
                self._log(f"Waiting {self.check_interval} seconds before next check...", "debug")
                time.sleep(self.check_interval)

        # Size checks passed - now do additional checks

        # 1. Hash verification for untracked files
        if self.hash_check_for_untracked and untracked_files:
            self._log(f"Verifying hashes for {len(untracked_files)} untracked file(s)...", "debug")
            current_hashes = self._get_file_hashes(list(untracked_files))

            for item in list(untracked_items):
                for file_path in item_files_map.get(item, []):
                    if file_path in untracked_files:
                        prev_hash = previous_hashes.get(file_path, "")
                        curr_hash = current_hashes.get(file_path, "")

                        if prev_hash and curr_hash and prev_hash != curr_hash:
                            if item not in unstable_items:
                                unstable_items.append(item)
                                unstable_reasons[item] = f"hash changed for '{file_path.name}' - still being modified"
                            break

        # 2. Check for 0-byte files (unless allowed)
        if not self.allow_zero_byte_files:
            for item, files in item_files_map.items():
                if item in unstable_items:
                    continue

                for file_path in files:
                    if current_sizes.get(file_path, 0) == 0:
                        unstable_items.append(item)
                        unstable_reasons[item] = f"has 0-byte file: {file_path.name}"
                        break

        # Build final stable list
        for item in item_files_map.keys():
            if item not in unstable_items:
                stable_items.append(item)

        return stable_items

    def _get_file_hashes(self, files: List[Path], chunk_size: int = 65536) -> Dict[Path, str]:
        """
        Compute quick hashes for files.

        Uses a sampling approach for large files to balance speed and accuracy:
        - For files < 1MB: hash entire file
        - For files >= 1MB: hash first 64KB + last 64KB + size

        Args:
            files: List of file paths
            chunk_size: Bytes to read per chunk

        Returns:
            Dictionary mapping file paths to hash strings
        """
        hashes: Dict[Path, str] = {}
        size_threshold = 1024 * 1024  # 1MB

        for file_path in files:
            try:
                if not file_path.exists():
                    continue

                file_size = file_path.stat().st_size

                if file_size == 0:
                    # 0-byte file - use empty hash
                    hashes[file_path] = "empty"
                    continue

                hasher = hashlib.md5()

                if file_size < size_threshold:
                    # Small file - hash entire content
                    with open(file_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(chunk_size), b''):
                            hasher.update(chunk)
                else:
                    # Large file - sample beginning and end
                    with open(file_path, 'rb') as f:
                        # Read first chunk
                        hasher.update(f.read(chunk_size))
                        # Seek to end and read last chunk
                        f.seek(max(0, file_size - chunk_size))
                        hasher.update(f.read(chunk_size))
                        # Include file size in hash
                        hasher.update(str(file_size).encode())

                hashes[file_path] = hasher.hexdigest()

            except (OSError, PermissionError) as e:
                logger.debug(f"Error hashing file {file_path}: {e}")
                hashes[file_path] = "error"

        return hashes

    def is_transfer_complete(self, path: Path) -> bool:
        """
        Check if a file or directory transfer is complete.

        For files: Checks if file size is stable over time and no Syncthing temp files exist.
        For directories: Recursively checks all files within.

        Args:
            path: Path to file or directory to check

        Returns:
            True if transfer is complete and stable, False otherwise
        """
        if not path.exists():
            logger.warning(f"Path does not exist: {path}")
            return False

        # Check for Syncthing temporary files first
        if self.syncthing_enabled and self._has_syncthing_tmp_files(path):
            logger.info(f"'{path.name}' has Syncthing temporary files - still syncing")
            return False

        # Check sync status via Syncthing API (only if enabled)
        is_tracked = False
        if self.syncthing_enabled:
            is_syncing, is_tracked = self.syncthing.get_sync_status(path)
            if is_syncing:
                logger.info(f"'{path.name}' is actively syncing")
                return False

        # Get all files to check
        if path.is_file():
            files_to_check = [path]
        else:
            files_to_check = self._get_all_files(path)

        if not files_to_check:
            logger.debug(f"No files to check in: {path}")
            return True

        # Get initial hashes for untracked items
        previous_hashes: Dict[Path, str] = {}
        if not is_tracked and self.hash_check_for_untracked:
            previous_hashes = self._get_file_hashes(files_to_check)

        # Perform stability checks
        for attempt in range(self.retries):
            # Get current sizes
            current_sizes = self._get_file_sizes(files_to_check)

            if current_sizes is None:
                logger.warning(f"Failed to get file sizes for: {path}")
                return False

            # On first check, just record sizes
            if attempt == 0:
                previous_sizes = current_sizes
                logger.debug(
                    f"Initial stability check for '{path.name}': "
                    f"{len(files_to_check)} file(s), {sum(current_sizes.values())} bytes total"
                )
            else:
                # Compare with previous sizes
                if current_sizes != previous_sizes:
                    unstable_files = []
                    for file_path, size in current_sizes.items():
                        prev_size = previous_sizes.get(file_path, 0)
                        if size != prev_size:
                            unstable_files.append(f"{file_path.name} ({prev_size}→{size})")

                    logger.info(
                        f"'{path.name}' still transferring - {len(unstable_files)} file(s) changed size"
                    )
                    logger.debug(f"Unstable files: {', '.join(unstable_files)}")
                    return False

                logger.debug(
                    f"Stability check {attempt + 1}/{self.retries} passed for '{path.name}'"
                )
                previous_sizes = current_sizes

            # Wait before next check (except on last iteration)
            if attempt < self.retries - 1:
                time.sleep(self.check_interval)

        # Size checks passed - do additional checks for untracked items
        if not is_tracked and self.hash_check_for_untracked:
            current_hashes = self._get_file_hashes(files_to_check)
            for file_path in files_to_check:
                prev_hash = previous_hashes.get(file_path, "")
                curr_hash = current_hashes.get(file_path, "")
                if prev_hash and curr_hash and prev_hash != curr_hash:
                    logger.info(f"'{path.name}' hash changed for '{file_path.name}' - still being modified")
                    return False

        # Check for 0-byte files (unless allowed)
        total_bytes = sum(current_sizes.values())

        if not self.allow_zero_byte_files:
            for file_path, size in current_sizes.items():
                if size == 0:
                    logger.info(
                        f"'{path.name}' has 0-byte file(s) - likely still downloading: {file_path.name}"
                    )
                    return False

        logger.info(
            f"Transfer complete for '{path.name}': "
            f"{len(files_to_check)} file(s), {total_bytes:,} bytes total"
        )
        return True

    def _get_all_files(self, directory: Path) -> List[Path]:
        """
        Recursively get all files in a directory.

        Args:
            directory: Directory to scan

        Returns:
            List of all file paths
        """
        files = []
        try:
            for item in directory.rglob("*"):
                if item.is_file():
                    files.append(item)
        except (OSError, PermissionError) as e:
            logger.warning(f"Error scanning directory {directory}: {e}")

        return files

    def _get_file_sizes(self, files: List[Path]) -> Optional[Dict[Path, int]]:
        """
        Get sizes of all files.

        Args:
            files: List of file paths

        Returns:
            Dictionary mapping file paths to sizes, or None if error
        """
        sizes = {}
        try:
            for file_path in files:
                if file_path.exists():
                    sizes[file_path] = file_path.stat().st_size
                else:
                    # File disappeared during check
                    logger.warning(f"File disappeared during check: {file_path}")
                    return None
        except (OSError, PermissionError) as e:
            logger.error(f"Error getting file sizes: {e}")
            return None

        return sizes

    def _has_syncthing_tmp_files(self, path: Path) -> bool:
        """
        Check if a file or directory has associated Syncthing temporary files.

        Syncthing creates temporary files with patterns like:
        - .syncthing.<filename>.tmp
        - <filename>.tmp (generic temporary files)

        Args:
            path: Path to file or directory to check

        Returns:
            True if Syncthing temporary files are detected, False otherwise
        """
        if not self.syncthing_enabled:
            return False

        try:
            if path.is_file():
                # For files, check in the parent directory for related temp files
                parent = path.parent
                filename = path.name

                # Check for Syncthing temporary file patterns
                for pattern in config.SYNCTHING_TMP_PATTERNS:
                    # Check for .syncthing.<filename>.tmp
                    if pattern == ".syncthing.*.tmp":
                        syncthing_tmp = parent / f".syncthing.{filename}.tmp"
                        if syncthing_tmp.exists():
                            logger.debug(f"Found Syncthing temp file: {syncthing_tmp.name}")
                            return True

                    # Check for <filename>.tmp
                    elif pattern == "*.tmp":
                        if filename.endswith('.tmp'):
                            logger.debug(f"File has .tmp extension: {filename}")
                            return True
                        tmp_file = parent / f"{filename}.tmp"
                        if tmp_file.exists():
                            logger.debug(f"Found temp file: {tmp_file.name}")
                            return True

            elif path.is_dir():
                # For directories, check for any .tmp files or .syncthing. files
                for item in path.rglob("*"):
                    # Check if any file matches Syncthing patterns
                    if item.is_file():
                        for pattern in config.SYNCTHING_TMP_PATTERNS:
                            if pattern == ".syncthing.*.tmp":
                                if item.name.startswith('.syncthing.') and item.name.endswith('.tmp'):
                                    logger.debug(f"Found Syncthing temp file in directory: {item.name}")
                                    return True
                            elif pattern == "*.tmp":
                                if item.name.endswith('.tmp'):
                                    logger.debug(f"Found .tmp file in directory: {item.name}")
                                    return True

        except (OSError, PermissionError) as e:
            logger.warning(f"Error checking for Syncthing temp files in {path}: {e}")
            return False

        return False
