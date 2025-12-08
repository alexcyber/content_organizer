"""
SFTP manager for deleting files from remote server.

Handles SFTP connections and file deletion after successful local moves.
"""

from pathlib import Path
from typing import Optional

import paramiko

import config
from utils.logger import get_logger

logger = get_logger()


class SFTPManager:
    """Manager for SFTP operations including remote file deletion."""

    def __init__(
        self,
        host: str = config.SFTP_HOST,
        port: int = config.SFTP_PORT,
        username: str = config.SFTP_USER,
        password: str = config.SFTP_PASSWORD,
        remote_dir: str = config.SFTP_REMOTE_DIR,
        timeout: int = config.SFTP_TIMEOUT,
        dry_run: bool = False
    ):
        """
        Initialize SFTP manager.

        Args:
            host: SFTP server hostname
            port: SFTP server port
            username: SFTP username
            password: SFTP password
            remote_dir: Remote directory path
            timeout: Connection timeout in seconds
            dry_run: If True, only simulate operations
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.remote_dir = remote_dir
        self.timeout = timeout
        self.dry_run = dry_run
        self.enabled = bool(host and username and password)

        if not self.enabled:
            logger.warning("SFTP configuration incomplete - remote deletion disabled")
        elif dry_run:
            logger.info("SFTP: DRY-RUN MODE - No files will be deleted from remote")

    def delete_remote_item(self, item_name: str, is_directory: bool = False) -> bool:
        """
        Delete a file or directory from the remote SFTP server.

        Searches recursively for the item by exact name match in the remote directory,
        then deletes it while leaving parent directories intact.

        Args:
            item_name: Name of the item to delete (basename only)
            is_directory: If True, recursively delete directory; if False, delete file

        Returns:
            True if deletion successful or simulated, False otherwise
        """
        if not self.enabled:
            logger.debug(f"SFTP disabled - skipping deletion of '{item_name}'")
            return False

        # Dry-run mode
        if self.dry_run:
            item_type = "directory" if is_directory else "file"
            logger.info(f"[DRY-RUN] Would search and delete {item_type} from SFTP: {item_name}")
            return True

        # Attempt deletion
        try:
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Connect
            logger.debug(f"Connecting to SFTP server: {self.username}@{self.host}:{self.port}")
            ssh.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout
            )

            # Open SFTP session
            sftp = ssh.open_sftp()

            # Search for the item recursively
            remote_path = self._find_item(sftp, self.remote_dir, item_name)

            if not remote_path:
                logger.warning(f"Remote item not found: {item_name}")
                sftp.close()
                ssh.close()
                return False

            # Delete based on type
            if is_directory:
                self._recursive_delete(sftp, remote_path)
                logger.info(f"Deleted directory from SFTP: {remote_path}")
            else:
                sftp.remove(remote_path)
                logger.info(f"Deleted file from SFTP: {remote_path}")

            # Cleanup
            sftp.close()
            ssh.close()

            return True

        except paramiko.AuthenticationException:
            logger.error(f"SFTP authentication failed for {self.username}@{self.host}")
            return False
        except paramiko.SSHException as e:
            logger.error(f"SFTP SSH error: {e}")
            return False
        except OSError as e:
            logger.error(f"SFTP connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting '{item_name}' from SFTP: {e}")
            return False

    def delete_remote_file(self, filename: str) -> bool:
        """
        Delete a file from the remote SFTP server.

        Args:
            filename: Name of the file to delete (basename only)

        Returns:
            True if deletion successful or simulated, False otherwise
        """
        return self.delete_remote_item(filename, is_directory=False)

    def _find_item(self, sftp, search_dir: str, item_name: str) -> str:
        """
        Recursively search for an item by exact name match.

        Args:
            sftp: Active SFTP connection
            search_dir: Directory to search in
            item_name: Exact name of item to find (basename)

        Returns:
            Full path to the item if found, None otherwise
        """
        try:
            # Normalize paths
            search_dir = search_dir.rstrip('/')

            # Get items in current directory
            items = sftp.listdir_attr(search_dir)

            for item in items:
                # Check for exact match
                if item.filename == item_name:
                    return f"{search_dir}/{item.filename}"

                # If it's a directory, search recursively
                import stat
                if stat.S_ISDIR(item.st_mode):
                    result = self._find_item(sftp, f"{search_dir}/{item.filename}", item_name)
                    if result:
                        return result

            return None

        except Exception as e:
            logger.debug(f"Error searching {search_dir}: {e}")
            return None

    def _recursive_delete(self, sftp, path: str) -> None:
        """
        Recursively delete a directory and all its contents.

        Args:
            sftp: Active SFTP connection
            path: Remote path to delete

        Raises:
            OSError: If deletion fails
        """
        # Get directory contents
        try:
            items = sftp.listdir_attr(path)
        except FileNotFoundError:
            # Directory doesn't exist, nothing to delete
            return

        # Delete all items in directory
        for item in items:
            item_path = f"{path}/{item.filename}"

            # Check if item is a directory using stat mode
            import stat
            if stat.S_ISDIR(item.st_mode):
                # Recursively delete subdirectory
                self._recursive_delete(sftp, item_path)
            else:
                # Delete file
                sftp.remove(item_path)
                logger.debug(f"Deleted file: {item_path}")

        # Delete the now-empty directory
        sftp.rmdir(path)
        logger.debug(f"Deleted directory: {path}")

    def _get_remote_path(self, filename: str) -> str:
        """
        Construct full remote path from filename.

        Args:
            filename: Basename of the file

        Returns:
            Full remote path
        """
        if self.remote_dir:
            # Ensure remote_dir uses forward slashes (Unix-style)
            remote_dir = self.remote_dir.replace('\\', '/')
            # Remove trailing slash if present
            remote_dir = remote_dir.rstrip('/')
            return f"{remote_dir}/{filename}"
        else:
            return filename

    def test_connection(self) -> bool:
        """
        Test SFTP connection without performing any operations.

        Returns:
            True if connection successful, False otherwise
        """
        if not self.enabled:
            logger.warning("SFTP not enabled - cannot test connection")
            return False

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            logger.info(f"Testing SFTP connection to {self.username}@{self.host}:{self.port}")
            ssh.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout
            )

            sftp = ssh.open_sftp()

            # Try to list remote directory if specified
            if self.remote_dir:
                sftp.listdir(self.remote_dir)
                logger.info(f"SFTP connection successful - remote directory accessible: {self.remote_dir}")
            else:
                logger.info("SFTP connection successful")

            sftp.close()
            ssh.close()

            return True

        except paramiko.AuthenticationException:
            logger.error(f"SFTP authentication failed for {self.username}@{self.host}")
            return False
        except FileNotFoundError:
            logger.error(f"SFTP remote directory not found: {self.remote_dir}")
            return False
        except Exception as e:
            logger.error(f"SFTP connection test failed: {e}")
            return False
