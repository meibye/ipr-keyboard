# ipr-keyboard

**IrisPen to Bluetooth keyboard bridge for Raspberry Pi**


This project bridges an IrisPen USB scanner to a paired device via Bluetooth HID keyboard emulation. It monitors a USB or MTP mount for new text files created by the IrisPen, reads their content, and sends the text to a paired computer as keyboard input. All actions are logged, and configuration/logs are accessible via a web API.

## Bluetooth Backend Management & Extras

- **BLE and uinput backends** are installed and managed by `scripts/ble_install_helper.sh`.
- **Pairing wizard, diagnostics, and backend manager** are provided by `scripts/ble_setup_extras.sh`.
- **BLE diagnostics**: `ipr_ble_diagnostics.sh` (health check), `ipr_ble_hid_analyzer.py` (HID report analyzer).
- **Web pairing wizard**: `/pairing` endpoint (see web server docs).
- **Backend selection**: `/etc/ipr-keyboard/backend` or config.json `KeyboardBackend`.
- **Agent service**: `bt_hid_agent.service` ensures seamless pairing and authorization.

### Example Local Scripts

You can create local scripts to call these helpers, e.g.:

```bash
# Run BLE diagnostics
./scripts/ipr_ble_diagnostics.sh

# Start pairing wizard (web)
curl http://localhost:8080/pairing/start

# Switch backend
echo ble | sudo tee /etc/ipr-keyboard/backend
sudo systemctl restart bt_hid_ble.service
```


## Main Features
- **USB File Monitoring**: Detects new text files from IrisPen (configurable folder)
- **Bluetooth Keyboard Emulation**: Sends scanned text to paired device using a system helper (`/usr/local/bin/bt_kb_send`)
- **Web API**: View/update config and logs at `/config/`, `/logs/`, `/health` (Flask-based)
- **Logging**: Rotating file logger (`logs/ipr_keyboard.log`) and console output
- **Automatic File Cleanup**: Optionally deletes processed files
- **Thread-safe Configuration**: Live updates via web or file

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ipr-keyboard System                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌──────────────┐     ┌──────────────────┐     ┌────────────────────────┐  │
│  │   IrisPen    │────>│   USB/MTP Mount  │────>│   File Detection Loop  │  │
│  │   Scanner    │     │   /mnt/irispen   │     │   (detector.py)        │  │
│  └──────────────┘     └──────────────────┘     └───────────┬────────────┘  │
│                                                            │              │
│                                                            ▼              │
│                 ┌────────────────────────────────────────────────────┐    │
│                 │               ipr_keyboard Application             │    │
│                 │                                                    │    │
│                 │  ┌────────────────┐         ┌──────────────────┐   │    │
│                 │  │  main.py       │◄───────>│ config/manager.py│   │    │
│                 │  │  (Entry Point) │         │ (Thread-safe cfg)│   │    │
│                 │  └───────┬────────┘         └────────┬─────────┘   │    │
│                 │          │                           │             │    │
│                 │          ├───────────────────────────┤             │    │
│                 │          │                           │             │    │
│                 │          ▼                           ▼             │    │
│                 │  ┌────────────────┐         ┌──────────────────┐   │    │
│                 │  │  usb/reader.py │         │ logging/logger.py│   │    │
│                 │  │  (Read files)  │         │ (Rotating logs)  │   │    │
│                 │  └───────┬────────┘         └────────┬─────────┘   │    │
│                 │          │                           │             │    │
│                 │          ▼                           ▼             │    │
│                 │  ┌────────────────┐         ┌──────────────────┐   │    │
│                 │  │ usb/deleter.py │         │ web/server.py    │   │    │
│                 │  │ (Cleanup files)│         │ (Flask API)      │   │    │
│                 │  └───────┬────────┘         │ Port 8080        │   │    │
│                 │          │                  └──────────────────┘   │    │
│                 └──────────┼─────────────────────────────────────────┘    │
│                            │                                              │
│                            ▼                                              │
│                 ┌────────────────────────────────────────────────────┐    │
│                 │         bluetooth/keyboard.py                      │    │
│                 │         (BluetoothKeyboard class)                  │    │
│                 │              │                                     │    │
│                 │              ▼                                     │    │
│                 │     ┌────────────────┐                             │    │
│                 │     │ bt_kb_send     │  (System helper script)     │    │
│                 │     │ (/usr/local/bin)                             │    │
│                 │     └───────┬────────┘                             │    │
│                 │             │                                      │    │
│                 │             ▼                                      │    │
│                 │     ┌────────────────────────────────┐             │    │
│                 │     │  Bluetooth Backend             │             │    │
│                 │     │  ┌──────────┐   ┌──────────┐   │             │    │
│                 │     │  │  uinput  │   │   BLE    │   │             │    │
│                 │     │  │  daemon  │   │  daemon  │   │             │    │
│                 │     │  └──────────┘   └──────────┘   │             │    │
│                 │     └───────────────┬────────────────┘             │    │
│                 │                     │                              │    │
│                 │                     ▼                              │    │
│                 │     ┌────────────────────────────────────────────┐ │    │
│                 │     │  BLE Setup/Extras                         │ │    │
│                 │     │  ┌───────────────┐ ┌────────────────────┐  │ │    │
│                 │     │  │ Pairing Agent │ │ Pairing Wizard     │  │ │    │
│                 │     │  │ (bt_hid_agent)| │ (web /pairing)     │  │ │    │
│                 │     │  └───────────────┘ └────────────────────┘  │ │    │
│                 │     │  ┌───────────────┐ ┌────────────────────┐  │ │    │
│                 │     │  │ BLE Diag      │ │ Backend Manager    │  │ │    │
│                 │     │  │ (diagnostics) │ │ (switcher/config)  │  │ │    │
│                 │     │  └───────────────┘ └────────────────────┘  │ │    │
│                 │     └────────────────────────────────────────────┘ │    │
│                 └────────────────────────────────────────────────────┘    │
│                                                                            │
│                                    ┌─────────────────┐                      │
│                                    │  Paired Device  │                      │
│                                    │  (PC / Tablet)  │                      │
│                                    │  Receives text  │                      │
│                                    │  as keystrokes  │                      │
│                                    └─────────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Overview

| Component | Path | Description |
|-----------|------|-------------|
| Entry Point | `src/ipr_keyboard/main.py` | Starts web server and USB/Bluetooth monitor threads |
| Bluetooth | `src/ipr_keyboard/bluetooth/keyboard.py` | Wraps system helper for keyboard emulation |
| USB Handling | `src/ipr_keyboard/usb/` | File detection, reading, deletion |
| Config | `src/ipr_keyboard/config/manager.py` | Thread-safe singleton, JSON-backed |
| Logging | `src/ipr_keyboard/logging/logger.py` | Rotating file + console logging |
| Web API | `src/ipr_keyboard/web/server.py` | Flask with blueprints for config/logs |
| Utilities | `src/ipr_keyboard/utils/helpers.py` | Project root, config path, JSON helpers |

## Developer Workflows
- **Setup**: Use scripts in `scripts/` (see `scripts/README.md` for order)
- **Run in Dev Mode**: `./scripts/dev_run_app.sh` (foreground, logs to console)
- **Testing**: `pytest` or `pytest --cov=ipr_keyboard` (see `tests/README.md`)
- **Service Mode**: Installed as systemd service via `svc_install_systemd.sh`
- **Diagnostics**: `./scripts/diag_troubleshoot.sh` for troubleshooting

## Configuration
Edit `config.json` in the project root or use the web API:

```json
{
  "IrisPenFolder": "/mnt/irispen",
  "DeleteFiles": true,
  "Logging": true,
  "MaxFileSize": 1048576,
  "LogPort": 8080
}
```

## Usage Examples
- **Send text via Bluetooth**:
  ```python
  from ipr_keyboard.bluetooth.keyboard import BluetoothKeyboard
  kb = BluetoothKeyboard()
  if kb.is_available():
      kb.send_text("Hello world!")
  ```
- **Update config via web API**:
  ```bash
  curl -X POST http://localhost:8080/config/ -H "Content-Type: application/json" -d '{"DeleteFiles": false}'
  ```
- **View logs via web API**:
  ```bash
  curl http://localhost:8080/logs/tail?lines=50
  ```

## References
- [scripts/README.md](scripts/README.md) — Setup and workflow scripts
- [src/ipr_keyboard/README.md](src/ipr_keyboard/README.md) — Code structure
- [tests/README.md](tests/README.md) — Test suite
- [TESTING_PLAN.md](TESTING_PLAN.md) — Comprehensive testing strategy

---
Michael Eibye <michael@eibye.name>
