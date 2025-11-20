from __future__ import annotations

import threading
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

from ..utils.helpers import config_path, load_json, save_json


@dataclass
class AppConfig:
    IrisPenFolder: str = "/mnt/irispen"    # folder with scanned text files
    DeleteFiles: bool = True
    Logging: bool = True
    MaxFileSize: int = 1024 * 1024        # bytes
    LogPort: int = 8080                   # for web/log server

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        base = cls()
        for field in asdict(base).keys():
            if field in data:
                setattr(base, field, data[field])
        return base

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfigManager:
    """Thread-safe configuration manager with JSON backing."""

    _instance: Optional["ConfigManager"] = None
    _lock = threading.Lock()

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or config_path()
        self._cfg = AppConfig.from_dict(load_json(self._path))
        self._cfg_lock = threading.RLock()

    @classmethod
    def instance(cls) -> "ConfigManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = ConfigManager()
            return cls._instance

    def get(self) -> AppConfig:
        with self._cfg_lock:
            # return a shallow copy to avoid accidental mutation
            return AppConfig.from_dict(self._cfg.to_dict())

    def update(self, **kwargs: Any) -> AppConfig:
        with self._cfg_lock:
            for k, v in kwargs.items():
                if hasattr(self._cfg, k):
                    setattr(self._cfg, k, v)
            save_json(self._path, self._cfg.to_dict())
            return self.get()

    def reload(self) -> AppConfig:
        with self._cfg_lock:
            data = load_json(self._path)
            self._cfg = AppConfig.from_dict(data)
            return self.get()
