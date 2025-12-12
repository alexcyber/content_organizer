"""
Unit tests for main MediaOrganizer module.

Tests directory processing logic including parent directory handling.
"""

import shutil
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import config
from main import MediaOrganizer, LockFile


class TestMediaOrganizer:
    """Test cases for MediaOrganizer."""

    @pytest.fixture
    def temp_download_dir(self, tmp_path):
        """Create a temporary download directory with test structure."""
        download_dir = tmp_path / "downloads"
        download_dir.mkdir()

        # Create parent directories
        (download_dir / "TV_Shows").mkdir()
        (download_dir / "Movies").mkdir()
        (download_dir / "Porn").mkdir()
        (download_dir / "@eaDir").mkdir()

        # Create test files in parent directories
        (download_dir / "TV_Shows" / "Show.S01E01.mkv").touch()
        (download_dir / "TV_Shows" / "SubDir").mkdir()
        (download_dir / "TV_Shows" / "SubDir" / "Nested.Movie.mkv").touch()
        (download_dir / "Movies" / "Movie.2024.mkv").touch()

        # Create files in skip directories (should be skipped)
        (download_dir / "Porn" / "ShouldBeSkipped.mkv").touch()
        (download_dir / "@eaDir" / "Thumbnail.jpg").touch()

        # Create regular files
        (download_dir / "Regular.Release.S01E01.mkv").touch()
        (download_dir / "RegularDir").mkdir()
        (download_dir / "RegularDir" / "episode.mkv").touch()

        return download_dir

    def test_parent_directory_children_processed(self, temp_download_dir):
        """Test that children of TV_Shows and Movies are processed."""
        with patch.object(config, 'DOWNLOAD_DIR', str(temp_download_dir)):
            organizer = MediaOrganizer(dry_run=True)
            items = organizer._get_items_to_process()

            # Convert to relative paths for easier assertion
            rel_paths = [str(item.relative_to(temp_download_dir)) for item in items]

            # Should include children of TV_Shows
            assert "TV_Shows/Show.S01E01.mkv" in rel_paths
            assert "TV_Shows/SubDir" in rel_paths

            # Should include children of Movies
            assert "Movies/Movie.2024.mkv" in rel_paths

            # Should include regular items
            assert "Regular.Release.S01E01.mkv" in rel_paths
            assert "RegularDir" in rel_paths

    def test_skip_dirs_completely_skipped(self, temp_download_dir):
        """Test that SKIP_DIRS are completely ignored."""
        with patch.object(config, 'DOWNLOAD_DIR', str(temp_download_dir)):
            organizer = MediaOrganizer(dry_run=True)
            items = organizer._get_items_to_process()

            # Convert to relative paths
            rel_paths = [str(item.relative_to(temp_download_dir)) for item in items]

            # Should NOT include anything from Porn or @eaDir
            assert not any("Porn" in path for path in rel_paths)
            assert not any("@eaDir" in path for path in rel_paths)

    def test_parent_dirs_not_processed_as_items(self, temp_download_dir):
        """Test that TV_Shows and Movies directories themselves are not processed."""
        with patch.object(config, 'DOWNLOAD_DIR', str(temp_download_dir)):
            organizer = MediaOrganizer(dry_run=True)
            items = organizer._get_items_to_process()

            # Convert to names only
            names = [item.name for item in items]

            # Should NOT include the parent directories themselves
            assert "TV_Shows" not in names
            assert "Movies" not in names

    def test_nested_parent_directory_structure(self, temp_download_dir):
        """Test handling of nested parent directory like TV_Shows/TV_Shows."""
        # Create nested structure: TV_Shows/TV_Shows/Warfare.2025.mkv
        (temp_download_dir / "TV_Shows" / "TV_Shows").mkdir()
        (temp_download_dir / "TV_Shows" / "TV_Shows" / "Warfare.2025.mkv").touch()

        with patch.object(config, 'DOWNLOAD_DIR', str(temp_download_dir)):
            organizer = MediaOrganizer(dry_run=True)
            items = organizer._get_items_to_process()

            # Convert to relative paths
            rel_paths = [str(item.relative_to(temp_download_dir)) for item in items]

            # Should recursively process through both parent dirs and find the video file
            assert "TV_Shows/TV_Shows/Warfare.2025.mkv" in rel_paths

            # Should NOT process either parent directory as a media item
            assert "TV_Shows" not in rel_paths
            assert "TV_Shows/TV_Shows" not in rel_paths

    def test_hidden_files_skipped(self, temp_download_dir):
        """Test that hidden files and directories are skipped."""
        (temp_download_dir / ".hidden_file.mkv").touch()
        (temp_download_dir / ".hidden_dir").mkdir()
        (temp_download_dir / ".hidden_dir" / "video.mkv").touch()

        with patch.object(config, 'DOWNLOAD_DIR', str(temp_download_dir)):
            organizer = MediaOrganizer(dry_run=True)
            items = organizer._get_items_to_process()

            # Convert to names
            names = [item.name for item in items]

            # Should NOT include hidden items
            assert ".hidden_file.mkv" not in names
            assert ".hidden_dir" not in names

    def test_non_video_files_skipped(self, temp_download_dir):
        """Test that non-video files are skipped."""
        (temp_download_dir / "readme.txt").touch()
        (temp_download_dir / "poster.jpg").touch()

        with patch.object(config, 'DOWNLOAD_DIR', str(temp_download_dir)):
            organizer = MediaOrganizer(dry_run=True)
            items = organizer._get_items_to_process()

            # Convert to names
            names = [item.name for item in items]

            # Should NOT include non-video files
            assert "readme.txt" not in names
            assert "poster.jpg" not in names

    def test_quiet_mode_initialization(self):
        """Test that quiet mode is properly initialized."""
        organizer_quiet = MediaOrganizer(dry_run=True, quiet=True)
        organizer_normal = MediaOrganizer(dry_run=True, quiet=False)

        assert organizer_quiet.quiet is True
        assert organizer_quiet.mover.quiet is True

        assert organizer_normal.quiet is False
        assert organizer_normal.mover.quiet is False

    def test_quiet_mode_no_summary_when_no_moves(self, temp_download_dir, caplog):
        """Test that quiet mode doesn't print summary when no files are moved."""
        # Create a temporary download directory with no files
        empty_dir = temp_download_dir / "empty"
        empty_dir.mkdir()

        with patch.object(config, 'DOWNLOAD_DIR', str(empty_dir)):
            organizer = MediaOrganizer(dry_run=True, quiet=True)
            organizer.run()

            # Check that summary was not printed in quiet mode
            assert "Processing Summary" not in caplog.text


class TestLockFile:
    """Test cases for LockFile."""

    def test_lock_acquired_and_released(self, tmp_path):
        """Test that lock is properly acquired and released."""
        lock_path = tmp_path / "test.lock"

        with LockFile(lock_path=str(lock_path)):
            # Lock file should exist and be locked
            assert lock_path.exists()

        # Lock file should be cleaned up after exit
        # Note: File might still exist but should be unlocked
        # The important thing is that another process can acquire it

    def test_concurrent_lock_waiting(self, tmp_path):
        """Test that second instance waits for first to complete."""
        lock_path = tmp_path / "test.lock"
        results = []

        def hold_lock_briefly():
            """Hold lock for 2 seconds."""
            with LockFile(lock_path=str(lock_path), timeout=10):
                results.append("first_acquired")
                time.sleep(2)
                results.append("first_releasing")

        def wait_for_lock():
            """Wait for lock and acquire it."""
            time.sleep(0.5)  # Ensure first thread acquires first
            with LockFile(lock_path=str(lock_path), timeout=10):
                results.append("second_acquired")

        # Start first thread
        t1 = threading.Thread(target=hold_lock_briefly)
        t1.start()

        # Start second thread (should wait)
        t2 = threading.Thread(target=wait_for_lock)
        t2.start()

        # Wait for both to complete
        t1.join()
        t2.join()

        # Verify order
        assert results == ["first_acquired", "first_releasing", "second_acquired"]

    def test_lock_timeout(self, tmp_path):
        """Test that lock times out if held too long."""
        lock_path = tmp_path / "test.lock"

        def hold_lock_forever():
            """Hold lock indefinitely."""
            with LockFile(lock_path=str(lock_path), timeout=30):
                time.sleep(10)

        # Start thread holding lock
        t1 = threading.Thread(target=hold_lock_forever)
        t1.start()

        # Wait a bit for lock to be acquired
        time.sleep(0.5)

        # Try to acquire with short timeout (should fail)
        with pytest.raises(SystemExit):
            with LockFile(lock_path=str(lock_path), timeout=2):
                pass

        # Clean up
        t1.join()
