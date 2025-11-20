"""Tests for Bluetooth keyboard functionality.

Tests the BluetoothKeyboard class methods for sending text via Bluetooth.
"""
import subprocess
from ipr_keyboard.bluetooth.keyboard import BluetoothKeyboard


def test_send_text(monkeypatch):
    """Test sending text via Bluetooth keyboard.
    
    Verifies that send_text calls the helper script with correct arguments.
    """
    calls = {}

    def fake_run(args, **kwargs):
        calls["args"] = args
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("ipr_keyboard.bluetooth.keyboard.subprocess.run", fake_run)

    kb = BluetoothKeyboard(helper_path="/fake/path")
    assert kb.send_text("abc") is True
    assert "abc" in calls["args"]
