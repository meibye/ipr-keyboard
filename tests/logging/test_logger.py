"""Tests for logging functionality.

Tests the logger setup and file writing.
"""
from ipr_keyboard.logging.logger import get_logger, log_path


def test_logger_writes(tmp_path, monkeypatch):
    """Test that logger writes messages to the log file.
    
    Verifies that log messages are written to disk and can be read back.
    """
    monkeypatch.setattr("ipr_keyboard.logging.logger._LOG_FILE", tmp_path / "test.log")
    logger = get_logger()
    logger.info("Hello log")
    path = log_path()
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Hello log" in text
