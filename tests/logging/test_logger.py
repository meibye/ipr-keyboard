"""Tests for logging functionality.

Tests the logger setup and file writing.
"""
import logging


def test_get_logger(temp_log_dir):
    """Test that get_logger returns a logger instance.
    
    Verifies that the logger is properly created with correct configuration.
    """
    from ipr_keyboard.logging.logger import get_logger
    
    logger = get_logger()
    
    assert logger is not None
    assert isinstance(logger, logging.Logger)
    assert logger.name == "ipr_keyboard"
    assert logger.level == logging.INFO


def test_logger_singleton(temp_log_dir):
    """Test that get_logger returns the same instance each time.
    
    Verifies the singleton pattern is implemented correctly.
    """
    from ipr_keyboard.logging.logger import get_logger
    
    logger1 = get_logger()
    logger2 = get_logger()
    
    assert logger1 is logger2


def test_logger_writes_to_file(temp_log_dir):
    """Test that logger writes messages to the log file.
    
    Verifies that log messages are written to disk and can be read back.
    Uses the temp_log_dir fixture to ensure proper singleton reset.
    """
    from ipr_keyboard.logging.logger import get_logger, log_path
    
    logger = get_logger()
    logger.info("Hello log test message")
    
    # Flush handlers to ensure write
    for handler in logger.handlers:
        handler.flush()
    
    path = log_path()
    assert path.exists(), f"Log file should exist at {path}"
    
    text = path.read_text(encoding="utf-8")
    assert "Hello log test message" in text


def test_log_path(temp_log_dir):
    """Test that log_path returns the correct path.
    
    Verifies the log path is correctly resolved.
    """
    from ipr_keyboard.logging.logger import log_path
    
    path = log_path()
    assert path == temp_log_dir
    assert path.name == "test.log"


def test_logger_handlers(temp_log_dir):
    """Test that logger has both file and stream handlers.
    
    Verifies that both console and file output are configured.
    """
    from ipr_keyboard.logging.logger import get_logger
    from logging.handlers import RotatingFileHandler
    
    logger = get_logger()
    
    # Should have at least 2 handlers (file + console)
    assert len(logger.handlers) >= 2
    
    # Check for file handler
    file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(file_handlers) >= 1, "Should have a RotatingFileHandler"
    
    # Check for stream handler
    stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler) 
                       and not isinstance(h, RotatingFileHandler)]
    assert len(stream_handlers) >= 1, "Should have a StreamHandler"


def test_logger_creates_directory(tmp_path, monkeypatch):
    """Test that logger creates parent directories for log file.
    
    Verifies that missing directories are created automatically.
    """
    import ipr_keyboard.logging.logger as logger_module
    
    # Reset the singleton
    logger_module._LOGGER = None
    
    # Point to a nested path that doesn't exist
    log_file = tmp_path / "deep" / "nested" / "logs" / "test.log"
    monkeypatch.setattr(logger_module, "_LOG_FILE", log_file)
    
    from ipr_keyboard.logging.logger import get_logger
    
    logger = get_logger()
    logger.info("Creating directories test")
    
    # Flush handlers
    for handler in logger.handlers:
        handler.flush()
    
    assert log_file.parent.exists(), "Parent directory should be created"
    assert log_file.exists(), "Log file should be created"
    
    # Clean up
    logger_module._LOGGER = None
