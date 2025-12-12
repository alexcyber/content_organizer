"""
File and folder moving operations with dry-run support.

Handles actual file/folder moves or simulates them in dry-run mode.
"""

import shutil
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

logger = get_logger()


class FileMover:
    """Handles moving files and folders with dry-run support."""

    def __init__(self, dry_run: bool = False, quiet: bool = False):
        """
        Initialize file mover.

        Args:
            dry_run: If True, only simulate operations without actual moves
            quiet: Kept for backward compatibility but not used (quiet mode handled at MediaOrganizer level)
        """
        self.dry_run = dry_run
        self.quiet = quiet

        if dry_run:
            logger.info("DRY-RUN MODE: No files will be moved")

    def move(self, source: Path, destination_folder: Path) -> Optional[Path]:
        """
        Move file or folder to destination.

        Args:
            source: Source file or folder path
            destination_folder: Destination folder path

        Returns:
            Final path of moved item or None if operation failed
        """
        if not source.exists():
            logger.error(f"Source does not exist: {source}")
            return None

        # Ensure destination folder exists (or would exist)
        if not self.dry_run:
            destination_folder.mkdir(parents=True, exist_ok=True)

        # Determine final destination path
        destination_path = destination_folder / source.name

        # Check if destination already exists
        if destination_path.exists():
            if self._is_same_file(source, destination_path):
                logger.info(f"File already at destination: {destination_path}")
                return destination_path
            else:
                logger.warning(f"Destination already exists: {destination_path}")
                # Generate unique name
                destination_path = self._get_unique_path(destination_path)
                logger.info(f"Using unique name: {destination_path.name}")

        # Perform move (or simulate)
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would move: {source} -> {destination_path}")
            return destination_path
        else:
            try:
                shutil.move(str(source), str(destination_path))
                logger.info(f"Moved: {source.name} -> {destination_path}")
                return destination_path
            except (OSError, shutil.Error) as e:
                logger.error(f"Failed to move {source} to {destination_path}: {e}")
                return None

    @staticmethod
    def _is_same_file(path1: Path, path2: Path) -> bool:
        """
        Check if two paths refer to the same file/folder.

        Args:
            path1: First path
            path2: Second path

        Returns:
            True if paths refer to the same file/folder
        """
        try:
            return path1.resolve() == path2.resolve()
        except (OSError, RuntimeError):
            return False

    @staticmethod
    def _get_unique_path(path: Path) -> Path:
        """
        Generate unique path by appending number if path exists.

        Args:
            path: Original path

        Returns:
            Unique path that doesn't exist
        """
        if not path.exists():
            return path

        parent = path.parent
        stem = path.stem
        suffix = path.suffix

        counter = 1
        while True:
            new_path = parent / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return new_path
            counter += 1
