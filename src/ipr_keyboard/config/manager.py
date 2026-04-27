"""Configuration management module.

Provides thread-safe configuration management with JSON file persistence
and singleton pattern for application-wide config access.
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.helpers import config_path, load_json, save_json
from ..logging.logger import get_logger

logger = get_logger()

VERSION = '2026-04-12 19:40:39'

def log_version_info():
    logger.info(f"==== ipr_keyboard.config.manager VERSION: {VERSION} ====")


@dataclass
class AppConfig:
    """Application configuration dataclass.

    Attributes:
        IrisPenFolders: List of folder paths to monitor for scanned text files from IrisPen.
        DeleteFiles: Whether to delete files after processing them.
        Logging: Whether logging is enabled.
        MaxFileSize: Maximum file size in bytes to process (default: 1MB = 1048576 bytes).
        LogPort: Port number for the web/log server.
        LogLevel: Logging level (DEBUG, INFO, WARNING, ERROR).
        PairingTimeoutSeconds: Seconds Bluetooth stays in pairing mode.
        ReadTimeoutSeconds: Max seconds to wait when reading a pen file.
        PollIntervalSeconds: Seconds between folder polls for new files.
        StatusIntervalSeconds: Seconds between SSE status push events.
        NetworkMode: Network configuration mode ("dhcp" or "static").
        StaticIP: Static IP address (used when NetworkMode is "static").
        StaticNetmask: Static netmask (used when NetworkMode is "static").
        StaticGateway: Static gateway (used when NetworkMode is "static").
    """

    IrisPenFolders: List[str] = None  # type: ignore[assignment]
    DeleteFiles: bool = True
    Logging: bool = True
    MaxFileSize: int = 1024 * 1024
    LogPort: int = 8080
    LogLevel: str = "INFO"
    PairingTimeoutSeconds: int = 120
    ReadTimeoutSeconds: int = 10
    PollIntervalSeconds: float = 1.0
    StatusIntervalSeconds: int = 5
    NetworkMode: str = "dhcp"
    StaticIP: str = ""
    StaticNetmask: str = "255.255.255.0"
    StaticGateway: str = ""

    def __post_init__(self) -> None:
        if self.IrisPenFolders is None:
            self.IrisPenFolders = [
                "/mnt/irispen/Intern delt lagerplads/Scan text and save"
            ]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create an AppConfig instance from a dictionary."""
        base = cls()
        for field in asdict(base).keys():
            if field in data:
                setattr(base, field, data[field])
        # Migrate legacy single-string IrisPenFolder key
        if "IrisPenFolders" not in data and "IrisPenFolder" in data:
            base.IrisPenFolders = [data["IrisPenFolder"]]
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
