"""
File stability checker to verify files are fully transferred.

Ensures files/directories are completely copied before processing by checking:
1. File sizes remain stable over time (traditional file size monitoring)
2. No Syncthing temporary files are present (for Syncthing sync detection)
3. Syncthing API status (if configured) - most reliable method
4. File hash verification for untracked files (extra assurance)
"""

import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

import config
from utils.logger import get_logger
from utils.syncthing_integration import SyncthingIntegration

logger = get_logger()


class FileStabilityChecker:
    """Checks if files/directories are fully transferred and stable."""

    def __init__(
        self,
        check_interval: int = config.FILE_STABILITY_CHECK_INTERVAL,
        retries: int = config.FILE_STABILITY_CHECK_RETRIES,
        syncthing_enabled: bool = config.SYNCTHING_ENABLED,
        allow_zero_byte_files: bool = config.ALLOW_ZERO_BYTE_FILES,
        hash_check_for_untracked: bool = config.HASH_CHECK_FOR_UNTRACKED
    ):
        """
        Initialize stability checker.

        Args:
            check_interval: Seconds to wait between stability checks
            retries: Number of times to verify stability
            syncthing_enabled: Enable Syncthing temporary file detection
            allow_zero_byte_files: Allow 0-byte files to be considered stable
            hash_check_for_untracked: Use hash verification for untracked files
        """
        self.check_interval = check_interval
        self.retries = retries
        self.syncthing_enabled = syncthing_enabled
        self.allow_zero_byte_files = allow_zero_byte_files
        self.hash_check_for_untracked = hash_check_for_untracked

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

    def get_stable_items(self, items: List[Path]) -> List[Path]:
        """
        Check multiple items and return only those that are stable.

        This is more efficient than checking items individually as it performs
        a single batch check with one wait period.

        For items not tracked by Syncthing, additional verification is performed:
        - Size stability over multiple checks
        - Hash stability (if enabled)
        - 0-byte file detection (unless allowed)

        Args:
            items: List of file/directory paths to check

        Returns:
            List of items that are stable and ready to process
        """
        if not items:
            return []

        logger.info(f"Checking stability of {len(items)} item(s)...")

        # Build maps for tracking
        item_files_map: Dict[Path, List[Path]] = {}
        untracked_items: Set[Path] = set()  # Items not tracked by Syncthing
        syncthing_unstable_items: List[Path] = []

        for item in items:
            if not item.exists():
                logger.warning(f"Item does not exist: {item}")
                continue

            # Check for Syncthing temporary files first (quick check)
            if self.syncthing_enabled and self._has_syncthing_tmp_files(item):
                logger.info(f"'{item.name}' has Syncthing temporary files - still syncing")
                syncthing_unstable_items.append(item)
                continue

            # Get detailed sync status (is_syncing, is_tracked)
            is_syncing, is_tracked = self.syncthing.get_sync_status(item)

            if is_syncing:
                logger.info(f"'{item.name}' is actively syncing - skipping")
                syncthing_unstable_items.append(item)
                continue

            if not is_tracked:
                logger.info(f"'{item.name}' is not tracked by Syncthing - will use enhanced stability checks")
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
            return []

        # Get all unique files across all items
        all_files: List[Path] = []
        for files in item_files_map.values():
            all_files.extend(files)

        if not all_files:
            # All items are empty directories
            logger.info(f"All {len(item_files_map)} item(s) are empty directories (stable)")
            return list(item_files_map.keys())

        # Perform stability checks with enhanced verification for untracked items
        stable_items = self._perform_stability_checks(
            item_files_map, all_files, untracked_items
        )

        return stable_items

    def _perform_stability_checks(
        self,
        item_files_map: Dict[Path, List[Path]],
        all_files: List[Path],
        untracked_items: Set[Path]
    ) -> List[Path]:
        """
        Perform stability checks on files.

        For untracked items, performs additional hash verification.

        Args:
            item_files_map: Map of items to their files
            all_files: All files to check
            untracked_items: Items not tracked by Syncthing

        Returns:
            List of stable items
        """
        stable_items: List[Path] = []
        unstable_items: List[Path] = []

        # Get files that belong to untracked items (need hash verification)
        untracked_files: Set[Path] = set()
        for item in untracked_items:
            for file_path in item_files_map.get(item, []):
                untracked_files.add(file_path)

        # Initial hashes for untracked files (if hash checking enabled)
        previous_hashes: Dict[Path, str] = {}
        if self.hash_check_for_untracked and untracked_files:
            logger.info(f"Computing initial hashes for {len(untracked_files)} untracked file(s)...")
            previous_hashes = self._get_file_hashes(list(untracked_files))

        for attempt in range(self.retries):
            # Get current sizes
            current_sizes = self._get_file_sizes(all_files)

            if current_sizes is None:
                logger.warning("Failed to get file sizes during batch check")
                return []

            # On first check, just record sizes
            if attempt == 0:
                previous_sizes = current_sizes
                total_bytes = sum(current_sizes.values())
                logger.info(
                    f"Initial check: {len(all_files)} file(s), {total_bytes:,} bytes total"
                )
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
                                logger.info(
                                    f"'{item.name}' still transferring "
                                    f"({file_path.name}: {prev_size:,}→{curr_size:,} bytes)"
                                )
                                size_changed = True
                            break

                if size_changed:
                    # Return only stable items (those not in unstable list)
                    for item in item_files_map.keys():
                        if item not in unstable_items:
                            stable_items.append(item)

                    logger.info(
                        f"Stability check complete: {len(stable_items)} stable, "
                        f"{len(unstable_items)} still transferring"
                    )
                    return stable_items
                else:
                    logger.debug(f"Size check {attempt + 1}/{self.retries} passed")

                previous_sizes = current_sizes

            # Wait before next check (except on last iteration)
            if attempt < self.retries - 1:
                logger.debug(f"Waiting {self.check_interval} seconds before next check...")
                time.sleep(self.check_interval)

        # Size checks passed - now do additional checks

        # 1. Hash verification for untracked files
        hash_unstable_count = 0
        if self.hash_check_for_untracked and untracked_files:
            logger.info(f"Verifying hashes for {len(untracked_files)} untracked file(s)...")
            current_hashes = self._get_file_hashes(list(untracked_files))

            for item in list(untracked_items):
                for file_path in item_files_map.get(item, []):
                    if file_path in untracked_files:
                        prev_hash = previous_hashes.get(file_path, "")
                        curr_hash = current_hashes.get(file_path, "")

                        if prev_hash and curr_hash and prev_hash != curr_hash:
                            if item not in unstable_items:
                                unstable_items.append(item)
                                hash_unstable_count += 1
                                logger.info(
                                    f"'{item.name}' hash changed for '{file_path.name}' - still being modified"
                                )
                            break

            if hash_unstable_count == 0:
                logger.info(f"Hash verification passed for all {len(untracked_files)} untracked file(s)")

        # 2. Check for 0-byte files (unless allowed)
        zero_byte_items: List[Path] = []

        if not self.allow_zero_byte_files:
            for item, files in item_files_map.items():
                if item in unstable_items:
                    continue

                for file_path in files:
                    if current_sizes.get(file_path, 0) == 0:
                        logger.info(
                            f"'{item.name}' has 0-byte file(s) - likely still downloading: {file_path.name}"
                        )
                        zero_byte_items.append(item)
                        break

        # Build final stable list
        for item in item_files_map.keys():
            if item not in unstable_items and item not in zero_byte_items:
                stable_items.append(item)

        total_bytes = sum(current_sizes.values())

        if unstable_items or zero_byte_items:
            logger.info(
                f"Transfer check complete: {len(stable_items)} stable, "
                f"{len(unstable_items)} still transferring, "
                f"{len(zero_byte_items)} with 0-byte file(s)"
            )
        else:
            logger.info(
                f"Transfer complete for all {len(stable_items)} item(s): "
                f"{len(all_files)} file(s), {total_bytes:,} bytes total"
            )

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
