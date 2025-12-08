"""
Fuzzy folder matcher for finding existing destination directories.

Uses string similarity to match media titles against existing folder names.
"""

from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz, process

import config
from parsers.filename_parser import FilenameParser
from utils.logger import get_logger

logger = get_logger()


class FolderMatcher:
    """Fuzzy matcher for finding existing media folders."""

    def __init__(self, threshold: int = config.FUZZY_MATCH_THRESHOLD):
        """
        Initialize folder matcher.

        Args:
            threshold: Minimum similarity score (0-100) for a match
        """
        self.threshold = threshold

    def find_matching_folder(
        self,
        title: str,
        destination_dir: str
    ) -> Optional[Path]:
        """
        Find existing folder that matches the given title.

        Args:
            title: Media title to match
            destination_dir: Directory to search for existing folders

        Returns:
            Path to matching folder or None if no match found
        """
        dest_path = Path(destination_dir)

        if not dest_path.exists():
            logger.warning(f"Destination directory does not exist: {destination_dir}")
            return None

        # Get all existing folders in destination
        existing_folders = [
            f for f in dest_path.iterdir()
            if f.is_dir() and not f.name.startswith('.')
        ]

        if not existing_folders:
            logger.debug(f"No existing folders in {destination_dir}")
            return None

        # Normalize title for matching
        normalized_title = FilenameParser.normalize_title(title)

        # Prepare folder names for matching
        folder_names = [f.name for f in existing_folders]
        normalized_folder_names = [
            FilenameParser.normalize_title(name) for name in folder_names
        ]

        # Find best match using fuzzy matching
        match_result = process.extractOne(
            normalized_title,
            normalized_folder_names,
            scorer=fuzz.ratio
        )

        if match_result is None:
            logger.debug(f"No fuzzy match found for '{title}'")
            return None

        matched_name, score, index = match_result

        if score >= self.threshold:
            matched_folder = existing_folders[index]
            logger.info(
                f"Fuzzy match: '{title}' -> '{matched_folder.name}' "
                f"(score: {score})"
            )
            return matched_folder
        else:
            logger.debug(
                f"Best match for '{title}' was '{folder_names[index]}' "
                f"with score {score} (below threshold {self.threshold})"
            )
            return None

    def get_or_create_folder(
        self,
        title: str,
        destination_dir: str
    ) -> Path:
        """
        Find existing folder or determine path for new folder.

        Args:
            title: Media title
            destination_dir: Destination directory

        Returns:
            Path to existing folder or path where new folder should be created
        """
        # Try to find existing folder
        existing = self.find_matching_folder(title, destination_dir)

        if existing:
            return existing

        # Determine path for new folder with cleaned title
        dest_path = Path(destination_dir)
        new_folder = dest_path / self._sanitize_folder_name(title)

        return new_folder

    @staticmethod
    def _sanitize_folder_name(name: str) -> str:
        """
        Sanitize folder name by removing invalid characters.

        Args:
            name: Folder name to sanitize

        Returns:
            Sanitized folder name
        """
        # Remove/replace invalid characters for filesystem
        invalid_chars = '<>:"/\\|?*'
        sanitized = name
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '')

        # Clean up multiple spaces and trim
        sanitized = ' '.join(sanitized.split())
        sanitized = sanitized.strip('. ')  # Remove leading/trailing dots and spaces

        return sanitized
