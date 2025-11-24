"""Tests for Bluetooth keyboard functionality.

Tests the BluetoothKeyboard class methods for sending text via Bluetooth.
"""
import subprocess
from ipr_keyboard.bluetooth.keyboard import BluetoothKeyboard


def test_send_text_success(temp_config, monkeypatch):
    """Test sending text via Bluetooth keyboard.
    
    Verifies that send_text calls the helper script with correct arguments.
    """
    calls = {"args": None}

    def fake_run(args, **kwargs):
        calls["args"] = args
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("ipr_keyboard.bluetooth.keyboard.subprocess.run", fake_run)

    kb = BluetoothKeyboard(helper_path="/fake/path")
    result = kb.send_text("abc")
    
    assert result is True
    assert calls["args"] is not None
    assert "/fake/path" in calls["args"]
    assert "abc" in calls["args"]


def test_send_text_empty(temp_config, monkeypatch):
    """Test sending empty text skips the helper call.
    
    Verifies that empty strings are handled without calling the helper.
    """
    call_count = {"count": 0}

    def fake_run(args, **kwargs):
        call_count["count"] += 1
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("ipr_keyboard.bluetooth.keyboard.subprocess.run", fake_run)

    kb = BluetoothKeyboard(helper_path="/fake/path")
    result = kb.send_text("")
    
    assert result is True
    assert call_count["count"] == 0, "Helper should not be called for empty text"


def test_send_text_helper_not_found(temp_config, monkeypatch):
    """Test handling FileNotFoundError from helper.
    
    Verifies that missing helper script returns False.
    """
    def fake_run(args, **kwargs):
        raise FileNotFoundError(f"No such file or directory: {args[0]}")

    monkeypatch.setattr("ipr_keyboard.bluetooth.keyboard.subprocess.run", fake_run)

    kb = BluetoothKeyboard(helper_path="/nonexistent/path")
    result = kb.send_text("test text")
    
    assert result is False


def test_send_text_helper_error(temp_config, monkeypatch):
    """Test handling CalledProcessError from helper.
    
    Verifies that helper errors return False.
    """
    def fake_run(args, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=args,
            stderr="Helper failed"
        )

    monkeypatch.setattr("ipr_keyboard.bluetooth.keyboard.subprocess.run", fake_run)

    kb = BluetoothKeyboard(helper_path="/fake/path")
    result = kb.send_text("test text")
    
    assert result is False


def test_send_text_unicode(temp_config, monkeypatch):
    """Test sending Unicode text.
    
    Verifies that special characters are passed correctly to the helper.
    """
    calls = {"args": None}

    def fake_run(args, **kwargs):
        calls["args"] = args
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("ipr_keyboard.bluetooth.keyboard.subprocess.run", fake_run)

    kb = BluetoothKeyboard(helper_path="/fake/path")
    unicode_text = "Test æøå ÆØÅ 日本語"
    result = kb.send_text(unicode_text)
    
    assert result is True
    assert unicode_text in calls["args"]


def test_send_text_check_true(temp_config, monkeypatch):
    """Test that subprocess.run is called with check=True.
    
    Verifies that the helper is called with error checking enabled.
    """
    captured_kwargs = {}

    def fake_run(args, **kwargs):
        captured_kwargs.update(kwargs)
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("ipr_keyboard.bluetooth.keyboard.subprocess.run", fake_run)

    kb = BluetoothKeyboard(helper_path="/fake/path")
    kb.send_text("test")
    
    assert captured_kwargs.get("check") is True


def test_bluetooth_keyboard_default_helper_path():
    """Test default helper path.
    
    Verifies that the default helper path is set correctly.
    """
    kb = BluetoothKeyboard()
    
    assert kb.helper_path == "/usr/local/bin/bt_kb_send"


def test_bluetooth_keyboard_custom_helper_path():
    """Test custom helper path.
    
    Verifies that a custom helper path can be set.
    """
    kb = BluetoothKeyboard(helper_path="/custom/helper")
    
    assert kb.helper_path == "/custom/helper"


def test_send_text_long_text(temp_config, monkeypatch):
    """Test sending a long text string.
    
    Verifies that long text is handled correctly.
    """
    calls = {"args": None}

    def fake_run(args, **kwargs):
        calls["args"] = args
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("ipr_keyboard.bluetooth.keyboard.subprocess.run", fake_run)

    kb = BluetoothKeyboard(helper_path="/fake/path")
    long_text = "x" * 10000  # 10KB of text
    result = kb.send_text(long_text)
    
    assert result is True
    assert long_text in calls["args"]


def test_send_text_with_newlines(temp_config, monkeypatch):
    """Test sending text with newline characters.
    
    Verifies that multiline text is handled correctly.
    """
    calls = {"args": None}

    def fake_run(args, **kwargs):
        calls["args"] = args
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("ipr_keyboard.bluetooth.keyboard.subprocess.run", fake_run)

    kb = BluetoothKeyboard(helper_path="/fake/path")
    multiline = "Line 1\nLine 2\nLine 3"
    result = kb.send_text(multiline)
    
    assert result is True
    assert multiline in calls["args"]


def test_is_available_true(tmp_path):
    """Test is_available returns True when helper exists and is executable.
    
    Verifies that an executable helper is detected correctly.
    """
    import os
    
    helper = tmp_path / "bt_kb_send"
    helper.write_text("#!/bin/bash\necho 'helper'")
    os.chmod(helper, 0o755)  # Make executable
    
    kb = BluetoothKeyboard(helper_path=str(helper))
    
    assert kb.is_available() is True


def test_is_available_false_not_exists():
    """Test is_available returns False when helper doesn't exist.
    
    Verifies that missing helper is detected correctly.
    """
    kb = BluetoothKeyboard(helper_path="/nonexistent/path")
    
    assert kb.is_available() is False


def test_is_available_false_not_executable(tmp_path):
    """Test is_available returns False when helper is not executable.
    
    Verifies that non-executable files are rejected.
    """
    helper = tmp_path / "bt_kb_send"
    helper.write_text("#!/bin/bash\necho 'helper'")
    # Don't make it executable
    
    kb = BluetoothKeyboard(helper_path=str(helper))
    
    assert kb.is_available() is False


def test_is_available_false_directory(tmp_path):
    """Test is_available returns False when path is a directory.
    
    Verifies that directories are not treated as valid helpers.
    """
    helper_dir = tmp_path / "bt_kb_send"
    helper_dir.mkdir()
    
    kb = BluetoothKeyboard(helper_path=str(helper_dir))
    
    assert kb.is_available() is False
