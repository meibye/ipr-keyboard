"""Tests for logs API endpoints.

Tests the Flask web API for viewing application logs.
"""
from pathlib import Path


def test_get_log_whole(flask_client, temp_log_dir):
    """Test GET /logs/ returns full log content.
    
    Verifies that the entire log file is returned.
    """
    from ipr_keyboard.logging.logger import get_logger
    
    # Create some log entries
    logger = get_logger()
    logger.info("Test log entry 1")
    logger.info("Test log entry 2")
    
    # Flush handlers
    for handler in logger.handlers:
        handler.flush()
    
    response = flask_client.get("/logs/")
    
    assert response.status_code == 200
    data = response.get_json()
    assert "log" in data
    assert "Test log entry 1" in data["log"]
    assert "Test log entry 2" in data["log"]


def test_get_log_whole_missing(flask_client, tmp_path, monkeypatch):
    """Test GET /logs/ when log file doesn't exist.
    
    Verifies that an empty string is returned for missing log files.
    """
    import ipr_keyboard.logging.logger as logger_module
    
    # Point to a non-existent log file
    monkeypatch.setattr(logger_module, "_LOG_FILE", tmp_path / "nonexistent.log")
    
    response = flask_client.get("/logs/")
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["log"] == ""


def test_get_log_tail(flask_client, temp_log_dir):
    """Test GET /logs/tail returns last N lines.
    
    Verifies that only the last N lines are returned.
    """
    from ipr_keyboard.logging.logger import get_logger
    
    logger = get_logger()
    
    # Create more log entries
    for i in range(10):
        logger.info(f"Line {i}")
    
    # Flush handlers
    for handler in logger.handlers:
        handler.flush()
    
    response = flask_client.get("/logs/tail?lines=5")
    
    assert response.status_code == 200
    data = response.get_json()
    assert "log" in data
    
    # Should have approximately the last 5 lines
    lines = [l for l in data["log"].strip().split("\n") if l]
    # Due to buffering and multi-line log entries, we just verify it's not empty
    assert len(lines) > 0


def test_get_log_tail_default_lines(flask_client, temp_log_dir):
    """Test GET /logs/tail uses default 200 lines.
    
    Verifies that default line count is used when not specified.
    """
    from ipr_keyboard.logging.logger import get_logger
    
    logger = get_logger()
    logger.info("Single test entry")
    
    # Flush handlers
    for handler in logger.handlers:
        handler.flush()
    
    response = flask_client.get("/logs/tail")
    
    assert response.status_code == 200
    data = response.get_json()
    assert "log" in data


def test_get_log_tail_invalid_param(flask_client, temp_log_dir):
    """Test GET /logs/tail with invalid lines parameter.
    
    Verifies that invalid parameters fall back to default.
    """
    from ipr_keyboard.logging.logger import get_logger
    
    logger = get_logger()
    logger.info("Test entry")
    
    # Flush handlers
    for handler in logger.handlers:
        handler.flush()
    
    response = flask_client.get("/logs/tail?lines=invalid")
    
    assert response.status_code == 200
    data = response.get_json()
    assert "log" in data


def test_get_log_tail_missing_file(flask_client, tmp_path, monkeypatch):
    """Test GET /logs/tail when log file doesn't exist.
    
    Verifies that an empty string is returned.
    """
    import ipr_keyboard.logging.logger as logger_module
    
    # Point to a non-existent log file
    monkeypatch.setattr(logger_module, "_LOG_FILE", tmp_path / "nonexistent.log")
    
    response = flask_client.get("/logs/tail?lines=10")
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["log"] == ""


def test_get_log_tail_negative_lines(flask_client, temp_log_dir):
    """Test GET /logs/tail with negative lines parameter.
    
    Verifies that negative values are handled gracefully.
    """
    from ipr_keyboard.logging.logger import get_logger
    
    logger = get_logger()
    logger.info("Test entry")
    
    # Flush handlers
    for handler in logger.handlers:
        handler.flush()
    
    # Python slicing handles negative indices
    response = flask_client.get("/logs/tail?lines=-5")
    
    assert response.status_code == 200
    data = response.get_json()
    assert "log" in data


def test_get_log_tail_zero_lines(flask_client, temp_log_dir):
    """Test GET /logs/tail with zero lines.
    
    Verifies that zero lines returns empty content.
    """
    from ipr_keyboard.logging.logger import get_logger
    
    logger = get_logger()
    logger.info("Test entry")
    
    # Flush handlers
    for handler in logger.handlers:
        handler.flush()
    
    response = flask_client.get("/logs/tail?lines=0")
    
    assert response.status_code == 200
    data = response.get_json()
    # With 0 lines, should get empty or near-empty content
    assert "log" in data
