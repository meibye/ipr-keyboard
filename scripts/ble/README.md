
# Bluetooth Scripts

This directory contains scripts for configuring and managing Bluetooth HID functionality for the ipr-keyboard project. These scripts handle:
- Bluetooth system configuration
- Installation of the bt_kb_send helper and backend daemons
- BLE extras (diagnostics, pairing wizard, backend manager)
- Bluetooth-related testing and diagnostics

## Overview

These scripts handle:
- Bluetooth system configuration
- Installation of the bt_kb_send helper and backend daemons
- BLE extras (diagnostics, pairing wizard, backend manager)
- Bluetooth-related testing and diagnostics

## Scripts


### Core Configuration and Installation

| Script | Description | Run as |
|--------|-------------|--------|
| `bt_configure_system.sh` | Configures `/etc/bluetooth/main.conf` for HID keyboard profile. Sets controller mode (LE-only or dual), auto-enable, and creates systemd overrides for bluetoothd. | root |
| `ble_install_helper.sh` | **CRITICAL** - Installs bt_kb_send helper, backend daemons, and systemd services:<br>&nbsp;- `bt_hid_uinput.service` (uinput backend)<br>&nbsp;- `bt_hid_ble.service` (BLE backend)<br>&nbsp;- `bt_hid_agent_unified.service` (pairing agent) | root |
| `ble_setup_extras.sh` | Installs advanced RPi extras including backend manager, pairing wizard, and diagnostic tools. | root |


### Helper Script Source

| File | Description |
|------|-------------|
| `bt_kb_send.sh` | Source file for the bt_kb_send helper script. This is installed to `/usr/local/bin/bt_kb_send` by `ble_install_helper.sh`. Writes text to the BLE keyboard FIFO with proper waiting for FIFO and notification readiness. |


### Utilities

| Script | Description | Run as |
|--------|-------------|--------|
| `ble_show_bt_mac_for_windows.sh` | Shows the Raspberry Pi Bluetooth MAC address in both Linux format (with colons) and Windows instance-id format (no colons, uppercase) for troubleshooting. | user |


### Testing Scripts

| Script | Description | Run as |
|--------|-------------|--------|
| `test_bluetooth.sh` | Sends a test string via the Bluetooth HID helper (`bt_kb_send`) or daemon to verify Bluetooth keyboard emulation is working end-to-end. | user |
| `test_pairing.sh` | Interactive pairing test script. Guides through pairing process with real-time agent event monitoring, passkey display, and connection verification. | root |


### Diagnostic Scripts

| Script | Description | Run as |
|--------|-------------|--------|
| `diag_bt_visibility.sh` | Diagnoses why the BLE HID device is not visible on PC/phone scans. Can apply best-effort fixes with `--fix` flag. | root |
| `diag_pairing.sh` | Comprehensive Bluetooth pairing diagnostics. Checks adapter status, agent/backend services, paired devices, recent pairing events, and provides recommendations. | root |


## Installation Order

For fresh installation:

1. **Configure Bluetooth**: `sudo ./scripts/ble/bt_configure_system.sh`
2. **Install helper and backends**: `sudo ./scripts/ble/ble_install_helper.sh`
3. **Install extras**: `sudo ./scripts/ble/ble_setup_extras.sh`

These are automatically called by the provisioning scripts in `provision/`.


## Backend Management

The system supports two keyboard backends:
- **uinput**: Classic Bluetooth using uinput device (bt_hid_uinput.service)
- **ble**: BLE HID over GATT (bt_hid_ble.service)

Backend selection is synchronized between `config.json` and `/etc/ipr-keyboard/backend`.

To switch backends:
```bash
./scripts/ble/ble_switch_backend.sh ble    # Switch to BLE backend
./scripts/ble/ble_switch_backend.sh uinput # Switch to uinput backend
```


## bt_kb_send Helper

The `bt_kb_send` helper script is the primary interface for sending text to paired devices:

- **Source**: `bt_kb_send.sh` (in this directory)
- **Installed to**: `/usr/local/bin/bt_kb_send`
- **Installer**: `ble_install_helper.sh`

### Usage

```bash
# Send text (waits for FIFO and notification readiness)
bt_kb_send "Hello world"

# Send text without waiting for notification
bt_kb_send --nowait "Quick text"

# Send text with custom wait time
bt_kb_send --wait 15 "Text with 15 second timeout"
```

The helper:
- Waits for the FIFO at `/run/ipr_bt_keyboard_fifo` to exist
- Waits for Windows to subscribe to InputReport notifications (flag file at `/run/ipr_bt_keyboard_notifying`)
- Writes text to the FIFO for the backend daemon to process


## Bluetooth Configuration

The `bt_configure_system.sh` script configures `/etc/bluetooth/main.conf`:

- **AutoEnable**: true (adapter powers on automatically)
- **ControllerMode**: le (BLE-only) or dual (supports both BLE and classic)
- **Systemd override**: Disables unused BlueZ plugins (SAP, AVRCP, A2DP, etc.)

Controller mode can be overridden via `/opt/ipr_common.env`:
```bash
BT_CONTROLLER_MODE=dual  # or "le"
```


## Diagnostics

### BLE Visibility Issues

If the Pi is not visible to Windows/phone:
```bash
sudo ./scripts/ble/diag_bt_visibility.sh         # Diagnose only
sudo ./scripts/ble/diag_bt_visibility.sh --fix   # Apply fixes
```

### Pairing Issues

For comprehensive pairing diagnostics:
```bash
sudo ./scripts/ble/diag_pairing.sh
```

### Test Pairing Workflow

For interactive pairing test with monitoring:
```bash
sudo ./scripts/ble/test_pairing.sh ble
```


## See Also

- [Main Scripts README](../README.md) - All project scripts
- [Bluetooth Pairing Guide](../../BLUETOOTH_PAIRING.md) - Detailed pairing troubleshooting
- [Services Documentation](../../SERVICES.md) - Systemd services reference
- [Main README](../../README.md) - Project overview
