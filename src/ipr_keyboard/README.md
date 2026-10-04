# src/ipr_keyboard/

Python application package for `ipr-keyboard`.

## Package Layout

| Path | Role |
|---|---|
| `main.py` | Entry point: web thread, the USB→Bluetooth loop, the LED/menu thread and the panel |
| `transmission.py` | Shared send state (idle / sending / success / failed) and the live character count the panel and dashboard both read |
| `delivery.py` | Which scans have already been delivered, by `name\|mtime\|size`, so a restart neither re-types nor strands a file |
| `metrics.py` | Performance KPIs — a bounded ring buffer, off unless `MetricsEnabled` |
| `keydelay.py` | The typing speed, handed to the BLE daemon at runtime (no restart, no re-pairing) |
| `bt_progress.py` | How far the BLE daemon has got through typing; spans its per-line drains |
| `bt_link.py` | Which PCs are paired, published by the daemon, so the panel can say whose move it is |
| `gpio_monitor.py` | Reed switch and RGB LED: the debounced press, the phases, the privileged actions |
| `menu.py` | The magnet menu as a pure state machine — no hardware, no clock of its own |
| `recovery.py` | Hotspot and dashboard credentials for the panel, with a disk-counted reveal limit |
| `oled/manager.py` | The panel's thread: builds a `Snapshot`, renders it, honours the display timeout |
| `oled/screens.py` | `Snapshot` → `Screen`, pure data; every word the panel shows is decided here |
| `oled/render.py` | `Screen` → 128×64 frame: layout, fonts, icons, marquee, progress bar |
| `oled/ssd1306.py` | The I²C panel itself, and probing for its absence |
| `bluetooth/keyboard.py` | Wrapper around `/usr/local/bin/bt_kb_send`, waiting for the typing to finish |
| `config/manager.py` | `AppConfig` + singleton `ConfigManager` |
| `config/web.py` | Flask blueprint for `/config/` |
| `logging/logger.py` | Rotating file logger setup (256 KB × 6) |
| `logging/web.py` | Flask blueprint for `/logs/` |
| `usb/detector.py` | File listing/new-file polling, and pen presence |
| `usb/reader.py` | Size-capped file reading |
| `usb/deleter.py` | File deletion helpers |
| `usb/mtp_sync.py` | MTP → cache sync utility + CLI |
| `utils/helpers.py` | Project/config path and JSON helpers |
| `web/server.py` | Flask app factory, legacy HTML endpoints, and dashboard root |
| `web/api.py` | `/api/` Blueprint — dashboard JSON API (all `/api/*` routes) |
| `web/setup.py` | The setup portal served on the hotspot |
| `web/auth.py` | Dashboard accounts (`users.json`), hashed |
| `web/templates/dashboard.html` | Image-first SPA dashboard (primary UI) |
| `web/templates/` | Legacy HTML templates (status, config, logs, pairing) and the setup portal |
| `web/static/` | SVG icons, the device-flow illustration, and `ipr.css` |

## Runtime Model

One process, several threads:

- **The main loop** polls the configured folders, reads a new scan, sends it
  through `BluetoothKeyboard`, and deletes it once the text has actually been
  typed. It re-applies `MetricsEnabled` and `TypingDelayMs` each iteration, so
  a dashboard change takes effect without a restart.
- **The web server** serves the dashboard SPA at `/`, the JSON API under
  `/api/` (see `web/api.py` and `docs/ui/api-contract.md`), and the setup
  portal on the hotspot.
- **`GpioMonitor`** ticks at 20 Hz: it debounces the reed switch, drives the
  RGB LED, and owns the magnet menu.
- **`OledManager`** renders the panel from a `Snapshot` of everything above.

Bluetooth is delegated to the systemd BLE daemon stack. `bt_kb_send` only
writes the text to a FIFO and returns, so the application waits on
`bt_progress` to learn when the characters actually reached the host —
otherwise a send looks finished in milliseconds while the host is still
receiving.

Three runtime files carry state between the daemon and the application, all on
tmpfs and all optional (an older daemon simply publishes nothing):

| File | Written by | Read by |
|---|---|---|
| `/run/ipr_bt_progress.json` | daemon | `bt_progress` — the live character count |
| `/run/ipr_bt_key_delay` | application | daemon — the typing speed, per send |
| `/run/ipr_bt_link.json` | daemon | `bt_link` — which PCs are paired |

## Config Fields

`AppConfig` (`config/manager.py`) is the single source of truth — 34 fields,
seeded from `config.default.json` and saved to `config.json`. Grouped:

- **Pen**: `IrisPenFolders`, `DeleteFiles`, `MaxFileSize`,
  `ReadTimeoutSeconds`, `PollIntervalSeconds`
- **Bluetooth**: `PairingTimeoutSeconds`, `TypingDelayMs`
- **Web and TLS**: `LogPort`, `TlsCertFile`, `TlsKeyFile`,
  `StatusIntervalSeconds`
- **Network**: `NetworkMode`, `StaticIP`, `StaticNetmask`, `StaticGateway`
- **LED and magnet**: `GpioEnabled`, `GpioReedPin`, `GpioLedRPin`,
  `GpioLedGPin`, `GpioLedBPin`, `GpioLedIdleSeconds`, `MenuTimeoutSeconds`,
  `RecoveryRevealLimit`
- **Panel**: `OledEnabled`, `OledI2cBus`, `OledI2cAddress`, `OledContrast`,
  `OledRotate`, `OledSendHoldSeconds`, `OledMarqueeFps`,
  `OledDisplayTimeoutMinutes`
- **Diagnostics**: `Logging`, `LogLevel`, `MetricsEnabled`

Editing `config.json` while the service runs does not work: the process holds
the configuration in memory and rewrites the whole file on its next save.
Change it in the dashboard, or stop the service first.

## Notes

Pairing actions are BLE-only and do not depend on backend-switch manager
services.
