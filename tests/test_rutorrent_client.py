"""
Tests for RuTorrent client module.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from utils.rutorrent_client import RuTorrentClient, TorrentInfo


class TestRuTorrentClient:
    """Test RuTorrent client functionality."""

    def test_disabled_client(self):
        """Test that client can be disabled."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/downloads",
            subfolders=["TV_Shows"],
            enabled=False
        )
        assert not client.enabled

    def test_missing_credentials_disables(self):
        """Test that missing credentials disables client."""
        # Missing URL
        client = RuTorrentClient(
            url="",
            username="user",
            password="pass",
            base_path="/downloads",
            subfolders=["TV_Shows"],
            enabled=True
        )
        assert not client.enabled

        # Missing username
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="",
            password="pass",
            base_path="/downloads",
            subfolders=["TV_Shows"],
            enabled=True
        )
        assert not client.enabled

        # Missing password
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="",
            base_path="/downloads",
            subfolders=["TV_Shows"],
            enabled=True
        )
        assert not client.enabled

        # All provided
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/downloads",
            subfolders=["TV_Shows"],
            enabled=True
        )
        assert client.enabled

    def test_api_not_available(self):
        """Test behavior when API is not available."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/downloads",
            subfolders=["TV_Shows"],
            enabled=True,
            timeout=1
        )

        with patch('utils.rutorrent_client.requests.post') as mock_post:
            import requests as req_lib
            mock_post.side_effect = req_lib.RequestException("Connection refused")
            assert not client.is_available()
            # Should cache the result
            assert client._api_available is False

    def test_api_available(self):
        """Test successful API connection."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/downloads",
            subfolders=["TV_Shows"],
            enabled=True
        )

        with patch('utils.rutorrent_client.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            assert client.is_available()
            # Should cache the result
            assert client._api_available is True

    def test_parse_torrent(self):
        """Test parsing torrent data from RuTorrent response."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/downloads",
            subfolders=["TV_Shows"],
            enabled=True
        )

        # Sample torrent data (34 fields as returned by RuTorrent)
        sample_data = [
            "1",  # 0: is_open
            "0",  # 1: is_hash_checking
            "1",  # 2: is_hash_checked
            "1",  # 3: state
            "The.Show.S01E01.1080p.WEB.mkv",  # 4: name
            "1073741824",  # 5: size_bytes (1GB)
            "256",  # 6: size_chunks
            "256",  # 7: completed_chunks
            "1073741824",  # 8: bytes_done
            "500000000",  # 9: up_total
            "50",  # 10: ratio
            "0",  # 11: current speed?
            "0",  # 12
            "8388608",  # 13: chunk_size
            "sonarr",  # 14: label
            "1",  # 15
            "0",  # 16
            "1",  # 17
            "0",  # 18
            "0",  # 19
            "2",  # 20
            "1766010007",  # 21: timestamp?
            "0",  # 22
            "0",  # 23
            "256",  # 24
            "/home/user/downloads/TV_Shows/The.Show.S01E01.1080p.WEB.mkv",  # 25: base_path
            "0",  # 26
            "10",  # 27
            "1",  # 28
            "",  # 29
            "",  # 30
            "23199931715584",  # 31
            "0",  # 32
            "1",  # 33
        ]

        torrent = client._parse_torrent("ABC123", sample_data)

        assert torrent.hash_id == "ABC123"
        assert torrent.name == "The.Show.S01E01.1080p.WEB.mkv"
        assert torrent.size_bytes == 1073741824
        assert torrent.size_chunks == 256
        assert torrent.completed_chunks == 256
        assert torrent.bytes_done == 1073741824
        assert torrent.label == "sonarr"
        assert torrent.base_path == "/home/user/downloads/TV_Shows/The.Show.S01E01.1080p.WEB.mkv"
        assert torrent.is_complete is True
        assert torrent.progress == 100.0
        assert torrent.folder_name == "The.Show.S01E01.1080p.WEB.mkv"

    def test_parse_incomplete_torrent(self):
        """Test parsing incomplete torrent data."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/downloads",
            subfolders=["TV_Shows"],
            enabled=True
        )

        # Incomplete torrent (128/256 chunks)
        sample_data = [
            "1", "0", "1", "1",
            "The.Show.S01E02.1080p.WEB.mkv",  # name
            "1073741824",  # size_bytes
            "256",  # size_chunks
            "128",  # completed_chunks (50%)
            "536870912",  # bytes_done (half)
            "0", "0", "0", "0", "8388608", "", "1", "0", "1", "0", "0", "2",
            "1766010007", "0", "0", "128",
            "/home/user/downloads/TV_Shows/The.Show.S01E02.1080p.WEB.mkv",
            "0", "10", "0", "", "", "23199931715584", "0", "0",
        ]

        torrent = client._parse_torrent("DEF456", sample_data)

        assert torrent.is_complete is False
        assert torrent.progress == 50.0
        assert torrent.completed_chunks == 128
        assert torrent.size_chunks == 256

    def test_find_torrent_by_folder_direct_path(self):
        """Test finding torrent by direct path lookup."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/home/user/downloads/manual",
            subfolders=["TV_Shows", "Movies"],
            enabled=True
        )

        # Mock the cache with a torrent
        mock_torrent = TorrentInfo(
            hash_id="ABC123",
            name="The.Show.S01",
            size_bytes=1000000,
            size_chunks=100,
            completed_chunks=100,
            bytes_done=1000000,
            base_path="/home/user/downloads/manual/TV_Shows/The.Show.S01",
            label="sonarr",
            is_complete=True,
            progress=100.0
        )

        client._torrents_cache = {"ABC123": mock_torrent}
        client._torrents_by_path = {
            "/home/user/downloads/manual/tv_shows/the.show.s01": mock_torrent
        }
        client._torrents_by_folder = {
            "the.show.s01": mock_torrent
        }

        # Should find by direct path
        result = client.find_torrent_by_folder("The.Show.S01")
        assert result is not None
        assert result.hash_id == "ABC123"

    def test_find_torrent_by_folder_fallback_search(self):
        """Test finding torrent by folder name when direct path fails."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/home/user/downloads/manual",
            subfolders=["TV_Shows"],
            enabled=True
        )

        mock_torrent = TorrentInfo(
            hash_id="ABC123",
            name="The.Show.S01",
            size_bytes=1000000,
            size_chunks=100,
            completed_chunks=100,
            bytes_done=1000000,
            base_path="/home/user/downloads/different_path/The.Show.S01",  # Different path
            label="",
            is_complete=True,
            progress=100.0
        )

        client._torrents_cache = {"ABC123": mock_torrent}
        client._torrents_by_path = {
            "/home/user/downloads/different_path/the.show.s01": mock_torrent
        }
        client._torrents_by_folder = {
            "the.show.s01": mock_torrent
        }

        # Direct path won't match, but folder name search should work
        result = client.find_torrent_by_folder("The.Show.S01")
        assert result is not None
        assert result.hash_id == "ABC123"

    def test_find_torrent_not_found(self):
        """Test behavior when torrent is not found."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/home/user/downloads/manual",
            subfolders=["TV_Shows"],
            enabled=True
        )

        client._torrents_cache = {}
        client._torrents_by_path = {}
        client._torrents_by_folder = {}

        result = client.find_torrent_by_folder("NonExistent.Folder")
        assert result is None

    def test_is_torrent_complete_complete(self):
        """Test is_torrent_complete for complete torrent."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/home/user/downloads/manual",
            subfolders=["TV_Shows"],
            enabled=True
        )

        mock_torrent = TorrentInfo(
            hash_id="ABC123",
            name="The.Show.S01",
            size_bytes=1000000,
            size_chunks=100,
            completed_chunks=100,
            bytes_done=1000000,
            base_path="/home/user/downloads/manual/TV_Shows/The.Show.S01",
            label="",
            is_complete=True,
            progress=100.0
        )

        with patch.object(client, 'is_available', return_value=True):
            with patch.object(client, 'find_torrent_by_folder', return_value=mock_torrent):
                is_complete, reason, info = client.is_torrent_complete("The.Show.S01")

                assert is_complete is True
                assert "complete" in reason.lower()
                assert info is not None
                assert info.hash_id == "ABC123"

    def test_is_torrent_complete_incomplete(self):
        """Test is_torrent_complete for incomplete torrent."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/home/user/downloads/manual",
            subfolders=["TV_Shows"],
            enabled=True
        )

        mock_torrent = TorrentInfo(
            hash_id="ABC123",
            name="The.Show.S01",
            size_bytes=1000000,
            size_chunks=100,
            completed_chunks=50,
            bytes_done=500000,
            base_path="/home/user/downloads/manual/TV_Shows/The.Show.S01",
            label="",
            is_complete=False,
            progress=50.0
        )

        with patch.object(client, 'is_available', return_value=True):
            with patch.object(client, 'find_torrent_by_folder', return_value=mock_torrent):
                is_complete, reason, info = client.is_torrent_complete("The.Show.S01")

                assert is_complete is False
                assert "incomplete" in reason.lower()
                assert "50" in reason  # Should mention progress
                assert info is not None

    def test_is_torrent_complete_not_found(self):
        """Test is_torrent_complete when torrent not found (manual copy)."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/home/user/downloads/manual",
            subfolders=["TV_Shows"],
            enabled=True
        )

        with patch.object(client, 'is_available', return_value=True):
            with patch.object(client, 'find_torrent_by_folder', return_value=None):
                is_complete, reason, info = client.is_torrent_complete("Manual.Copy.Folder")

                # Should return True when not found (treat as manual copy)
                assert is_complete is True
                assert "not found" in reason.lower() or "manual" in reason.lower()
                assert info is None

    def test_is_torrent_complete_api_unavailable(self):
        """Test is_torrent_complete when API is unavailable."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/home/user/downloads/manual",
            subfolders=["TV_Shows"],
            enabled=True
        )

        with patch.object(client, 'is_available', return_value=False):
            is_complete, reason, info = client.is_torrent_complete("Any.Folder")

            # Should return True when API unavailable (skip check)
            assert is_complete is True
            assert "not available" in reason.lower()
            assert info is None

    def test_is_torrent_complete_disabled(self):
        """Test is_torrent_complete when client is disabled."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/home/user/downloads/manual",
            subfolders=["TV_Shows"],
            enabled=False
        )

        is_complete, reason, info = client.is_torrent_complete("Any.Folder")

        assert is_complete is True
        assert "disabled" in reason.lower()
        assert info is None

    def test_refresh_cache(self):
        """Test cache refresh from RuTorrent API."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/home/user/downloads/manual",
            subfolders=["TV_Shows"],
            enabled=True
        )

        # Sample API response
        api_response = {
            "t": {
                "ABC123": [
                    "1", "0", "1", "1",
                    "The.Show.S01E01",
                    "1073741824", "256", "256", "1073741824",
                    "0", "0", "0", "0", "8388608", "sonarr",
                    "1", "0", "1", "0", "0", "2", "1766010007", "0", "0", "256",
                    "/home/user/downloads/manual/TV_Shows/The.Show.S01E01",
                    "0", "10", "1", "", "", "23199931715584", "0", "1",
                ]
            },
            "cid": 12345
        }

        with patch('utils.rutorrent_client.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = api_response
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            result = client.refresh_cache()

            assert result is True
            assert len(client._torrents_cache) == 1
            assert "ABC123" in client._torrents_cache
            assert client._torrents_cache["ABC123"].name == "The.Show.S01E01"

    def test_clear_cache(self):
        """Test clearing the cache."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/home/user/downloads/manual",
            subfolders=["TV_Shows"],
            enabled=True
        )

        # Set up some cached data
        client._torrents_cache = {"ABC123": Mock()}
        client._torrents_by_path = {"path": Mock()}
        client._torrents_by_folder = {"folder": Mock()}
        client._api_available = True

        client.clear_cache()

        assert client._torrents_cache is None
        assert client._torrents_by_path is None
        assert client._torrents_by_folder is None
        assert client._api_available is None

    def test_torrent_info_folder_name(self):
        """Test TorrentInfo.folder_name property."""
        torrent = TorrentInfo(
            hash_id="ABC123",
            name="The.Show.S01",
            size_bytes=1000000,
            size_chunks=100,
            completed_chunks=100,
            bytes_done=1000000,
            base_path="/home/user/downloads/manual/TV_Shows/The.Show.S01.1080p.WEB",
            label="",
            is_complete=True,
            progress=100.0
        )

        assert torrent.folder_name == "The.Show.S01.1080p.WEB"

    def test_multiple_subfolders(self):
        """Test client with multiple subfolders."""
        client = RuTorrentClient(
            url="https://example.com/rutorrent/",
            username="user",
            password="pass",
            base_path="/home/user/downloads/manual",
            subfolders=["TV_Shows", "Movies", "Anime", "Documentaries"],
            enabled=True
        )

        assert len(client.subfolders) == 4
        assert "TV_Shows" in client.subfolders
        assert "Movies" in client.subfolders
        assert "Anime" in client.subfolders
        assert "Documentaries" in client.subfolders
