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
| `web/server.py` | Flask app factory, legacy HTML endpoints, and dashboard root |
| `web/api.py` | `/api/` Blueprint — dashboard JSON API (all `/api/*` routes) |
| `web/pairing_routes.py` | Legacy pairing wizard endpoints |
| `web/templates/dashboard.html` | Image-first SPA dashboard (primary UI) |
| `web/templates/` | Legacy HTML templates (status, config, logs, pairing) |
| `web/static/` | SVG icons and device-flow illustration for the dashboard |

## Runtime Model

- Main loop monitors configured folder and sends text through `BluetoothKeyboard`.
- Web server runs concurrently, serving the image-first dashboard SPA at `/` and dashboard
  API endpoints under `/api/` (see `web/api.py` and `docs/ui/api-contract.md`).
- Bluetooth transmission is delegated to external helper (`bt_kb_send`) and systemd BLE daemon stack.

## Current Config Fields

`AppConfig` currently supports:
- `IrisPenFolder`
- `DeleteFiles`
- `Logging`
- `MaxFileSize`
- `LogPort`

## Notes

`web/pairing_routes.py` uses BLE-only pairing actions and does not depend on backend-switch manager services.
