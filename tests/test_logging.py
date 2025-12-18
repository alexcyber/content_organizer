"""
Comprehensive tests for logging functionality.

Tests cover:
- Default mode (INFO level on console and file)
- Quiet mode (WARNING+ on console, INFO+ on file)
- Debug mode (DEBUG level on all handlers)
- Deferred logging mechanism for quiet mode
- Stability checker log collection
- ProcessingRecord log collection

All tests are isolated from .env settings and filesystem state.
Uses ./tests/tmp/ for all temporary file operations.
"""

import io
import logging
import logging.handlers
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from utils.logger import setup_logger, get_logger, set_quiet_mode, set_debug_mode


# Base directory for all test files
TEST_TMP_DIR = Path(__file__).parent / "tmp" / "logging_tests"


def setup_module():
    """Create test tmp directory before any tests run."""
    TEST_TMP_DIR.mkdir(parents=True, exist_ok=True)


def teardown_module():
    """Clean up test tmp directory after all tests complete."""
    if TEST_TMP_DIR.exists():
        shutil.rmtree(TEST_TMP_DIR, ignore_errors=True)


class TestLoggerSetup:
    """Tests for basic logger setup and configuration."""

    def setup_method(self):
        """Reset logger state before each test."""
        # Remove all handlers from the media_organizer logger
        logger = logging.getLogger("media_organizer")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)

        # Create test-specific log directory
        self.log_dir = TEST_TMP_DIR / "logger_setup"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Clean up test-specific directory."""
        if self.log_dir.exists():
            shutil.rmtree(self.log_dir, ignore_errors=True)

    def test_setup_logger_creates_console_handler(self):
        """Logger should have a console handler (StreamHandler)."""
        logger = setup_logger("test_console")

        stream_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(stream_handlers) == 1

    def test_setup_logger_creates_file_handler(self):
        """Logger should have a rotating file handler."""
        log_file = self.log_dir / "test.log"
        logger = setup_logger("test_file", log_file=str(log_file))

        file_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(file_handlers) == 1

    def test_setup_logger_default_level_is_info(self):
        """Logger default level should be INFO."""
        logger = setup_logger("test_level")
        assert logger.level == logging.INFO

    def test_setup_logger_formatter_format(self):
        """Logger formatter should use expected format."""
        logger = setup_logger("test_formatter")

        for handler in logger.handlers:
            formatter = handler.formatter
            assert formatter is not None
            # Check format includes timestamp and level
            fmt = formatter._fmt
            assert fmt is not None
            assert "%(asctime)s" in fmt
            assert "%(levelname)" in fmt
            assert "%(message)s" in fmt

    def test_get_logger_returns_existing_logger(self):
        """get_logger should return existing logger if already configured."""
        logger1 = setup_logger("test_existing")
        logger2 = get_logger("test_existing")

        assert logger1 is logger2

    def test_get_logger_creates_new_if_not_exists(self):
        """get_logger should create new logger if not configured."""
        # Ensure logger doesn't exist
        logger_name = "test_new_logger"
        existing = logging.getLogger(logger_name)
        existing.handlers.clear()

        logger = get_logger(logger_name)
        assert len(logger.handlers) > 0

    def test_setup_logger_no_duplicate_handlers(self):
        """Calling setup_logger twice should not add duplicate handlers."""
        logger1 = setup_logger("test_duplicate")
        handler_count = len(logger1.handlers)

        logger2 = setup_logger("test_duplicate")
        assert len(logger2.handlers) == handler_count


class TestQuietMode:
    """Tests for quiet mode logging behavior."""

    def setup_method(self):
        """Set up fresh logger for each test."""
        self.logger = logging.getLogger("media_organizer")
        self.logger.handlers.clear()
        self.logger.setLevel(logging.INFO)

        # Create string stream for console output capture
        self.console_stream = io.StringIO()
        self.console_handler = logging.StreamHandler(self.console_stream)
        self.console_handler.setLevel(logging.INFO)
        self.console_handler.setFormatter(
            logging.Formatter("%(levelname)s - %(message)s")
        )
        self.logger.addHandler(self.console_handler)

        # Create log file in tests/tmp
        self.log_dir = TEST_TMP_DIR / "quiet_mode"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "test.log"

        self.file_handler = logging.handlers.RotatingFileHandler(
            str(self.log_file), maxBytes=1024*1024, backupCount=1
        )
        self.file_handler.setLevel(logging.INFO)
        self.file_handler.setFormatter(
            logging.Formatter("%(levelname)s - %(message)s")
        )
        self.logger.addHandler(self.file_handler)

    def teardown_method(self):
        """Clean up after each test."""
        self.logger.handlers.clear()
        if self.log_dir.exists():
            shutil.rmtree(self.log_dir, ignore_errors=True)

    def test_quiet_mode_console_shows_warning_only(self):
        """In quiet mode, console should only show WARNING and above."""
        set_quiet_mode(True)

        self.logger.debug("debug message")
        self.logger.info("info message")
        self.logger.warning("warning message")
        self.logger.error("error message")

        output = self.console_stream.getvalue()

        assert "debug message" not in output
        assert "info message" not in output
        assert "warning message" in output
        assert "error message" in output

    def test_quiet_mode_file_shows_info(self):
        """In quiet mode, file should still show INFO and above."""
        set_quiet_mode(True)

        self.logger.debug("debug message")
        self.logger.info("info message")
        self.logger.warning("warning message")

        # Flush and read file
        self.file_handler.flush()
        output = self.log_file.read_text()

        assert "debug message" not in output
        assert "info message" in output
        assert "warning message" in output

    def test_quiet_mode_can_be_disabled(self):
        """Quiet mode can be toggled off to restore INFO on console."""
        set_quiet_mode(True)
        self.logger.info("quiet info")

        set_quiet_mode(False)
        self.logger.info("normal info")

        output = self.console_stream.getvalue()

        assert "quiet info" not in output
        assert "normal info" in output

    def test_quiet_mode_only_affects_console_not_file(self):
        """Quiet mode should only modify StreamHandler, not RotatingFileHandler."""
        set_quiet_mode(True)

        # Console handler should be WARNING
        assert self.console_handler.level == logging.WARNING

        # File handler should still be INFO
        assert self.file_handler.level == logging.INFO


class TestDebugMode:
    """Tests for debug mode logging behavior."""

    def setup_method(self):
        """Set up fresh logger for each test."""
        self.logger = logging.getLogger("media_organizer")
        self.logger.handlers.clear()
        self.logger.setLevel(logging.INFO)

        # Create string stream for console output capture
        self.console_stream = io.StringIO()
        self.console_handler = logging.StreamHandler(self.console_stream)
        self.console_handler.setLevel(logging.INFO)
        self.console_handler.setFormatter(
            logging.Formatter("%(levelname)s - %(message)s")
        )
        self.logger.addHandler(self.console_handler)

        # Create log file in tests/tmp
        self.log_dir = TEST_TMP_DIR / "debug_mode"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "test.log"

        self.file_handler = logging.handlers.RotatingFileHandler(
            str(self.log_file), maxBytes=1024*1024, backupCount=1
        )
        self.file_handler.setLevel(logging.INFO)
        self.file_handler.setFormatter(
            logging.Formatter("%(levelname)s - %(message)s")
        )
        self.logger.addHandler(self.file_handler)

    def teardown_method(self):
        """Clean up after each test."""
        self.logger.handlers.clear()
        if self.log_dir.exists():
            shutil.rmtree(self.log_dir, ignore_errors=True)

    def test_debug_mode_shows_debug_on_console(self):
        """In debug mode, console should show DEBUG and above."""
        set_debug_mode(True)

        self.logger.debug("debug message")
        self.logger.info("info message")

        output = self.console_stream.getvalue()

        assert "debug message" in output
        assert "info message" in output

    def test_debug_mode_shows_debug_in_file(self):
        """In debug mode, file should show DEBUG and above."""
        set_debug_mode(True)

        self.logger.debug("debug message")
        self.logger.info("info message")

        self.file_handler.flush()
        output = self.log_file.read_text()

        assert "debug message" in output
        assert "info message" in output

    def test_debug_mode_sets_logger_level(self):
        """Debug mode should set logger level to DEBUG."""
        set_debug_mode(True)
        assert self.logger.level == logging.DEBUG

    def test_debug_mode_sets_all_handler_levels(self):
        """Debug mode should set all handler levels to DEBUG."""
        set_debug_mode(True)

        for handler in self.logger.handlers:
            assert handler.level == logging.DEBUG

    def test_debug_mode_can_be_disabled(self):
        """Debug mode can be toggled off to restore INFO level."""
        set_debug_mode(True)
        self.logger.debug("debug visible")

        set_debug_mode(False)
        # Need to clear the stream to test new behavior
        self.console_stream.truncate(0)
        self.console_stream.seek(0)

        self.logger.debug("debug hidden")
        self.logger.info("info visible")

        output = self.console_stream.getvalue()

        assert "debug hidden" not in output
        assert "info visible" in output


class TestDefaultMode:
    """Tests for default (no flags) logging behavior."""

    def setup_method(self):
        """Set up fresh logger for each test."""
        self.logger = logging.getLogger("media_organizer")
        self.logger.handlers.clear()
        self.logger.setLevel(logging.INFO)

        # Create string stream for console output capture
        self.console_stream = io.StringIO()
        self.console_handler = logging.StreamHandler(self.console_stream)
        self.console_handler.setLevel(logging.INFO)
        self.console_handler.setFormatter(
            logging.Formatter("%(levelname)s - %(message)s")
        )
        self.logger.addHandler(self.console_handler)

        # Create log file in tests/tmp
        self.log_dir = TEST_TMP_DIR / "default_mode"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "test.log"

        self.file_handler = logging.handlers.RotatingFileHandler(
            str(self.log_file), maxBytes=1024*1024, backupCount=1
        )
        self.file_handler.setLevel(logging.INFO)
        self.file_handler.setFormatter(
            logging.Formatter("%(levelname)s - %(message)s")
        )
        self.logger.addHandler(self.file_handler)

    def teardown_method(self):
        """Clean up after each test."""
        self.logger.handlers.clear()
        if self.log_dir.exists():
            shutil.rmtree(self.log_dir, ignore_errors=True)

    def test_default_mode_console_shows_info(self):
        """In default mode, console should show INFO and above."""
        self.logger.debug("debug message")
        self.logger.info("info message")
        self.logger.warning("warning message")

        output = self.console_stream.getvalue()

        assert "debug message" not in output
        assert "info message" in output
        assert "warning message" in output

    def test_default_mode_file_shows_info(self):
        """In default mode, file should show INFO and above."""
        self.logger.debug("debug message")
        self.logger.info("info message")
        self.logger.warning("warning message")

        self.file_handler.flush()
        output = self.log_file.read_text()

        assert "debug message" not in output
        assert "info message" in output
        assert "warning message" in output

    def test_default_mode_console_and_file_match(self):
        """In default mode, console and file should show same levels."""
        self.logger.info("test message")
        self.logger.warning("warning message")

        console_output = self.console_stream.getvalue()

        self.file_handler.flush()
        file_output = self.log_file.read_text()

        # Both should have same messages
        assert "test message" in console_output
        assert "test message" in file_output
        assert "warning message" in console_output
        assert "warning message" in file_output


class TestFileStabilityLogging:
    """Tests for FileStabilityChecker logging in different modes.

    Uses mocked config to avoid .env dependencies.
    """

    def setup_method(self):
        """Set up test fixtures with isolated config."""
        self.test_dir = TEST_TMP_DIR / "file_stability"
        self.test_dir.mkdir(parents=True, exist_ok=True)

        # Mock config to avoid .env dependencies
        self.config_patcher = patch('utils.file_stability.config')
        self.mock_config = self.config_patcher.start()

        # Set default config values
        self.mock_config.FILE_STABILITY_CHECK_INTERVAL = 0
        self.mock_config.FILE_STABILITY_CHECK_RETRIES = 1
        self.mock_config.SYNCTHING_ENABLED = False
        self.mock_config.ALLOW_ZERO_BYTE_FILES = False
        self.mock_config.HASH_CHECK_FOR_UNTRACKED = False
        self.mock_config.RUTORRENT_ENABLED = False
        self.mock_config.RUTORRENT_URL = ''
        self.mock_config.RUTORRENT_USERNAME = ''
        self.mock_config.RUTORRENT_PASSWORD = ''
        self.mock_config.RUTORRENT_BASE_PATH = ''
        self.mock_config.RUTORRENT_SUBFOLDERS = []
        self.mock_config.RUTORRENT_TIMEOUT = 30
        self.mock_config.SYNCTHING_URL = ''
        self.mock_config.SYNCTHING_API_KEY = ''
        self.mock_config.SYNCTHING_API_ENABLED = False
        self.mock_config.SYNCTHING_API_TIMEOUT = 5
        self.mock_config.SYNCTHING_PATH_MAPPING = {}
        self.mock_config.SYNCTHING_TMP_PATTERNS = ['.syncthing.*.tmp', '*.tmp']

    def teardown_method(self):
        """Clean up test directory and patches."""
        self.config_patcher.stop()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_checker(self, quiet=False, syncthing_enabled=False, **kwargs):
        """Create a FileStabilityChecker with mocked config."""
        from utils.file_stability import FileStabilityChecker

        self.mock_config.SYNCTHING_ENABLED = syncthing_enabled

        return FileStabilityChecker(
            check_interval=kwargs.get('check_interval', 0),
            retries=kwargs.get('retries', 1),
            syncthing_enabled=syncthing_enabled,
            rutorrent_enabled=False,
            quiet=quiet
        )

    def test_quiet_mode_collects_logs(self):
        """In quiet mode, stability checker should collect logs for deferred output."""
        checker = self._create_checker(quiet=True)

        # Create a test file
        test_file = self.test_dir / "test.mkv"
        test_file.write_bytes(b"test content")

        # Run stability check
        checker.get_stable_items([test_file])

        # Should have collected logs
        logs = checker.get_stability_logs()
        assert len(logs) > 0
        assert any("test.mkv" in log for log in logs)

    def test_quiet_mode_does_not_log_immediately(self):
        """In quiet mode, stability checker should not log stability details to console."""
        # Capture stdout
        captured_output = io.StringIO()

        # Set up a logger that writes to our captured output
        logger = logging.getLogger("media_organizer")
        original_handlers = logger.handlers.copy()
        logger.handlers.clear()

        handler = logging.StreamHandler(captured_output)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        try:
            checker = self._create_checker(quiet=True)

            test_file = self.test_dir / "test.mkv"
            test_file.write_bytes(b"test content")

            checker.get_stable_items([test_file])

            # Should not have logged stability details to console
            output = captured_output.getvalue()
            assert "Checking stability" not in output
            assert "test.mkv" not in output
            assert "Stable items" not in output
        finally:
            logger.handlers.clear()
            logger.handlers.extend(original_handlers)

    def test_non_quiet_mode_logs_immediately(self):
        """In non-quiet mode, stability checker should log to console immediately."""
        captured_output = io.StringIO()

        logger = logging.getLogger("media_organizer")
        original_handlers = logger.handlers.copy()
        logger.handlers.clear()

        handler = logging.StreamHandler(captured_output)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        try:
            checker = self._create_checker(quiet=False)

            test_file = self.test_dir / "test.mkv"
            test_file.write_bytes(b"test content")

            checker.get_stable_items([test_file])

            # Should have logged to console
            output = captured_output.getvalue()
            assert "test.mkv" in output
        finally:
            logger.handlers.clear()
            logger.handlers.extend(original_handlers)

    def test_stability_logs_include_item_list(self):
        """Stability logs should include list of items being checked."""
        checker = self._create_checker(quiet=True)

        test_file1 = self.test_dir / "show1.mkv"
        test_file2 = self.test_dir / "show2.mkv"
        test_file1.write_bytes(b"content1")
        test_file2.write_bytes(b"content2")

        checker.get_stable_items([test_file1, test_file2])

        logs = checker.get_stability_logs()
        log_text = "\n".join(logs)

        assert "show1.mkv" in log_text
        assert "show2.mkv" in log_text
        assert "Checking stability of 2 item(s)" in log_text

    def test_stability_logs_include_stable_summary(self):
        """Stability logs should include summary of stable items."""
        checker = self._create_checker(quiet=True)

        test_file = self.test_dir / "stable.mkv"
        test_file.write_bytes(b"stable content")

        checker.get_stable_items([test_file])

        logs = checker.get_stability_logs()
        log_text = "\n".join(logs)

        assert "Stable items ready for processing" in log_text
        assert "stable.mkv" in log_text

    def test_stability_logs_include_unstable_summary_with_reasons(self):
        """Stability logs should include summary of unstable items with reasons."""
        checker = self._create_checker(quiet=True, syncthing_enabled=True)

        # Create a file that looks like it's still syncing (has .tmp file)
        test_file = self.test_dir / "syncing.mkv"
        test_file.write_bytes(b"content")
        tmp_file = self.test_dir / ".syncthing.syncing.mkv.tmp"
        tmp_file.write_bytes(b"temp")

        checker.get_stable_items([test_file])

        logs = checker.get_stability_logs()
        log_text = "\n".join(logs)

        assert "Unstable items skipped" in log_text
        assert "syncing.mkv" in log_text
        # Check for reason (syncthing temp files)
        assert "Syncthing temporary files" in log_text or "syncing" in log_text.lower()

    def test_clear_stability_logs(self):
        """clear_stability_logs should clear collected logs."""
        checker = self._create_checker(quiet=True)

        test_file = self.test_dir / "test.mkv"
        test_file.write_bytes(b"content")

        checker.get_stable_items([test_file])
        assert len(checker.get_stability_logs()) > 0

        checker.clear_stability_logs()
        assert len(checker.get_stability_logs()) == 0

    def test_stability_logs_cleared_on_new_check(self):
        """Stability logs should be cleared when starting a new check."""
        checker = self._create_checker(quiet=True)

        test_file1 = self.test_dir / "first.mkv"
        test_file1.write_bytes(b"content")

        checker.get_stable_items([test_file1])

        test_file2 = self.test_dir / "second.mkv"
        test_file2.write_bytes(b"content")

        checker.get_stable_items([test_file2])
        second_logs = checker.get_stability_logs()

        # Second run should not contain first file
        log_text = "\n".join(second_logs)
        assert "first.mkv" not in log_text
        assert "second.mkv" in log_text


class TestDeferredLoggingIntegration:
    """Integration tests for deferred logging in quiet mode with MediaOrganizer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_dir = TEST_TMP_DIR / "deferred_logging"
        self.test_dir.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Clean up test directory."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('main.config')
    @patch('utils.file_stability.config')
    def test_quiet_mode_replays_stability_logs_when_moves_occur(self, mock_fs_config, mock_main_config):
        """In quiet mode, stability logs should be replayed when files are moved."""
        from main import MediaOrganizer

        # Set up mock configs for both main and file_stability
        for mock_config in [mock_main_config, mock_fs_config]:
            mock_config.DOWNLOAD_DIR = str(self.test_dir)
            mock_config.MOVIE_DIR = str(self.test_dir / "movies")
            mock_config.TV_CURRENT_DIR = str(self.test_dir / "tv_current")
            mock_config.TV_CONCLUDED_DIR = str(self.test_dir / "tv_concluded")
            mock_config.LOCK_FILE = str(self.test_dir / ".lock")
            mock_config.VIDEO_EXTENSIONS = ['.mkv', '.mp4', '.avi']
            mock_config.SKIP_DIRS = []
            mock_config.PARENT_DIRS = []
            mock_config.FUZZY_MATCH_THRESHOLD = 80
            mock_config.SYNCTHING_ENABLED = False
            mock_config.SYNCTHING_API_ENABLED = False
            mock_config.SYNCTHING_URL = ''
            mock_config.SYNCTHING_API_KEY = ''
            mock_config.SYNCTHING_API_TIMEOUT = 5
            mock_config.SYNCTHING_PATH_MAPPING = {}
            mock_config.SYNCTHING_TMP_PATTERNS = []
            mock_config.FILE_STABILITY_CHECK_INTERVAL = 0
            mock_config.FILE_STABILITY_CHECK_RETRIES = 1
            mock_config.ALLOW_ZERO_BYTE_FILES = False
            mock_config.HASH_CHECK_FOR_UNTRACKED = False
            mock_config.RUTORRENT_ENABLED = False
            mock_config.RUTORRENT_URL = ''
            mock_config.RUTORRENT_USERNAME = ''
            mock_config.RUTORRENT_PASSWORD = ''
            mock_config.RUTORRENT_BASE_PATH = ''
            mock_config.RUTORRENT_SUBFOLDERS = []
            mock_config.RUTORRENT_TIMEOUT = 30
            mock_config.TVDB_API_KEY = ''
            mock_config.TVDB_BASE_URL = ''
            mock_config.SFTP_HOST = ''
            mock_config.SFTP_PORT = 22
            mock_config.SFTP_REMOTE_DIR = ''

        mock_main_config.validate_config = MagicMock(return_value=[])

        # Create directories
        (self.test_dir / "movies").mkdir(parents=True, exist_ok=True)
        (self.test_dir / "tv_current").mkdir(parents=True, exist_ok=True)
        (self.test_dir / "tv_concluded").mkdir(parents=True, exist_ok=True)

        organizer = MediaOrganizer(dry_run=True, quiet=True)

        # Verify stability checker has quiet mode
        assert organizer.stability_checker.quiet is True

    def test_processing_record_collects_logs(self):
        """ProcessingRecord should collect logs for each item."""
        from main import ProcessingRecord

        record = ProcessingRecord(item_name="test.mkv")
        record.logs.append("Processing: test.mkv")
        record.logs.append("Classified: TV Show")
        record.logs.append("Status: CURRENT")

        assert len(record.logs) == 3
        assert "Processing: test.mkv" in record.logs
        assert "Classified: TV Show" in record.logs


class TestLogLevelTransitions:
    """Tests for transitioning between log modes."""

    def setup_method(self):
        """Set up fresh logger for each test."""
        self.logger = logging.getLogger("media_organizer")
        self.logger.handlers.clear()
        self.logger.setLevel(logging.INFO)

        self.console_stream = io.StringIO()
        self.console_handler = logging.StreamHandler(self.console_stream)
        self.console_handler.setLevel(logging.INFO)
        self.console_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        self.logger.addHandler(self.console_handler)

    def teardown_method(self):
        """Clean up after each test."""
        self.logger.handlers.clear()

    def test_quiet_to_normal_transition(self):
        """Transitioning from quiet to normal should restore INFO logging."""
        set_quiet_mode(True)
        self.logger.info("quiet mode info")

        set_quiet_mode(False)
        self.logger.info("normal mode info")

        output = self.console_stream.getvalue()
        assert "quiet mode info" not in output
        assert "normal mode info" in output

    def test_debug_to_normal_transition(self):
        """Transitioning from debug to normal should restore INFO level."""
        set_debug_mode(True)
        self.logger.debug("debug mode")

        set_debug_mode(False)
        # Clear stream to test new state
        self.console_stream.truncate(0)
        self.console_stream.seek(0)

        self.logger.debug("should not appear")
        self.logger.info("should appear")

        output = self.console_stream.getvalue()
        assert "should not appear" not in output
        assert "should appear" in output

    def test_quiet_and_debug_interaction(self):
        """Debug mode should override quiet mode for console."""
        set_quiet_mode(True)
        set_debug_mode(True)

        self.logger.debug("debug message")

        output = self.console_stream.getvalue()
        # Debug mode sets handler to DEBUG, overriding quiet's WARNING
        assert "debug message" in output

    def test_multiple_mode_changes(self):
        """Logger should handle multiple mode changes correctly."""
        # Start normal
        self.logger.info("normal 1")

        # Go quiet
        set_quiet_mode(True)
        self.logger.info("quiet 1")

        # Go debug
        set_debug_mode(True)
        self.logger.debug("debug 1")

        # Back to normal
        set_debug_mode(False)
        set_quiet_mode(False)
        self.logger.info("normal 2")
        self.logger.debug("should not show")

        output = self.console_stream.getvalue()
        assert "normal 1" in output
        assert "quiet 1" not in output
        assert "debug 1" in output
        assert "normal 2" in output
        assert "should not show" not in output


class TestLogMessages:
    """Tests for specific log message content and format."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_dir = TEST_TMP_DIR / "log_messages"
        self.test_dir.mkdir(parents=True, exist_ok=True)

        # Mock config
        self.config_patcher = patch('utils.file_stability.config')
        self.mock_config = self.config_patcher.start()
        self._setup_mock_config()

    def _setup_mock_config(self):
        """Set up mock config values."""
        self.mock_config.FILE_STABILITY_CHECK_INTERVAL = 0
        self.mock_config.FILE_STABILITY_CHECK_RETRIES = 1
        self.mock_config.SYNCTHING_ENABLED = False
        self.mock_config.ALLOW_ZERO_BYTE_FILES = False
        self.mock_config.HASH_CHECK_FOR_UNTRACKED = False
        self.mock_config.RUTORRENT_ENABLED = False
        self.mock_config.RUTORRENT_URL = ''
        self.mock_config.RUTORRENT_USERNAME = ''
        self.mock_config.RUTORRENT_PASSWORD = ''
        self.mock_config.RUTORRENT_BASE_PATH = ''
        self.mock_config.RUTORRENT_SUBFOLDERS = []
        self.mock_config.RUTORRENT_TIMEOUT = 30
        self.mock_config.SYNCTHING_URL = ''
        self.mock_config.SYNCTHING_API_KEY = ''
        self.mock_config.SYNCTHING_API_ENABLED = False
        self.mock_config.SYNCTHING_API_TIMEOUT = 5
        self.mock_config.SYNCTHING_PATH_MAPPING = {}
        self.mock_config.SYNCTHING_TMP_PATTERNS = ['.syncthing.*.tmp', '*.tmp']

    def teardown_method(self):
        """Clean up test directory and patches."""
        self.config_patcher.stop()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_checker(self, quiet=True, syncthing_enabled=False):
        """Create a FileStabilityChecker with mocked config."""
        from utils.file_stability import FileStabilityChecker
        self.mock_config.SYNCTHING_ENABLED = syncthing_enabled
        return FileStabilityChecker(
            check_interval=0,
            retries=1,
            syncthing_enabled=syncthing_enabled,
            rutorrent_enabled=False,
            quiet=quiet
        )

    def test_stability_check_header_format(self):
        """Stability check should log header with item count."""
        checker = self._create_checker()

        test_files = [
            self.test_dir / f"file{i}.mkv" for i in range(3)
        ]
        for f in test_files:
            f.write_bytes(b"content")

        checker.get_stable_items(test_files)
        logs = checker.get_stability_logs()

        # First log should be the header
        assert "Checking stability of 3 item(s):" in logs[0]

    def test_stable_item_format(self):
        """Stable items should be logged with checkmark."""
        checker = self._create_checker()

        test_file = self.test_dir / "stable.mkv"
        test_file.write_bytes(b"content")

        checker.get_stable_items([test_file])
        log_text = "\n".join(checker.get_stability_logs())

        assert "✓ stable.mkv" in log_text

    def test_unstable_item_format(self):
        """Unstable items should be logged with X mark and reason."""
        checker = self._create_checker(syncthing_enabled=True)

        test_file = self.test_dir / "syncing.mkv"
        test_file.write_bytes(b"content")
        tmp_file = self.test_dir / ".syncthing.syncing.mkv.tmp"
        tmp_file.write_bytes(b"temp")

        checker.get_stable_items([test_file])
        log_text = "\n".join(checker.get_stability_logs())

        assert "✗ syncing.mkv" in log_text

    def test_item_list_bullet_format(self):
        """Item list should use bullet points."""
        checker = self._create_checker()

        test_file = self.test_dir / "test.mkv"
        test_file.write_bytes(b"content")

        checker.get_stable_items([test_file])
        logs = checker.get_stability_logs()

        # Should have bullet point for item
        assert any("• test.mkv" in log for log in logs)


class TestLogFileOutput:
    """Tests for log file output in different modes."""

    def setup_method(self):
        """Set up fresh logger with file handler."""
        self.logger = logging.getLogger("media_organizer")
        self.logger.handlers.clear()
        self.logger.setLevel(logging.INFO)

        # Console handler
        self.console_stream = io.StringIO()
        self.console_handler = logging.StreamHandler(self.console_stream)
        self.console_handler.setLevel(logging.INFO)
        self.console_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        self.logger.addHandler(self.console_handler)

        # Create log file in tests/tmp
        self.log_dir = TEST_TMP_DIR / "log_file_output"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "test.log"

        self.file_handler = logging.handlers.RotatingFileHandler(
            str(self.log_file), maxBytes=1024*1024, backupCount=1
        )
        self.file_handler.setLevel(logging.INFO)
        self.file_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        self.logger.addHandler(self.file_handler)

    def teardown_method(self):
        """Clean up after each test."""
        self.logger.handlers.clear()
        if self.log_dir.exists():
            shutil.rmtree(self.log_dir, ignore_errors=True)

    def test_quiet_mode_file_receives_all_info_logs(self):
        """In quiet mode, file should receive INFO logs that console doesn't show."""
        set_quiet_mode(True)

        self.logger.info("important info")
        self.logger.warning("warning")

        console_output = self.console_stream.getvalue()

        self.file_handler.flush()
        file_output = self.log_file.read_text()

        # Console should not have INFO
        assert "important info" not in console_output
        assert "warning" in console_output

        # File should have both
        assert "important info" in file_output
        assert "warning" in file_output

    def test_debug_mode_file_receives_debug_logs(self):
        """In debug mode, file should receive DEBUG logs."""
        set_debug_mode(True)

        self.logger.debug("debug info")
        self.logger.info("normal info")

        self.file_handler.flush()
        file_output = self.log_file.read_text()

        assert "debug info" in file_output
        assert "normal info" in file_output

    def test_file_always_logs_warnings_and_errors(self):
        """File should always receive warnings and errors regardless of mode."""
        for mode in ["normal", "quiet", "debug"]:
            # Clear file
            self.log_file.write_text("")

            if mode == "quiet":
                set_quiet_mode(True)
            elif mode == "debug":
                set_debug_mode(True)
            else:
                set_quiet_mode(False)
                set_debug_mode(False)

            self.logger.warning(f"warning in {mode}")
            self.logger.error(f"error in {mode}")

            self.file_handler.flush()
            file_output = self.log_file.read_text()

            assert f"warning in {mode}" in file_output, f"Warning missing in {mode} mode"
            assert f"error in {mode}" in file_output, f"Error missing in {mode} mode"
