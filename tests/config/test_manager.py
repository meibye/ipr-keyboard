"""Tests for configuration manager.

Tests the AppConfig and ConfigManager classes for loading and updating configuration.
"""

import threading

from ipr_keyboard.config.manager import AppConfig, ConfigManager
from ipr_keyboard.utils.helpers import save_json, load_json


# AppConfig tests

def test_appconfig_defaults():
    """Test default configuration values."""
    cfg = AppConfig()

    assert isinstance(cfg.IrisPenFolders, list)
    assert len(cfg.IrisPenFolders) > 0
    assert cfg.DeleteFiles is True
    assert cfg.Logging is True
    assert cfg.MaxFileSize == 1024 * 1024  # 1MB
    assert cfg.LogPort == 443


def test_appconfig_from_dict():
    """Test creating config from dictionary."""
    data = {
        "IrisPenFolders": ["/custom/path"],
        "DeleteFiles": False,
        "Logging": False,
        "MaxFileSize": 2048,
        "LogPort": 9000,
    }

    cfg = AppConfig.from_dict(data)

    assert cfg.IrisPenFolders == ["/custom/path"]
    assert cfg.DeleteFiles is False
    assert cfg.Logging is False
    assert cfg.MaxFileSize == 2048
    assert cfg.LogPort == 9000


def test_appconfig_from_dict_legacy_single_folder():
    """Test that legacy IrisPenFolder (singular) key is migrated to a list."""
    data = {"IrisPenFolder": "/legacy/path"}

    cfg = AppConfig.from_dict(data)

    assert cfg.IrisPenFolders == ["/legacy/path"]


def test_appconfig_from_dict_partial():
    """Test creating config from partial dictionary."""
    data = {"IrisPenFolders": ["/custom/path"]}

    cfg = AppConfig.from_dict(data)

    assert cfg.IrisPenFolders == ["/custom/path"]
    assert cfg.DeleteFiles is True  # default
    assert cfg.MaxFileSize == 1024 * 1024  # default


def test_appconfig_from_dict_extra_keys():
    """Test that extra keys in dictionary are ignored."""
    data = {
        "IrisPenFolders": ["/path"],
        "UnknownKey": "value",
        "AnotherUnknown": 123,
    }

    cfg = AppConfig.from_dict(data)

    assert cfg.IrisPenFolders == ["/path"]
    assert not hasattr(cfg, "UnknownKey")


def test_appconfig_to_dict():
    """Test converting config to dictionary."""
    cfg = AppConfig(
        IrisPenFolders=["/test"],
        DeleteFiles=False,
        MaxFileSize=500,
    )

    data = cfg.to_dict()

    assert data["IrisPenFolders"] == ["/test"]
    assert data["DeleteFiles"] is False
    assert data["MaxFileSize"] == 500


# ConfigManager tests

def test_config_load_and_update(tmp_path, monkeypatch):
    """Test configuration loading and updating."""
    cfg_file = tmp_path / "config.json"
    save_json(cfg_file, {"IrisPenFolders": ["/tmp/iris"], "DeleteFiles": False})

    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: cfg_file,
    )
    ConfigManager._instance = None

    mgr = ConfigManager()
    cfg = mgr.get()
    assert cfg.IrisPenFolders == ["/tmp/iris"]
    assert cfg.DeleteFiles is False

    mgr.update(DeleteFiles=True, MaxFileSize=1234)
    cfg2 = mgr.get()
    assert cfg2.DeleteFiles is True
    assert cfg2.MaxFileSize == 1234


def test_config_singleton(temp_config, reset_config_manager):
    """Test that ConfigManager uses singleton pattern."""
    mgr1 = ConfigManager.instance()
    mgr2 = ConfigManager.instance()

    assert mgr1 is mgr2


def test_config_get_returns_copy(temp_config):
    """Test that get() returns a copy, not the original."""
    mgr = ConfigManager.instance()
    cfg1 = mgr.get()
    cfg1.IrisPenFolders = ["/modified"]

    cfg2 = mgr.get()
    assert cfg2.IrisPenFolders != ["/modified"]


def test_config_reload(tmp_path, monkeypatch):
    """Test reloading configuration from disk."""
    cfg_file = tmp_path / "config.json"
    save_json(cfg_file, {"IrisPenFolders": ["/original"]})

    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: cfg_file,
    )
    ConfigManager._instance = None

    mgr = ConfigManager()
    cfg1 = mgr.get()
    assert cfg1.IrisPenFolders == ["/original"]

    # Modify the file externally
    save_json(cfg_file, {"IrisPenFolders": ["/modified"]})

    # Reload and verify
    cfg2 = mgr.reload()
    assert cfg2.IrisPenFolders == ["/modified"]


def test_config_missing_file(tmp_path, monkeypatch):
    """Test loading configuration when file doesn't exist."""
    cfg_file = tmp_path / "nonexistent.json"

    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: cfg_file,
    )
    ConfigManager._instance = None

    mgr = ConfigManager()
    cfg = mgr.get()

    # Should use defaults
    assert isinstance(cfg.IrisPenFolders, list)
    assert len(cfg.IrisPenFolders) > 0
    assert cfg.DeleteFiles is True


def test_config_persistence(tmp_path, monkeypatch):
    """Test that updates are persisted to disk."""
    cfg_file = tmp_path / "config.json"
    save_json(cfg_file, {"IrisPenFolders": ["/original"]})

    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: cfg_file,
    )
    ConfigManager._instance = None

    mgr = ConfigManager()
    mgr.update(IrisPenFolders=["/updated"], DeleteFiles=False)

    # Read the file directly
    data = load_json(cfg_file)
    assert data["IrisPenFolders"] == ["/updated"]
    assert data["DeleteFiles"] is False


def test_config_update_ignores_unknown_keys(tmp_path, monkeypatch):
    """Test that update() ignores unknown configuration keys."""
    cfg_file = tmp_path / "config.json"
    save_json(cfg_file, {})

    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: cfg_file,
    )
    ConfigManager._instance = None

    mgr = ConfigManager()
    cfg = mgr.update(UnknownKey="value", IrisPenFolders=["/valid"])

    assert cfg.IrisPenFolders == ["/valid"]
    assert not hasattr(cfg, "UnknownKey")


def test_config_thread_safety(temp_config):
    """Test thread-safe access to configuration."""
    mgr = ConfigManager.instance()
    results = {"reads": [], "errors": []}

    def reader_thread():
        try:
            for _ in range(10):
                cfg = mgr.get()
                results["reads"].append(cfg.IrisPenFolders)
        except Exception as e:  # pragma: no cover - defensive
            results["errors"].append(str(e))

    def writer_thread():
        try:
            for i in range(10):
                mgr.update(MaxFileSize=i * 100)
        except Exception as e:  # pragma: no cover - defensive
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
