# Service Scripts

This directory contains scripts and files for managing systemd services for ipr-keyboard.

## Directory Structure

```
service/
├── bin/                              # Service executables
│   ├── bt_hid_agent_unified.py       # BlueZ agent for pairing
│   └── bt_hid_ble_daemon.py          # BLE HID GATT keyboard daemon
├── svc/                              # Service unit definitions
│   ├── bt_hid_agent_unified.service  # Agent service definition
│   └── bt_hid_ble.service            # BLE daemon service definition
├── svc_install_bt_gatt_hid.sh        # Installer for Bluetooth GATT HID services
├── svc_install_all_services.sh       # Convenience installer for all services
├── svc_install_systemd.sh            # Install main ipr_keyboard service
├── svc_enable_services.sh            # Enable all Bluetooth GATT HID services
├── svc_disable_services.sh           # Disable all ipr-keyboard services
├── svc_status_services.sh            # Show status of all services
├── svc_status_monitor.py             # Service status monitor (Python)
└── svc_tail_all_logs.sh              # Tail logs from all services
```

## Bluetooth GATT HID Services

The ipr-keyboard system uses Bluetooth Low Energy (BLE) HID over GATT for keyboard emulation. This provides compatibility with modern devices that support BLE.

### Services

Two systemd services work together to provide Bluetooth GATT HID functionality:

1. **bt_hid_agent_unified.service**
   - Handles Bluetooth pairing requests
   - Configures the Bluetooth adapter for BLE
   - Automatically accepts and trusts pairing requests
   - Executable: `/usr/local/bin/bt_hid_agent_unified.py`
   - Source: `scripts/service/bin/bt_hid_agent_unified.py`

2. **bt_hid_ble.service**
   - Implements BLE HID over GATT keyboard
   - Reads text from FIFO and sends as HID input reports
   - Advertises as a BLE keyboard peripheral
   - Executable: `/usr/local/bin/bt_hid_ble_daemon.py`
   - Source: `scripts/service/bin/bt_hid_ble_daemon.py`

### Installation

To install Bluetooth GATT HID services:

```bash
sudo ./scripts/service/svc_install_bt_gatt_hid.sh
```

This script:
- Copies executables from `bin/` to `/usr/local/bin/`
- Copies service definitions from `svc/` to `/etc/systemd/system/`
- Configures Bluetooth daemon with minimal plugins
- Sets up environment file at `/opt/ipr_common.env`
- Enables and starts the services

### Configuration

The services are configured via `/opt/ipr_common.env`. See the installer script for details.

### Service Management

```bash
# Enable all services
sudo ./scripts/service/svc_enable_services.sh

# Disable all services
sudo ./scripts/service/svc_disable_services.sh

# Check service status
sudo ./scripts/service/svc_status_services.sh

# Tail all service logs
sudo ./scripts/service/svc_tail_all_logs.sh
```

## See Also

- [scripts/README.md](../README.md) - All scripts documentation
- [SERVICES.md](../../SERVICES.md) - Services reference
- [README.md](../../README.md) - Project overview
