"""Tests for configuration manager.

Tests the AppConfig and ConfigManager classes for loading and updating configuration.
"""
import json
import threading
from pathlib import Path

from ipr_keyboard.config.manager import AppConfig, ConfigManager
from ipr_keyboard.utils.helpers import save_json, load_json


# AppConfig tests

def test_appconfig_defaults():
    """Test default configuration values.
    
    Verifies that AppConfig has sensible defaults.
    """
    cfg = AppConfig()
    
    assert cfg.IrisPenFolder == "/mnt/irispen"
    assert cfg.DeleteFiles is True
    assert cfg.Logging is True
    assert cfg.MaxFileSize == 1024 * 1024  # 1MB
    assert cfg.LogPort == 8080
    assert cfg.KeyboardBackend == "uinput"


def test_appconfig_from_dict():
    """Test creating config from dictionary.
    
    Verifies that AppConfig can be created from a dict.
    """
    data = {
        "IrisPenFolder": "/custom/path",
        "DeleteFiles": False,
        "Logging": False,
        "MaxFileSize": 2048,
        "LogPort": 9000,
        "KeyboardBackend": "ble"
    }
    
    cfg = AppConfig.from_dict(data)
    
    assert cfg.IrisPenFolder == "/custom/path"
    assert cfg.DeleteFiles is False
    assert cfg.Logging is False
    assert cfg.MaxFileSize == 2048
    assert cfg.LogPort == 9000
    assert cfg.KeyboardBackend == "ble"


def test_appconfig_from_dict_partial():
    """Test creating config from partial dictionary.
    
    Verifies that missing keys use defaults.
    """
    data = {"IrisPenFolder": "/custom/path"}
    
    cfg = AppConfig.from_dict(data)
    
    assert cfg.IrisPenFolder == "/custom/path"
    assert cfg.DeleteFiles is True  # default
    assert cfg.MaxFileSize == 1024 * 1024  # default


def test_appconfig_from_dict_extra_keys():
    """Test that extra keys in dictionary are ignored.
    
    Verifies that unknown keys don't cause errors.
    """
    data = {
        "IrisPenFolder": "/path",
        "UnknownKey": "value",
        "AnotherUnknown": 123
    }
    
    cfg = AppConfig.from_dict(data)
    
    assert cfg.IrisPenFolder == "/path"
    assert not hasattr(cfg, "UnknownKey")


def test_appconfig_to_dict():
    """Test converting config to dictionary.
    
    Verifies that AppConfig can be serialized to dict.
    """
    cfg = AppConfig(
        IrisPenFolder="/test",
        DeleteFiles=False,
        MaxFileSize=500
    )
    
    data = cfg.to_dict()
    
    assert data["IrisPenFolder"] == "/test"
    assert data["DeleteFiles"] is False
    assert data["MaxFileSize"] == 500


def test_appconfig_keyboard_backend_normalization():
    """Test that invalid backend values are normalized.
    
    Verifies that invalid KeyboardBackend values default to 'uinput'.
    """
    # Valid values
    cfg_uinput = AppConfig.from_dict({"KeyboardBackend": "uinput"})
    assert cfg_uinput.KeyboardBackend == "uinput"
    
    cfg_ble = AppConfig.from_dict({"KeyboardBackend": "ble"})
    assert cfg_ble.KeyboardBackend == "ble"
    
    # Invalid value should normalize to uinput
    cfg_invalid = AppConfig.from_dict({"KeyboardBackend": "invalid"})
    assert cfg_invalid.KeyboardBackend == "uinput"


# ConfigManager tests

def test_config_load_and_update(tmp_path, monkeypatch):
    """Test configuration loading and updating.
    
    Verifies that ConfigManager correctly loads config from JSON,
    retrieves values, and updates them persistently.
    """
    cfg_file = tmp_path / "config.json"
    save_json(cfg_file, {"IrisPenFolder": "/tmp/iris", "DeleteFiles": False})

    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: cfg_file,
    )

    mgr = ConfigManager()
    cfg = mgr.get()
    assert cfg.IrisPenFolder == "/tmp/iris"
    assert cfg.DeleteFiles is False

    mgr.update(DeleteFiles=True, MaxFileSize=1234)
    cfg2 = mgr.get()
    assert cfg2.DeleteFiles is True
    assert cfg2.MaxFileSize == 1234


def test_config_singleton(temp_config, reset_config_manager):
    """Test that ConfigManager uses singleton pattern.
    
    Verifies that instance() returns the same object.
    """
    mgr1 = ConfigManager.instance()
    mgr2 = ConfigManager.instance()
    
    assert mgr1 is mgr2


def test_config_get_returns_copy(temp_config):
    """Test that get() returns a copy, not the original.
    
    Verifies that modifying the returned config doesn't affect the original.
    """
    mgr = ConfigManager.instance()
    cfg1 = mgr.get()
    cfg1.IrisPenFolder = "/modified"
    
    cfg2 = mgr.get()
    assert cfg2.IrisPenFolder != "/modified"


def test_config_reload(tmp_path, monkeypatch):
    """Test reloading configuration from disk.
    
    Verifies that reload() re-reads the config file.
    """
    cfg_file = tmp_path / "config.json"
    save_json(cfg_file, {"IrisPenFolder": "/original"})

    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: cfg_file,
    )

    mgr = ConfigManager()
    cfg1 = mgr.get()
    assert cfg1.IrisPenFolder == "/original"
    
    # Modify the file externally
    save_json(cfg_file, {"IrisPenFolder": "/modified"})
    
    # Reload and verify
    cfg2 = mgr.reload()
    assert cfg2.IrisPenFolder == "/modified"


def test_config_missing_file(tmp_path, monkeypatch):
    """Test loading configuration when file doesn't exist.
    
    Verifies that default values are used when no config file exists.
    """
    cfg_file = tmp_path / "nonexistent.json"

    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: cfg_file,
    )

    mgr = ConfigManager()
    cfg = mgr.get()
    
    # Should use defaults
    assert cfg.IrisPenFolder == "/mnt/irispen"
    assert cfg.DeleteFiles is True


def test_config_persistence(tmp_path, monkeypatch):
    """Test that updates are persisted to disk.
    
    Verifies that update() writes changes to the config file.
    """
    cfg_file = tmp_path / "config.json"
    save_json(cfg_file, {"IrisPenFolder": "/original"})

    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: cfg_file,
    )

    mgr = ConfigManager()
    mgr.update(IrisPenFolder="/updated", DeleteFiles=False)
    
    # Read the file directly
    data = load_json(cfg_file)
    assert data["IrisPenFolder"] == "/updated"
    assert data["DeleteFiles"] is False


def test_config_update_ignores_unknown_keys(tmp_path, monkeypatch):
    """Test that update() ignores unknown configuration keys.
    
    Verifies that invalid keys don't cause errors.
    """
    cfg_file = tmp_path / "config.json"
    save_json(cfg_file, {})

    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: cfg_file,
    )

    mgr = ConfigManager()
    cfg = mgr.update(UnknownKey="value", IrisPenFolder="/valid")
    
    assert cfg.IrisPenFolder == "/valid"
    assert not hasattr(cfg, "UnknownKey")


def test_config_thread_safety(temp_config):
    """Test thread-safe access to configuration.
    
    Verifies that concurrent access doesn't cause issues.
    """
    mgr = ConfigManager.instance()
    results = {"reads": [], "errors": []}
    
    def reader_thread():
        try:
            for _ in range(10):
                cfg = mgr.get()
                results["reads"].append(cfg.IrisPenFolder)
        except Exception as e:
            results["errors"].append(str(e))
    
    def writer_thread():
        try:
            for i in range(10):
                mgr.update(MaxFileSize=i * 100)
        except Exception as e:
            results["errors"].append(str(e))
    
    threads = [
        threading.Thread(target=reader_thread),
        threading.Thread(target=reader_thread),
        threading.Thread(target=writer_thread),
    ]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert len(results["errors"]) == 0, f"Errors occurred: {results['errors']}"
    assert len(results["reads"]) == 20


# Backend synchronization tests

def test_config_backend_sync_on_init_no_file(tmp_path, monkeypatch):
    """Test that ConfigManager creates backend file if it doesn't exist."""
    cfg_file = tmp_path / "config.json"
    backend_file = tmp_path / "backend"
    save_json(cfg_file, {"KeyboardBackend": "ble"})

    monkeypatch.setattr("ipr_keyboard.config.manager.config_path", lambda: cfg_file)
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))

    mgr = ConfigManager()
    cfg = mgr.get()

    assert cfg.KeyboardBackend == "ble"
    assert backend_file.exists()
    assert backend_file.read_text().strip() == "ble"


def test_config_backend_sync_on_init_file_takes_precedence(tmp_path, monkeypatch):
    """Test that backend file takes precedence over config.json on init."""
    cfg_file = tmp_path / "config.json"
    backend_file = tmp_path / "backend"
    save_json(cfg_file, {"KeyboardBackend": "uinput"})
    backend_file.write_text("ble\n")

    monkeypatch.setattr("ipr_keyboard.config.manager.config_path", lambda: cfg_file)
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))

    mgr = ConfigManager()
    cfg = mgr.get()

    # Backend file should win
    assert cfg.KeyboardBackend == "ble"
    # Config file should be updated
    data = load_json(cfg_file)
    assert data["KeyboardBackend"] == "ble"


def test_config_backend_sync_on_init_matching_values(tmp_path, monkeypatch):
    """Test that no updates occur when values already match."""
    cfg_file = tmp_path / "config.json"
    backend_file = tmp_path / "backend"
    save_json(cfg_file, {"KeyboardBackend": "ble"})
    backend_file.write_text("ble\n")

    monkeypatch.setattr("ipr_keyboard.config.manager.config_path", lambda: cfg_file)
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))

    mgr = ConfigManager()
    cfg = mgr.get()

    assert cfg.KeyboardBackend == "ble"
    assert backend_file.read_text().strip() == "ble"


def test_config_backend_sync_on_update(tmp_path, monkeypatch):
    """Test that updating KeyboardBackend syncs to backend file."""
    cfg_file = tmp_path / "config.json"
    backend_file = tmp_path / "backend"
    save_json(cfg_file, {"KeyboardBackend": "uinput"})
    backend_file.write_text("uinput\n")

    monkeypatch.setattr("ipr_keyboard.config.manager.config_path", lambda: cfg_file)
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))

    mgr = ConfigManager()
    cfg = mgr.update(KeyboardBackend="ble")

    assert cfg.KeyboardBackend == "ble"
    assert backend_file.read_text().strip() == "ble"


def test_config_backend_update_other_fields_no_sync(tmp_path, monkeypatch):
    """Test that updating non-backend fields doesn't trigger sync."""
    cfg_file = tmp_path / "config.json"
    backend_file = tmp_path / "backend"
    save_json(cfg_file, {"KeyboardBackend": "ble", "DeleteFiles": True})
    backend_file.write_text("ble\n")

    monkeypatch.setattr("ipr_keyboard.config.manager.config_path", lambda: cfg_file)
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))

    mgr = ConfigManager()
    original_content = backend_file.read_text()
    
    mgr.update(DeleteFiles=False)
    
    # Backend file should remain unchanged
    assert backend_file.read_text() == original_content


def test_config_backend_sync_permission_error(tmp_path, monkeypatch, caplog):
    """Test that ConfigManager handles permission errors gracefully."""
    cfg_file = tmp_path / "config.json"
    backend_file = tmp_path / "readonly" / "backend"
    save_json(cfg_file, {"KeyboardBackend": "ble"})

    monkeypatch.setattr("ipr_keyboard.config.manager.config_path", lambda: cfg_file)
    monkeypatch.setattr("ipr_keyboard.utils.backend_sync.BACKEND_FILE_PATH", str(backend_file))
    
    # Make parent directory non-writable
    backend_file.parent.mkdir(parents=True)
    backend_file.parent.chmod(0o444)
    
    try:
        mgr = ConfigManager()
        cfg = mgr.get()
        # Should still work, just log warning
        assert cfg.KeyboardBackend == "ble"
    finally:
        # Restore permissions for cleanup
        backend_file.parent.chmod(0o755)
