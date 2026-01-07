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
from ..logging.logger import get_logger

logger = get_logger()


@dataclass
class AppConfig:
    """Application configuration dataclass.

    Attributes:
        IrisPenFolder: Path to the folder containing scanned text files from IrisPen.
        DeleteFiles: Whether to delete files after processing them.
        Logging: Whether logging is enabled.
        MaxFileSize: Maximum file size in bytes to process (default: 1MB = 1048576 bytes).
        LogPort: Port number for the web/log server.
    """

    IrisPenFolder: str = "/mnt/irispen"
    DeleteFiles: bool = True
    Logging: bool = True
    MaxFileSize: int = 1024 * 1024
    LogPort: int = 8080

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create an AppConfig instance from a dictionary."""
        base = cls()
        for field in asdict(base).keys():
            if field in data:
                setattr(base, field, data[field])

        return base

    def to_dict(self) -> Dict[str, Any]:
        """Convert the AppConfig to a dictionary."""
        return asdict(self)


class ConfigManager:
    """Thread-safe configuration manager with JSON backing.

    Implements a simple singleton so the whole application shares the same
    loaded configuration instance. All access is protected by a re-entrant lock.
    """

    _instance: Optional["ConfigManager"] = None
    _lock = threading.Lock()

    def __init__(self, path: Optional[Path] = None) -> None:
        """Initialise the configuration manager."""
        self._path: Path = path or config_path()
        self._cfg_lock = threading.RLock()
        raw = load_json(self._path)
        self._cfg = AppConfig.from_dict(raw)

    @classmethod
    def instance(cls) -> "ConfigManager":
        """Get the singleton ConfigManager instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = ConfigManager()
            return cls._instance

    def get(self) -> AppConfig:
        """Return a shallow copy of the current configuration."""
        with self._cfg_lock:
            return AppConfig.from_dict(self._cfg.to_dict())

    def update(self, **kwargs: Any) -> AppConfig:
        """Update configuration values and persist them to disk.

        Only known AppConfig fields are updated; unknown keys are ignored.
        """
        with self._cfg_lock:
            for key, value in kwargs.items():
                if hasattr(self._cfg, key):
                    setattr(self._cfg, key, value)
            
            save_json(self._path, self._cfg.to_dict())
            
            return self.get()

    def reload(self) -> AppConfig:
        """Reload configuration from disk and return the new config."""
        with self._cfg_lock:
            data = load_json(self._path)
            self._cfg = AppConfig.from_dict(data)
            return self.get()
