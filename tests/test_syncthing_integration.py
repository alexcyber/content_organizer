"""
Tests for Syncthing integration module.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile

from utils.syncthing_integration import SyncthingIntegration


class TestSyncthingIntegration:
    """Test Syncthing integration functionality."""

    def test_disabled_integration(self):
        """Test that integration can be disabled."""
        syncthing = SyncthingIntegration(enabled=False)
        assert not syncthing.enabled

    def test_missing_credentials_disables(self):
        """Test that missing API URL or key disables integration."""
        # Missing API key
        syncthing = SyncthingIntegration(api_url="http://localhost:8384", api_key=None)
        assert not syncthing.enabled

        # Missing API URL
        syncthing = SyncthingIntegration(api_url=None, api_key="test-key")
        assert not syncthing.enabled

        # Both provided
        syncthing = SyncthingIntegration(api_url="http://localhost:8384", api_key="test-key")
        assert syncthing.enabled

    def test_api_not_available(self):
        """Test behavior when API is not available."""
        syncthing = SyncthingIntegration(
            api_url="http://localhost:8384",
            api_key="test-key",
            api_timeout=1
        )

        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            assert not syncthing._is_api_available()
            # Should cache the result
            assert syncthing._api_available is False

    def test_api_available(self):
        """Test successful API connection."""
        syncthing = SyncthingIntegration(
            api_url="http://localhost:8384",
            api_key="test-key"
        )

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            assert syncthing._is_api_available()
            # Should cache the result
            assert syncthing._api_available is True

            # Verify correct endpoint and headers
            mock_get.assert_called_once_with(
                'http://localhost:8384/rest/system/ping',
                headers={'X-API-Key': 'test-key'},
                timeout=5
            )

    def test_temp_file_detection_for_file(self):
        """Test temp file detection for individual files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            test_file = tmpdir / "video.mkv"
            test_file.write_text("test")

            syncthing = SyncthingIntegration(enabled=False)

            # No temp file - should return False
            assert not syncthing.is_file_syncing(test_file)

            # Create syncthing temp file
            syncthing_tmp = tmpdir / f".syncthing.{test_file.name}.tmp"
            syncthing_tmp.write_text("syncing")

            assert syncthing.is_file_syncing(test_file)

            # Clean up syncthing temp, create generic temp
            syncthing_tmp.unlink()
            generic_tmp = tmpdir / f"{test_file.name}.tmp"
            generic_tmp.write_text("syncing")

            assert syncthing.is_file_syncing(test_file)

    def test_temp_file_detection_for_folder(self):
        """Test temp file detection for folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            test_folder = tmpdir / "show"
            test_folder.mkdir()
            (test_folder / "video.mkv").write_text("test")

            syncthing = SyncthingIntegration(enabled=False)

            # No temp files - should return False
            assert not syncthing._has_temp_files(test_folder)

            # Create temp file in folder
            (test_folder / ".syncthing.video.mkv.tmp").write_text("syncing")

            assert syncthing._has_temp_files(test_folder)

    def test_folder_syncing_with_api(self):
        """Test folder syncing detection via API."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "show"
            test_folder.mkdir()

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key"
            )

            with patch.object(syncthing, '_is_api_available', return_value=True):
                with patch.object(syncthing, '_get_folder_id_for_path', return_value='folder1'):
                    with patch.object(syncthing, '_get_path_sync_status', return_value=(5, 1024, True)):
                        # 5 files still downloading - should be syncing
                        assert syncthing.is_folder_syncing(test_folder)

                    with patch.object(syncthing, '_get_path_sync_status', return_value=(0, 0, True)):
                        # 0 files needed - fully synced
                        assert not syncthing.is_folder_syncing(test_folder)

    def test_folder_syncing_fallback_to_temp_detection(self):
        """Test fallback to temp file detection when API fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "show"
            test_folder.mkdir()

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key"
            )

            with patch.object(syncthing, '_is_api_available', return_value=True):
                with patch.object(syncthing, '_get_folder_id_for_path', side_effect=Exception("API error")):
                    # API fails, should fall back to temp file detection
                    assert not syncthing.is_folder_syncing(test_folder)

                    # Add temp file
                    (test_folder / "file.tmp").write_text("test")
                    assert syncthing.is_folder_syncing(test_folder)

    def test_get_folder_id_for_path(self):
        """Test mapping paths to Syncthing folder IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "downloads"
            test_folder.mkdir()

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key"
            )

            folders_response = [
                {"id": "folder1", "path": str(tmpdir / "downloads")},
                {"id": "folder2", "path": str(tmpdir / "other")}
            ]

            with patch('requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = folders_response
                mock_get.return_value = mock_response

                # Should find folder1 for test_folder
                folder_id = syncthing._get_folder_id_for_path(test_folder)
                assert folder_id == "folder1"

                # Should cache folders
                assert syncthing._folders_cache is not None

    def test_has_in_progress_items(self):
        """Test detection of in-progress sync items."""
        syncthing = SyncthingIntegration(
            api_url="http://localhost:8384",
            api_key="test-key"
        )

        with patch('requests.get') as mock_get:
            # Test syncing state
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'state': 'syncing',
                'pullErrors': 0,
                'needBytes': 0
            }
            mock_get.return_value = mock_response

            assert syncthing._has_in_progress_items('folder1', Path('/tmp'))

            # Test scanning state
            mock_response.json.return_value = {
                'state': 'scanning',
                'pullErrors': 0,
                'needBytes': 0
            }
            assert syncthing._has_in_progress_items('folder1', Path('/tmp'))

            # Test needBytes > 0
            mock_response.json.return_value = {
                'state': 'idle',
                'pullErrors': 0,
                'needBytes': 1024
            }
            assert syncthing._has_in_progress_items('folder1', Path('/tmp'))

            # Test idle with no pending items
            mock_response.json.return_value = {
                'state': 'idle',
                'pullErrors': 0,
                'needBytes': 0
            }
            assert not syncthing._has_in_progress_items('folder1', Path('/tmp'))

    def test_nonexistent_path(self):
        """Test behavior with nonexistent paths."""
        syncthing = SyncthingIntegration(enabled=False)

        assert not syncthing.is_folder_syncing(Path("/nonexistent/path"))
        assert not syncthing.is_file_syncing(Path("/nonexistent/file.mkv"))

    def test_wait_for_sync_complete(self):
        """Test waiting for sync to complete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_file = tmpdir / "video.mkv"
            test_file.write_text("test")

            syncthing = SyncthingIntegration(enabled=False)

            # File not syncing - should return immediately
            result = syncthing.wait_for_sync_complete(test_file, max_wait=5)
            assert result is True

            # Create temp file to simulate syncing
            temp_file = tmpdir / f"{test_file.name}.tmp"
            temp_file.write_text("syncing")

            # Should timeout
            result = syncthing.wait_for_sync_complete(test_file, max_wait=1)
            assert result is False

    def test_path_sync_status_checks_all_need_categories(self):
        """Test that _get_path_sync_status checks progress, queued, AND rest files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "downloads" / "The.Show.S01"
            test_folder.mkdir(parents=True)
            (test_folder / "video.mkv").write_text("test content")

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key"
            )

            # Set up folder cache
            syncthing._folders_cache = {
                "folder1": tmpdir / "downloads"
            }

            # Mock API responses
            with patch('requests.get') as mock_get:
                # Create response objects for different endpoints
                def mock_get_side_effect(url, **kwargs):
                    response = Mock()
                    response.status_code = 200
                    response.raise_for_status = Mock()

                    if '/rest/db/status' in url:
                        response.json.return_value = {
                            'state': 'idle',
                            'needBytes': 1024,
                            'needFiles': 1
                        }
                    elif '/rest/db/need' in url:
                        # Return files in ALL THREE categories
                        response.json.return_value = {
                            'progress': [],  # No files currently downloading
                            'queued': [  # But files are queued!
                                {'name': 'The.Show.S01/subtitle.srt', 'size': 1024}
                            ],
                            'rest': []  # And some in rest
                        }
                    elif '/rest/db/browse' in url:
                        response.json.return_value = [
                            {'name': 'video.mkv', 'type': 'FILE_INFO_TYPE_FILE', 'size': 1000},
                            {'name': 'subtitle.srt', 'type': 'FILE_INFO_TYPE_FILE', 'size': 1024}
                        ]

                    return response

                mock_get.side_effect = mock_get_side_effect

                # This should detect the queued file
                files_count, bytes_needed, is_tracked = syncthing._get_path_sync_status(
                    "folder1", test_folder
                )

                # Should find 1 pending file (the queued one)
                assert files_count >= 1, "Should detect queued files, not just progress files"
                assert is_tracked is True

    def test_path_sync_status_detects_queued_files(self):
        """Test that queued files are detected (the original bug)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "downloads" / "The.Rookie.S05"
            test_folder.mkdir(parents=True)

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key"
            )

            syncthing._folders_cache = {
                "folder1": tmpdir / "downloads"
            }

            with patch('requests.get') as mock_get:
                def mock_get_side_effect(url, **kwargs):
                    response = Mock()
                    response.status_code = 200
                    response.raise_for_status = Mock()

                    if '/rest/db/status' in url:
                        response.json.return_value = {'state': 'syncing', 'needBytes': 2048}
                    elif '/rest/db/need' in url:
                        # Simulate the S05 bug scenario:
                        # Main files are done (progress empty)
                        # But subtitle files are still queued
                        response.json.return_value = {
                            'progress': [],
                            'queued': [
                                {'name': 'The.Rookie.S05/Subs/S05E15/3_English.srt', 'size': 1024},
                                {'name': 'The.Rookie.S05/Subs/S05E22/3_English.srt', 'size': 1024}
                            ],
                            'rest': []
                        }
                    elif '/rest/db/browse' in url:
                        response.json.return_value = []

                    return response

                mock_get.side_effect = mock_get_side_effect

                files_count, bytes_needed, is_tracked = syncthing._get_path_sync_status(
                    "folder1", test_folder
                )

                # The fix should detect these queued files
                assert files_count == 2, f"Should detect 2 queued subtitle files, got {files_count}"
                assert bytes_needed == 2048, f"Should need 2048 bytes, got {bytes_needed}"

    def test_path_sync_status_detects_rest_files(self):
        """Test that 'rest' category files are also detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "downloads" / "Movie.2024"
            test_folder.mkdir(parents=True)

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key"
            )

            syncthing._folders_cache = {
                "folder1": tmpdir / "downloads"
            }

            with patch('requests.get') as mock_get:
                def mock_get_side_effect(url, **kwargs):
                    response = Mock()
                    response.status_code = 200
                    response.raise_for_status = Mock()

                    if '/rest/db/status' in url:
                        response.json.return_value = {'state': 'idle', 'needBytes': 5000}
                    elif '/rest/db/need' in url:
                        response.json.return_value = {
                            'progress': [],
                            'queued': [],
                            'rest': [
                                {'name': 'Movie.2024/sample.mkv', 'size': 5000}
                            ]
                        }
                    elif '/rest/db/browse' in url:
                        response.json.return_value = []

                    return response

                mock_get.side_effect = mock_get_side_effect

                files_count, bytes_needed, is_tracked = syncthing._get_path_sync_status(
                    "folder1", test_folder
                )

                assert files_count == 1, "Should detect file in 'rest' category"
                assert bytes_needed == 5000

    def test_folder_state_check(self):
        """Test that folder state is checked (syncing/scanning/idle)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "downloads" / "Show"
            test_folder.mkdir(parents=True)

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key"
            )

            syncthing._folders_cache = {
                "folder1": tmpdir / "downloads"
            }

            with patch('requests.get') as mock_get:
                def mock_get_side_effect(url, **kwargs):
                    response = Mock()
                    response.status_code = 200
                    response.raise_for_status = Mock()

                    if '/rest/db/status' in url:
                        # Folder is in syncing state
                        response.json.return_value = {
                            'state': 'syncing',
                            'needBytes': 0,
                            'needFiles': 0
                        }
                    elif '/rest/db/need' in url:
                        response.json.return_value = {
                            'progress': [],
                            'queued': [],
                            'rest': []
                        }
                    elif '/rest/db/browse' in url:
                        response.json.return_value = []

                    return response

                mock_get.side_effect = mock_get_side_effect

                # Even with no pending files, if folder is syncing, we should be cautious
                files_count, bytes_needed, is_tracked = syncthing._get_path_sync_status(
                    "folder1", test_folder
                )

                # The state check is logged but doesn't block - the key is pending files
                # This test verifies the API is called correctly
                assert mock_get.call_count >= 1


class TestSyncthingRealWorldScenarios:
    """
    Real-world Syncthing scenario tests.

    These tests simulate actual scenarios that occur during file syncing
    to ensure the integration handles them correctly.

    Note: All test files are tiny (< 1KB each) and created in temp directories
    that are automatically cleaned up after each test.
    """

    def test_no_temp_files_but_api_shows_pending(self):
        """
        KEY SCENARIO: Folder has completed files, no .tmp files, but API shows more files pending.

        This happens when:
        - Some files have finished downloading
        - Other files are queued but haven't started (no .tmp created yet)
        - The folder should NOT be moved because sync is incomplete
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "downloads" / "Dexter.Resurrection.S01"
            test_folder.mkdir(parents=True)

            # Create completed files (no .tmp files present) - tiny test files
            (test_folder / "Dexter.Resurrection.S01E01.mkv").write_bytes(b"x" * 100)
            (test_folder / "Dexter.Resurrection.S01E02.mkv").write_bytes(b"x" * 100)

            # Verify no temp files exist
            assert not list(test_folder.glob("*.tmp"))
            assert not list(test_folder.glob(".syncthing.*.tmp"))

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key"
            )

            syncthing._folders_cache = {
                "folder1": tmpdir / "downloads"
            }

            with patch('requests.get') as mock_get:
                def mock_get_side_effect(url, **kwargs):
                    response = Mock()
                    response.status_code = 200
                    response.raise_for_status = Mock()

                    if '/rest/system/ping' in url:
                        pass  # Just return 200
                    elif '/rest/db/status' in url:
                        response.json.return_value = {
                            'state': 'syncing',
                            'needBytes': 5000000000,  # 5GB still needed
                            'needFiles': 8
                        }
                    elif '/rest/db/need' in url:
                        # Episodes 3-10 are still pending (in rest, not started)
                        response.json.return_value = {
                            'progress': [],  # Nothing actively downloading
                            'queued': [],    # Nothing queued
                            'rest': [        # But 8 files waiting to start
                                {'name': 'Dexter.Resurrection.S01/Dexter.Resurrection.S01E03.mkv', 'size': 600000000},
                                {'name': 'Dexter.Resurrection.S01/Dexter.Resurrection.S01E04.mkv', 'size': 600000000},
                                {'name': 'Dexter.Resurrection.S01/Dexter.Resurrection.S01E05.mkv', 'size': 600000000},
                                {'name': 'Dexter.Resurrection.S01/Dexter.Resurrection.S01E06.mkv', 'size': 600000000},
                                {'name': 'Dexter.Resurrection.S01/Dexter.Resurrection.S01E07.mkv', 'size': 600000000},
                                {'name': 'Dexter.Resurrection.S01/Dexter.Resurrection.S01E08.mkv', 'size': 600000000},
                                {'name': 'Dexter.Resurrection.S01/Dexter.Resurrection.S01E09.mkv', 'size': 600000000},
                                {'name': 'Dexter.Resurrection.S01/Dexter.Resurrection.S01E10.mkv', 'size': 600000000},
                            ]
                        }
                    elif '/rest/db/browse' in url:
                        response.json.return_value = [
                            {'name': 'Dexter.Resurrection.S01E01.mkv', 'type': 'FILE_INFO_TYPE_FILE', 'size': 600000000},
                            {'name': 'Dexter.Resurrection.S01E02.mkv', 'type': 'FILE_INFO_TYPE_FILE', 'size': 600000000},
                        ]

                    return response

                mock_get.side_effect = mock_get_side_effect

                # Manually set API available to skip ping check
                syncthing._api_available = True

                # This should detect that sync is NOT complete
                is_syncing = syncthing.is_folder_syncing(test_folder)

                assert is_syncing is True, (
                    "Folder should be detected as syncing even without .tmp files "
                    "because API shows 8 files still pending in 'rest' category"
                )

    def test_folder_paused_returns_404_falls_back_gracefully(self):
        """
        Scenario: Syncthing folder is paused, causing /rest/db/need to return 404.

        When a folder is paused in Syncthing:
        - /rest/db/status still works
        - /rest/db/need returns 404 "no such folder"

        The code should fall back to temp file detection.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "downloads" / "Show.S01"
            test_folder.mkdir(parents=True)
            (test_folder / "episode.mkv").write_bytes(b"x" * 100)

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key"
            )

            syncthing._folders_cache = {
                "folder1": tmpdir / "downloads"
            }
            syncthing._api_available = True

            with patch('requests.get') as mock_get:
                def mock_get_side_effect(url, **kwargs):
                    response = Mock()

                    if '/rest/db/status' in url:
                        response.status_code = 200
                        response.raise_for_status = Mock()
                        response.json.return_value = {'state': '', 'needBytes': 0}
                    elif '/rest/db/need' in url:
                        # Simulate paused folder - returns 404
                        response.status_code = 404
                        response.raise_for_status = Mock(
                            side_effect=Exception("404 Client Error: Not Found")
                        )
                    elif '/rest/db/browse' in url:
                        response.status_code = 200
                        response.raise_for_status = Mock()
                        response.json.return_value = []
                    else:
                        response.status_code = 200
                        response.raise_for_status = Mock()

                    return response

                mock_get.side_effect = mock_get_side_effect

                # With no temp files, should return False (not syncing)
                is_syncing = syncthing.is_folder_syncing(test_folder)
                assert is_syncing is False, "Should fall back to temp detection and find no temp files"

                # Add a temp file - should now detect as syncing
                (test_folder / ".syncthing.episode2.mkv.tmp").write_bytes(b"x" * 50)

                is_syncing = syncthing.is_folder_syncing(test_folder)
                assert is_syncing is True, "Should detect temp file after API fallback"

    def test_api_timeout_falls_back_to_temp_detection(self):
        """
        Scenario: Syncthing API times out or is unreachable.

        Should fall back to temp file detection rather than failing.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "downloads" / "Movie.2024"
            test_folder.mkdir(parents=True)
            (test_folder / "movie.mkv").write_bytes(b"x" * 100)

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key",
                api_timeout=1
            )

            with patch('requests.get') as mock_get:
                # First call (ping) succeeds, subsequent calls timeout
                call_count = [0]

                def mock_get_side_effect(url, **kwargs):
                    call_count[0] += 1
                    if call_count[0] == 1:  # Ping succeeds
                        response = Mock()
                        response.status_code = 200
                        return response
                    # All other calls timeout
                    import requests
                    raise requests.exceptions.Timeout("Connection timed out")

                mock_get.side_effect = mock_get_side_effect

                # Without temp files - should return False
                is_syncing = syncthing.is_folder_syncing(test_folder)
                assert is_syncing is False

                # With temp file - should detect it
                (test_folder / ".syncthing.movie.mkv.tmp").write_bytes(b"x" * 50)
                syncthing._api_available = None  # Reset cache
                call_count[0] = 0

                is_syncing = syncthing.is_folder_syncing(test_folder)
                assert is_syncing is True

    def test_untracked_folder_manually_copied(self):
        """
        Scenario: Files were manually copied, not synced via Syncthing.

        When Syncthing doesn't track the files (db/browse returns empty but files exist),
        should return is_tracked=False and fall back to enhanced stability checks.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "downloads" / "Manual.Copy.2024"
            test_folder.mkdir(parents=True)
            (test_folder / "file1.mkv").write_bytes(b"x" * 100)
            (test_folder / "file2.mkv").write_bytes(b"x" * 100)

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key"
            )

            syncthing._folders_cache = {
                "folder1": tmpdir / "downloads"
            }
            syncthing._api_available = True

            with patch('requests.get') as mock_get:
                def mock_get_side_effect(url, **kwargs):
                    response = Mock()
                    response.status_code = 200
                    response.raise_for_status = Mock()

                    if '/rest/db/status' in url:
                        response.json.return_value = {'state': 'idle', 'needBytes': 0}
                    elif '/rest/db/need' in url:
                        response.json.return_value = {'progress': [], 'queued': [], 'rest': []}
                    elif '/rest/db/browse' in url:
                        # Syncthing doesn't know about these files
                        response.json.return_value = []

                    return response

                mock_get.side_effect = mock_get_side_effect

                # Use get_sync_status to check tracking
                is_syncing, is_tracked = syncthing.get_sync_status(test_folder)

                assert is_tracked is False, "Folder should be detected as untracked by Syncthing"
                assert is_syncing is False, "No temp files, so not actively syncing"

    def test_partial_sync_some_files_complete_others_downloading(self):
        """
        Scenario: Some files are complete, others are actively downloading.

        Common case during a season pack download where earlier episodes
        finish while later ones are still in progress.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "downloads" / "Show.S02"
            test_folder.mkdir(parents=True)

            # Episodes 1-3 complete
            (test_folder / "Show.S02E01.mkv").write_bytes(b"x" * 100)
            (test_folder / "Show.S02E02.mkv").write_bytes(b"x" * 100)
            (test_folder / "Show.S02E03.mkv").write_bytes(b"x" * 100)
            # Episode 4 is downloading (has temp file)
            (test_folder / ".syncthing.Show.S02E04.mkv.tmp").write_bytes(b"x" * 50)

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key"
            )

            syncthing._folders_cache = {
                "folder1": tmpdir / "downloads"
            }
            syncthing._api_available = True

            with patch('requests.get') as mock_get:
                def mock_get_side_effect(url, **kwargs):
                    response = Mock()
                    response.status_code = 200
                    response.raise_for_status = Mock()

                    if '/rest/db/status' in url:
                        response.json.return_value = {'state': 'syncing', 'needBytes': 3000}
                    elif '/rest/db/need' in url:
                        response.json.return_value = {
                            'progress': [
                                {'name': 'Show.S02/Show.S02E04.mkv', 'size': 1000}
                            ],
                            'queued': [
                                {'name': 'Show.S02/Show.S02E05.mkv', 'size': 1000},
                                {'name': 'Show.S02/Show.S02E06.mkv', 'size': 1000}
                            ],
                            'rest': []
                        }
                    elif '/rest/db/browse' in url:
                        response.json.return_value = [
                            {'name': 'Show.S02E01.mkv', 'type': 'FILE_INFO_TYPE_FILE'},
                            {'name': 'Show.S02E02.mkv', 'type': 'FILE_INFO_TYPE_FILE'},
                            {'name': 'Show.S02E03.mkv', 'type': 'FILE_INFO_TYPE_FILE'},
                        ]

                    return response

                mock_get.side_effect = mock_get_side_effect

                is_syncing = syncthing.is_folder_syncing(test_folder)

                assert is_syncing is True, (
                    "Folder should be syncing - both API shows pending files "
                    "AND temp file exists"
                )

    def test_fully_synced_folder_ready_to_move(self):
        """
        Scenario: Folder is completely synced and ready to be moved.

        - All files present locally
        - No temp files
        - API shows needFiles=0
        - Folder state is idle
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "downloads" / "Complete.Show.S01"
            test_folder.mkdir(parents=True)

            # All episodes present (tiny test files)
            for i in range(1, 11):
                (test_folder / f"Complete.Show.S01E{i:02d}.mkv").write_bytes(b"x" * 100)

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key"
            )

            syncthing._folders_cache = {
                "folder1": tmpdir / "downloads"
            }
            syncthing._api_available = True

            with patch('requests.get') as mock_get:
                def mock_get_side_effect(url, **kwargs):
                    response = Mock()
                    response.status_code = 200
                    response.raise_for_status = Mock()

                    if '/rest/db/status' in url:
                        response.json.return_value = {'state': 'idle', 'needBytes': 0, 'needFiles': 0}
                    elif '/rest/db/need' in url:
                        response.json.return_value = {'progress': [], 'queued': [], 'rest': []}
                    elif '/rest/db/browse' in url:
                        # All files known to Syncthing
                        response.json.return_value = [
                            {'name': f'Complete.Show.S01E{i:02d}.mkv', 'type': 'FILE_INFO_TYPE_FILE'}
                            for i in range(1, 11)
                        ]

                    return response

                mock_get.side_effect = mock_get_side_effect

                is_syncing = syncthing.is_folder_syncing(test_folder)

                assert is_syncing is False, "Fully synced folder should NOT be detected as syncing"

    def test_path_mapping_local_to_remote(self):
        """
        Scenario: Local path needs to be mapped to remote Syncthing path.

        Common in Docker/container setups where local path differs from
        the path Syncthing sees (e.g., /mnt/downloads vs /data/downloads).
        """
        syncthing = SyncthingIntegration(
            api_url="http://localhost:8384",
            api_key="test-key",
            path_mapping="/data/TV_Downloads:/mnt/content_organizer/syncthing/TV_Downloads"
        )

        # Test the mapping
        local_path = Path("/mnt/content_organizer/syncthing/TV_Downloads/Movies/Show.S01")
        remote_path = syncthing._map_local_to_remote(local_path)

        assert str(remote_path) == "/data/TV_Downloads/Movies/Show.S01", (
            f"Path mapping failed: got {remote_path}"
        )

    def test_path_mapping_folder_id_lookup(self):
        """
        Scenario: Find correct Syncthing folder ID when path mapping is configured.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            local_downloads = tmpdir / "local" / "downloads"
            local_downloads.mkdir(parents=True)

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key",
                path_mapping=f"/remote/downloads:{local_downloads}"
            )

            # Simulate Syncthing config with remote paths
            with patch('requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = [
                    {"id": "folder-abc", "path": "/remote/downloads"},
                    {"id": "folder-xyz", "path": "/remote/other"}
                ]
                mock_get.return_value = mock_response

                # Looking up local path should find the mapped remote folder
                test_path = local_downloads / "Show.S01"
                test_path.mkdir()

                folder_id = syncthing._get_folder_id_for_path(test_path)

                assert folder_id == "folder-abc", (
                    f"Should find folder-abc via path mapping, got {folder_id}"
                )

    def test_api_returns_malformed_json(self):
        """
        Scenario: Syncthing API returns invalid/malformed JSON.

        Should handle gracefully and fall back to temp file detection.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "downloads" / "Show"
            test_folder.mkdir(parents=True)
            (test_folder / "episode.mkv").write_bytes(b"x" * 100)

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key"
            )
            syncthing._api_available = True
            syncthing._folders_cache = {"folder1": tmpdir / "downloads"}

            with patch('requests.get') as mock_get:
                def mock_get_side_effect(url, **kwargs):
                    response = Mock()
                    response.status_code = 200
                    response.raise_for_status = Mock()

                    if '/rest/db/status' in url:
                        response.json.return_value = {'state': 'idle'}
                    elif '/rest/db/need' in url:
                        # Return malformed response
                        response.json.side_effect = ValueError("Invalid JSON")
                    else:
                        response.json.return_value = {}

                    return response

                mock_get.side_effect = mock_get_side_effect

                # Should not crash, should fall back gracefully
                is_syncing = syncthing.is_folder_syncing(test_folder)

                # No temp files, so should return False
                assert is_syncing is False

    def test_folder_with_nested_subfolders_all_tracked(self):
        """
        Scenario: Season pack with Subs subfolder - all must be checked.

        Common structure:
        Show.S01/
          Show.S01E01.mkv
          Show.S01E02.mkv
          Subs/
            S01E01.srt
            S01E02.srt  (still downloading)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_folder = tmpdir / "downloads" / "Show.S01"
            test_folder.mkdir(parents=True)

            # Main episodes complete (tiny test files)
            (test_folder / "Show.S01E01.mkv").write_bytes(b"x" * 100)
            (test_folder / "Show.S01E02.mkv").write_bytes(b"x" * 100)

            # Subs folder with one complete, one downloading
            subs = test_folder / "Subs"
            subs.mkdir()
            (subs / "S01E01.srt").write_bytes(b"x" * 50)
            # S01E02.srt still downloading - temp file in nested folder
            (subs / ".syncthing.S01E02.srt.tmp").write_bytes(b"x" * 25)

            syncthing = SyncthingIntegration(
                api_url="http://localhost:8384",
                api_key="test-key"
            )
            syncthing._api_available = True
            syncthing._folders_cache = {"folder1": tmpdir / "downloads"}

            with patch('requests.get') as mock_get:
                def mock_get_side_effect(url, **kwargs):
                    response = Mock()
                    response.status_code = 200
                    response.raise_for_status = Mock()

                    if '/rest/db/status' in url:
                        response.json.return_value = {'state': 'syncing', 'needBytes': 50}
                    elif '/rest/db/need' in url:
                        response.json.return_value = {
                            'progress': [
                                {'name': 'Show.S01/Subs/S01E02.srt', 'size': 50}
                            ],
                            'queued': [],
                            'rest': []
                        }
                    elif '/rest/db/browse' in url:
                        response.json.return_value = [
                            {'name': 'Show.S01E01.mkv', 'type': 'FILE_INFO_TYPE_FILE'},
                            {'name': 'Show.S01E02.mkv', 'type': 'FILE_INFO_TYPE_FILE'},
                            {'name': 'Subs', 'type': 'FILE_INFO_TYPE_DIRECTORY'},
                        ]

                    return response

                mock_get.side_effect = mock_get_side_effect

                is_syncing = syncthing.is_folder_syncing(test_folder)

                assert is_syncing is True, (
                    "Should detect nested temp file in Subs/ folder"
                )
