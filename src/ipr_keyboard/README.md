# ipr_keyboard - Main Application Module

This directory contains the core implementation of the ipr-keyboard application, which bridges IrisPen USB scanner output to a paired device via Bluetooth HID keyboard emulation. The implementation is modular, with clear separation between USB file handling, Bluetooth keyboard emulation, configuration, logging, and a Flask-based web API. The system is designed for robust, headless operation on Raspberry Pi hardware, with automated provisioning and diagnostics.


## Component Dependency Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ipr_keyboard Package                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                        main.py                                    │  │
│  │                    (Entry Point)                                  │  │
│  │                                                                   │  │
│  │   - Orchestrates all modules                                      │  │
│  │   - Starts web server thread (Flask)                              │  │
│  │   - Starts USB/Bluetooth monitor thread                           │  │
│  │   - Handles graceful shutdown                                     │  │
│  └────────────────────────────┬──────────────────────────────────────┘  │
│                               │                                         │
│         ┌─────────────────────┼─────────────────────┐                   │
│         │                     │                     │                   │
│         ▼                     ▼                     ▼                   │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────────┐          │
│  │   config/   │      │  logging/   │      │      web/       │          │
│  ├─────────────┤      ├─────────────┤      ├─────────────────┤          │
│  │ manager.py  │◄─────│ logger.py   │      │ server.py       │          │
│  │ AppConfig   │      │ get_logger()│◄─────│ create_app()    │          │
│  │ ConfigMgr   │      │ log_path()  │      │ Flask blueprints│          │
│  │             │      │             │      │                 │          │
│  │ web.py      │─────>│ web.py      │─────>│ /config/        │          │
│  │ (Blueprint) │      │ (Blueprint) │      │ /logs/          │          │
│  └──────┬──────┘      └──────┬──────┘      │ /health         │          │
│         │                    │             └────────┬────────┘          │
│         │                    │                      │                   │
│         └─────────────┬──────┴──────────────────────┘                   │
│                       │                                                 │
│                       ▼                                                 │
│              ┌────────────────┐                                         │
│              │   utils/       │                                         │
│              ├────────────────┤                                         │
│              │ helpers.py     │                                         │
│              │                │                                         │
│              │ project_root() │                                         │
│              │ config_path()  │                                         │
│              │ load_json()    │                                         │
│              │ save_json()    │                                         │
│              │ backend sync   │                                         │
│              └──────┬─────────┘                                         │
│                     │                                                   │
│         ┌───────────┴───────────┐                                       │
│         │                       │                                       │
│         ▼                       ▼                                       │
│  ┌─────────────┐       ┌───────────────────┐                            │
│  │    usb/     │       │   bluetooth/      │                            │
│  ├─────────────┤       ├───────────────────┤                            │
│  │ detector.py │       │ keyboard.py       │                            │
│  │ reader.py   │       │ BluetoothKeyboard │                            │
│  │ deleter.py  │──────>│ send_text()       │                            │
│  │ mtp_sync.py │       │ is_available()    │                            │
│  └─────────────┘       └────────┬──────────┘                            │
│                                 │                                       │
│                                 │ subprocess.run()                      │
│                                 ▼                                       │
│                        ┌────────────────────┐                           │
│                        │ /usr/local/bin/    │                           │
│                        │ bt_kb_send         │                           │
│                        │ (System helper)    │                           │
│                        └────────────────────┘                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

Legend:
   ──────>  Uses / Depends on
   ◄──────  Provides configuration to
```



## Structure

The application is organized into focused modules with clear responsibilities:

| Module | Purpose | Key Files |
|--------|---------|-----------|
| **main.py** | Entry point, orchestrates all modules, starts threads | `main.py` |
| **bluetooth/** | Bluetooth HID keyboard interface, wraps system helper | `keyboard.py` |
| **config/** | Configuration management, thread-safe, backend sync | `manager.py`, `web.py` |
| **logging/** | Centralized logging, rotating file + console | `logger.py`, `web.py` |
| **usb/** | File detection, reading, deletion, MTP sync | `detector.py`, `reader.py`, `deleter.py`, `mtp_sync.py` |
| **utils/** | Helper functions, backend sync | `helpers.py` |
| **web/** | Flask REST API server, blueprints | `server.py` |


## Application Flow

1. **Startup** (`main.py`):
   - Initialize configuration manager (thread-safe, JSON-backed)
   - Set up logging (rotating file + console)
   - Start web server thread (Flask, blueprints for config/logs)
   - Start USB/Bluetooth monitor thread

2. **USB/Bluetooth Monitor Loop** (background thread):
   - Detect new files in IrisPenFolder (`usb/detector.py`)
   - Read file content (`usb/reader.py`)
   - Send text via Bluetooth (`bluetooth/keyboard.py`)
   - Optionally delete file (`usb/deleter.py`)
   - Log all operations

3. **Web Server** (background thread):
   - Serve REST API on configured port
   - Handle configuration updates (`/config/`)
   - Provide log viewing (`/logs/`)
   - Health check endpoint (`/health`)
   - BLE pairing wizard (`/pairing`) if extras installed

4. **Bluetooth Backend**:
   - Application calls `bt_kb_send` helper
   - Helper writes to FIFO (`/run/ipr_bt_keyboard_fifo`)
   - Backend daemon reads FIFO and sends as keyboard input (uinput or BLE backend)
   - Backend selection is always kept in sync with config


## Backend Services

The Bluetooth functionality relies on systemd services installed by setup scripts:

| Service | Purpose | Installed By |
|---------|---------|--------------|
| `bt_hid_uinput.service` | UInput backend daemon | `scripts/ble/ble_install_helper.sh` |
| `bt_hid_ble.service` | BLE backend daemon | `scripts/ble/ble_install_helper.sh` |
| `bt_hid_agent_unified.service` | Pairing/auth agent (Just Works) | `scripts/ble/ble_install_helper.sh` |
| `ipr_backend_manager.service` | Backend switcher | `scripts/ble/ble_setup_extras.sh` |

See [SERVICES.md](../../SERVICES.md) for detailed service documentation.

### BLE Setup and Diagnostics

After running `scripts/ble_setup_extras.sh`, additional tools are available:

**Wrapper Scripts** (in `scripts/`):
```bash
# Run BLE diagnostics
sudo /usr/local/bin/ipr_ble_diagnostics.sh

# Analyze HID reports
sudo /usr/local/bin/ipr_ble_hid_analyzer.py

# Manually trigger backend manager
sudo ./scripts/ble_backend_manager.sh
```

**Web Pairing Wizard**:
```bash
# Access via browser
http://localhost:8080/pairing
```

**Backend Switching**:
```bash
# Use interactive script
sudo ./scripts/ble_switch_backend.sh

# Or manually
echo ble | sudo tee /etc/ipr-keyboard/backend
sudo systemctl start ipr_backend_manager.service
```


## Entry Point

The application can be run in multiple ways:

- **As a module** (development):
   ```bash
   python -m ipr_keyboard.main
   ```
- **As a systemd service** (production):
   ```bash
   sudo systemctl start ipr_keyboard.service
   ```
- **Development mode** (foreground with console logs):
   ```bash
   ./scripts/dev_run_app.sh
   ```

Entry point is defined in `pyproject.toml` as `ipr-keyboard` command.


## Configuration

Configuration is managed through `config/manager.py` and persisted to `config.json`. All config changes are thread-safe and persisted. Backend selection is always kept in sync with `/etc/ipr-keyboard/backend`.

Key settings:
- `IrisPenFolder`: USB or MTP mount path
- `DeleteFiles`: Auto-delete processed files
- `LogPort`: Web server port
- `KeyboardBackend`: "uinput" or "ble"
- `MaxFileSize`: Maximum file size to process
- `Logging`: Enable/disable logging

See [config/README.md](config/README.md) for details.


## Logging

All operations are logged to `logs/ipr_keyboard.log` with rotation. Logs are accessible via:
- File system: `logs/ipr_keyboard.log`
- Web API: `http://localhost:8080/logs/tail?lines=50`
- Systemd journal: `journalctl -u ipr_keyboard.service`

See [logging/README.md](logging/README.md) for details.


## Testing

Run tests with pytest:
```bash
pytest
pytest --cov=ipr_keyboard
```

Tests are organized by module in `tests/` directory and mirror the source structure. End-to-end/systemd tests are in `scripts/`.


## See Also

- [SERVICES.md](../../SERVICES.md) — Detailed service documentation
- [Main README](../../README.md) — Project overview
- [scripts/README.md](../../scripts/README.md) — Setup and diagnostic scripts
- [TESTING_PLAN.md](../../TESTING_PLAN.md) — Testing strategy

### Module Documentation

- [bluetooth/README.md](bluetooth/README.md) — Bluetooth HID keyboard
- [config/README.md](config/README.md) — Configuration management
- [logging/README.md](logging/README.md) — Logging system
- [usb/README.md](usb/README.md) — USB file handling
- [utils/README.md](utils/README.md) — Helper utilities
- [web/README.md](web/README.md) — Web API server

