# ipr_keyboard - Main Application Module

This directory contains the core implementation of the ipr-keyboard application, which bridges IrisPen USB scanner output to a paired device via Bluetooth HID keyboard emulation.

## Structure
- **main.py**: Application entry point. Starts the web server and USB/Bluetooth monitor threads, coordinates all modules, and handles graceful shutdown.
- **__init__.py**: Package initialization.
- **bluetooth/**: Bluetooth HID keyboard communication (see `bluetooth/README.md`).
- **config/**: Thread-safe configuration management and persistence (see `config/README.md`).
- **logging/**: Centralized logging with rotation and web API (see `logging/README.md`).
- **usb/**: USB file detection, reading, and cleanup (see `usb/README.md`).
- **utils/**: Utility functions for path resolution and JSON file operations (see `utils/README.md`).
- **web/**: Flask web server for configuration/log viewing and health checks (see `web/README.md`).

## Application Flow
1. **Startup**: Loads config, initializes logger, starts web server and USB/Bluetooth monitor threads.
2. **USB Monitoring**: Watches configured folder for new files, reads content, sends via Bluetooth, optionally deletes files, logs all actions.
3. **Web API**: Exposes `/config/`, `/logs/`, and `/health` endpoints for runtime config/log access.

## Threading Model
- Main thread: Keeps app alive, handles Ctrl+C
- Web server thread: Flask app (daemon)
- USB monitor thread: File detection and Bluetooth forwarding (daemon)

## Entry Point
Run as:
```bash
python -m ipr_keyboard.main
# or if installed:

```
Entry point is defined in `pyproject.toml`.

## See Also
- [bluetooth/README.md](bluetooth/README.md)
- [config/README.md](config/README.md)
- [logging/README.md](logging/README.md)
- [usb/README.md](usb/README.md)
- [utils/README.md](utils/README.md)
- [web/README.md](web/README.md)
   - Read file content when detected
