"""
Logging configuration for media file organizer.

Provides structured logging to both console and rotating file.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import config


def setup_logger(name: str = "media_organizer", log_file: Optional[str] = None) -> logging.Logger:
    """
    Configure and return a logger with console and file handlers.

    Args:
        name: Logger name
        log_file: Path to log file (defaults to config.LOG_PATH)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    # Formatter for structured logs
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (rotating)
    if log_file is None:
        log_file = config.LOG_PATH

    try:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=config.LOG_BACKUP_COUNT
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (PermissionError, OSError) as e:
        logger.warning(f"Could not create file handler for {log_file}: {e}")

    return logger


def get_logger(name: str = "media_organizer") -> logging.Logger:
    """
    Get existing logger or create new one if it doesn't exist.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


def set_quiet_mode(quiet: bool = True) -> None:
    """
    Enable or disable quiet mode for console output.

    In quiet mode:
    - Console output shows only WARNING and above (errors, warnings)
    - File output continues to show INFO and above (full logs)

    This allows cron jobs to run silently unless there are actual issues.

    Args:
        quiet: If True, suppress INFO on console; if False, show all INFO
    """
    logger = logging.getLogger("media_organizer")

    for handler in logger.handlers:
        # Only modify console (StreamHandler), not file (RotatingFileHandler)
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler):
            if quiet:
                handler.setLevel(logging.WARNING)  # Only show warnings and errors
            else:
                handler.setLevel(logging.INFO)  # Show all info messages


def set_debug_mode(debug: bool = True) -> None:
    """
    Enable or disable debug mode for all output.

    In debug mode:
    - Logger level set to DEBUG
    - All handlers show DEBUG and above

    Args:
        debug: If True, enable debug logging; if False, revert to INFO
    """
    logger = logging.getLogger("media_organizer")
    level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(level)

    for handler in logger.handlers:
        handler.setLevel(level)
