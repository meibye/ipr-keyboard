# ipr-keyboard Services and Scripts Reference

This document provides detailed descriptions of all systemd services, helper scripts, and tools used in the ipr-keyboard system.

## Systemd Services

### bt_hid_uinput.service

**Purpose**: UInput backend daemon for Bluetooth HID keyboard emulation.

**Description**: 
This service runs the uinput-based Bluetooth keyboard daemon (`bt_hid_uinput_daemon.py`). It creates a virtual keyboard device on the Raspberry Pi using the Linux uinput subsystem and reads text from a FIFO pipe (`/run/ipr_bt_keyboard_fifo`), then types it locally on the Pi via evdev key events.

**When to use**: Use this backend for classic Bluetooth HID pairing scenarios where the Pi acts as a virtual keyboard device using uinput.

**Dependencies**: 
- `bluetooth.target` (requires Bluetooth to be active)
- Python 3 with `python3-evdev` package
- `/run/ipr_bt_keyboard_fifo` FIFO pipe

**Location**: `/etc/systemd/system/bt_hid_uinput.service`

**Installed by**: `scripts/ble_install_helper.sh`

**Related scripts**: 
- `ble_switch_backend.sh` — Switch to/from uinput backend
- `bt_kb_send` — Sends text to the FIFO that this daemon reads

**Configuration**: Backend selection via `config.json` (`KeyboardBackend: "uinput"`)

---

### bt_hid_ble.service

**Purpose**: BLE HID backend daemon for Bluetooth Low Energy keyboard emulation.

**Description**:
This service runs the BLE-based Bluetooth keyboard daemon (`bt_hid_ble_daemon.py`). It registers a BLE HID GATT service (HID service UUID 0x1812) with BlueZ, advertises the Raspberry Pi as a BLE keyboard, and handles HID input reports over GATT characteristics. Like the uinput backend, it reads text from `/run/ipr_bt_keyboard_fifo` and converts characters to HID reports (including Danish æøåÆØÅ support).

**When to use**: Use this backend for Bluetooth Low Energy HID scenarios, particularly when pairing with modern devices that prefer BLE over classic Bluetooth.

**Dependencies**:
- `bluetooth.target` (requires Bluetooth to be active)
- Python 3 with `python3-dbus` and GLib
- BlueZ with GATT and LE Advertising support (may require `--experimental` flag)
- `/run/ipr_bt_keyboard_fifo` FIFO pipe

**Location**: `/etc/systemd/system/bt_hid_ble.service`

**Installed by**: `scripts/ble_install_helper.sh`

**Related scripts**:
- `ble_switch_backend.sh` — Switch to/from BLE backend
- `bt_kb_send` — Sends text to the FIFO that this daemon reads
- `ipr_ble_diagnostics.sh` — Diagnose BLE HID daemon issues

**Configuration**: Backend selection via `config.json` (`KeyboardBackend: "ble"`)

---

### bt_hid_daemon.service

**Purpose**: Alternative/legacy HID daemon service (advanced setup).

**Description**:
This is an optional advanced HID daemon service installed by `scripts/ble_install_daemon.sh`. It provides an alternative implementation for Bluetooth HID keyboard functionality. This service is separate from both `bt_hid_uinput.service` and `bt_hid_ble.service`.

**When to use**: This is for advanced users who want to use a custom HID daemon implementation. Most users should use `bt_hid_uinput.service` or `bt_hid_ble.service` instead.

**Dependencies**:
- `bluetooth.target`
- Custom HID daemon implementation

**Location**: `/etc/systemd/system/bt_hid_daemon.service`

**Installed by**: `scripts/ble_install_daemon.sh` (optional, not part of standard setup)

**Note**: The `ipr_backend_manager.service` recognizes this service as the "uinput" backend alternative, but `bt_hid_uinput.service` is the preferred and default uinput backend.

---

### bt_hid_agent.service

**Purpose**: Bluetooth pairing and service authorization agent.

**Description**:
This service runs the BlueZ Agent (`bt_hid_agent.py`) which handles Bluetooth pairing requests and service authorizations. It registers with BlueZ as a "KeyboardOnly" agent and automatically accepts pairing requests, passkey confirmations, and service authorizations. The agent also ensures the Bluetooth adapter is powered on, discoverable, and pairable.

**When to use**: This service should always be running when using either BLE or uinput backends, as it handles pairing with host devices.

**Dependencies**:
- `bluetooth.target` (requires Bluetooth to be active)
- Python 3 with `python3-dbus` and GLib
- BlueZ

**Location**: `/etc/systemd/system/bt_hid_agent.service`

**Installed by**: `scripts/ble_install_helper.sh`

**Key features**:
- Auto-accepts pairing requests
- Auto-accepts service authorizations (critical for HID profile)
- Sets adapter to powered/discoverable/pairable on startup
- Logs all pairing events to systemd journal

**Related scripts**:
- All backend switching scripts ensure this service is running

---

### ipr_backend_manager.service

**Purpose**: Backend selection and switching service.

**Description**:
This systemd oneshot service runs the backend manager script (`ipr_backend_manager.sh`) which reads the backend selection from `/etc/ipr-keyboard/backend` and ensures only the appropriate backend services are enabled and running. It prevents conflicts by stopping and disabling the non-selected backend.

**When to use**: This service runs automatically at boot to ensure the correct backend is active. It can also be triggered manually after changing `/etc/ipr-keyboard/backend` or when switching backends via the application.

**Dependencies**:
- `bluetooth.target`
- Must run after Bluetooth is available

**Location**: `/etc/systemd/system/ipr_backend_manager.service`

**Installed by**: `scripts/ble_setup_extras.sh`

**Backend logic**:
- If backend is `uinput`: Enables `bt_hid_uinput.service` (preferred) and disables BLE services. `bt_hid_daemon.service` is legacy/optional.
- If backend is `ble`: Enables `bt_hid_ble.service` and `bt_hid_agent.service`, disables uinput services

**Configuration file**: `/etc/ipr-keyboard/backend` (contains either "ble" or "uinput")

**Synchronization**: The backend file is automatically synchronized with `config.json` `KeyboardBackend`:
- On application startup, the backend file takes precedence if it exists
- When `KeyboardBackend` is updated via ConfigManager or web API, the backend file is automatically updated
- The `ble_switch_backend.sh` script updates both files simultaneously

**Related scripts**:
- `ble_switch_backend.sh` — Higher-level script that updates both config files and activates backend services
- `ipr_backend_manager.sh` — The actual script run by this service

---

## Helper Scripts and Tools

### bt_kb_send

**Purpose**: Command-line helper to send text to the Bluetooth keyboard.

**Description**:
This is the main interface for sending text to the Bluetooth keyboard backend. It writes text to the FIFO pipe (`/run/ipr_bt_keyboard_fifo`) which is monitored by either the uinput or BLE daemon. The ipr-keyboard application uses this script internally via the `BluetoothKeyboard` class.

**Location**: `/usr/local/bin/bt_kb_send`

**Installed by**: `scripts/ble_install_helper.sh`

**Usage**:
```bash
bt_kb_send "Hello world!"
bt_kb_send "Text with Danish characters: æøåÆØÅ"
```

**Dependencies**:
- `/run/ipr_bt_keyboard_fifo` must exist (created by backend daemons)
- Either `bt_hid_uinput.service` or `bt_hid_ble.service` must be running

**Used by**:
- `src/ipr_keyboard/bluetooth/keyboard.py` (`BluetoothKeyboard` class)
- Test scripts
- Manual testing and debugging

---

### ipr_backend_manager.sh

**Purpose**: Backend switcher script (invoked by `ipr_backend_manager.service`).

**Description**:
This script reads `/etc/ipr-keyboard/backend` and enables/disables the appropriate systemd services based on the selected backend ("ble" or "uinput"). It ensures only one backend is active at a time.

**Location**: `/usr/local/bin/ipr_backend_manager.sh`

**Installed by**: `scripts/ble_setup_extras.sh`

**Usage**: 
Typically invoked automatically by systemd, but can be run manually:
```bash
sudo /usr/local/bin/ipr_backend_manager.sh
```

**Backend selection file**: `/etc/ipr-keyboard/backend`

**Actions**:
- Reads backend from config file
- Stops and disables conflicting services
- Enables and starts required services for selected backend

---

### ipr_ble_diagnostics.sh

**Purpose**: BLE HID health check and diagnostics tool.

**Description**:
This script performs comprehensive diagnostics for the BLE HID backend. It checks:
1. Bluetooth adapter availability
2. HID service UUID (0x1812) exposure
3. BLE HID daemon service status
4. Agent service status
5. Adapter power state (via btmgmt)
6. Recent BLE HID daemon logs
7. FIFO pipe existence

**Location**: `/usr/local/bin/ipr_ble_diagnostics.sh`

**Installed by**: `scripts/ble_setup_extras.sh`

**Usage**:
```bash
sudo /usr/local/bin/ipr_ble_diagnostics.sh
```

**Output**: Color-coded status messages (green for OK, red for errors, yellow for warnings)

**When to use**:
- Troubleshooting BLE pairing issues
- Verifying BLE backend installation
- Checking HID service registration

---

### ipr_ble_hid_analyzer.py

**Purpose**: Real-time HID report analyzer and DBus signal monitor.

**Description**:
This Python script monitors DBus signals for GATT characteristic changes and logs HID report values. It's a debugging tool for BLE HID that watches for:
- HID input report Value changes (raw HID reports)
- Connection status changes
- GATT characteristic property updates

**Location**: `/usr/local/bin/ipr_ble_hid_analyzer.py`

**Installed by**: `scripts/ble_setup_extras.sh`

**Usage**:
```bash
sudo /usr/local/bin/ipr_ble_hid_analyzer.py
```

**Output**: Logs to systemd journal with details about HID reports in hexadecimal format

**When to use**:
- Debugging HID report generation
- Verifying character-to-HID-usage mapping
- Analyzing connection issues
- Understanding BLE GATT communication

**Dependencies**:
- Python 3 with `python3-dbus`, GLib, and `systemd` module
- Running BLE HID daemon

---

## Service Dependency and Backend Switching Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ipr-keyboard Service Dependencies                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────┐                                            │
│  │      bluetooth.target       │◄────────────────────────────────────────┐  │
│  └─────────────────────────────┘                                         │
│           ▲                ▲                ▲                ▲           │
│           │                │                │                │           │
│  ┌────────┴───────┐ ┌──────┴────────┐ ┌─────┴─────────┐ ┌────┴─────────┐ │
│  │bt_hid_uinput.sv│ │bt_hid_ble.sv  │ │bt_hid_agent.sv│ │ipr_backend_mgr││  │
│  └───────────────┬┘ └──────────────┬┘ └──────────────┬┘ └─────────────┬┘ │
│                  │                 │                 │                │  │
│                  │                 │                 │                │  │
│                  │                 │                 │                │  │
│                  │                 │                 │                │  │
│                  │                 │                 │                │  │
│                  └────────────┬─────┴────────────────┴────────────────┴──┘  │
│                               │                                             │
│                               ▼                                             │
│                    ┌─────────────────────────────┐                          │
│                    │    ipr_keyboard.service     │                          │
│                    └─────────────────────────────┘                          │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Backend Switching Logic:                                                   │
│                                                                             │
│  ┌─────────────────────────────┐                                            │
│  │ /etc/ipr-keyboard/backend   │◄─────┐                                     │
│  └─────────────────────────────┘      │                                     │
│           │                           │                                     │
│           ▼                           │                                     │
│  ┌─────────────────────────────┐      │                                     │
│  │ ipr_backend_manager.service │──────┘                                     │
│  └─────────────────────────────┘                                            │
│           │                                                                 │
│           ▼                                                                 │
│   ┌───────────────┬───────────────┐                                         │
│   │               │               │                                         │
│   ▼               ▼               ▼                                         │
│bt_hid_uinput.sv bt_hid_ble.sv bt_hid_agent.sv                               │
│   │               │               │                                         │
│   └───────────────┴───────────────┘                                         │
│                                                                             │
│  (Only one backend daemon is enabled at a time, agent always enabled)       │
└─────────────────────────────────────────────────────────────────────────────┘
```

- `ipr_keyboard.service` depends on `bt_hid_agent.service` (and optionally the active backend).
- `ipr_backend_manager.service` reads `/etc/ipr-keyboard/backend` and enables/disables the correct backend daemon.
- `bt_hid_agent.service` is always enabled for pairing/authorization.
- Only one backend daemon (`bt_hid_uinput.service` or `bt_hid_ble.service`) is enabled at a time. For uinput, use `bt_hid_uinput.service`.

## Diagnostic and Utility Tools

### Installed by ble_setup_extras.sh

These tools are created by running `sudo ./scripts/ble_setup_extras.sh`:

| Tool | Type | Purpose |
|------|------|---------|
| `ipr_backend_manager.sh` | Script | Backend switcher (invoked by service) |
| `ipr_ble_diagnostics.sh` | Script | BLE health check and diagnostics |
| `ipr_ble_hid_analyzer.py` | Script | HID report analyzer and DBus monitor |
| `/etc/ipr-keyboard/backend` | Config | Backend selection file (ble or uinput) |

### Wrapper Scripts

The following wrapper scripts are provided in the `scripts/` folder for convenience:

| Script | Calls | Purpose |
|--------|-------|---------|
| `diag_ble.sh` | `ipr_ble_diagnostics.sh` | Run BLE diagnostics |
| `diag_ble_analyzer.sh` | `ipr_ble_hid_analyzer.py` | Start HID report analyzer |
| `ble_backend_manager.sh` | `ipr_backend_manager.sh` | Manually trigger backend manager |

## Backend Selection Workflow

The backend selection is automatically synchronized between `config.json` and `/etc/ipr-keyboard/backend`:

1. **Initial Setup**: Run `scripts/ble_setup_extras.sh` to create `/etc/ipr-keyboard/backend` (initialized from `config.json` if available)
2. **Automatic Sync**: On application startup, the backend file takes precedence and updates `config.json` if they differ
3. **Update via Config**: Updating `KeyboardBackend` in `config.json` (via web API or ConfigManager) automatically updates the backend file
4. **Update via Script**: Use `scripts/ble_switch_backend.sh` which updates both files and activates backend services
5. **Service Activation**: Run `sudo systemctl restart ipr_backend_manager.service` or reboot to activate the selected backend

### Example Workflows

**Switch backend via script (recommended)**:
```bash
./scripts/ble_switch_backend.sh ble    # Updates both files and activates services
```

**Switch backend via web API**:
```bash
curl -X POST http://localhost:8080/config/ \
  -H "Content-Type: application/json" \
  -d '{"KeyboardBackend": "ble"}'
sudo systemctl restart ipr_backend_manager.service  # Activate services
```

**Manual backend file update**:
```bash
echo ble | sudo tee /etc/ipr-keyboard/backend
sudo systemctl restart ipr_backend_manager.service
# Note: config.json will be updated on next application startup
```

## Service Dependencies Summary

| Service | Depends On | Required By |
|---------|------------|-------------|
| `bluetooth.target` | System | All BT services |
| `bt_hid_agent.service` | `bluetooth.target` | Both backends |
| `bt_hid_uinput.service` | `bluetooth.target` | UInput backend |
| `bt_hid_ble.service` | `bluetooth.target` | BLE backend |
| `bt_hid_daemon.service` | `bluetooth.target` | Legacy/advanced (not default for uinput) |
| `ipr_backend_manager.service` | `bluetooth.target` | Backend selection |

## Troubleshooting Commands

```bash
systemctl status bt_hid_uinput.service
systemctl status bt_hid_ble.service
systemctl status bt_hid_agent.service
systemctl status ipr_backend_manager.service

journalctl -u bt_hid_uinput.service -n 50
journalctl -u bt_hid_ble.service -n 50
journalctl -u bt_hid_agent.service -n 50

sudo /usr/local/bin/ipr_ble_diagnostics.sh
./scripts/diag_status.sh
./scripts/diag_troubleshoot.sh

cat /etc/ipr-keyboard/backend
cat config.json | jq .KeyboardBackend

echo "test" | bt_kb_send "$(cat -)"
```

## Service Management Scripts


The following scripts in the `scripts/` folder provide convenient management of all ipr-keyboard systemd services:

- `svc_disable_all_services.sh`: Disables and stops all ipr-keyboard related services (main app, backends, agent, backend manager).
- `svc_enable_uinput_services.sh`: Enables and starts all required services for the uinput backend, disables BLE backend.
- `svc_enable_ble_services.sh`: Enables and starts all required services for the BLE backend, disables uinput backend.
- `svc_status_services.sh`: Shows the status of all handled services in a compact format.

### Usage Examples

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

These scripts ensure that only the correct backend is active and all dependencies are handled automatically. See each script for details.

## See Also

- [README.md](README.md) — Project overview
- [scripts/README.md](scripts/README.md) — Setup scripts
- [TESTING_PLAN.md](TESTING_PLAN.md) — Testing strategy
