# ipr-keyboard

IrisPen to Bluetooth keyboard bridge for Raspberry Pi. This project allows you to use an IrisPen scanner connected via USB to a Raspberry Pi, which then forwards the scanned text to a paired computer via Bluetooth keyboard emulation.

## Overview

The ipr-keyboard project monitors a USB mount point for new text files created by an IrisPen scanner, reads the content, and sends it to a paired device using Bluetooth HID (Human Interface Device) keyboard protocol. This enables seamless integration of the IrisPen scanner with any Bluetooth-enabled device.

### Key Features

- **USB File Monitoring**: Automatically detects new files from IrisPen scanner
- **Bluetooth Keyboard Emulation**: Forwards scanned text as keyboard input via Bluetooth HID
- **Web-based Configuration**: Manage settings through a simple web interface
- **Logging and Monitoring**: Built-in logging with web-based log viewing
- **Automatic File Cleanup**: Optionally delete processed files after transmission
- **Thread-safe Configuration**: Runtime configuration updates without restart

## Architecture

The application consists of several main components:

- **Main Loop** (`main.py`): Orchestrates the USB monitoring and Bluetooth forwarding
- **Bluetooth Module** (`bluetooth/`): Handles Bluetooth HID keyboard communication
- **USB Module** (`usb/`): Detects, reads, and optionally deletes files from USB mount
- **Config Module** (`config/`): Thread-safe configuration management with JSON persistence
- **Logging Module** (`logging/`): Centralized logging with rotation and web access
- **Web Server** (`web/`): Flask-based API for configuration and log viewing
- **Utils** (`utils/`): Helper functions for file operations and paths

## Quick Start

1. Clone the repository to your Raspberry Pi
2. Run the setup scripts in order (see `scripts/README.md` for details)
3. Configure your IrisPen mount point in `config.json`
4. Start the service with systemd or run manually

For detailed installation and setup instructions, see the [scripts/README.md](scripts/README.md) file.

## Configuration

The application is configured via `config.json` in the project root:

```json
{
  "IrisPenFolder": "/mnt/irispen",
  "DeleteFiles": true,
  "Logging": true,
  "MaxFileSize": 1048576,
  "LogPort": 8080
}
```

Configuration can be updated at runtime via the web API (`POST /config/`) or by editing the JSON file and reloading.

## Usage

### Running the Application

```bash
# Using uv (recommended)
uv run ipr-keyboard

# Or activate the virtual environment
source .venv/bin/activate
ipr-keyboard
```

### Web Interface

Access the web interface at `http://<pi-ip>:8080` (default port):

- `GET /health` - Health check endpoint
- `GET /config/` - View current configuration
- `POST /config/` - Update configuration
- `GET /logs/` - View full log
- `GET /logs/tail?lines=N` - View last N lines of log

## Development

The project uses modern Python tooling:

- **Python 3.13+** required
- **uv** for dependency management
- **pytest** for testing
- **Flask** for web server

See individual module README files for detailed documentation:

- [src/ipr_keyboard/](src/ipr_keyboard/README.md) - Main application modules
- [scripts/](scripts/README.md) - Installation and setup scripts
- [tests/](tests/README.md) - Test suite documentation

## Requirements

- Raspberry Pi (tested on Pi 4)
- IrisPen scanner with USB interface
- Bluetooth capability (built-in or USB dongle)
- Python 3.13 or higher
- Linux with systemd (for service mode)

## License

See project metadata for license information.

## Author

Michael Eibye <michael@eibye.name>
