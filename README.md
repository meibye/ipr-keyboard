# ipr-keyboard

**IrisPen to Bluetooth keyboard bridge for Raspberry Pi**

This project bridges an IrisPen USB scanner to a paired device via Bluetooth HID keyboard emulation. It monitors a USB or MTP mount for new text files created by the IrisPen, reads their content, and sends the text to a paired computer as keyboard input. All actions are logged, and configuration/logs are accessible via a web API.

## Main Features
- **USB File Monitoring**: Detects new text files from IrisPen (configurable folder)
- **Bluetooth Keyboard Emulation**: Sends scanned text to paired device using a system helper (`/usr/local/bin/bt_kb_send`)
- **Web API**: View/update config and logs at `/config/`, `/logs/`, `/health` (Flask-based)
- **Logging**: Rotating file logger (`logs/ipr_keyboard.log`) and console output
- **Automatic File Cleanup**: Optionally deletes processed files
- **Thread-safe Configuration**: Live updates via web or file

## Architecture
- **Entry Point**: `src/ipr_keyboard/main.py` (starts web server and USB/Bluetooth monitor threads)
- **Bluetooth**: `src/ipr_keyboard/bluetooth/keyboard.py` (wraps system helper)
- **USB Handling**: `src/ipr_keyboard/usb/` (file detection, reading, deletion)
- **Config**: `src/ipr_keyboard/config/manager.py` (singleton, JSON-backed)
- **Logging**: `src/ipr_keyboard/logging/logger.py` (rotating file + console)
- **Web API**: `src/ipr_keyboard/web/server.py` (Flask, blueprints)
- **Utilities**: `src/ipr_keyboard/utils/helpers.py` (project root, config path, JSON helpers)

## Developer Workflows
- **Setup**: Use scripts in `scripts/` (see `scripts/README.md` for order)
- **Run in Dev Mode**: `./scripts/run_dev.sh` (foreground, logs to console)
- **Testing**: `pytest` or `pytest --cov=ipr_keyboard` (see `tests/README.md`)
- **Service Mode**: Installed as systemd service via `05_install_service.sh`
- **Diagnostics**: `./scripts/10_diagnose_failure.sh` for troubleshooting

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

---
Michael Eibye <michael@eibye.name>
