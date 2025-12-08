"""
Unit tests for file stability checker.

Tests verification of complete file transfers.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from utils.file_stability import FileStabilityChecker


class TestFileStabilityChecker:
    """Test cases for FileStabilityChecker."""

    def test_single_file_stable(self, tmp_path):
        """Test stable single file passes check."""
        # Create test file
        test_file = tmp_path / "video.mkv"
        test_file.write_bytes(b"x" * 1000)

        # Check stability (with minimal interval for testing)
        checker = FileStabilityChecker(check_interval=0.1, retries=2)
        result = checker.is_transfer_complete(test_file)

        assert result is True

    def test_single_file_growing(self, tmp_path):
        """Test growing file fails stability check."""
        # Create test file
        test_file = tmp_path / "video.mkv"
        test_file.write_bytes(b"x" * 1000)

        # Mock _get_file_sizes to simulate growing file
        checker = FileStabilityChecker(check_interval=0.1, retries=2)

        call_count = [0]

        def mock_get_file_sizes(files):
            call_count[0] += 1
            # First call returns initial size, subsequent calls return larger size
            size = 1000 + (call_count[0] - 1) * 100
            return {test_file: size}

        with patch.object(checker, '_get_file_sizes', side_effect=mock_get_file_sizes):
            result = checker.is_transfer_complete(test_file)

        assert result is False

    def test_directory_all_stable(self, tmp_path):
        """Test directory with all stable files passes."""
        # Create directory structure
        test_dir = tmp_path / "release"
        test_dir.mkdir()
        (test_dir / "video.mkv").write_bytes(b"x" * 1000)
        (test_dir / "sample.mkv").write_bytes(b"y" * 500)
        subdir = test_dir / "subs"
        subdir.mkdir()
        (subdir / "subtitle.srt").write_bytes(b"z" * 100)

        # Check stability
        checker = FileStabilityChecker(check_interval=0.1, retries=2)
        result = checker.is_transfer_complete(test_dir)

        assert result is True

    def test_directory_file_growing(self, tmp_path):
        """Test directory with growing file fails check."""
        # Create directory structure
        test_dir = tmp_path / "release"
        test_dir.mkdir()
        stable_file = test_dir / "video.mkv"
        stable_file.write_bytes(b"x" * 1000)
        growing_file = test_dir / "sample.mkv"
        growing_file.write_bytes(b"y" * 500)

        # Mock _get_file_sizes to simulate one growing file
        checker = FileStabilityChecker(check_interval=0.1, retries=2)

        call_count = [0]

        def mock_get_file_sizes(files):
            call_count[0] += 1
            # stable_file stays same, growing_file increases
            return {
                stable_file: 1000,
                growing_file: 500 + (call_count[0] - 1) * 100
            }

        with patch.object(checker, '_get_file_sizes', side_effect=mock_get_file_sizes):
            result = checker.is_transfer_complete(test_dir)

        assert result is False

    def test_empty_directory(self, tmp_path):
        """Test empty directory passes stability check."""
        test_dir = tmp_path / "empty"
        test_dir.mkdir()

        checker = FileStabilityChecker(check_interval=0.1, retries=2)
        result = checker.is_transfer_complete(test_dir)

        assert result is True

    def test_nonexistent_path(self, tmp_path):
        """Test nonexistent path fails check."""
        nonexistent = tmp_path / "does_not_exist.mkv"

        checker = FileStabilityChecker(check_interval=0.1, retries=2)
        result = checker.is_transfer_complete(nonexistent)

        assert result is False

    def test_file_disappears_during_check(self, tmp_path):
        """Test file that disappears during check fails."""
        test_file = tmp_path / "video.mkv"
        test_file.write_bytes(b"x" * 1000)

        # Track calls
        call_count = [0]

        def mock_exists(self):
            call_count[0] += 1
            if call_count[0] <= 2:
                return True
            else:
                # File disappears on later checks
                return False

        with patch.object(Path, 'exists', mock_exists):
            checker = FileStabilityChecker(check_interval=0.1, retries=3)
            result = checker.is_transfer_complete(test_file)

        assert result is False

    def test_nested_directory_structure(self, tmp_path):
        """Test deeply nested directory with all stable files."""
        # Create nested structure
        base = tmp_path / "Season01"
        base.mkdir()
        ep1 = base / "Episode01"
        ep1.mkdir()
        ep2 = base / "Episode02"
        ep2.mkdir()

        (ep1 / "video.mkv").write_bytes(b"a" * 1000)
        (ep1 / "sample.mkv").write_bytes(b"b" * 500)
        (ep2 / "video.mkv").write_bytes(b"c" * 1000)
        (ep2 / "sample.mkv").write_bytes(b"d" * 500)

        checker = FileStabilityChecker(check_interval=0.1, retries=2)
        result = checker.is_transfer_complete(base)

        assert result is True

    def test_configurable_retries(self, tmp_path):
        """Test configurable number of retries."""
        test_file = tmp_path / "video.mkv"
        test_file.write_bytes(b"x" * 1000)

        # With 1 retry, should pass quickly
        checker = FileStabilityChecker(check_interval=0.1, retries=1)
        start_time = time.time()
        result = checker.is_transfer_complete(test_file)
        elapsed = time.time() - start_time

        assert result is True
        # Should be very quick (no waiting needed with 1 retry)
        assert elapsed < 0.5

    def test_configurable_interval(self, tmp_path):
        """Test configurable check interval."""
        test_file = tmp_path / "video.mkv"
        test_file.write_bytes(b"x" * 1000)

        # With longer interval and 2 retries, should wait
        checker = FileStabilityChecker(check_interval=0.5, retries=2)
        start_time = time.time()
        result = checker.is_transfer_complete(test_file)
        elapsed = time.time() - start_time

        assert result is True
        # Should wait at least for the interval
        assert elapsed >= 0.5

    def test_get_all_files(self, tmp_path):
        """Test getting all files from directory."""
        # Create structure
        base = tmp_path / "test"
        base.mkdir()
        (base / "file1.mkv").write_bytes(b"a")
        (base / "file2.txt").write_bytes(b"b")
        subdir = base / "sub"
        subdir.mkdir()
        (subdir / "file3.mkv").write_bytes(b"c")

        checker = FileStabilityChecker()
        files = checker._get_all_files(base)

        # Should find all 3 files
        assert len(files) == 3
        file_names = {f.name for f in files}
        assert file_names == {"file1.mkv", "file2.txt", "file3.mkv"}

    def test_get_file_sizes(self, tmp_path):
        """Test getting file sizes."""
        file1 = tmp_path / "file1.mkv"
        file2 = tmp_path / "file2.mkv"
        file1.write_bytes(b"x" * 100)
        file2.write_bytes(b"y" * 200)

        checker = FileStabilityChecker()
        sizes = checker._get_file_sizes([file1, file2])

        assert sizes is not None
        assert sizes[file1] == 100
        assert sizes[file2] == 200

    def test_get_file_sizes_missing_file(self, tmp_path):
        """Test getting sizes when file is missing."""
        file1 = tmp_path / "exists.mkv"
        file2 = tmp_path / "missing.mkv"
        file1.write_bytes(b"x" * 100)

        checker = FileStabilityChecker()
        sizes = checker._get_file_sizes([file1, file2])

        # Should return None when a file is missing
        assert sizes is None

    def test_batch_check_all_stable(self, tmp_path):
        """Test batch checking with all stable items."""
        # Create multiple stable files
        file1 = tmp_path / "video1.mkv"
        file2 = tmp_path / "video2.mkv"
        file1.write_bytes(b"x" * 1000)
        file2.write_bytes(b"y" * 2000)

        checker = FileStabilityChecker(check_interval=0.1, retries=2)
        stable = checker.get_stable_items([file1, file2])

        # All should be stable
        assert len(stable) == 2
        assert file1 in stable
        assert file2 in stable

    def test_batch_check_mixed_stability(self, tmp_path):
        """Test batch checking with mix of stable and unstable items."""
        # Create files
        stable_file = tmp_path / "stable.mkv"
        growing_file = tmp_path / "growing.mkv"
        stable_file.write_bytes(b"x" * 1000)
        growing_file.write_bytes(b"y" * 500)

        checker = FileStabilityChecker(check_interval=0.1, retries=2)

        # Mock to make growing_file unstable
        call_count = [0]

        def mock_get_file_sizes(files):
            call_count[0] += 1
            return {
                stable_file: 1000,
                growing_file: 500 + (call_count[0] - 1) * 100
            }

        with patch.object(checker, '_get_file_sizes', side_effect=mock_get_file_sizes):
            stable = checker.get_stable_items([stable_file, growing_file])

        # Only stable_file should be returned
        assert len(stable) == 1
        assert stable_file in stable
        assert growing_file not in stable

    def test_batch_check_all_unstable(self, tmp_path):
        """Test batch checking with all unstable items."""
        # Create files
        file1 = tmp_path / "growing1.mkv"
        file2 = tmp_path / "growing2.mkv"
        file1.write_bytes(b"x" * 1000)
        file2.write_bytes(b"y" * 2000)

        checker = FileStabilityChecker(check_interval=0.1, retries=2)

        # Mock to make both files unstable
        call_count = [0]

        def mock_get_file_sizes(files):
            call_count[0] += 1
            return {
                file1: 1000 + (call_count[0] - 1) * 100,
                file2: 2000 + (call_count[0] - 1) * 200
            }

        with patch.object(checker, '_get_file_sizes', side_effect=mock_get_file_sizes):
            stable = checker.get_stable_items([file1, file2])

        # Nothing should be stable
        assert len(stable) == 0

    def test_batch_check_with_directories(self, tmp_path):
        """Test batch checking with mix of files and directories."""
        # Create file
        file1 = tmp_path / "video.mkv"
        file1.write_bytes(b"x" * 1000)

        # Create directory with files
        dir1 = tmp_path / "release"
        dir1.mkdir()
        (dir1 / "video.mkv").write_bytes(b"y" * 2000)
        (dir1 / "sample.mkv").write_bytes(b"z" * 500)

        checker = FileStabilityChecker(check_interval=0.1, retries=2)
        stable = checker.get_stable_items([file1, dir1])

        # Both should be stable
        assert len(stable) == 2
        assert file1 in stable
        assert dir1 in stable

    def test_batch_check_directory_with_unstable_file(self, tmp_path):
        """Test batch checking where directory has unstable file."""
        # Create stable file
        file1 = tmp_path / "stable.mkv"
        file1.write_bytes(b"x" * 1000)

        # Create directory with stable and unstable files
        dir1 = tmp_path / "release"
        dir1.mkdir()
        stable_in_dir = dir1 / "video.mkv"
        growing_in_dir = dir1 / "sample.mkv"
        stable_in_dir.write_bytes(b"y" * 2000)
        growing_in_dir.write_bytes(b"z" * 500)

        checker = FileStabilityChecker(check_interval=0.1, retries=2)

        # Mock to make one file in directory unstable
        call_count = [0]

        def mock_get_file_sizes(files):
            call_count[0] += 1
            return {
                file1: 1000,
                stable_in_dir: 2000,
                growing_in_dir: 500 + (call_count[0] - 1) * 100
            }

        with patch.object(checker, '_get_file_sizes', side_effect=mock_get_file_sizes):
            stable = checker.get_stable_items([file1, dir1])

        # Only file1 should be stable, not the directory
        assert len(stable) == 1
        assert file1 in stable
        assert dir1 not in stable

    def test_batch_check_empty_list(self, tmp_path):
        """Test batch checking with empty list."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2)
        stable = checker.get_stable_items([])

        assert len(stable) == 0

    def test_batch_check_nonexistent_items(self, tmp_path):
        """Test batch checking with nonexistent items."""
        nonexistent = tmp_path / "does_not_exist.mkv"

        checker = FileStabilityChecker(check_interval=0.1, retries=2)
        stable = checker.get_stable_items([nonexistent])

        # Nonexistent items should not be returned
        assert len(stable) == 0
