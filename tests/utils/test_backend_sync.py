"""Tests for backend synchronization utilities.

Tests the functions for reading and writing the /etc/ipr-keyboard/backend file.
"""
import os
from pathlib import Path
from unittest.mock import patch, mock_open

from ipr_keyboard.utils.backend_sync import (
    read_backend_file,
    write_backend_file,
    sync_backend_to_file,
    BACKEND_FILE_PATH,
)


def test_read_backend_file_success(tmp_path, monkeypatch):
    """Test reading backend file when it exists."""
    backend_file = tmp_path / "backend"
    backend_file.write_text("ble\n")
    
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))
    
    result = read_backend_file()
    assert result == "ble"


def test_read_backend_file_uinput(tmp_path, monkeypatch):
    """Test reading backend file with uinput value."""
    backend_file = tmp_path / "backend"
    backend_file.write_text("uinput")
    
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))
    
    result = read_backend_file()
    assert result == "uinput"


def test_read_backend_file_with_whitespace(tmp_path, monkeypatch):
    """Test reading backend file strips whitespace."""
    backend_file = tmp_path / "backend"
    backend_file.write_text("  ble  \n")
    
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))
    
    result = read_backend_file()
    assert result == "ble"


def test_read_backend_file_invalid_value(tmp_path, monkeypatch):
    """Test reading backend file with invalid value returns None."""
    backend_file = tmp_path / "backend"
    backend_file.write_text("invalid\n")
    
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))
    
    result = read_backend_file()
    assert result is None


def test_read_backend_file_missing(tmp_path, monkeypatch):
    """Test reading backend file when it doesn't exist."""
    backend_file = tmp_path / "nonexistent"
    
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))
    
    result = read_backend_file()
    assert result is None


def test_read_backend_file_permission_error(monkeypatch):
    """Test reading backend file when permission is denied."""
    with patch("builtins.open", side_effect=PermissionError):
        monkeypatch.setattr("os.path.exists", lambda x: True)
        result = read_backend_file()
        assert result is None


def test_write_backend_file_success(tmp_path, monkeypatch):
    """Test writing backend file successfully."""
    backend_dir = tmp_path / "ipr-keyboard"
    backend_file = backend_dir / "backend"
    
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))
    
    result = write_backend_file("ble")
    
    assert result is True
    assert backend_file.exists()
    assert backend_file.read_text().strip() == "ble"


def test_write_backend_file_uinput(tmp_path, monkeypatch):
    """Test writing uinput backend."""
    backend_file = tmp_path / "backend"
    
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))
    
    result = write_backend_file("uinput")
    
    assert result is True
    assert backend_file.read_text().strip() == "uinput"


def test_write_backend_file_creates_directory(tmp_path, monkeypatch):
    """Test that writing creates the parent directory if needed."""
    backend_dir = tmp_path / "etc" / "ipr-keyboard"
    backend_file = backend_dir / "backend"
    
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))
    
    result = write_backend_file("ble")
    
    assert result is True
    assert backend_dir.exists()
    assert backend_file.exists()


def test_write_backend_file_invalid_value(tmp_path, monkeypatch):
    """Test writing invalid backend value returns False."""
    backend_file = tmp_path / "backend"
    
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))
    
    result = write_backend_file("invalid")
    
    assert result is False
    assert not backend_file.exists()


def test_write_backend_file_permission_error(tmp_path, monkeypatch):
    """Test writing backend file when permission is denied."""
    backend_file = tmp_path / "backend"
    
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))
    
    with patch("builtins.open", side_effect=PermissionError):
        result = write_backend_file("ble")
        assert result is False


def test_sync_backend_to_file(tmp_path, monkeypatch):
    """Test sync_backend_to_file wrapper function."""
    backend_file = tmp_path / "backend"
    
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))
    
    result = sync_backend_to_file("ble")
    
    assert result is True
    assert backend_file.read_text().strip() == "ble"
