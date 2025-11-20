# ipr_keyboard - Main Application Module

This directory contains the core implementation of the ipr-keyboard application.

## Module Overview

The application is structured as a modular Python package with the following components:

### Core Files

- **`main.py`** - Application entry point that coordinates all modules
  - Runs web server in a background thread
  - Monitors USB folder for new files in the main loop
  - Forwards text via Bluetooth keyboard
  - Handles graceful shutdown

- **`__init__.py`** - Package initialization

### Submodules

Each subdirectory is a focused module with specific responsibilities:

- **[bluetooth/](bluetooth/README.md)** - Bluetooth HID keyboard communication
- **[config/](config/README.md)** - Configuration management and persistence
- **[logging/](logging/README.md)** - Centralized logging with rotation
- **[usb/](usb/README.md)** - USB file detection, reading, and cleanup
- **[utils/](utils/README.md)** - Utility functions and helpers
- **[web/](web/README.md)** - Flask web server for API and monitoring

## Application Flow

1. **Startup** (`main.py:main()`)
   - Load configuration from `config.json`
   - Initialize logger
   - Start web server thread on configured port
   - Start USB/Bluetooth monitoring loop

2. **USB Monitoring Loop** (`main.py:run_usb_bt_loop()`)
   - Check if IrisPen folder exists
   - Wait for new files (based on modification time)
   - Read file content when detected
   - Send text via Bluetooth keyboard
   - Optionally delete processed files
   - Log all operations

3. **Web Server** (`main.py:run_web_server()`)
   - Serve configuration API
   - Provide log viewing endpoints
   - Health check endpoint

## Threading Model

The application uses a simple threading model:
- **Main thread**: Keeps application alive, handles Ctrl+C
- **Web server thread**: Flask application (daemon)
- **USB monitor thread**: File detection and Bluetooth forwarding (daemon)

Configuration is thread-safe via `ConfigManager` using locks.

## Entry Point

The application can be started via:

```bash
# As installed script
ipr-keyboard

# Or directly
python -m ipr_keyboard.main
```

The entry point is defined in `pyproject.toml`:
```toml
[project.scripts]
ipr-keyboard = "ipr_keyboard.main:main"
```

## Dependencies

Core dependencies:
- **Flask** - Web server for configuration and monitoring
- **Python 3.13+** - Uses modern Python features (dataclasses, type hints, etc.)

External system dependencies:
- `/usr/local/bin/bt_kb_send` - Bluetooth HID helper script (see bluetooth module)

## Configuration

See [config/README.md](config/README.md) for details on configuration management.

Default configuration is loaded from `config.json` in the project root with the following fields:
- `IrisPenFolder` - Path to USB mount point
- `DeleteFiles` - Whether to delete files after processing
- `Logging` - Enable/disable logging
- `MaxFileSize` - Maximum file size to read (bytes)
- `LogPort` - Web server port
