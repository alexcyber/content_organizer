"""
Unit tests for folder matcher.

Tests fuzzy matching logic and folder operations.
"""

import tempfile
from pathlib import Path

import pytest

from matchers.folder_matcher import FolderMatcher


class TestFolderMatcher:
    """Test cases for FolderMatcher."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def matcher(self):
        """Create FolderMatcher instance."""
        return FolderMatcher(threshold=80)

    def test_exact_match(self, temp_dir, matcher):
        """Test exact folder name match."""
        # Create existing folder
        existing = temp_dir / "The Pitt"
        existing.mkdir()

        # Try to match
        result = matcher.find_matching_folder("The Pitt", str(temp_dir))

        assert result is not None
        assert result.name == "The Pitt"

    def test_fuzzy_match_case_insensitive(self, temp_dir, matcher):
        """Test fuzzy matching with different case."""
        existing = temp_dir / "The Pitt"
        existing.mkdir()

        result = matcher.find_matching_folder("the pitt", str(temp_dir))

        assert result is not None
        assert result.name == "The Pitt"

    def test_fuzzy_match_with_year(self, temp_dir, matcher):
        """Test fuzzy matching with year in folder name."""
        existing = temp_dir / "Breaking Bad (2008)"
        existing.mkdir()

        result = matcher.find_matching_folder("Breaking Bad", str(temp_dir))

        assert result is not None
        assert result.name == "Breaking Bad (2008)"

    def test_fuzzy_match_special_characters(self, temp_dir, matcher):
        """Test fuzzy matching with special characters."""
        existing = temp_dir / "The Walking Dead"
        existing.mkdir()

        result = matcher.find_matching_folder("The.Walking.Dead", str(temp_dir))

        assert result is not None
        assert result.name == "The Walking Dead"

    def test_no_match_below_threshold(self, temp_dir, matcher):
        """Test that low-similarity matches are rejected."""
        existing = temp_dir / "Breaking Bad"
        existing.mkdir()

        result = matcher.find_matching_folder("The Wire", str(temp_dir))

        assert result is None

    def test_multiple_folders_best_match(self, temp_dir, matcher):
        """Test selecting best match among multiple folders."""
        (temp_dir / "The Office").mkdir()
        (temp_dir / "The Office US").mkdir()
        (temp_dir / "The Office UK").mkdir()

        result = matcher.find_matching_folder("The Office", str(temp_dir))

        assert result is not None
        assert result.name == "The Office"  # Exact match should win

    def test_get_or_create_existing(self, temp_dir, matcher):
        """Test get_or_create with existing folder."""
        existing = temp_dir / "Game of Thrones"
        existing.mkdir()

        result = matcher.get_or_create_folder("Game of Thrones", str(temp_dir))

        assert result == existing
        assert result.exists()

    def test_get_or_create_new(self, temp_dir, matcher):
        """Test get_or_create with new folder."""
        result = matcher.get_or_create_folder("New Show", str(temp_dir))

        expected = temp_dir / "New Show"
        assert result == expected
        # Note: get_or_create doesn't actually create the folder, just returns the path

    def test_sanitize_folder_name(self):
        """Test folder name sanitization."""
        test_cases = [
            ("Normal Show", "Normal Show"),
            ("Show: The Series", "Show The Series"),
            ("Show/Spin-off", "ShowSpin-off"),
            ('Show "Quote"', 'Show Quote'),
            ("Show*Name?", "ShowName"),
            ("Show  Multiple   Spaces", "Show Multiple Spaces"),
            ("  Leading and Trailing  ", "Leading and Trailing"),
        ]

        for input_name, expected in test_cases:
            result = FolderMatcher._sanitize_folder_name(input_name)
            assert result == expected

    def test_hidden_folders_ignored(self, temp_dir, matcher):
        """Test that hidden folders are ignored."""
        visible = temp_dir / "The Pitt"
        visible.mkdir()

        hidden = temp_dir / ".hidden"
        hidden.mkdir()

        result = matcher.find_matching_folder("The Pitt", str(temp_dir))

        assert result is not None
        assert result.name == "The Pitt"

    def test_nonexistent_directory(self, matcher):
        """Test handling of non-existent destination directory."""
        result = matcher.find_matching_folder("Show", "/nonexistent/path")

        assert result is None

    def test_empty_directory(self, temp_dir, matcher):
        """Test matching in empty directory."""
        result = matcher.find_matching_folder("Show", str(temp_dir))

        assert result is None
