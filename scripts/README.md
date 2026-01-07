# ipr-keyboard Setup Scripts

This directory contains installation, setup, backend management, and diagnostic scripts for deploying and maintaining the ipr-keyboard application on a Raspberry Pi.

## Overview

The scripts automate the complete setup process from system configuration to service installation, backend switching, headless provisioning, and troubleshooting. They handle:
- System package installation
- Bluetooth configuration
- Python environment setup with uv
- Systemd service installation
- USB mount configuration
- Keyboard backend switching (uinput/BLE)
- **Headless provisioning** (Wi-Fi hotspot, USB OTG, factory reset)
- Testing and diagnostics

## Automated Provisioning

For fresh device setup from clean OS install, use the automated provisioning system in `provision/`:

📖 **[provision/README.md](../provision/README.md)** - Complete provisioning system documentation

**Quick overview**:
```bash
# 1. Configure device-specific settings
cp provision/common.env.example provision/common.env
nano provision/common.env
sudo cp provision/common.env /opt/ipr_common.env

# 2. Run provisioning scripts in order
sudo ./provision/00_bootstrap.sh
sudo ./provision/01_os_base.sh
sudo reboot
sudo ./provision/02_device_identity.sh  
sudo reboot
sudo ./provision/03_app_install.sh
sudo ./provision/04_enable_services.sh
sudo ./provision/05_verify.sh
```

The provisioning scripts leverage the existing scripts in this directory for the actual installation work.


## BLE Setup, Diagnostics, and Pairing

- **BLE/uinput backend install & management**: See `ble_install_helper.sh`.
- **BLE extras (diagnostics, pairing wizard, backend manager)**: See `ble_setup_extras.sh`.
- **Agent service**: `bt_hid_agent.service` (handles pairing/authorization).
- **Web pairing wizard**: `/pairing` endpoint (see web server docs).
- **BLE diagnostics**: Available via wrapper scripts in this directory.
- **Backend synchronization**: `config.json` and `/etc/ipr-keyboard/backend` are automatically synchronized.

### Backend Synchronization

The backend selection is kept in sync between `config.json` and `/etc/ipr-keyboard/backend`:
- `ble_setup_extras.sh` initializes `/etc/ipr-keyboard/backend` from `config.json` if it exists
- The application synchronizes both files on startup (backend file takes precedence)
- `ble_switch_backend.sh` updates both files simultaneously when switching backends

### Wrapper Scripts for BLE Extras

These wrapper scripts call tools installed by `ble_setup_extras.sh`:

```bash
# Run BLE diagnostics (wrapper for /usr/local/bin/ipr_ble_diagnostics.sh)
sudo ./scripts/diag_ble.sh

# Start BLE HID analyzer (wrapper for /usr/local/bin/ipr_ble_hid_analyzer.py)
sudo ./scripts/diag_ble_analyzer.sh

# Manually trigger backend manager (wrapper for /usr/local/bin/ipr_backend_manager.sh)
sudo ./scripts/ble_backend_manager.sh

# Start pairing wizard (web)
curl http://localhost:8080/pairing/start

# Switch backend (recommended - updates both config files and activates services)
./scripts/ble_switch_backend.sh ble
```

## Script Organization

Scripts are organized by domain with descriptive prefixes:

| Prefix | Domain | Description |
|--------|--------|-------------|
| `env_` | Environment | Environment variable configuration |
| `sys_` | System | System-level setup (packages, venv) |
| `ble_` | Bluetooth | Bluetooth HID configuration and backends |
| `usb_` | USB/MTP | IrisPen mount and sync operations |
| `headless/` | Headless | Wi-Fi provisioning (auto-hotspot service), USB OTG, factory reset (in headless/ subdirectory) |
| `service/` | Service | Systemd service installation (in service/ subdirectory) |
| `test_` | Testing | Smoke tests, E2E tests, Bluetooth tests |
| `dev_` | Development | Development helpers |
| `diag_` | Diagnostics | Troubleshooting and status tools |
| `extras/` | Extras | BLE diagnostics and tools (in extras/ subdirectory) |


## Fresh Installation Order

For a fresh Raspberry Pi installation, run scripts in this order:

```bash
# Navigate to project directory
cd $IPR_PROJECT_ROOT/ipr-keyboard

# Step 1: Configure environment variables (edit this file first)
nano scripts/env_set_variables.sh

# Step 2: System setup (requires root)
sudo ./provision/00_bootstrap.sh
sudo ./provision/01_os_base.sh
sudo reboot
sudo ./provision/02_device_identity.sh
sudo reboot
sudo ./provision/03_app_install.sh
sudo ./provision/04_enable_services.sh
sudo ./provision/05_verify.sh
```

**Note:** The headless Wi-Fi provisioning service (`ipr-provision.service`) is automatically installed and enabled during provisioning. If the device cannot connect to Wi-Fi, it will create a hotspot for browser-based setup on boot.

## Script Reference

### Environment Configuration

| Script | Description | Run as |
|--------|-------------|--------|
| `env_set_variables.sh` | Sets IPR_USER and IPR_PROJECT_ROOT environment variables. Sourced by all other scripts. | Source |

### System Setup

| Script | Description | Run as |
|--------|-------------|--------|
| `sys_install_packages.sh` | Installs system packages (git, bluez, mtp-tools, uv, etc.) | root |
| `sys_setup_venv.sh` | Creates Python venv with uv and installs project dependencies | user |


### Bluetooth / HID

| Script | Description | Run as |
|--------|-------------|--------|
| `ble_configure_system.sh` | Configures /etc/bluetooth/main.conf for HID keyboard profile | root |
| `ble_install_helper.sh` | **CRITICAL** - Installs bt_kb_send helper, backend daemons, and systemd services:<br> &nbsp; - `bt_hid_uinput.service` (uinput backend)<br> &nbsp; - `bt_hid_ble.service` (BLE backend)<br> &nbsp; - `bt_hid_agent.service` (pairing agent) | root |
| `ble_install_daemon.sh` | Optional advanced HID daemon installation | root |
| `ble_switch_backend.sh` | Switch between uinput and BLE keyboard backends. Updates both `/etc/ipr-keyboard/backend` and `config.json`, then enables/disables appropriate systemd services. Can read backend from config.json if no argument provided. | root |
| `ble_setup_extras.sh` | Advanced RPi extras (backend manager, pairing wizard, diagnostics). Initializes `/etc/ipr-keyboard/backend` from `config.json` if available. | root |

### USB / IrisPen

| Script | Description | Run as |
|--------|-------------|--------|
| `usb_setup_mount.sh` | Sets up persistent USB mount for IrisPen | root |
| `usb_mount_mtp.sh` | Mount/unmount IrisPen as MTP device | root |
| `usb_sync_cache.sh` | Sync files from MTP mount to local cache | user |

### Headless Provisioning Scripts

The following scripts enable headless Pi access and Wi-Fi provisioning:

| Script | Description | Run as |
|--------|-------------|--------|
| `headless/net_provision_web.py` | **Flask web interface** for Wi-Fi configuration. Runs on port 80 at `http://10.42.0.1/` when hotspot is active. Allows scanning and connecting to Wi-Fi networks via browser. | root |
| `headless/net_provision_hotspot.sh` | **Auto-hotspot provisioning**. If Pi can't connect to known Wi-Fi within 45s, creates hotspot `ipr-setup-XXXX` with web provisioning interface. | root |
| `headless/net_factory_reset.sh` | **Factory reset via boot marker**. Detects `IPR_RESET_WIFI` file on boot partition, wipes Wi-Fi profiles, and reboots into provisioning mode. | root |
| `headless/usb_otg_setup.sh` | **USB OTG Ethernet setup** for Pi Zero 2 W. Enables USB gadget mode - connect Pi Zero to laptop via USB for direct SSH access at `192.168.7.1`. | root |
| `headless/gpio_factory_reset.py` | **GPIO-based factory reset**. Monitors GPIO17 (Pin 11) for jumper to ground. If held for 2 seconds during boot, wipes Wi-Fi and enters provisioning mode. | root |

**Headless provisioning workflow**:
1. **Normal operation**: Pi connects to known Wi-Fi automatically
2. **Unknown Wi-Fi**: After 45s wait, Pi creates hotspot `ipr-setup-XXXX`
   - Connect phone/laptop to hotspot
   - Open `http://10.42.0.1/` in browser
   - Select Wi-Fi network and enter password
3. **USB OTG (Pi Zero)**: Plug USB cable to laptop
   - SSH to `192.168.7.1`
   - Configure Wi-Fi via `nmcli`
4. **Factory reset**: Two methods
   - Create empty file `IPR_RESET_WIFI` on boot partition
   - Or connect GPIO17 to GND during boot (if enabled)

**Installation** (done automatically by provisioning scripts):
```bash
# Web interface
sudo cp scripts/headless/net_provision_web.py /usr/local/sbin/ipr-provision-web.py
sudo chmod +x /usr/local/sbin/ipr-provision-web.py

# Hotspot script  
sudo cp scripts/headless/net_provision_hotspot.sh /usr/local/sbin/ipr-provision.sh
sudo chmod +x /usr/local/sbin/ipr-provision.sh

# Factory reset
sudo cp scripts/headless/net_factory_reset.sh /usr/local/sbin/ipr-factory-reset.sh
sudo chmod +x /usr/local/sbin/ipr-factory-reset.sh

# GPIO reset (optional)
sudo cp scripts/headless/gpio_factory_reset.py /usr/local/sbin/ipr-gpio-reset.py
sudo chmod +x /usr/local/sbin/ipr-gpio-reset.py

# USB OTG (Pi Zero only)
sudo ./scripts/headless/usb_otg_setup.sh
```



### Backend Service Management Scripts

The following scripts manage ipr-keyboard systemd services:

| Script                        | Description                                                      | Run as    |
|-------------------------------|------------------------------------------------------------------|-----------|
| `svc_disable_all_services.sh` | Disables and stops all ipr-keyboard related services             | root      |
| `svc_enable_uinput_services.sh` | Enables uinput backend services, disables BLE backend           | root      |
| `svc_enable_ble_services.sh`  | Enables BLE backend services, disables uinput backend            | root      |
| `svc_status_services.sh`      | Shows status of all managed services                            | user/root |

Usage examples:

```bash
# Disable all ipr-keyboard services
sudo ./scripts/svc_disable_all_services.sh

# Enable uinput backend services
sudo ./scripts/svc_enable_uinput_services.sh

# Enable BLE backend services
sudo ./scripts/svc_enable_ble_services.sh

# Show status of all managed services
sudo ./scripts/svc_status_services.sh
```

These scripts ensure only the correct backend is active and provide quick status checks.

### Diagnostic and Troubleshooting Scripts

The following scripts help diagnose and troubleshoot Bluetooth pairing and system issues:

| Script                        | Description                                                      | Run as    |
|-------------------------------|------------------------------------------------------------------|-----------|
| `diag_pairing.sh`             | **NEW** - Comprehensive Bluetooth pairing diagnostics. Checks adapter status, agent/backend services, paired devices, recent pairing events, and provides recommendations. | root      |
| `test_pairing.sh`             | **NEW** - Interactive pairing test script. Guides through pairing process with real-time agent event monitoring, passkey display, and connection verification. | root      |
| `diag_troubleshoot.sh`        | General system diagnostics. Checks venv, config, services, logs, and Bluetooth helper availability. | user/root |
| `diag_status.sh`              | System status overview. Shows backend config, service status, paired devices, and adapter info. | user      |
| `diag_ble.sh`                 | BLE-specific diagnostics (wrapper for `/usr/local/bin/ipr_ble_diagnostics.sh`). Checks HID UUID exposure, daemon status, and adapter state. | root      |
| `diag_ble_analyzer.sh`        | BLE HID analyzer (wrapper for `/usr/local/bin/ipr_ble_hid_analyzer.py`). Monitors GATT characteristic changes in real-time. | root      |

Usage examples:

```bash
# Comprehensive Bluetooth pairing diagnostics
sudo ./scripts/diag_pairing.sh

# Interactive pairing test with real-time monitoring
sudo ./scripts/test_pairing.sh ble

# General system troubleshooting
./scripts/diag_troubleshoot.sh

# Quick status overview
./scripts/diag_status.sh

# BLE-specific diagnostics
sudo ./scripts/diag_ble.sh

# Monitor BLE HID reports in real-time
sudo ./scripts/diag_ble_analyzer.sh
```

**NEW Pairing Diagnostics Features:**
- Analyzes agent pairing method implementations (RequestPasskey, DisplayPasskey, RequestConfirmation)
- Detects hardcoded vs. random passkey generation
- Shows recent pairing events with passkey values
- Provides step-by-step pairing guidance
- Tests keyboard input after pairing
- Saves full logs for later analysis

See [BLUETOOTH_PAIRING.md](../BLUETOOTH_PAIRING.md) for detailed pairing troubleshooting guide.

### Remote Diagnostic Scripts

For **remote troubleshooting via GitHub Copilot Chat** using MCP SSH server, see the dedicated diagnostic scripts:

📖 **[diag/README.md](diag/README.md)** - Remote diagnostic scripts documentation

**Quick overview:**
- `diag/dbg_deploy.sh` - Deploy latest code and restart service
- `diag/dbg_diag_bundle.sh` - Collect comprehensive diagnostics
- `diag/dbg_pairing_capture.sh` - Capture bounded pairing attempts with btmon
- `diag/dbg_bt_restart.sh` - Safe Bluetooth service restart
- `diag/dbg_bt_soft_reset.sh` - Conservative Bluetooth reset

These scripts are designed for installation in `/usr/local/bin/` and use with GitHub Copilot's diagnostic agent mode. See the [diag/README.md](diag/README.md) for complete setup and usage instructions.

## Environment Configuration

All scripts source `env_set_variables.sh` to ensure consistent environment variables. Edit this file to set:
- `IPR_USER`: Your username (default: meibye)
- `IPR_PROJECT_ROOT`: Your development directory path (default: /home/meibye/dev)

Alternatively, export these in your shell profile:
```bash
export IPR_USER="your_username"
export IPR_PROJECT_ROOT="/your/dev/path"
```

## Architecture Diagram


```
┌─────────────────────────────────────────────────────────────────────┐
│                         ipr-keyboard System                        │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │   IrisPen    │───>│ USB/MTP Mount│───>│ File Detection Loop   │   │
│  │   Scanner    │    │ /mnt/irispen │    │ (main.py)            │   │
│  └──────────────┘    └──────────────┘    └──────────┬───────────┘   │
│                                                      │               │
│  Scripts:                                            ▼               │
│  - usb_setup_mount.sh      ┌───────────────────────────────────────┐ │
│  - usb_mount_mtp.sh        │            Core Application           │ │
│  - usb_sync_cache.sh       │                                       │ │
│                            │  ┌─────────┐  ┌────────┐  ┌────────┐  │ │
│                            │  │ Config  │  │ Logger │  │  USB   │  │ │
│                            │  │ Manager │  │        │  │ Reader │  │ │
│                            │  └────┬────┘  └────┬───┘  └───┬────┘  │ │
│                            │       │            │          │       │ │
│                            └───────┴────────────┴──────────┴───────┘ │
│                                     │                      │         │
│  Scripts:                           ▼                      ▼         │
│  - sys_install_packages.sh   ┌─────────────┐    ┌─────────────────┐  │
│  - sys_setup_venv.sh         │  Web API    │    │ Bluetooth       │  │
│  - svc_install_systemd.sh    │  (Flask)    │    │ Keyboard        │  │
│                              │  Port 8080  │    │ (bt_kb_send)    │  │
│                              └─────────────┘    └────────┬────────┘  │
│                                                          │           │
│  Scripts:                                                ▼           │
│  - ble_configure_system.sh              ┌────────────────────────────┐│
│  - ble_install_helper.sh                │  Bluetooth Backend Services││
│  - ble_switch_backend.sh                │                            ││
│                                         │  ┌─────────────────────────────┐│
│                                         │  │ bt_hid_uinput.service       │◄────────┐│
│                                         │  │ (uinput daemon, uinput only)│         ││
│                                         │  └─────────────────────────────┘         ││
│                                         │  ┌─────────────────────────────┐         ││
│                                         │  │ bt_hid_ble.service          │◄─────┐  ││
│                                         │  │ (BLE daemon, BLE only)      │      │  ││
│                                         │  └─────────────────────────────┘      │  ││
│                                         │  ┌─────────────────────────────┐      │  ││
│                                         │  │ bt_hid_agent.service        │◄──┐  │  ││
│                                         │  │ (Pairing agent, BLE only)   │  │  │  ││
│                                         │  └─────────────────────────────┘  │  │  ││
│                                         │  ┌─────────────────────────────┐  │  │  ││
│                                         │  │ ipr_backend_manager.service │◄─┘  │  ││
│                                         │  │ (Backend switcher, both)    │─────┘  ││
│                                         │  └─────────────────────────────┘         ││
│                                         └──────────────────────────────────────────┘│
│                                                          │           │
│                                                          ▼           │
│                                           ┌─────────────────┐        │
│                                           │  Paired Device  │        │
│                                           │  (PC/Tablet)    │        │
│                                           └─────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
```

## Testing Individual Features

### Configuration Management
```bash
# Unit tests
pytest tests/config/

# Web API test
curl http://localhost:8080/config/
curl -X POST http://localhost:8080/config/ -H "Content-Type: application/json" -d '{"DeleteFiles": false}'
```

### USB File Handling
1. Plug in USB stick and mount it (e.g., `/mnt/irispen`)
2. Set `IrisPenFolder` to mount path in `config.json`
3. Test file detection by creating files in the folder
4. Use IrisPen to scan and create files

### Bluetooth Keyboard
1. Pair PC with Raspberry Pi (from PC side, see Pi as "Keyboard")
2. Test from Python REPL:
   ```python
   from ipr_keyboard.bluetooth.keyboard import BluetoothKeyboard
   kb = BluetoothKeyboard()
   kb.send_text("Hello world")
   ```
3. Verify text appears on paired PC

### Logging
1. Start application: `python -m ipr_keyboard.main`
2. Check log file: `cat logs/ipr_keyboard.log`
3. View via web API: `curl http://localhost:8080/logs/tail?lines=50`

## Prerequisites

- Raspberry Pi with Raspbian/Raspberry Pi OS
- Network connectivity for package installation
- Root access (via sudo)
- IrisPen scanner device
- Basic familiarity with Linux command line

## Script Permissions

Make scripts executable:
```bash
chmod +x scripts/*.sh
```

## Troubleshooting

If installation fails:
1. Check environment variables are set correctly
2. Ensure you have internet connectivity
3. Run diagnostic script: `./scripts/diag_troubleshoot.sh`
4. Check logs: `cat logs/ipr_keyboard.log`
5. Verify systemd service status: `sudo systemctl status ipr_keyboard`

## Notes

- Scripts use `set -euo pipefail` for safety (exit on error)
- All scripts source `env_set_variables.sh` for consistent configuration
- Some scripts require root privileges (use `sudo`)
- Python environment uses `uv` for dependency management
- The Bluetooth helper (`bt_kb_send`) is created by `ble_install_helper.sh`


## See Also

- [Main README](../README.md) - Project overview
- [Bluetooth Pairing Guide](../BLUETOOTH_PAIRING.md) - Pairing troubleshooting and diagnostics
- [Source Code Documentation](../src/ipr_keyboard/README.md) - Code structure
- [Testing Documentation](../tests/README.md) - Running tests
- [Testing Plan](../TESTING_PLAN.md) - Comprehensive testing strategy
