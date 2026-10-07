"""Configuration management module.

Provides thread-safe configuration management with JSON file persistence
and singleton pattern for application-wide config access.
"""

from __future__ import annotations

import os
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.helpers import config_default_path, config_path, load_json, save_json, seed_from_default
from ..logging.logger import get_logger

logger = get_logger()

VERSION = '2026-04-12 19:40:39'


def _provisioned_typing_delay(default: int = 20) -> int:
    """The typing speed provisioning chose: BT_KEY_DELAY_MS.

    There used to be two defaults that disagreed.  The BLE daemon starts at
    BT_KEY_DELAY_MS from /opt/ipr_common.env (12 ms in the shipped example),
    but this app re-applies TypingDelayMs about once a second and its default
    was a hard-coded 20 -- so every fresh install silently typed at 25
    characters a second instead of the ~40 provisioning asked for, and nothing
    said so.  The app's default now IS the provisioned value; a speed chosen
    in Settings is saved to config.json and still wins.

    ipr_keyboard.service does not load the env file, so it is read directly
    (it belongs to the app user).  Read once, at import: from_dict() builds a
    default config on every get(), about once a second.
    """
    raw = os.environ.get("BT_KEY_DELAY_MS")
    if raw is None:
        env_file = Path(os.environ.get("IPR_COMMON_ENV", "/opt/ipr_common.env"))
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                key, sep, value = line.strip().partition("=")
                if sep and key == "BT_KEY_DELAY_MS":
                    raw = value.strip().strip('"').strip("'")
        except OSError:
            pass
    try:
        ms = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return ms if 1 <= ms <= 200 else default


_PROVISIONED_TYPING_DELAY_MS = _provisioned_typing_delay()

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
        MetricsEnabled: Record performance KPIs (latency, send time, boot time)
            and expose them at /api/metrics. Off by default: when off the
            instrumentation costs one boolean check per event.
    """

    IrisPenFolders: List[str] = None  # type: ignore[assignment]
    DeleteFiles: bool = True
    Logging: bool = True
    MaxFileSize: int = 1024 * 1024
    LogPort: int = 443
    LogLevel: str = "INFO"
    PairingTimeoutSeconds: int = 120
    ReadTimeoutSeconds: int = 10
    PollIntervalSeconds: float = 1.0
    StatusIntervalSeconds: int = 5
    NetworkMode: str = "dhcp"
    StaticIP: str = ""
    StaticNetmask: str = "255.255.255.0"
    StaticGateway: str = ""
    # TLS certificate paths — read by main.py; not surfaced via the config API.
    TlsCertFile: str = "/etc/ipr-ssl/server.crt"
    TlsKeyFile: str = "/etc/ipr-ssl/server.key"
    # GPIO — reed switch and RGB LED (BCM pin numbers).
    # Set GpioEnabled: false to disable on non-Pi hosts or when no hardware is wired.
    GpioEnabled: bool = True
    GpioReedPin: int = 27
    GpioLedRPin: int = 22
    GpioLedGPin: int = 23
    GpioLedBPin: int = 24
    GpioLedIdleSeconds: int = 30
    # OLED status display (SSD1306 128x64 on I2C).  Auto-detected: the app
    # runs without it when nothing answers at OledI2cAddress.  The idle
    # window is GpioLedIdleSeconds (the display follows the LED phase).
    OledEnabled: bool = True
    OledI2cBus: int = 1
    OledI2cAddress: int = 0x3C
    OledContrast: int = 128  # 0-255
    OledRotate: int = 0  # 0 or 180
    OledSendHoldSeconds: int = 10  # keep SENT / FAILED on screen this long
    OledMarqueeFps: int = 8  # redraw rate while a long line rolls (6 on a Zero W)
    # How long the panel stays on after the last interaction, in minutes.
    # Chosen from the magnet menu (Display -> Timeout); 5, 15, 30 or 60.
    # Dimming is unaffected: the contrast still drops after five minutes
    # on, which is what protects the panel from burn-in.
    OledDisplayTimeoutMinutes: int = 30
    # How many times the recovery credentials may be shown on the panel
    # per boot.  Each reveal needs a confirming tap; once the credentials
    # have actually been used they are never shown again.
    # Total reveals allowed for one hotspot key -- counted on disk, so a
    # reboot does not hand out a fresh allowance.  Generating a new key
    # starts a new allowance (see docs/hardware/oled-display.md).
    RecoveryRevealLimit: int = 10
    # How long the magnet menu waits before closing itself: 20, 60, 120
    # or 300 seconds, chosen from Display -> Menu timeout.
    MenuTimeoutSeconds: int = 20
    # Pause after each HID report, in milliseconds, which is what sets the
    # typing speed: two reports per character, so 1000 / (2 * value)
    # characters a second -- 25/s at 20 ms.  It is the single largest cost
    # of a send.  The floor is the BLE connection interval the PC
    # negotiates (7.5-30 ms on Windows); below that the host drops or
    # reorders keystrokes, which is far worse than slow, so lower it by
    # measurement with Debug -> Typing speed trial.
    # See docs/operations/performance.md.  Defaults to the provisioned
    # BT_KEY_DELAY_MS, so the app and the daemon start out agreeing.
    TypingDelayMs: int = _PROVISIONED_TYPING_DELAY_MS
    # Performance KPIs. Off by default; see ipr_keyboard/metrics.py.
    MetricsEnabled: bool = False

    def __post_init__(self) -> None:
        if self.IrisPenFolders is None:
            # "*" stands for the pen's storage folder, whose name follows the
            # pen's UI language (Intern delt lagerplads / Internal shared storage).
            self.IrisPenFolders = ["/mnt/irispen/*/Scan text and save"]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create an AppConfig instance from a dictionary."""
        # Migrate pre-September-2026 configs that hard-coded the Danish storage
        # folder name; the wildcard form survives a change of the pen's language.
        folders = data.get("IrisPenFolders")
        if isinstance(folders, list):
            data = dict(data)
            data["IrisPenFolders"] = [
                (f.replace("/mnt/irispen/Intern delt lagerplads/", "/mnt/irispen/*/", 1)
                 if isinstance(f, str) else f)
                for f in folders
            ]
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
        seed_from_default(self._path, config_default_path())
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
