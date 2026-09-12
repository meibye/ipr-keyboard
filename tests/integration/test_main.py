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
    
    # Call directly; app.run is mocked so this does not block.
    run_web_server()
    
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
    The loop uses detector.list_files() internally; after processing the file
    (and deleting it) the next iteration finds nothing and calls time.sleep(),
    which we raise as KeyboardInterrupt to exit.
    """
    from ipr_keyboard.config.manager import ConfigManager
    from ipr_keyboard.main import run_usb_bt_loop

    # Point config at our temp folder
    ConfigManager.instance().update(
        IrisPenFolders=[str(usb_folder)],
        DeleteFiles=True,
    )

    # Create a test file
    test_file = usb_folder / "test.txt"
    test_file.write_text("test content")

    processed = {"text": None}

    class MockBT:
        def is_available(self):
            return True

        def send_text(self, text):
            processed["text"] = text
            return True

    monkeypatch.setattr("ipr_keyboard.main.BluetoothKeyboard", MockBT)

    # After the file is processed and deleted the loop finds nothing and
    # calls time.sleep(); raise KeyboardInterrupt there to stop the loop.
    monkeypatch.setattr("ipr_keyboard.main.time.sleep",
                        lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))

    try:
        run_usb_bt_loop()
    except KeyboardInterrupt:
        pass

    assert processed["text"] == "test content"
    assert not test_file.exists()


def test_usb_bt_loop_bt_unavailable(temp_config, usb_folder, monkeypatch):
    """Test USB/BT loop when Bluetooth is unavailable.

    Verifies that files are not deleted when BT is unavailable and DeleteFiles=False.
    After the file is processed (but not deleted), mtime is unchanged so the next
    iteration finds nothing and calls time.sleep(); we raise KeyboardInterrupt there.
    """
    from ipr_keyboard.config.manager import ConfigManager
    from ipr_keyboard.main import run_usb_bt_loop

    ConfigManager.instance().update(
        IrisPenFolders=[str(usb_folder)],
        DeleteFiles=False,
    )

    test_file = usb_folder / "test.txt"
    test_file.write_text("test content")

    class MockBT:
        def is_available(self):
            return False

        def send_text(self, text):
            return False

    monkeypatch.setattr("ipr_keyboard.main.BluetoothKeyboard", MockBT)
    monkeypatch.setattr("ipr_keyboard.main.time.sleep",
                        lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))

    try:
        run_usb_bt_loop()
    except KeyboardInterrupt:
        pass

    assert test_file.exists()


# ---------------------------------------------------------------------------
# Performance metrics instrumentation in the loop
# ---------------------------------------------------------------------------

def _run_loop_once_with_file(usb_folder, monkeypatch, *, metrics_enabled, bt_ok=True):
    """Drive run_usb_bt_loop through exactly one file, then stop it."""
    from ipr_keyboard import metrics
    from ipr_keyboard.config.manager import ConfigManager
    from ipr_keyboard.main import run_usb_bt_loop

    metrics.reset()
    ConfigManager.instance().update(
        IrisPenFolders=[str(usb_folder)],
        DeleteFiles=True,
        MetricsEnabled=metrics_enabled,
    )
    (usb_folder / "scan.txt").write_text("hello world")

    class MockBT:
        def is_available(self):
            return True

        def send_text(self, text):
            return bt_ok

    monkeypatch.setattr("ipr_keyboard.main.BluetoothKeyboard", MockBT)
    monkeypatch.setattr("ipr_keyboard.main.time.sleep",
                        lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        run_usb_bt_loop()
    except KeyboardInterrupt:
        pass
    return metrics.snapshot()


def test_loop_records_pipeline_kpis_when_enabled(temp_config, usb_folder, monkeypatch):
    snap = _run_loop_once_with_file(usb_folder, monkeypatch, metrics_enabled=True)
    k = snap["kpis"]
    assert snap["enabled"] is True
    assert k["detect_latency_ms"]["count"] == 1
    assert k["read_ms"]["count"] == 1
    assert k["send_ms"]["count"] == 1
    assert k["e2e_latency_ms"]["count"] == 1
    # "hello world" is 11 chars
    assert k["send_ms_per_char"]["count"] == 1
    # Timing sanity: the file was written moments before detection.
    assert 0 <= k["detect_latency_ms"]["last"] < 10_000
    assert k["e2e_latency_ms"]["last"] >= k["detect_latency_ms"]["last"]


def test_loop_records_nothing_when_disabled(temp_config, usb_folder, monkeypatch):
    """The whole point: a production device with the flag off pays nothing."""
    snap = _run_loop_once_with_file(usb_folder, monkeypatch, metrics_enabled=False)
    assert snap["enabled"] is False
    assert all(v["count"] == 0 for v in snap["kpis"].values())


def test_loop_failed_send_records_no_send_kpis(temp_config, usb_folder, monkeypatch):
    """A failed BT send must not be counted as a successful end-to-end delivery."""
    snap = _run_loop_once_with_file(usb_folder, monkeypatch, metrics_enabled=True, bt_ok=False)
    k = snap["kpis"]
    assert k["detect_latency_ms"]["count"] == 1
    assert k["send_ms"]["count"] == 0
    assert k["e2e_latency_ms"]["count"] == 0


def test_loop_applies_toggle_from_config_each_iteration(temp_config, usb_folder, monkeypatch):
    """Turning the flag on in config must take effect without a restart."""
    from ipr_keyboard import metrics
    metrics.set_enabled(False)
    _run_loop_once_with_file(usb_folder, monkeypatch, metrics_enabled=True)
    assert metrics.is_enabled() is True
