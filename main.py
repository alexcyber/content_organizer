#!/usr/bin/env python3
"""
Media File Organizer - Main Entry Point

Automated media file organizer that monitors download directory and routes
files to appropriate destinations based on content type.
"""

import argparse
import sys
from pathlib import Path
from typing import List

import config
from matchers.folder_matcher import FolderMatcher
from operations.file_mover import FileMover
from parsers.content_classifier import ContentClassifier
from parsers.filename_parser import FilenameParser
from utils.logger import setup_logger

logger = setup_logger()


class LockFile:
    """Simple file-based lock to prevent concurrent runs."""

    def __init__(self, lock_path: str = config.LOCK_FILE):
        """Initialize lock file."""
        self.lock_path = Path(lock_path)
        self.locked = False

    def __enter__(self):
        """Acquire lock."""
        if self.lock_path.exists():
            logger.error(f"Lock file exists: {self.lock_path}")
            logger.error("Another instance may be running. Exiting.")
            sys.exit(1)

        try:
            self.lock_path.touch()
            self.locked = True
            logger.debug(f"Lock acquired: {self.lock_path}")
        except OSError as e:
            logger.error(f"Failed to create lock file: {e}")
            sys.exit(1)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock."""
        if self.locked and self.lock_path.exists():
            try:
                self.lock_path.unlink()
                logger.debug(f"Lock released: {self.lock_path}")
            except OSError as e:
                logger.warning(f"Failed to remove lock file: {e}")


class MediaOrganizer:
    """Main orchestrator for media file organization."""

    def __init__(self, dry_run: bool = False):
        """
        Initialize media organizer.

        Args:
            dry_run: If True, only simulate operations
        """
        self.dry_run = dry_run
        self.parser = FilenameParser()
        self.classifier = ContentClassifier()
        self.matcher = FolderMatcher()
        self.mover = FileMover(dry_run=dry_run)

        self.stats = {
            "processed": 0,
            "moved": 0,
            "skipped": 0,
            "errors": 0
        }

    def run(self) -> int:
        """
        Run the media organizer.

        Returns:
            Exit code (0 for success, 1 for errors)
        """
        logger.info("=" * 60)
        logger.info("Media File Organizer - Starting")
        logger.info("=" * 60)

        # Validate configuration
        issues = config.validate_config()
        for issue in issues:
            logger.warning(issue)

        # Get items to process
        items = self._get_items_to_process()

        if not items:
            logger.info("No items to process")
            return 0

        logger.info(f"Found {len(items)} items to process")

        # Process each item
        for item in items:
            self._process_item(item)

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
            # Skip hidden files and excluded directories
            if item.name.startswith('.'):
                continue

            if item.name in config.SKIP_DIRS:
                logger.debug(f"Skipping excluded directory: {item.name}")
                continue

            # For files, check if they're video files
            if item.is_file():
                if item.suffix.lower() in config.VIDEO_EXTENSIONS:
                    items.append(item)
                else:
                    logger.debug(f"Skipping non-video file: {item.name}")
            # For directories, check if they contain video files
            elif item.is_dir():
                if self._contains_video_files(item):
                    items.append(item)
                else:
                    logger.debug(f"Skipping directory without videos: {item.name}")

        return items

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

        Args:
            item: Path to file or folder
        """
        self.stats["processed"] += 1

        logger.info(f"Processing: {item.name}")

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
        "--version",
        action="version",
        version="%(prog)s 1.0.0"
    )

    args = parser.parse_args()

    # Use lock file to prevent concurrent runs
    with LockFile():
        organizer = MediaOrganizer(dry_run=args.dry_run)
        return organizer.run()


if __name__ == "__main__":
    sys.exit(main())
