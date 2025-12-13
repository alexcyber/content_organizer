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
