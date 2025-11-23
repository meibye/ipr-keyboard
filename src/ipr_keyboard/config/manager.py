"""Configuration management module.

Provides thread-safe configuration management with JSON file persistence
and singleton pattern for application-wide config access.
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..utils.helpers import config_path, load_json, save_json


@dataclass
class AppConfig:
    """Application configuration dataclass.

    Attributes:
        IrisPenFolder: Path to the folder containing scanned text files from IrisPen.
        DeleteFiles: Whether to delete files after processing them.
        Logging: Whether logging is enabled.
        MaxFileSize: Maximum file size in bytes to process (default: 1MB = 1048576 bytes).
        LogPort: Port number for the web/log server.
        KeyboardBackend: select keyboard backend, either "uinput" or "ble". uinput is for USB keyboards, ble is for Bluetooth keyboards.
    """

    IrisPenFolder: str = "/mnt/irispen"  # folder with scanned text files
    DeleteFiles: bool = True
    Logging: bool = True
    MaxFileSize: int = 1024 * 1024  # bytes
    LogPort: int = 8080  # for web/log server
    KeyboardBackend: str = "uinput"  # "uinput" or "ble"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create an AppConfig instance from a dictionary.

        Args:
            data: Dictionary containing configuration key-value pairs.

        Returns:
            AppConfig instance with values from the dictionary, using defaults
            for any missing keys.
        """
        base = cls()
        for field in asdict(base).keys():
            if field in data:
                setattr(base, field, data[field])
        return base

    def to_dict(self) -> Dict[str, Any]:
        """Convert the AppConfig to a dictionary.

        Returns:
            Dictionary representation of the configuration.
        """
        return asdict(self)


class ConfigManager:
    """Thread-safe configuration manager with JSON backing.

    Implements the singleton pattern to provide a single, application-wide
    configuration instance. All operations are thread-safe.

    Attributes:
        _instance: Singleton instance of ConfigManager.
        _lock: Class-level lock for singleton instance creation.
    """

    _instance: Optional["ConfigManager"] = None
    _lock = threading.Lock()

    def __init__(self, path: Optional[Path] = None) -> None:
        """Initialize the configuration manager.

        Args:
            path: Path to the config JSON file. If None, uses the default
                path from config_path().
        """
        self._path = path or config_path()
        self._cfg = AppConfig.from_dict(load_json(self._path))
        self._cfg_lock = threading.RLock()

    @classmethod
    def instance(cls) -> "ConfigManager":
        """Get the singleton ConfigManager instance.

        Creates the instance on first call, subsequent calls return the same instance.

        Returns:
            The singleton ConfigManager instance.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = ConfigManager()
            return cls._instance

    def get(self) -> AppConfig:
        """Get a copy of the current configuration.

        Returns:
            A shallow copy of the current AppConfig to avoid accidental mutation.
        """
        with self._cfg_lock:
            # return a shallow copy to avoid accidental mutation
            return AppConfig.from_dict(self._cfg.to_dict())

    def update(self, **kwargs: Any) -> AppConfig:
        """Update configuration values and persist to disk.

        Args:
            **kwargs: Configuration key-value pairs to update. Only existing
                configuration fields will be updated.

        Returns:
            Updated AppConfig instance.
        """
        with self._cfg_lock:
            for k, v in kwargs.items():
                if hasattr(self._cfg, k):
                    setattr(self._cfg, k, v)
            save_json(self._path, self._cfg.to_dict())
            return self.get()

    def reload(self) -> AppConfig:
        """Reload configuration from disk.

        Returns:
            Reloaded AppConfig instance.
        """
        with self._cfg_lock:
            data = load_json(self._path)
            self._cfg = AppConfig.from_dict(data)
            return self.get()
