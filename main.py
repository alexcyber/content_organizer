#!/usr/bin/env python3
"""
Media File Organizer - Main Entry Point

Automated media file organizer that monitors download directory and routes
files to appropriate destinations based on content type.
"""

import argparse
import fcntl
import sys
import time
from pathlib import Path
from typing import List

import config
from matchers.folder_matcher import FolderMatcher
from operations.file_mover import FileMover
from operations.sftp_manager import SFTPManager
from parsers.content_classifier import ContentClassifier
from parsers.filename_parser import FilenameParser
from utils.file_stability import FileStabilityChecker
from utils.logger import setup_logger, set_quiet_mode

logger = setup_logger()


class LockFile:
    """File-based lock using fcntl to prevent concurrent runs.

    This implementation uses OS-level file locking (fcntl.flock) which:
    - Automatically releases when process exits or crashes
    - Blocks waiting for lock instead of failing immediately
    - Works correctly with syncthing and other file sync solutions
    - Only locks the lockfile itself, not downloaded files
    """

    def __init__(self, lock_path: str = config.LOCK_FILE, timeout: int = 300):
        """Initialize lock file.

        Args:
            lock_path: Path to lock file
            timeout: Maximum seconds to wait for lock (default: 5 minutes)
        """
        self.lock_path = Path(lock_path)
        self.timeout = timeout
        self.lock_file = None
        self.locked = False

    def __enter__(self):
        """Acquire lock, waiting if another instance is running."""
        # Ensure lock directory exists
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        # Open lock file (create if doesn't exist)
        self.lock_file = open(self.lock_path, 'w')

        logger.debug(f"Attempting to acquire lock: {self.lock_path}")

        # Try to acquire lock with timeout
        start_time = time.time()
        waited = False

        while True:
            try:
                # Try non-blocking lock first
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.locked = True

                if waited:
                    logger.info(f"Lock acquired after waiting")
                else:
                    logger.debug(f"Lock acquired: {self.lock_path}")

                # Write PID to lock file for debugging
                self.lock_file.write(str(Path('/proc/self').resolve().name if Path('/proc/self').exists() else 'unknown'))
                self.lock_file.flush()

                return self

            except BlockingIOError:
                # Lock is held by another process
                elapsed = time.time() - start_time

                if elapsed >= self.timeout:
                    logger.error(f"Timeout waiting for lock after {self.timeout} seconds")
                    logger.error("Another instance is still running. Exiting.")
                    self.lock_file.close()
                    sys.exit(1)

                # First time waiting
                if not waited:
                    logger.info(f"Another instance is running. Waiting for lock...")
                    waited = True

                # Wait a bit before retrying
                time.sleep(1)

            except OSError as e:
                logger.error(f"Failed to acquire lock: {e}")
                if self.lock_file:
                    self.lock_file.close()
                sys.exit(1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock."""
        if self.locked and self.lock_file:
            try:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                logger.debug(f"Lock released: {self.lock_path}")
            except OSError as e:
                logger.warning(f"Failed to release lock: {e}")
            finally:
                self.lock_file.close()
                # Clean up lock file
                try:
                    self.lock_path.unlink()
                except OSError:
                    pass  # Ignore if already deleted


class MediaOrganizer:
    """Main orchestrator for media file organization."""

    def __init__(self, dry_run: bool = False, sftp_delete: bool = False, quiet: bool = False):
        """
        Initialize media organizer.

        Args:
            dry_run: If True, only simulate operations
            sftp_delete: If True, delete files from remote SFTP server after successful move
            quiet: If True, only log when there's work to do or errors occur
        """
        self.dry_run = dry_run
        self.sftp_delete = sftp_delete
        self.quiet = quiet

        # Enable quiet mode on logger if requested
        # This suppresses INFO messages on console while keeping them in log file
        if quiet:
            set_quiet_mode(True)

        self.parser = FilenameParser()
        self.classifier = ContentClassifier()
        self.matcher = FolderMatcher()
        self.mover = FileMover(dry_run=dry_run, quiet=quiet)
        self.sftp_manager = SFTPManager(dry_run=dry_run) if sftp_delete else None
        self.stability_checker = FileStabilityChecker()

        self.stats = {
            "processed": 0,
            "moved": 0,
            "skipped": 0,
            "errors": 0,
            "sftp_deleted": 0,
            "sftp_failed": 0
        }

    def run(self) -> int:
        """
        Run the media organizer.

        Returns:
            Exit code (0 for success, 1 for errors)
        """
        # Validate configuration
        issues = config.validate_config()
        for issue in issues:
            logger.warning(issue)

        # Get items to process
        items = self._get_items_to_process()

        if not items:
            # In quiet mode, don't log when there's nothing to do
            if not self.quiet:
                logger.info("=" * 60)
                logger.info("Media File Organizer - Starting")
                logger.info("=" * 60)
                logger.info("No items to process")
            return 0

        # Only show banner when there's work to do (unless quiet mode)
        if not self.quiet:
            logger.info("=" * 60)
            logger.info("Media File Organizer - Starting")
            logger.info("=" * 60)
            logger.info(f"Found {len(items)} item(s) to process")
            logger.info("")

        # Batch stability check - wait once for all items
        stable_items = self.stability_checker.get_stable_items(items)

        # Calculate skipped items
        skipped_count = len(items) - len(stable_items)
        if skipped_count > 0 and not self.quiet:
            logger.info("")
            logger.info(f"Skipping {skipped_count} item(s) still transferring (will retry on next run)")
            logger.info("")

        if not stable_items:
            if not self.quiet:
                logger.info("No stable items ready to process")
            self.stats["skipped"] = skipped_count
            # Only print summary in quiet mode if there were items found
            if not self.quiet:
                self._print_summary()
            return 0

        # We have stable items - in quiet mode, re-enable INFO logging for processing
        if self.quiet:
            set_quiet_mode(False)  # Show INFO messages during actual processing
            logger.info("=" * 60)
            logger.info("Media File Organizer - Starting")
            logger.info("=" * 60)
            logger.info(f"Found {len(items)} item(s) to process")
            logger.info("")
            if skipped_count > 0:
                logger.info("")
                logger.info(f"Skipping {skipped_count} item(s) still transferring (will retry on next run)")
                logger.info("")

        logger.info(f"Processing {len(stable_items)} stable item(s)...")
        logger.info("")

        # Process each stable item
        for item in stable_items:
            self._process_item(item)

        # Update skipped count
        self.stats["skipped"] = skipped_count

        # Print summary
        self._print_summary()

        # Return appropriate exit code
        return 0 if self.stats["errors"] == 0 else 1

    def _get_items_to_process(self) -> List[Path]:
        """
        Get list of files and folders to process from download directory.

        Returns:
            List of paths to process
        """
        download_dir = Path(config.DOWNLOAD_DIR)

        if not download_dir.exists():
            logger.error(f"Download directory does not exist: {download_dir}")
            return []

        items = []
        for item in download_dir.iterdir():
            items.extend(self._process_item_for_queue(item))
        return items

    def _process_item_for_queue(self, item: Path) -> List[Path]:
        """
        Process an item and return list of items to queue for organization.

        Handles parent directories recursively.

        Args:
            item: Path to process

        Returns:
            List of items to add to processing queue
        """
        results = []

        # Skip hidden files and excluded directories
        if item.name.startswith('.'):
            return results

        if item.name in config.SKIP_DIRS:
            logger.debug(f"Skipping excluded directory: {item.name}")
            return results

        # Handle parent directories recursively - process their children instead
        if item.is_dir() and item.name in config.PARENT_DIRS:
            logger.debug(f"Processing children of parent directory: {item.name}")
            for child in item.iterdir():
                # Recursively process children (handles nested parent dirs)
                results.extend(self._process_item_for_queue(child))
            return results

        # For files, check if they're video files
        if item.is_file():
            if item.suffix.lower() in config.VIDEO_EXTENSIONS:
                results.append(item)
            else:
                logger.debug(f"Skipping non-video file: {item.name}")
        # For directories, check if they contain video files
        elif item.is_dir():
            if self._contains_video_files(item):
                results.append(item)
            else:
                logger.debug(f"Skipping directory without videos: {item.name}")

        return results

    def _contains_video_files(self, directory: Path) -> bool:
        """
        Check if directory contains video files.

        Args:
            directory: Directory to check

        Returns:
            True if directory contains at least one video file
        """
        try:
            for item in directory.rglob("*"):
                if item.is_file() and item.suffix.lower() in config.VIDEO_EXTENSIONS:
                    return True
        except (OSError, PermissionError) as e:
            logger.warning(f"Error checking directory {directory}: {e}")

        return False

    def _process_item(self, item: Path) -> None:
        """
        Process a single file or folder.

        Assumes item has already been verified as stable by batch check.

        Args:
            item: Path to file or folder
        """
        self.stats["processed"] += 1

        logger.info(f"Processing: {item.name}")

        # Store original item info for SFTP deletion
        original_item_name = item.name
        is_directory = item.is_dir()

        try:
            # Parse filename
            parsed = self.parser.parse(item.name)
            logger.info(f"Classified: {parsed}")

            # Classify content and get destination
            classification = self.classifier.classify_content(
                title=parsed.title,
                is_tv_show=parsed.is_tv_show,
                year=parsed.year
            )

            # Log status for TV shows
            if classification["type"] == "tv_show" and classification["status"]:
                status_name = classification["status"].value.upper()
                logger.info(f"Status: {status_name}")

            # Find or create destination folder
            destination_dir = classification["destination"]
            destination_folder = self.matcher.get_or_create_folder(
                title=parsed.title,
                destination_dir=destination_dir
            )

            # Log matched folder
            if destination_folder.exists():
                logger.info(f"Matched existing folder: {destination_folder}")
            else:
                logger.info(f"Will create new folder: {destination_folder}")

            # Move file/folder
            final_path = self.mover.move(item, destination_folder)

            if final_path:
                self.stats["moved"] += 1

                # Delete from SFTP if enabled and move was successful
                # Only attempt deletion if SFTP is properly configured
                if self.sftp_delete and self.sftp_manager and self.sftp_manager.enabled:
                    if self.sftp_manager.delete_remote_item(original_item_name, is_directory=is_directory):
                        self.stats["sftp_deleted"] += 1
                    else:
                        self.stats["sftp_failed"] += 1
                        logger.warning(f"Failed to delete '{original_item_name}' from SFTP server")
            else:
                self.stats["errors"] += 1

        except Exception as e:
            logger.error(f"Error processing {item.name}: {e}", exc_info=True)
            self.stats["errors"] += 1

        logger.info("")  # Blank line for readability

    def _print_summary(self) -> None:
        """Print processing summary."""
        logger.info("=" * 60)
        logger.info("Processing Summary")
        logger.info("=" * 60)
        logger.info(f"Items processed: {self.stats['processed']}")
        logger.info(f"Items moved:     {self.stats['moved']}")
        logger.info(f"Items skipped:   {self.stats['skipped']}")
        logger.info(f"Errors:          {self.stats['errors']}")

        # Include SFTP stats if enabled
        if self.sftp_delete:
            logger.info(f"SFTP deleted:    {self.stats['sftp_deleted']}")
            if self.stats['sftp_failed'] > 0:
                logger.info(f"SFTP failed:     {self.stats['sftp_failed']}")

        logger.info("=" * 60)


def main() -> int:
    """
    Main entry point for CLI.

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Automated media file organizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Process files and move them
  %(prog)s --dry-run          # Preview what would be moved
  %(prog)s --version          # Show version

Configuration:
  Set environment variables or edit config.py to customize paths and settings.
        """
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview operations without actually moving files"
    )

    parser.add_argument(
        "--sftp-delete",
        action="store_true",
        help="Delete files from remote SFTP server after successful move"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Quiet mode - only show output when files are actually moved (recommended for cron jobs)"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0"
    )

    args = parser.parse_args()

    # Use lock file to prevent concurrent runs
    with LockFile():
        organizer = MediaOrganizer(
            dry_run=args.dry_run,
            sftp_delete=args.sftp_delete,
            quiet=args.quiet
        )
        return organizer.run()


if __name__ == "__main__":
    sys.exit(main())
