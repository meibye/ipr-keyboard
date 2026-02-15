# src/ipr_keyboard/

Python application package for `ipr-keyboard`.

## Package Layout

| Path | Role |
|---|---|
| `main.py` | Entry point, launches web thread + USB/Bluetooth loop |
| `bluetooth/keyboard.py` | Wrapper around `/usr/local/bin/bt_kb_send` |
| `config/manager.py` | `AppConfig` + singleton `ConfigManager` |
| `config/web.py` | Flask blueprint for `/config/` |
| `logging/logger.py` | Rotating file logger setup |
| `logging/web.py` | Flask blueprint for `/logs/` |
| `usb/detector.py` | File listing/new-file polling |
| `usb/reader.py` | Size-capped file reading |
| `usb/deleter.py` | File deletion helpers |
| `usb/mtp_sync.py` | MTP -> cache sync utility + CLI |
| `utils/helpers.py` | Project/config path and JSON helpers |
| `web/server.py` | Flask app factory and root endpoints |
| `web/pairing_routes.py` | Pairing wizard endpoints |
| `web/templates/pairing_wizard.html` | Pairing UI template |

## Runtime Model

- Main loop monitors configured folder and sends text through `BluetoothKeyboard`.
- Web server runs concurrently for config/log/status routes.
- Bluetooth transmission is delegated to external helper (`bt_kb_send`) and systemd BLE daemon stack.

## Current Config Fields

`AppConfig` currently supports:
- `IrisPenFolder`
- `DeleteFiles`
- `Logging`
- `MaxFileSize`
- `LogPort`

## Notes

`web/pairing_routes.py` includes an `/activate-ble` action that invokes `ipr_backend_manager.service`. This service is not part of current shipped unit files and should be treated as legacy integration logic.
