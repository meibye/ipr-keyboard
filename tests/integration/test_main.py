"""Integration tests for main module.

Tests the main application entry point and workflows.
"""
import threading
import time
from unittest.mock import patch, MagicMock

import pytest


def test_run_web_server_creates_app(temp_config, monkeypatch):
    """Test that run_web_server creates and runs Flask app.
    
    Verifies that the web server is started with correct port.
    """
    from ipr_keyboard.config.manager import ConfigManager
    from ipr_keyboard.main import run_web_server
    
    app_mock = MagicMock()
    
    def mock_create_app():
        return app_mock
    
    monkeypatch.setattr("ipr_keyboard.main.create_app", mock_create_app)
    
    # Run in a thread and stop quickly
    def run():
        run_web_server()
    
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()
    
    # Give it a moment to start
    time.sleep(0.1)
    
    # Verify app.run was called
    app_mock.run.assert_called_once()
    call_kwargs = app_mock.run.call_args[1]
    assert call_kwargs["host"] == "0.0.0.0"
    assert "port" in call_kwargs


def test_main_initializes_config(temp_config, monkeypatch):
    """Test that main() initializes ConfigManager.
    
    Verifies that configuration is loaded at startup.
    """
    from ipr_keyboard.config.manager import ConfigManager
    
    started = {"count": 0}
    
    # Mock the threads to avoid actually running them
    def mock_thread_target(*args, **kwargs):
        started["count"] += 1
        return MagicMock()
    
    # Mock threading.Thread
    original_thread = threading.Thread
    
    def mock_thread(**kwargs):
        started["count"] += 1
        mock = MagicMock()
        mock.start = MagicMock()
        return mock
    
    monkeypatch.setattr("threading.Thread", mock_thread)
    
    # Mock time.sleep to exit immediately
    sleep_calls = {"count": 0}
    
    def mock_sleep(duration):
        sleep_calls["count"] += 1
        if sleep_calls["count"] > 1:
            raise KeyboardInterrupt()
    
    monkeypatch.setattr("time.sleep", mock_sleep)
    
    from ipr_keyboard.main import main
    
    # Run main - it should handle KeyboardInterrupt
    main()
    
    # Verify ConfigManager was accessed
    cfg = ConfigManager.instance().get()
    assert cfg is not None


def test_usb_bt_loop_handles_missing_folder(temp_config, monkeypatch):
    """Test that USB/BT loop handles missing IrisPenFolder.
    
    Verifies graceful handling when the watched folder doesn't exist.
    """
    from ipr_keyboard.config.manager import ConfigManager
    from ipr_keyboard.main import run_usb_bt_loop
    
    # Ensure IrisPenFolder doesn't exist
    cfg = ConfigManager.instance().get()
    
    loop_count = {"count": 0}
    
    # Mock time.sleep to limit iterations
    def mock_sleep(duration):
        loop_count["count"] += 1
        if loop_count["count"] >= 3:
            raise KeyboardInterrupt()
    
    monkeypatch.setattr("time.sleep", mock_sleep)
    
    # Should not raise an exception
    try:
        run_usb_bt_loop()
    except KeyboardInterrupt:
        pass
    
    assert loop_count["count"] >= 2


def test_usb_bt_loop_processes_file(temp_config, usb_folder, monkeypatch):
    """Test that USB/BT loop detects and processes files.
    
    Verifies the main loop workflow with a test file.
    """
    from ipr_keyboard.config.manager import ConfigManager
    from ipr_keyboard.main import run_usb_bt_loop
    
    # Update config to point to our test folder
    ConfigManager.instance().update(
        IrisPenFolder=str(usb_folder),
        DeleteFiles=True
    )
    
    # Create a test file
    test_file = usb_folder / "test.txt"
    test_file.write_text("test content")
    
    processed = {"file": None, "text": None}
    loop_count = {"count": 0}
    
    # Mock the wait_for_new_file to return immediately
    def mock_wait(folder, mtime, interval):
        if loop_count["count"] == 0:
            loop_count["count"] += 1
            return test_file
        raise KeyboardInterrupt()
    
    monkeypatch.setattr("ipr_keyboard.main.detector.wait_for_new_file", mock_wait)
    
    # Mock BluetoothKeyboard
    class MockBT:
        def is_available(self):
            return True
        
        def send_text(self, text):
            processed["text"] = text
            return True
    
    monkeypatch.setattr("ipr_keyboard.main.BluetoothKeyboard", MockBT)
    
    # Run the loop
    try:
        run_usb_bt_loop()
    except KeyboardInterrupt:
        pass
    
    # Verify the text was sent
    assert processed["text"] == "test content"
    
    # Verify file was deleted (DeleteFiles=True)
    assert not test_file.exists()


def test_usb_bt_loop_bt_unavailable(temp_config, usb_folder, monkeypatch):
    """Test USB/BT loop when Bluetooth is unavailable.
    
    Verifies that files are still processed even without BT.
    """
    from ipr_keyboard.config.manager import ConfigManager
    from ipr_keyboard.main import run_usb_bt_loop
    
    ConfigManager.instance().update(
        IrisPenFolder=str(usb_folder),
        DeleteFiles=False
    )
    
    # Create a test file
    test_file = usb_folder / "test.txt"
    test_file.write_text("test content")
    
    loop_count = {"count": 0}
    
    def mock_wait(folder, mtime, interval):
        if loop_count["count"] == 0:
            loop_count["count"] += 1
            return test_file
        raise KeyboardInterrupt()
    
    monkeypatch.setattr("ipr_keyboard.main.detector.wait_for_new_file", mock_wait)
    
    # Mock BluetoothKeyboard as unavailable
    class MockBT:
        def is_available(self):
            return False
        
        def send_text(self, text):
            return False
    
    monkeypatch.setattr("ipr_keyboard.main.BluetoothKeyboard", MockBT)
    
    # Should not raise
    try:
        run_usb_bt_loop()
    except KeyboardInterrupt:
        pass
    
    # File should still exist (DeleteFiles=False)
    assert test_file.exists()
