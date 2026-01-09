# ipr-keyboard


**IrisPen to Bluetooth Keyboard Bridge for Raspberry Pi**

This project bridges an IrisPen USB scanner to a paired device via Bluetooth HID keyboard emulation. It monitors a USB or MTP mount for new text files created by the IrisPen, reads their content, and sends the text to a paired computer as keyboard input using a system helper and backend daemons. All actions are logged, and configuration/logs are accessible via a web API. The implementation is modular, with clear separation between USB file handling, Bluetooth keyboard emulation, configuration, logging, and a Flask-based web API. The system is designed for robust, headless operation on Raspberry Pi hardware, with automated provisioning and diagnostics.

## Target Hardware & Device Names

### Development Setup

- **RPi 4 Model B (4GB)** - Primary development device
  - Hostname: `ipr-dev-pi4`
  - Bluetooth: "IPR Keyboard (Dev)"
  - mDNS: `ipr-dev-pi4.local`
  
- **RPi Zero 2 W** - Target deployment hardware  
  - Hostname: `ipr-target-zero2`
  - Bluetooth: "IPR Keyboard"
  - mDNS: `ipr-target-zero2.local`

**Development Environment**: Windows 11 PC with VS Code Remote-SSH → RPi 4

**Repository**: https://github.com/meibye/ipr-keyboard



## Bluetooth Backend Management & Extras

- **BLE and uinput backends** are installed and managed by `scripts/ble/ble_install_helper.sh`, which creates and enables:
  - `bt_hid_uinput.service` — UInput backend daemon
  - `bt_hid_ble.service` — BLE HID backend daemon (recommended for Windows 11)
  - `bt_hid_agent_unified.service` — Unified pairing/authorization agent with "Just Works" pairing
- **Pairing wizard, diagnostics, and backend manager** are provided by `scripts/ble/ble_setup_extras.sh` (creates `ipr_backend_manager.service`).
- **BLE diagnostics**: `scripts/extras/ipr_ble_diagnostics.sh` (health check), `scripts/extras/ipr_ble_hid_analyzer.py` (HID report analyzer).
- **Web pairing wizard**: `/pairing` endpoint (if extras installed).
- **Backend selection**: Synchronized between `config.json` (`KeyboardBackend`) and `/etc/ipr-keyboard/backend`.
- **Agent service**: `bt_hid_agent_unified.service` ensures seamless "Just Works" pairing (NoInputNoOutput) for Windows 11.

### Backend Synchronization

Backend selection is always kept in sync between `config.json` and `/etc/ipr-keyboard/backend`:
- On startup, `/etc/ipr-keyboard/backend` takes precedence if present
- Updates to `KeyboardBackend` in config.json (via web API or ConfigManager) update the backend file
- The `ble_switch_backend.sh` script updates both files and manages systemd services
- The `ipr_backend_manager.service` reads `/etc/ipr-keyboard/backend` to manage backend daemons

#### Example Backend Switching

```bash
# Switch to BLE backend (updates both config.json and /etc/ipr-keyboard/backend)
./scripts/ble/ble_switch_backend.sh ble

# Switch to uinput backend
./scripts/ble/ble_switch_backend.sh uinput

# Or read from config.json automatically
./scripts/ble/ble_switch_backend.sh
```




## Main Features
- **USB File Monitoring**: Detects new text files from IrisPen (configurable folder, USB or MTP mount)
- **Bluetooth Keyboard Emulation**: Sends scanned text to paired device using `/usr/local/bin/bt_kb_send` and backend daemons
- **Backend Services**: UInput and BLE HID backends managed by systemd (`bt_hid_uinput.service`, `bt_hid_ble.service`)
- **Web API**: View/update config and logs at `/config/`, `/logs/`, `/health` (Flask-based)
- **Logging**: Rotating file logger (`logs/ipr_keyboard.log`) and console output
- **Automatic File Cleanup**: Optionally deletes processed files after sending
- **Thread-safe Configuration**: Live updates via web or file, always persisted


## System Architecture

The ipr-keyboard system consists of modular components working together to bridge IrisPen scanner input to Bluetooth keyboard output. The architecture is designed for reliability, testability, and headless operation on Raspberry Pi.

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                           ipr-keyboard System                                             │
├───────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                           │
│  ┌──────────────┐     ┌──────────────────┐     ┌──────────────────────────┐               │
│  │   IrisPen    │────>│   USB/MTP Mount  │────>│  File Detection Loop     │               │
│  │   Scanner    │     │   /mnt/irispen   │     │  (usb/detector.py)       │               │
│  └──────────────┘     └──────────────────┘     └───────────┬──────────────┘               │
│                                                            │                              │
│  Setup Scripts:                                            ▼                              │
│  • usb_setup_mount.sh                      ┌────────────────────────────────┐             │
│  • usb_mount_mtp.sh                        │   ipr_keyboard Application     │             │
│  • usb_sync_cache.sh                       │   (ipr_keyboard.service)       │             │
│                                            │                                │             │
│                                            │  • main.py (entry point)       │             │
│                                            │  • config/manager.py           │             │
│                                            │  • usb/reader.py, deleter.py   │             │
│                                            │  • logging/logger.py           │             │
│                                            │  • web/server.py (Flask:8080)  │             │
│                                            └─────────┬──────────────────────┘             │
│                                                      │                                    │
│  Setup Scripts:                                      ▼                                    │
│  • sys_install_packages.sh          ┌───────────────────────────────────────┐             │
│  • sys_setup_venv.sh                │  bluetooth/keyboard.py                │             │
│  • svc_install_systemd.sh           │  (BluetoothKeyboard class)            │             │
│                                     └──────────┬────────────────────────────┘             │
│                                                │                                          │
│  Setup Scripts:                                ▼                                          │
│  • ble_configure_system.sh      ┌──────────────────────────────────────────┐              │
│  • ble_install_helper.sh        │         bt_kb_send                       │              │
│                                 │   /usr/local/bin/bt_kb_send              │              │
│                                 │   (writes to FIFO)                       │              │
│                                 └──────────┬───────────────────────────────┘              │
│                                            │                                              │
│                                            ▼                                              │
│                       ┌────────────────────────────────────────────────┐                  │
│                       │     /run/ipr_bt_keyboard_fifo (Named Pipe)     │                  │
│                       └─────────────┬──────────────────┬───────────────┘                  │
│                                     │                  │                                  │
│                   ┌─────────────────┴──┐           ┌───┴─────────────────┐                │
│  ┌────────────────▼────────────────┐   │           │  ┌──────────────────▼───────────────┐│
│  │ bt_hid_uinput.service           │   │           │  │ bt_hid_ble.service               ││
│  │ (UInput Backend Daemon)         │   │           │  │ (BLE HID Backend Daemon)         ││
│  │                                 │   │           │  │                                  ││
│  │ • Reads from FIFO               │   │           │  │ • Reads from FIFO                ││
│  │ • Creates uinput device         │   │           │  │ • Registers BLE GATT HID service ││
│  │ • Types via evdev               │   │           │  │ • BLE advertising (0x1812)       ││
│  │ • For classic BT pairing        │   │           │  │ • HID over GATT notifications    ││
│  │                                 │   │           │  │ • Danish æøå support             ││
│  └─────────────────────────────────┘   │           │  └──────────────────────────────────┘│
│                                        │           │                                      │
│  Alternative (legacy):                 │           │                                      │
│  ┌─────────────────────────────────┐   │           │                                      │
│  │ bt_hid_daemon.service           │◄──┘           │                                      │
│  │ (Advanced HID Daemon)           │               │                                      │
│  │ • Optional, installed separately│               │                                      │
│  └─────────────────────────────────┘               │                                      │
│                                                    │                                      │
│  ┌─────────────────────────────────────────────────┴──────────────────────────┐           │
│  │                       Common Supporting Services                           │           │
│  │                                                                            │           │
│  │  ┌────────────────────────────────────────┐  ┌──────────────────────────┐  │           │
│  │  │ bt_hid_agent_unified.service           │  │ ipr_backend_manager.     │  │           │
│  │  │ (Bluetooth Pairing & Auth Agent)       │  │ service                  │  │           │
│  │  │                                        │  │ (Backend Switcher)       │  │           │
│  │  │ • Registers as BlueZ Agent1            │  │                          │  │           │
│  │  │ • NoInputNoOutput capability           │  │ • Reads /etc/ipr-        │  │           │
│  │  │ • "Just Works" auto-pairing            │  │   keyboard/backend       │  │           │
│  │  │ • Auto-accepts service auth            │  │ • Enables correct backend│  │           │
│  │  │ • Sets adapter powered/discoverable    │  │ • Disables conflicting   │  │           │
│  │  │ • Required for both backends           │  │   services               │  │           │
│  │  └────────────────────────────────────────┘  └──────────────────────────┘  │           │
│  └────────────────────────────────────────────────────────────────────────────┘           │
│                                        │                                                  │
│                                        ▼                                                  │
│            ┌────────────────────────────────────────────────────────┐                     │
│            │              Diagnostic & Management Tools             │                     │
│            │                                                        │                     │
│            │  Wrapper Scripts (in scripts/):                        │                     │
│            │  • diag_ble.sh → /usr/local/bin/ipr_ble_diagnostics.sh │                     │
│            │  • diag_ble_analyzer.sh → ipr_ble_hid_analyzer.py      │                     │
│            │  • ble_backend_manager.sh → ipr_backend_manager.sh     │                     │
│            │  • diag_status.sh (system status overview)             │                     │
│            │  • diag_troubleshoot.sh (comprehensive diagnostics)    │                     │
│            │  • svc_status_monitor.py (interactive TUI)             │                     │
│            │  • ble_switch_backend.sh (backend switching helper)    │                     │
│            │                                                        │                     │
│            │  Tools installed by ble_setup_extras.sh:               │                     │
│            │  • /usr/local/bin/ipr_ble_diagnostics.sh               │                     │
│            │  • /usr/local/bin/ipr_ble_hid_analyzer.py              │                     │
│            │  • /usr/local/bin/ipr_backend_manager.sh               │                     │
│            │  • Web pairing wizard at /pairing endpoint             │                     │
│            └────────────────────────────────────────────────────────┘                     │
│                                        │                                                  │
│                                        ▼                                                  │
│                            ┌────────────────────────┐                                     │
│                            │     Paired Device      │                                     │
│                            │     (PC / Tablet)      │                                     │
│                            │  Receives text as      │                                     │
│                            │  keyboard input        │                                     │
│                            └────────────────────────┘                                     │
└───────────────────────────────────────────────────────────────────────────────────────────┘

Backend Selection:  uinput ◄──┬──► ble
                              │
                    /etc/ipr-keyboard/backend
                    or config.json KeyboardBackend
```

### Service Relationships

| Service | Purpose | Required By | Installed By |
|---------|---------|-------------|--------------|
| **ipr_keyboard.service** | Main application | - | `svc_install_systemd.sh` |
| **bt_hid_uinput.service** | UInput backend | uinput mode | `ble_install_helper.sh` |
| **bt_hid_ble.service** | BLE backend | ble mode | `ble_install_helper.sh` |
| **bt_hid_daemon.service** | Legacy HID daemon | uinput mode (alt) | `ble_install_daemon.sh` |
| **bt_hid_agent_unified.service** | Pairing agent (Just Works) | Both backends | `ble_install_helper.sh` |
| **ipr_backend_manager.service** | Backend switcher | Both backends | `ble_setup_extras.sh` |

### Key Components

- **bt_kb_send**: Helper script that writes text to FIFO pipe
- **FIFO pipe** (`/run/ipr_bt_keyboard_fifo`): Communication channel between app and backends
- **Backend daemons**: Read from FIFO and send as keyboard input (uinput or BLE GATT)
- **Agent**: Handles Bluetooth pairing and authorization
- **Backend manager**: Ensures only one backend is active at a time

For detailed service descriptions, see [SERVICES.md](SERVICES.md).
```



## Component Overview

| Component | Path | Description |
|-----------|------|-------------|
| Entry Point | `src/ipr_keyboard/main.py` | Orchestrates all modules, starts web server and USB/Bluetooth monitor threads |
| Bluetooth | `src/ipr_keyboard/bluetooth/keyboard.py` | Wraps `/usr/local/bin/bt_kb_send` for keyboard emulation; supports BLE and uinput backends |
| Backend Services | Installed by `scripts/ble/ble_install_helper.sh`:<br> &nbsp; - `bt_hid_uinput.service` (uinput backend)<br> &nbsp; - `bt_hid_ble.service` (BLE backend, recommended for Windows 11)<br> &nbsp; - `bt_hid_agent_unified.service` (pairing agent, "Just Works") |
| USB Handling | `src/ipr_keyboard/usb/` | File detection, reading, deletion, MTP sync |
| Config | `src/ipr_keyboard/config/manager.py` | Thread-safe singleton, JSON-backed, auto-syncs backend |
| Logging | `src/ipr_keyboard/logging/logger.py` | Rotating file + console logging |
| Web API | `src/ipr_keyboard/web/server.py` | Flask with blueprints for config/logs |
| Utilities | `src/ipr_keyboard/utils/helpers.py` | Project root, config path, JSON helpers, backend sync |



## Getting Started

### Quick Start for Fresh Devices

For detailed step-by-step instructions to set up both RPis from scratch:

📖 **[DEVICE_BRINGUP.md](DEVICE_BRINGUP.md)** — Complete bring-up procedure (automated provisioning)

**Summary:**
1. Flash SD cards with Raspberry Pi OS Lite (64-bit) Bookworm
2. Configure device-specific settings via `provision/common.env`
3. Run automated provisioning scripts (`provision/00_bootstrap.sh` through `05_verify.sh`)
4. Both devices configured identically with BLE HID over GATT

### Development Workflow

For day-to-day development procedures:

📖 **[DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md)** — Daily development workflow

**Summary:**
- Develop on RPi 4 via VS Code Remote-SSH
- Test features locally with `pytest`
- Validate on Pi Zero 2 W iteratively
- Keep devices in sync using Git tags


## Developer Workflows

- **Automated Provisioning**: Use scripts in `provision/` for fresh device setup
- **Manual Setup**: Use scripts in `scripts/` (see `scripts/README.md` for order)
- **Run in Dev Mode**: `./scripts/dev_run_app.sh` (foreground, logs to console)
- **Testing**: `pytest` or `pytest --cov=ipr_keyboard` (see `tests/README.md`)
- **Service Mode**: Installed as systemd service via `svc_install_systemd.sh` and backend services via `ble/ble_install_helper.sh`
- **Diagnostics**: `./scripts/diag_troubleshoot.sh` for troubleshooting
- **Remote Diagnostics**: GitHub Copilot integration via MCP SSH - see `scripts/rpi-debug/README.md`
- **Headless Access**: Wi-Fi hotspot provisioning + USB OTG (Pi Zero) - see `scripts/headless/`



## Configuration
Edit `config.json` in the project root or use the web API. All config changes are persisted and thread-safe. Backend selection is always kept in sync with `/etc/ipr-keyboard/backend`.

```json
{
  "IrisPenFolder": "/mnt/irispen",
  "DeleteFiles": true,
  "Logging": true,
  "MaxFileSize": 1048576,
  "LogPort": 8080,
  "KeyboardBackend": "uinput"  // or "ble"
}
```




## Usage Examples

- **Send text via Bluetooth:**
  ```python
  from ipr_keyboard.bluetooth.keyboard import BluetoothKeyboard
  kb = BluetoothKeyboard()
  if kb.is_available():
      kb.send_text("Hello world!")
  ```
- **Service management scripts:**
  ```bash
  # Disable all ipr-keyboard services
  sudo ./scripts/service/svc_disable_all_services.sh

  # Enable uinput backend services
  sudo ./scripts/service/svc_enable_uinput_services.sh

  # Enable BLE backend services
  sudo ./scripts/service/svc_enable_ble_services.sh

  # Show status of all managed services
  sudo ./scripts/service/svc_status_services.sh
  ```
- **Update config via web API:**
  ```bash
  curl -X POST http://localhost:8080/config/ -H "Content-Type: application/json" -d '{"DeleteFiles": false}'
  ```
- **View logs via web API:**
  ```bash
  curl http://localhost:8080/logs/tail?lines=50
  ```


## References
- [DEVICE_BRINGUP.md](DEVICE_BRINGUP.md) — Complete device setup from fresh OS install
- [DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md) — Daily development procedures
- [BLUETOOTH_PAIRING.md](BLUETOOTH_PAIRING.md) — Bluetooth pairing troubleshooting guide
- [SERVICES.md](SERVICES.md) — Detailed service and script documentation
- [provision/README.md](provision/README.md) — Automated provisioning system
- [scripts/README.md](scripts/README.md) — Setup and workflow scripts
- [src/ipr_keyboard/README.md](src/ipr_keyboard/README.md) — Code structure
- [tests/README.md](tests/README.md) — Test suite
- [TESTING_PLAN.md](TESTING_PLAN.md) — Comprehensive testing strategy

---
Michael Eibye <michael@eibye.name>
