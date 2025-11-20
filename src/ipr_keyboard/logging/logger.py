"""Logging configuration and utilities.

Provides a centralized logger with rotating file handler and console output.
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from ..utils.helpers import project_root

_LOGGER: Optional[logging.Logger] = None
_LOG_FILE = project_root() / "logs" / "ipr_keyboard.log"


def get_logger() -> logging.Logger:
    """Get or create the application logger.
    
    Creates a logger with both file and console handlers on first call.
    The file handler uses rotation (max 256KB per file, 5 backups).
    
    Returns:
        The configured Logger instance.
    """
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ipr_keyboard")
    logger.setLevel(logging.INFO)

    handler = RotatingFileHandler(
        _LOG_FILE, maxBytes=256 * 1024, backupCount=5, encoding="utf-8"
    )
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    # Also log to stdout for debugging on console
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    _LOGGER = logger
    return logger


def log_path() -> Path:
    """Get the path to the log file.
    
    Returns:
        Path to the application log file.
    """
    return _LOG_FILE
