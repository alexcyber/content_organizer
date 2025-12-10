"""
Unit tests for SFTP manager.

Tests SFTP connection, deletion, and error handling.
"""

from unittest.mock import MagicMock, patch
import stat as stat_module

import paramiko

from operations.sftp_manager import SFTPManager


class TestSFTPManager:
    """Test cases for SFTPManager."""

    def test_manager_disabled_without_host(self):
        """Test that manager is disabled when host is not configured."""
        manager = SFTPManager(host="", username="user", password="pass")
        assert manager.enabled is False

    def test_manager_disabled_without_username(self):
        """Test that manager is disabled when username is not configured."""
        manager = SFTPManager(host="example.com", username="", password="pass")
        assert manager.enabled is False

    def test_manager_disabled_without_password(self):
        """Test that manager is disabled when password is not configured."""
        manager = SFTPManager(host="example.com", username="user", password="")
        assert manager.enabled is False

    def test_manager_enabled_with_full_config(self):
        """Test that manager is enabled with complete configuration."""
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass"
        )
        assert manager.enabled is True

    def test_dry_run_mode(self):
        """Test that dry-run mode prevents actual deletion."""
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            dry_run=True
        )

        # Should return True without attempting connection
        result = manager.delete_remote_file("test.mkv")
        assert result is True

    def test_delete_disabled_manager(self):
        """Test deletion with disabled manager returns False."""
        manager = SFTPManager(host="", username="", password="")

        result = manager.delete_remote_file("test.mkv")
        assert result is False

    @patch('paramiko.SSHClient')
    def test_delete_remote_file_success(self, mock_ssh_client):
        """Test successful remote file deletion."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Mock listdir_attr to return a file matching the search
        mock_file_attr = MagicMock()
        mock_file_attr.filename = "test.mkv"
        mock_file_attr.st_mode = 0o100644  # Regular file
        mock_sftp.listdir_attr.return_value = [mock_file_attr]

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="testuser",
            password="testpass",
            remote_dir="/downloads"
        )

        # Execute deletion
        result = manager.delete_remote_file("test.mkv")

        # Verify
        assert result is True
        mock_ssh_instance.connect.assert_called_once_with(
            hostname="example.com",
            port=22,
            username="testuser",
            password="testpass",
            timeout=30
        )
        # Verify search was performed
        mock_sftp.listdir_attr.assert_called()
        # Verify file was deleted
        mock_sftp.remove.assert_called_once_with("/downloads/test.mkv")
        mock_sftp.close.assert_called_once()
        mock_ssh_instance.close.assert_called_once()

    @patch('paramiko.SSHClient')
    def test_delete_remote_file_not_found(self, mock_ssh_client):
        """Test deletion when remote file doesn't exist."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Make stat raise FileNotFoundError
        mock_sftp.stat.side_effect = FileNotFoundError("File not found")

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="testuser",
            password="testpass",
            remote_dir="/downloads"
        )

        # Execute deletion
        result = manager.delete_remote_file("missing.mkv")

        # Verify
        assert result is False
        mock_sftp.remove.assert_not_called()

    @patch('paramiko.SSHClient')
    def test_delete_authentication_failure(self, mock_ssh_client):
        """Test deletion with authentication failure."""
        # Setup mock to raise authentication error
        mock_ssh_instance = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.connect.side_effect = paramiko.AuthenticationException("Auth failed")

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="baduser",
            password="badpass"
        )

        # Execute deletion
        result = manager.delete_remote_file("test.mkv")

        # Verify
        assert result is False

    @patch('paramiko.SSHClient')
    def test_delete_ssh_exception(self, mock_ssh_client):
        """Test deletion with SSH exception."""
        # Setup mock to raise SSH error
        mock_ssh_instance = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.connect.side_effect = paramiko.SSHException("Connection error")

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass"
        )

        # Execute deletion
        result = manager.delete_remote_file("test.mkv")

        # Verify
        assert result is False

    @patch('paramiko.SSHClient')
    def test_delete_connection_error(self, mock_ssh_client):
        """Test deletion with connection error."""
        # Setup mock to raise OS error
        mock_ssh_instance = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.connect.side_effect = OSError("Network unreachable")

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass"
        )

        # Execute deletion
        result = manager.delete_remote_file("test.mkv")

        # Verify
        assert result is False

    def test_get_remote_path_with_directory(self):
        """Test remote path construction with directory."""
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads/media"
        )

        path = manager._get_remote_path("test.mkv")
        assert path == "/downloads/media/test.mkv"

    def test_get_remote_path_without_directory(self):
        """Test remote path construction without directory."""
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir=""
        )

        path = manager._get_remote_path("test.mkv")
        assert path == "test.mkv"

    def test_get_remote_path_trailing_slash(self):
        """Test remote path construction with trailing slash."""
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads/"
        )

        path = manager._get_remote_path("test.mkv")
        assert path == "/downloads/test.mkv"

    def test_get_remote_path_windows_style(self):
        """Test remote path conversion from Windows-style backslashes."""
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="\\downloads\\media"
        )

        path = manager._get_remote_path("test.mkv")
        assert path == "/downloads/media/test.mkv"

    @patch('paramiko.SSHClient')
    def test_test_connection_success(self, mock_ssh_client):
        """Test successful connection test."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads"
        )

        # Test connection
        result = manager.test_connection()

        # Verify
        assert result is True
        mock_sftp.listdir.assert_called_once_with("/downloads")

    @patch('paramiko.SSHClient')
    def test_test_connection_no_remote_dir(self, mock_ssh_client):
        """Test connection test without remote directory."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir=""
        )

        # Test connection
        result = manager.test_connection()

        # Verify
        assert result is True
        mock_sftp.listdir.assert_not_called()

    @patch('paramiko.SSHClient')
    def test_test_connection_authentication_failure(self, mock_ssh_client):
        """Test connection test with authentication failure."""
        # Setup mock
        mock_ssh_instance = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.connect.side_effect = paramiko.AuthenticationException("Auth failed")

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="baduser",
            password="badpass"
        )

        # Test connection
        result = manager.test_connection()

        # Verify
        assert result is False

    @patch('paramiko.SSHClient')
    def test_test_connection_directory_not_found(self, mock_ssh_client):
        """Test connection test when remote directory doesn't exist."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp
        mock_sftp.listdir.side_effect = FileNotFoundError("Directory not found")

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/nonexistent"
        )

        # Test connection
        result = manager.test_connection()

        # Verify
        assert result is False

    def test_test_connection_disabled(self):
        """Test connection test with disabled manager."""
        manager = SFTPManager(host="", username="", password="")

        result = manager.test_connection()
        assert result is False

    @patch('paramiko.SSHClient')
    def test_custom_port(self, mock_ssh_client):
        """Test connection with custom port."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Create manager with custom port
        manager = SFTPManager(
            host="example.com",
            port=2222,
            username="user",
            password="pass"
        )

        # Execute deletion
        manager.delete_remote_file("test.mkv")

        # Verify custom port was used
        mock_ssh_instance.connect.assert_called_once_with(
            hostname="example.com",
            port=2222,
            username="user",
            password="pass",
            timeout=30
        )

    @patch('paramiko.SSHClient')
    def test_custom_timeout(self, mock_ssh_client):
        """Test connection with custom timeout."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Create manager with custom timeout
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            timeout=60
        )

        # Execute deletion
        manager.delete_remote_file("test.mkv")

        # Verify custom timeout was used
        mock_ssh_instance.connect.assert_called_once_with(
            hostname="example.com",
            port=22,
            username="user",
            password="pass",
            timeout=60
        )

    @patch('paramiko.SSHClient')
    def test_delete_remote_directory(self, mock_ssh_client):
        """Test successful remote directory deletion."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Mock directory "AAA" in the search directory
        mock_dir = MagicMock()
        mock_dir.filename = "AAA"
        mock_dir.st_mode = stat_module.S_IFDIR | 0o755  # Directory

        # Mock files inside AAA directory
        mock_file1 = MagicMock()
        mock_file1.filename = "file1.mkv"
        mock_file1.st_mode = stat_module.S_IFREG | 0o644  # Regular file

        mock_file2 = MagicMock()
        mock_file2.filename = "file2.mkv"
        mock_file2.st_mode = stat_module.S_IFREG | 0o644

        # Mock listdir_attr to return different results based on path
        def listdir_side_effect(path):
            if path == "/downloads":
                return [mock_dir]  # Search finds AAA directory
            elif path == "/downloads/AAA":
                return [mock_file1, mock_file2]  # Contents of AAA
            return []

        mock_sftp.listdir_attr.side_effect = listdir_side_effect

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads"
        )

        # Execute deletion
        result = manager.delete_remote_item("AAA", is_directory=True)

        # Verify
        assert result is True
        # Verify search and deletion
        assert mock_sftp.listdir_attr.call_count >= 2
        mock_sftp.remove.assert_any_call("/downloads/AAA/file1.mkv")
        mock_sftp.remove.assert_any_call("/downloads/AAA/file2.mkv")
        mock_sftp.rmdir.assert_called_once_with("/downloads/AAA")

    @patch('paramiko.SSHClient')
    def test_delete_remote_nested_directory(self, mock_ssh_client):
        """Test deletion of directory with subdirectories."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Mock nested structure: /downloads/AAA/BBB/CCC/
        # Mock AAA directory for search
        mock_aaa_dir = MagicMock()
        mock_aaa_dir.filename = "AAA"
        mock_aaa_dir.st_mode = stat_module.S_IFDIR | 0o755  # Directory

        # Top level: AAA contains subdirectory BBB
        mock_subdir = MagicMock()
        mock_subdir.filename = "BBB"
        mock_subdir.st_mode = stat_module.S_IFDIR | 0o755  # Directory

        # BBB contains file
        mock_file = MagicMock()
        mock_file.filename = "video.mkv"
        mock_file.st_mode = stat_module.S_IFREG | 0o644

        # Setup listdir_attr to return different results for different paths
        def listdir_side_effect(path):
            if path == "/downloads":
                return [mock_aaa_dir]  # Search finds AAA directory
            elif path == "/downloads/AAA":
                return [mock_subdir]
            elif path == "/downloads/AAA/BBB":
                return [mock_file]
            else:
                return []

        mock_sftp.listdir_attr.side_effect = listdir_side_effect

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads"
        )

        # Execute deletion
        result = manager.delete_remote_item("AAA", is_directory=True)

        # Verify
        assert result is True
        # Should recursively delete subdirectory first
        mock_sftp.remove.assert_called_once_with("/downloads/AAA/BBB/video.mkv")
        # Should remove directories from deepest to shallowest
        assert mock_sftp.rmdir.call_count == 2

    @patch('paramiko.SSHClient')
    def test_delete_remote_empty_directory(self, mock_ssh_client):
        """Test deletion of empty directory."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Mock EmptyDir for search
        mock_empty_dir = MagicMock()
        mock_empty_dir.filename = "EmptyDir"
        mock_empty_dir.st_mode = stat_module.S_IFDIR | 0o755  # Directory

        # Setup listdir_attr to return different results based on path
        def listdir_side_effect(path):
            if path == "/downloads":
                return [mock_empty_dir]  # Search finds EmptyDir
            elif path == "/downloads/EmptyDir":
                return []  # EmptyDir is empty
            return []

        mock_sftp.listdir_attr.side_effect = listdir_side_effect

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads"
        )

        # Execute deletion
        result = manager.delete_remote_item("EmptyDir", is_directory=True)

        # Verify
        assert result is True
        mock_sftp.remove.assert_not_called()
        mock_sftp.rmdir.assert_called_once_with("/downloads/EmptyDir")

    def test_delete_remote_directory_dry_run(self):
        """Test directory deletion in dry-run mode."""
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads",
            dry_run=True
        )

        # Should return True without attempting connection
        result = manager.delete_remote_item("AAA", is_directory=True)
        assert result is True

    @patch('paramiko.SSHClient')
    def test_delete_remote_item_file_mode(self, mock_ssh_client):
        """Test delete_remote_item with is_directory=False."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Mock file for search
        mock_file = MagicMock()
        mock_file.filename = "video.mkv"
        mock_file.st_mode = stat_module.S_IFREG | 0o644  # Regular file

        # Setup listdir_attr to return file in search results
        mock_sftp.listdir_attr.return_value = [mock_file]

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads"
        )

        # Execute deletion as file
        result = manager.delete_remote_item("video.mkv", is_directory=False)

        # Verify
        assert result is True
        mock_sftp.remove.assert_called_once_with("/downloads/video.mkv")
        mock_sftp.rmdir.assert_not_called()

    @patch('paramiko.SSHClient')
    def test_find_item_in_deeply_nested_directory(self, mock_ssh_client):
        """Test finding item several levels deep in directory tree."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Create deep directory structure: /downloads/A/B/C/D/target.mkv
        mock_a = MagicMock()
        mock_a.filename = "A"
        mock_a.st_mode = stat_module.S_IFDIR | 0o755

        mock_b = MagicMock()
        mock_b.filename = "B"
        mock_b.st_mode = stat_module.S_IFDIR | 0o755

        mock_c = MagicMock()
        mock_c.filename = "C"
        mock_c.st_mode = stat_module.S_IFDIR | 0o755

        mock_d = MagicMock()
        mock_d.filename = "D"
        mock_d.st_mode = stat_module.S_IFDIR | 0o755

        mock_target = MagicMock()
        mock_target.filename = "target.mkv"
        mock_target.st_mode = stat_module.S_IFREG | 0o644

        # Setup listdir_attr to simulate deep nesting
        def listdir_side_effect(path):
            if path == "/downloads":
                return [mock_a]
            elif path == "/downloads/A":
                return [mock_b]
            elif path == "/downloads/A/B":
                return [mock_c]
            elif path == "/downloads/A/B/C":
                return [mock_d]
            elif path == "/downloads/A/B/C/D":
                return [mock_target]
            return []

        mock_sftp.listdir_attr.side_effect = listdir_side_effect

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads"
        )

        # Execute deletion
        result = manager.delete_remote_file("target.mkv")

        # Verify it found and deleted the deeply nested file
        assert result is True
        mock_sftp.remove.assert_called_once_with("/downloads/A/B/C/D/target.mkv")

    @patch('paramiko.SSHClient')
    def test_find_item_with_error_in_subdirectory(self, mock_ssh_client):
        """Test search continues when encountering error in one subdirectory."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Create two directories: BadDir (throws error) and GoodDir (has target)
        mock_bad_dir = MagicMock()
        mock_bad_dir.filename = "BadDir"
        mock_bad_dir.st_mode = stat_module.S_IFDIR | 0o755

        mock_good_dir = MagicMock()
        mock_good_dir.filename = "GoodDir"
        mock_good_dir.st_mode = stat_module.S_IFDIR | 0o755

        mock_target = MagicMock()
        mock_target.filename = "target.mkv"
        mock_target.st_mode = stat_module.S_IFREG | 0o644

        # Setup listdir_attr to throw error for BadDir but succeed for GoodDir
        def listdir_side_effect(path):
            if path == "/downloads":
                return [mock_bad_dir, mock_good_dir]
            elif path == "/downloads/BadDir":
                raise PermissionError("Access denied")
            elif path == "/downloads/GoodDir":
                return [mock_target]
            return []

        mock_sftp.listdir_attr.side_effect = listdir_side_effect

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads"
        )

        # Execute deletion - should find file in GoodDir despite BadDir error
        result = manager.delete_remote_file("target.mkv")

        # Verify it found and deleted the file from accessible directory
        assert result is True
        mock_sftp.remove.assert_called_once_with("/downloads/GoodDir/target.mkv")

    @patch('paramiko.SSHClient')
    def test_delete_file_with_special_characters(self, mock_ssh_client):
        """Test deletion of files with spaces and special characters in name."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # File with spaces and special chars
        mock_file = MagicMock()
        mock_file.filename = "Movie (2024) - Director's Cut.mkv"
        mock_file.st_mode = stat_module.S_IFREG | 0o644

        mock_sftp.listdir_attr.return_value = [mock_file]

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads"
        )

        # Execute deletion
        result = manager.delete_remote_file("Movie (2024) - Director's Cut.mkv")

        # Verify
        assert result is True
        mock_sftp.remove.assert_called_once_with("/downloads/Movie (2024) - Director's Cut.mkv")

    @patch('paramiko.SSHClient')
    def test_find_item_returns_first_match(self, mock_ssh_client):
        """Test that search returns first match when multiple items have same name."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Create two directories with same filename in each
        mock_dir_a = MagicMock()
        mock_dir_a.filename = "DirA"
        mock_dir_a.st_mode = stat_module.S_IFDIR | 0o755

        mock_dir_b = MagicMock()
        mock_dir_b.filename = "DirB"
        mock_dir_b.st_mode = stat_module.S_IFDIR | 0o755

        mock_file_a = MagicMock()
        mock_file_a.filename = "duplicate.mkv"
        mock_file_a.st_mode = stat_module.S_IFREG | 0o644

        mock_file_b = MagicMock()
        mock_file_b.filename = "duplicate.mkv"
        mock_file_b.st_mode = stat_module.S_IFREG | 0o644

        # Setup listdir_attr
        def listdir_side_effect(path):
            if path == "/downloads":
                return [mock_dir_a, mock_dir_b]
            elif path == "/downloads/DirA":
                return [mock_file_a]
            elif path == "/downloads/DirB":
                return [mock_file_b]
            return []

        mock_sftp.listdir_attr.side_effect = listdir_side_effect

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads"
        )

        # Execute deletion - should delete first match
        result = manager.delete_remote_file("duplicate.mkv")

        # Verify it deleted from first directory found (DirA)
        assert result is True
        mock_sftp.remove.assert_called_once_with("/downloads/DirA/duplicate.mkv")

    @patch('paramiko.SSHClient')
    def test_recursive_delete_with_file_error(self, mock_ssh_client):
        """Test recursive delete when a file cannot be deleted."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Mock directory with files
        mock_dir = MagicMock()
        mock_dir.filename = "TestDir"
        mock_dir.st_mode = stat_module.S_IFDIR | 0o755

        mock_file1 = MagicMock()
        mock_file1.filename = "file1.mkv"
        mock_file1.st_mode = stat_module.S_IFREG | 0o644

        mock_file2 = MagicMock()
        mock_file2.filename = "readonly.mkv"
        mock_file2.st_mode = stat_module.S_IFREG | 0o444

        # Setup listdir and remove to simulate permission error
        def listdir_side_effect(path):
            if path == "/downloads":
                return [mock_dir]
            elif path == "/downloads/TestDir":
                return [mock_file1, mock_file2]
            return []

        mock_sftp.listdir_attr.side_effect = listdir_side_effect

        # Make file2 raise error when trying to delete
        def remove_side_effect(path):
            if "readonly.mkv" in path:
                raise PermissionError("Cannot delete readonly file")

        mock_sftp.remove.side_effect = remove_side_effect

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads"
        )

        # Execute deletion - should raise error
        result = manager.delete_remote_item("TestDir", is_directory=True)

        # Verify it failed due to permission error
        assert result is False

    @patch('paramiko.SSHClient')
    def test_find_item_with_trailing_slash_in_remote_dir(self, mock_ssh_client):
        """Test search works correctly when remote_dir has trailing slash."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Mock file
        mock_file = MagicMock()
        mock_file.filename = "test.mkv"
        mock_file.st_mode = stat_module.S_IFREG | 0o644

        mock_sftp.listdir_attr.return_value = [mock_file]

        # Create manager with trailing slash
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads/"  # Note trailing slash
        )

        # Execute deletion
        result = manager.delete_remote_file("test.mkv")

        # Verify - should normalize path (no double slashes)
        assert result is True
        # The path should be normalized to /downloads/test.mkv, not /downloads//test.mkv
        call_args = mock_sftp.remove.call_args[0][0]
        assert call_args == "/downloads/test.mkv"
        assert "//" not in call_args

    @patch('paramiko.SSHClient')
    def test_delete_when_directory_disappears_during_operation(self, mock_ssh_client):
        """Test graceful handling when directory disappears during deletion."""
        # Setup mocks
        mock_ssh_instance = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_client.return_value = mock_ssh_instance
        mock_ssh_instance.open_sftp.return_value = mock_sftp

        # Mock directory
        mock_dir = MagicMock()
        mock_dir.filename = "DisappearingDir"
        mock_dir.st_mode = stat_module.S_IFDIR | 0o755

        # Directory exists in search but disappears when trying to list contents
        def listdir_side_effect(path):
            if path == "/downloads":
                return [mock_dir]
            elif path == "/downloads/DisappearingDir":
                raise FileNotFoundError("Directory no longer exists")
            return []

        mock_sftp.listdir_attr.side_effect = listdir_side_effect

        # Create manager
        manager = SFTPManager(
            host="example.com",
            username="user",
            password="pass",
            remote_dir="/downloads"
        )

        # Execute deletion - should handle gracefully
        result = manager.delete_remote_item("DisappearingDir", is_directory=True)

        # Verify it returns True (directory found and deleted, FileNotFoundError during
        # recursive delete is handled gracefully as the directory is already gone)
        assert result is True
