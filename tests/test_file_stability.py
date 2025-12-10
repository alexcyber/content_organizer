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


class TestSyncthingIntegration:
    """Test cases for Syncthing temporary file detection."""

    def test_syncthing_enabled_by_default(self):
        """Test that Syncthing detection is enabled by default."""
        checker = FileStabilityChecker()
        assert checker.syncthing_enabled is True

    def test_syncthing_can_be_disabled(self):
        """Test that Syncthing detection can be disabled."""
        checker = FileStabilityChecker(syncthing_enabled=False)
        assert checker.syncthing_enabled is False

    def test_single_file_syncthing_tmp_pattern(self, tmp_path):
        """Test detection of .syncthing.<filename>.tmp for a single file."""
        checker = FileStabilityChecker(syncthing_enabled=True)

        # Simulate: The.Pitt.S01E10.1080p.WEB.h264-ETHEL.mkv being synced
        test_file = tmp_path / "The.Pitt.S01E10.1080p.WEB.h264-ETHEL.mkv"
        test_file.write_bytes(b"partial content")

        # Syncthing creates temp file
        syncthing_tmp = tmp_path / ".syncthing.The.Pitt.S01E10.1080p.WEB.h264-ETHEL.mkv.tmp"
        syncthing_tmp.write_bytes(b"temp content")

        # Should detect Syncthing temp file
        assert checker._has_syncthing_tmp_files(test_file) is True
        assert checker.is_transfer_complete(test_file) is False

    def test_single_file_no_tmp(self, tmp_path):
        """Test that completed single file has no temp files."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2, syncthing_enabled=True)

        # Simulate: The.Pitt.S01E10.1080p.WEB.h264-ETHEL.mkv fully synced
        test_file = tmp_path / "The.Pitt.S01E10.1080p.WEB.h264-ETHEL.mkv"
        test_file.write_bytes(b"complete content")

        # No temp files
        assert checker._has_syncthing_tmp_files(test_file) is False
        assert checker.is_transfer_complete(test_file) is True

    def test_folder_with_single_file_syncing(self, tmp_path):
        """Test folder structure where main file is still syncing."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2, syncthing_enabled=True)

        # Simulate: Breaking.Bad.S05E16.Felina.1080p.BluRay.x264-ROVERS/
        folder = tmp_path / "Breaking.Bad.S05E16.Felina.1080p.BluRay.x264-ROVERS"
        folder.mkdir()

        # Main video file still syncing
        mkv_file = folder / "breaking.bad.s05e16.1080p.bluray.x264-rovers.mkv"
        mkv_file.write_bytes(b"partial video")
        (folder / ".syncthing.breaking.bad.s05e16.1080p.bluray.x264-rovers.mkv.tmp").write_bytes(b"temp")

        # NFO file already complete
        (folder / "breaking.bad.s05e16.1080p.bluray.x264-rovers.nfo").write_bytes(b"nfo content")

        # Folder should be detected as unstable
        assert checker._has_syncthing_tmp_files(folder) is True
        assert checker.is_transfer_complete(folder) is False

    def test_folder_all_files_complete(self, tmp_path):
        """Test folder where all files have completed syncing."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2, syncthing_enabled=True)

        # Simulate: Breaking.Bad.S05E16.Felina.1080p.BluRay.x264-ROVERS/ fully synced
        folder = tmp_path / "Breaking.Bad.S05E16.Felina.1080p.BluRay.x264-ROVERS"
        folder.mkdir()

        # All files complete, no temp files
        (folder / "breaking.bad.s05e16.1080p.bluray.x264-rovers.mkv").write_bytes(b"complete video")
        (folder / "breaking.bad.s05e16.1080p.bluray.x264-rovers.nfo").write_bytes(b"nfo content")

        # Folder should be stable
        assert checker._has_syncthing_tmp_files(folder) is False
        assert checker.is_transfer_complete(folder) is True

    def test_nested_folder_with_sample_directory(self, tmp_path):
        """Test nested folder structure with Sample subdirectory."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2, syncthing_enabled=True)

        # Simulate: Spartacus.House.of.Ashur.S01E01.1080p.WEB.H264-SYLiX/
        top_folder = tmp_path / "Spartacus.House.of.Ashur.S01E01.1080p.WEB.H264-SYLiX"
        sample_folder = top_folder / "Sample"
        sample_folder.mkdir(parents=True)

        # Main files complete
        (top_folder / "spartacus.house.of.ashur.s01e01.1080p.web.h264-sylix.mkv").write_bytes(b"main video")
        (top_folder / "spartacus.house.of.ashur.s01e01.1080p.web.h264-sylix.nfo").write_bytes(b"nfo")

        # Sample file still syncing
        sample_file = sample_folder / "spartacus.house.of.ashur.s01e01.1080p.web.h264-sylix-sample.mkv"
        sample_file.write_bytes(b"partial sample")
        (sample_folder / ".syncthing.spartacus.house.of.ashur.s01e01.1080p.web.h264-sylix-sample.mkv.tmp").write_bytes(b"temp")

        # Top folder should be detected as unstable due to nested temp file
        assert checker._has_syncthing_tmp_files(top_folder) is True
        assert checker.is_transfer_complete(top_folder) is False

    def test_complex_nested_folder_all_complete(self, tmp_path):
        """Test complex nested folder structure where all files are complete."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2, syncthing_enabled=True)

        # Simulate: Spartacus.House.of.Ashur.S01E01.1080p.WEB.H264-SYLiX/ fully synced
        top_folder = tmp_path / "Spartacus.House.of.Ashur.S01E01.1080p.WEB.H264-SYLiX"
        sample_folder = top_folder / "Sample"
        sample_folder.mkdir(parents=True)

        # All files complete
        (top_folder / "spartacus.house.of.ashur.s01e01.1080p.web.h264-sylix.mkv").write_bytes(b"main video")
        (top_folder / "spartacus.house.of.ashur.s01e01.1080p.web.h264-sylix.nfo").write_bytes(b"nfo")
        (top_folder / "spartacus.house.of.ashur.s01e01.1080p.web.h264-sylix.srr").write_bytes(b"srr")
        (sample_folder / "spartacus.house.of.ashur.s01e01.1080p.web.h264-sylix-sample.mkv").write_bytes(b"sample video")

        # No temp files - should be stable
        assert checker._has_syncthing_tmp_files(top_folder) is False
        assert checker.is_transfer_complete(top_folder) is True

    def test_movie_folder_with_multiple_files(self, tmp_path):
        """Test movie folder containing movie file and subtitles."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2, syncthing_enabled=True)

        # Simulate: 12.Angry.Men.1957.720p.BRrip.x264.YIFY/
        folder = tmp_path / "12.Angry.Men.1957.720p.BRrip.x264.YIFY"
        folder.mkdir()

        # Movie file syncing
        (folder / "12.Angry.Men.1957.720p.BRrip.x264.YIFY.mp4").write_bytes(b"partial movie")
        (folder / ".syncthing.12.Angry.Men.1957.720p.BRrip.x264.YIFY.mp4.tmp").write_bytes(b"temp")

        # Subtitle already complete
        (folder / "12.Angry.Men.1957.720p.BRrip.x264.YIFY.srt").write_bytes(b"subtitles")

        # Should be unstable
        assert checker._has_syncthing_tmp_files(folder) is True

    def test_batch_mixed_single_files_and_folders(self, tmp_path):
        """Test batch processing of mix of single files and folders."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2, syncthing_enabled=True)

        # Single file - complete
        single_file1 = tmp_path / "The.Pitt.S01E10.1080p.WEB.h264-ETHEL.mkv"
        single_file1.write_bytes(b"complete")

        # Single file - still syncing
        single_file2 = tmp_path / "Severance.S02E03.1080p.WEB.H264-CAKES.mkv"
        single_file2.write_bytes(b"partial")
        (tmp_path / ".syncthing.Severance.S02E03.1080p.WEB.H264-CAKES.mkv.tmp").write_bytes(b"temp")

        # Folder - complete
        folder1 = tmp_path / "Breaking.Bad.Complete"
        folder1.mkdir()
        (folder1 / "episode.mkv").write_bytes(b"complete")
        (folder1 / "episode.nfo").write_bytes(b"nfo")

        # Folder - still syncing
        folder2 = tmp_path / "Oppenheimer.2023.1080p.BluRay.x264-VARYG"
        folder2.mkdir()
        (folder2 / "oppenheimer.2023.1080p.bluray.x264-varyg.mkv").write_bytes(b"partial")
        (folder2 / ".syncthing.oppenheimer.2023.1080p.bluray.x264-varyg.mkv.tmp").write_bytes(b"temp")

        items = [single_file1, single_file2, folder1, folder2]
        stable_items = checker.get_stable_items(items)

        # Only single_file1 and folder1 should be stable
        assert len(stable_items) == 2
        assert single_file1 in stable_items
        assert folder1 in stable_items
        assert single_file2 not in stable_items
        assert folder2 not in stable_items

    def test_folder_with_spaces_in_name(self, tmp_path):
        """Test folder with spaces in name (realistic scenario)."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2, syncthing_enabled=True)

        # Simulate: www.UIndex.org    -    The Pitt S01E13 7 00 P M...
        folder = tmp_path / "www.UIndex.org    -    The Pitt S01E13 7 00 P M 1080p WEBRip"
        folder.mkdir()

        # Files inside
        (folder / "The Pitt S01E13 7 00 P M 1080p WEBRip.mkv").write_bytes(b"partial")
        (folder / ".syncthing.The Pitt S01E13 7 00 P M 1080p WEBRip.mkv.tmp").write_bytes(b"temp")
        (folder / "Torrent Downloaded From     UIndex.org      .txt").write_bytes(b"info")

        # Should detect as unstable
        assert checker._has_syncthing_tmp_files(folder) is True

    def test_combined_file_size_and_syncthing_checks(self, tmp_path):
        """Test combination of file size stability and Syncthing checks."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2, syncthing_enabled=True)

        # Create file that's stable in size but has Syncthing temp
        test_file = tmp_path / "video.mkv"
        test_file.write_bytes(b"stable size content")

        syncthing_tmp = tmp_path / ".syncthing.video.mkv.tmp"
        syncthing_tmp.write_bytes(b"temp")

        # Should be detected as unstable due to Syncthing temp file
        # even though size is stable
        assert checker.is_transfer_complete(test_file) is False

        # Remove temp file
        syncthing_tmp.unlink()

        # Now should be stable
        assert checker.is_transfer_complete(test_file) is True

    def test_syncthing_disabled_allows_all_files(self, tmp_path):
        """Test that disabling Syncthing allows files with .tmp to pass."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2, syncthing_enabled=False)

        # Create file with temp file
        test_file = tmp_path / "video.mkv"
        test_file.write_bytes(b"content")

        syncthing_tmp = tmp_path / ".syncthing.video.mkv.tmp"
        syncthing_tmp.write_bytes(b"temp")

        # With Syncthing disabled, should not check for temp files
        assert checker._has_syncthing_tmp_files(test_file) is False
        assert checker.is_transfer_complete(test_file) is True

    def test_generic_tmp_extension(self, tmp_path):
        """Test detection of files with .tmp extension."""
        checker = FileStabilityChecker(syncthing_enabled=True)

        # File itself has .tmp extension
        tmp_file = tmp_path / "video.mkv.tmp"
        tmp_file.write_bytes(b"temp content")

        # Should detect .tmp extension
        assert checker._has_syncthing_tmp_files(tmp_file) is True

    def test_folder_with_many_files_one_syncing(self, tmp_path):
        """Test folder with many files where only one is still syncing."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2, syncthing_enabled=True)

        # Create folder with many complete files
        folder = tmp_path / "Complete.Series"
        folder.mkdir()

        # Add 10 complete files
        for i in range(1, 11):
            (folder / f"episode{i:02d}.mkv").write_bytes(f"episode {i}".encode())

        # Add one file that's still syncing
        (folder / "episode11.mkv").write_bytes(b"partial episode 11")
        (folder / ".syncthing.episode11.mkv.tmp").write_bytes(b"temp")

        # Should detect the one unstable file
        assert checker._has_syncthing_tmp_files(folder) is True
        assert checker.is_transfer_complete(folder) is False

        # Remove the temp file
        (folder / ".syncthing.episode11.mkv.tmp").unlink()

        # Now should be stable
        assert checker.is_transfer_complete(folder) is True

    def test_realistic_download_scenario_progression(self, tmp_path):
        """Test realistic scenario of file progressing from syncing to complete."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2, syncthing_enabled=True)

        # Simulate download folder
        download_dir = tmp_path / "TV_Downloads"
        download_dir.mkdir()

        # File 1: Already complete
        file1 = download_dir / "The.Pitt.S01E10.1080p.WEB.h264-ETHEL.mkv"
        file1.write_bytes(b"complete video")

        # File 2: Still syncing
        file2 = download_dir / "Severance.S02E03.1080p.WEB.H264-CAKES.mkv"
        file2.write_bytes(b"partial video")
        tmp2 = download_dir / ".syncthing.Severance.S02E03.1080p.WEB.H264-CAKES.mkv.tmp"
        tmp2.write_bytes(b"temp")

        # Folder: Still syncing
        folder = download_dir / "Breaking.Bad.S05E16.Felina.1080p.BluRay.x264-ROVERS"
        folder.mkdir()
        (folder / "breaking.bad.s05e16.1080p.bluray.x264-rovers.mkv").write_bytes(b"partial")
        tmp3 = folder / ".syncthing.breaking.bad.s05e16.1080p.bluray.x264-rovers.mkv.tmp"
        tmp3.write_bytes(b"temp")

        # Initial check - only file1 should be stable
        items = [file1, file2, folder]
        stable = checker.get_stable_items(items)
        assert len(stable) == 1
        assert file1 in stable

        # File 2 completes - remove temp
        tmp2.unlink()

        # Second check - file1 and file2 should be stable
        stable = checker.get_stable_items(items)
        assert len(stable) == 2
        assert file1 in stable
        assert file2 in stable

        # Folder completes - remove temp
        tmp3.unlink()

        # Final check - all should be stable
        stable = checker.get_stable_items(items)
        assert len(stable) == 3

    def test_empty_folder_is_stable(self, tmp_path):
        """Test that empty folders are considered stable."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2, syncthing_enabled=True)

        empty_folder = tmp_path / "Empty_Folder"
        empty_folder.mkdir()

        assert checker._has_syncthing_tmp_files(empty_folder) is False
        items = [empty_folder]
        stable = checker.get_stable_items(items)
        assert len(stable) == 1

    def test_nonexistent_path(self, tmp_path):
        """Test handling of nonexistent paths."""
        checker = FileStabilityChecker(check_interval=0.1, retries=2, syncthing_enabled=True)

        nonexistent = tmp_path / "does_not_exist.mkv"

        # Should return False for nonexistent path
        assert checker.is_transfer_complete(nonexistent) is False

    def test_permission_error_handling(self, tmp_path):
        """Test graceful handling of permission errors."""
        checker = FileStabilityChecker(syncthing_enabled=True)

        test_dir = tmp_path / "test_folder"
        test_dir.mkdir()

        # Mock rglob to raise PermissionError
        with patch.object(Path, 'rglob', side_effect=PermissionError("Access denied")):
            # Should return False without crashing
            result = checker._has_syncthing_tmp_files(test_dir)
            assert result is False
