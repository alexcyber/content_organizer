"""
File stability checker to verify files are fully transferred.

Ensures files/directories are completely copied before processing by checking
if file sizes remain stable over time.
"""

import time
from pathlib import Path
from typing import Dict, List

import config
from utils.logger import get_logger

logger = get_logger()


class FileStabilityChecker:
    """Checks if files/directories are fully transferred and stable."""

    def __init__(
        self,
        check_interval: int = config.FILE_STABILITY_CHECK_INTERVAL,
        retries: int = config.FILE_STABILITY_CHECK_RETRIES
    ):
        """
        Initialize stability checker.

        Args:
            check_interval: Seconds to wait between stability checks
            retries: Number of times to verify stability
        """
        self.check_interval = check_interval
        self.retries = retries

    def get_stable_items(self, items: List[Path]) -> List[Path]:
        """
        Check multiple items and return only those that are stable.

        This is more efficient than checking items individually as it performs
        a single batch check with one wait period.

        Args:
            items: List of file/directory paths to check

        Returns:
            List of items that are stable and ready to process
        """
        if not items:
            return []

        logger.info(f"Checking stability of {len(items)} item(s)...")

        # Build a map of item -> files to check
        item_files_map = {}
        for item in items:
            if not item.exists():
                logger.warning(f"Item does not exist: {item}")
                continue

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
            logger.warning("No valid items to check")
            return []

        # Get all unique files across all items
        all_files = []
        for files in item_files_map.values():
            all_files.extend(files)

        if not all_files:
            # All items are empty directories
            logger.info(f"All {len(item_files_map)} item(s) are empty directories (stable)")
            return list(item_files_map.keys())

        # Perform stability checks
        stable_items = []
        unstable_items = []

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
                if current_sizes != previous_sizes:
                    # Find which items have unstable files
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
                                break

                    # Items not in unstable list are stable
                    for item in item_files_map.keys():
                        if item not in unstable_items:
                            stable_items.append(item)

                    logger.info(
                        f"Stability check complete: {len(stable_items)} stable, "
                        f"{len(unstable_items)} still transferring"
                    )
                    return stable_items
                else:
                    logger.debug(f"Stability check {attempt + 1}/{self.retries} passed")

                previous_sizes = current_sizes

            # Wait before next check (except on last iteration)
            if attempt < self.retries - 1:
                logger.debug(f"Waiting {self.check_interval} seconds before next check...")
                time.sleep(self.check_interval)

        # All checks passed - all items are stable
        stable_items = list(item_files_map.keys())
        total_bytes = sum(current_sizes.values())
        logger.info(
            f"Transfer complete for all {len(stable_items)} item(s): "
            f"{len(all_files)} file(s), {total_bytes:,} bytes total"
        )
        return stable_items

    def is_transfer_complete(self, path: Path) -> bool:
        """
        Check if a file or directory transfer is complete.

        For files: Checks if file size is stable over time.
        For directories: Recursively checks all files within.

        Args:
            path: Path to file or directory to check

        Returns:
            True if transfer is complete and stable, False otherwise
        """
        if not path.exists():
            logger.warning(f"Path does not exist: {path}")
            return False

        # Get all files to check
        if path.is_file():
            files_to_check = [path]
        else:
            files_to_check = self._get_all_files(path)

        if not files_to_check:
            logger.debug(f"No files to check in: {path}")
            return True

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

        # All checks passed
        logger.info(
            f"Transfer complete for '{path.name}': "
            f"{len(files_to_check)} file(s), {sum(current_sizes.values())} bytes total"
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

    def _get_file_sizes(self, files: List[Path]) -> Dict[Path, int]:
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
