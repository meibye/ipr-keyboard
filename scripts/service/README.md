# Service Installation Scripts

This directory contains systemd service installation and management scripts for ipr-keyboard.

## Overview

The service scripts handle installation, configuration, and management of various systemd services required for ipr-keyboard operation, including:
- Main ipr-keyboard application service
- Bluetooth HID backend services (uinput and BLE)
- Bluetooth agent service for pairing
- Backend manager service for switching between backends

## Service Scripts

### Main Application Service

- **svc_install_systemd.sh** - Installs the main ipr_keyboard systemd service
  - Service name: `ipr_keyboard.service`
  - Runs the main application automatically on system boot
  - Runs as non-root user for security

### Bluetooth Backend Services

- **svc_install_bt_hid_uinput.sh** - Installs uinput backend service
  - Service name: `bt_hid_uinput.service`
  - Local keyboard emulation via Linux uinput

- **svc_install_bt_hid_ble.sh** - Installs BLE HID backend service
  - Service name: `bt_hid_ble.service`
  - Bluetooth Low Energy HID over GATT

- **svc_install_bt_hid_daemon.sh** - Installs alternative HID daemon
  - Service name: `bt_hid_daemon.service`
  - Optional alternative implementation

### Supporting Services

- **svc_install_bt_hid_agent.sh** - Installs Bluetooth pairing agent
  - Service name: `bt_hid_agent.service`
  - Handles Bluetooth pairing and authorization
  - Required for successful BLE connections

- **svc_install_ipr_backend_manager.sh** - Installs backend manager
  - Service name: `ipr_backend_manager.service`
  - Ensures only one backend (uinput or BLE) is active at a time
  - Automatically switches services based on `/etc/ipr-keyboard/backend`

### Management Scripts

- **svc_install_all_services.sh** - Installs all Bluetooth services at once
- **svc_enable_uinput_services.sh** - Enables uinput backend and disables BLE
- **svc_enable_ble_services.sh** - Enables BLE backend and disables uinput
- **svc_disable_all_services.sh** - Disables all managed services
- **svc_status_services.sh** - Shows status of all managed services
- **svc_status_monitor.py** - Python script for monitoring service status

## Usage Examples

### Install Main Service
```bash
sudo ./scripts/service/svc_install_systemd.sh
sudo systemctl start ipr_keyboard.service
sudo systemctl status ipr_keyboard.service
```

### Switch Between Backends
```bash
# Enable uinput backend
sudo ./scripts/service/svc_enable_uinput_services.sh

# Enable BLE backend
sudo ./scripts/service/svc_enable_ble_services.sh
```

### Check Service Status
```bash
# Quick status check
sudo ./scripts/service/svc_status_services.sh

# Detailed status with monitoring
sudo ./scripts/service/svc_status_monitor.py
```

### Install All Bluetooth Services
```bash
sudo ./scripts/service/svc_install_all_services.sh
```

## Prerequisites

All service scripts require:
- Root access (run with `sudo`)
- Environment variables set (via `../env_set_variables.sh`)
- Python virtual environment set up (for main application service)
- Bluetooth packages installed (for BLE services)

## Service Dependencies

The services have the following dependency relationships:
- `ipr_keyboard.service` requires `bt_hid_agent.service`
- Backend services (uinput/BLE) should not run simultaneously
- `ipr_backend_manager.service` manages backend conflicts

## See Also

- Parent directory README: `../README.md`
- Backend switching script: `../ble_switch_backend.sh`
- System setup scripts: `../sys_*.sh`
