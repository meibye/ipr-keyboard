"""Configuration management module.

Provides thread-safe configuration management with JSON file persistence
and singleton pattern for application-wide config access.

The configuration manager automatically synchronizes the KeyboardBackend setting
with /etc/ipr-keyboard/backend to ensure system services and application config
stay in sync.
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..utils.helpers import config_path, load_json, save_json
from ..utils.backend_sync import read_backend_file, write_backend_file
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
        KeyboardBackend: Backend used by the Bluetooth keyboard helper:
                         "uinput" (local virtual keyboard) or "ble" (BLE HID GATT).
    """

    IrisPenFolder: str = "/mnt/irispen"
    DeleteFiles: bool = True
    Logging: bool = True
    MaxFileSize: int = 1024 * 1024
    LogPort: int = 8080
    KeyboardBackend: str = "uinput"  # "uinput" or "ble"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create an AppConfig instance from a dictionary."""
        base = cls()
        for field in asdict(base).keys():
            if field in data:
                setattr(base, field, data[field])

        # Normalise KeyboardBackend
        kb = getattr(base, "KeyboardBackend", "uinput")
        if kb not in ("uinput", "ble"):
            kb = "uinput"
        base.KeyboardBackend = kb

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
        """Initialise the configuration manager.
        
        On initialization, the backend selection is synchronized:
        1. If /etc/ipr-keyboard/backend exists, it takes precedence (system-level setting)
        2. Otherwise, the KeyboardBackend from config.json is used as the initial value
        3. The backend file is updated to match the config if needed
        """
        self._path: Path = path or config_path()
        self._cfg_lock = threading.RLock()
        raw = load_json(self._path)
        self._cfg = AppConfig.from_dict(raw)
        
        # Synchronize backend selection on startup
        self._sync_backend_on_init()

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
        
        If KeyboardBackend is updated, the /etc/ipr-keyboard/backend file is
        automatically synchronized with the new value.
        """
        with self._cfg_lock:
            backend_changed = False
            old_backend = self._cfg.KeyboardBackend
            
            for key, value in kwargs.items():
                if hasattr(self._cfg, key):
                    setattr(self._cfg, key, value)
                    if key == "KeyboardBackend" and value != old_backend:
                        backend_changed = True
            
            save_json(self._path, self._cfg.to_dict())
            
            # Sync backend file if backend was changed
            if backend_changed:
                self._sync_backend_file()
            
            return self.get()

    def reload(self) -> AppConfig:
        """Reload configuration from disk and return the new config."""
        with self._cfg_lock:
            data = load_json(self._path)
            self._cfg = AppConfig.from_dict(data)
            return self.get()
    
    def _sync_backend_on_init(self) -> None:
        """Synchronize backend selection on initialization.
        
        The /etc/ipr-keyboard/backend file takes precedence if it exists.
        Otherwise, we ensure the backend file matches the config.
        """
        backend_from_file = read_backend_file()
        
        if backend_from_file is not None and backend_from_file != self._cfg.KeyboardBackend:
            # System-level setting takes precedence
            logger.info(
                "Backend file (/etc/ipr-keyboard/backend) contains '%s', "
                "updating config.json from '%s'",
                backend_from_file,
                self._cfg.KeyboardBackend
            )
            self._cfg.KeyboardBackend = backend_from_file
            save_json(self._path, self._cfg.to_dict())
        elif backend_from_file is None:
            # No backend file exists, write current config value
            logger.info(
                "No backend file found, creating /etc/ipr-keyboard/backend with '%s'",
                self._cfg.KeyboardBackend
            )
            self._sync_backend_file()
    
    def _sync_backend_file(self) -> None:
        """Write the current backend selection to /etc/ipr-keyboard/backend."""
        success = write_backend_file(self._cfg.KeyboardBackend)
        if success:
            logger.info(
                "Synchronized backend file: /etc/ipr-keyboard/backend = '%s'",
                self._cfg.KeyboardBackend
            )
        else:
            logger.warning(
                "Failed to write backend file /etc/ipr-keyboard/backend "
                "(insufficient permissions or directory doesn't exist)"
            )
