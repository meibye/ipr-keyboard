# Bluetooth Module

This module provides Bluetooth HID (Human Interface Device) keyboard functionality for sending text to paired devices.

## Overview

The bluetooth module wraps a system-level Bluetooth HID helper script to send keyboard input to paired devices. It provides a simple Python interface while delegating the actual Bluetooth communication to an external helper binary.

The system supports two Bluetooth HID backends:
- **UInput backend** (`bt_hid_uinput.service`) — Classic Bluetooth using Linux uinput
- **BLE backend** (`bt_hid_ble.service`) — Bluetooth Low Energy with GATT HID service

Both backends read from the same FIFO pipe (`/run/ipr_bt_keyboard_fifo`) written to by the `bt_kb_send` helper.

## Files

- **`keyboard.py`** — Main BluetoothKeyboard class
- **`__init__.py`** — Module initialization

## Architecture

```
┌──────────────────────────┐
│ BluetoothKeyboard class  │
│ (src/ipr_keyboard/      │
│  bluetooth/keyboard.py)  │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ bt_kb_send               │
│ /usr/local/bin/bt_kb_send│
│ (writes to FIFO)         │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────────────┐
│ /run/ipr_bt_keyboard_fifo        │
│ (Named pipe)                     │
└────┬────────────────────┬────────┘
     │                    │
     ▼                    ▼
┌─────────────────┐  ┌──────────────────┐
│ bt_hid_uinput.  │  │ bt_hid_ble.      │
│ service         │  │ service          │
│ (uinput backend)│  │ (BLE backend)    │
└─────────────────┘  └──────────────────┘
```

## Related Scripts & Services

### Installation Scripts

| Script | Purpose |
|--------|---------|
| `scripts/ble_install_helper.sh` | Installs bt_kb_send, backends, and agent |
| `scripts/ble_setup_extras.sh` | Installs diagnostics and backend manager |
| `scripts/ble_switch_backend.sh` | Switch between uinput and BLE backends |

### Systemd Services

| Service | Description |
|---------|-------------|
| `bt_hid_uinput.service` | UInput backend daemon |
| `bt_hid_ble.service` | BLE backend daemon |
| `bt_hid_agent.service` | Bluetooth pairing & authorization agent |
| `ipr_backend_manager.service` | Backend selection service |

See [SERVICES.md](../../../SERVICES.md) for detailed service descriptions.

### Diagnostic Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| `diag_ble.sh` | BLE health check | `sudo ./scripts/diag_ble.sh` |
| `diag_ble_analyzer.sh` | HID report analyzer | `sudo ./scripts/diag_ble_analyzer.sh` |
| Web pairing wizard | Browser-based pairing | Visit `/pairing` endpoint |

## BluetoothKeyboard Class

The `BluetoothKeyboard` class is a wrapper around the system Bluetooth HID helper.

### Key Methods

#### `__init__(helper_path: str = "/usr/local/bin/bt_kb_send")`
Initialize the Bluetooth keyboard wrapper.
- **Parameters**: 
  - `helper_path` — Path to the Bluetooth HID helper script
- **Default**: `/usr/local/bin/bt_kb_send`

#### `is_available() -> bool`
Check if the Bluetooth helper is installed and available.
- **Returns**: `True` if helper exists and responds, `False` otherwise
- **Usage**: Call before attempting to send text to gracefully handle missing helper

#### `send_text(text: str) -> bool`
Send text to the paired device via Bluetooth keyboard emulation.
- **Parameters**:
  - `text` — String to send as keyboard input
- **Returns**: `True` if successful, `False` on error
- **Behavior**: 
  - Calls external helper script with text as argument
  - Helper writes to FIFO which is read by backend daemon
  - Logs operation and any errors
  - Returns `False` if helper not found or exits with error

## Bluetooth Helper Script

The module relies on an external helper script (`bt_kb_send`) installed at `/usr/local/bin/bt_kb_send`. This helper handles writing text to the FIFO pipe.

### Helper Installation

The helper is installed by the setup scripts:
```bash
sudo ./scripts/ble_install_helper.sh
```

### Helper Requirements

The helper script must:
- Accept `--help` flag for availability checking
- Accept text as command-line argument
- Write to `/run/ipr_bt_keyboard_fifo`
- Exit with code 0 on success

## Backend Selection

The system uses one of two backends (configured in `/etc/ipr-keyboard/backend` or `config.json`):

### UInput Backend
- Service: `bt_hid_uinput.service`
- Creates virtual keyboard via Linux uinput
- Types locally on the Pi via evdev
- Best for classic Bluetooth pairing

### BLE Backend
- Service: `bt_hid_ble.service`
- Registers BLE GATT HID service (UUID 0x1812)
- Advertises as BLE keyboard
- Sends HID reports via GATT notifications
- Best for modern BLE devices

Switch backends using:
```bash
sudo ./scripts/ble_switch_backend.sh
```

## Usage Example

```python
from ipr_keyboard.bluetooth.keyboard import BluetoothKeyboard

kb = BluetoothKeyboard()

# Check if Bluetooth is available
if not kb.is_available():
    print("Bluetooth helper not installed")
    exit(1)

# Send text to paired device
success = kb.send_text("Hello, World!")
if success:
    print("Text sent successfully")
else:
    print("Failed to send text")
```

## Danish Character Support

Both backends support Danish characters (æøåÆØÅ) with proper HID usage codes and keyboard layout mappings.

## Error Handling

The module handles several error conditions:
- **Helper not found**: Returns `False` and logs error
- **Helper execution failure**: Returns `False` and logs subprocess error
- **Graceful degradation**: Main application can run without Bluetooth (logs only mode)

## Logging

All operations are logged via the centralized logger:
- Info level: Normal operations (text sent)
- Error level: Helper not found or execution failures
- Includes text length in log messages for debugging

## Thread Safety

The `BluetoothKeyboard` class is thread-safe:
- No internal state beyond configuration
- Each `send_text()` call is independent
- Safe to use from multiple threads (though typically used from single USB monitor thread)

## Testing

Tests are located in `tests/bluetooth/test_keyboard.py`:
- Helper availability checking
- Text sending functionality
- Error handling scenarios

## System Requirements

- Linux system with Bluetooth capability
- Bluetooth HID helper script installed (`bt_kb_send`)
- One of the backend daemons running (`bt_hid_uinput.service` or `bt_hid_ble.service`)
- `bt_hid_agent.service` running for pairing support
- Paired Bluetooth device (typically done from the target device)
- Appropriate permissions to execute helper script

## Troubleshooting

If Bluetooth keyboard is not working:

1. **Check helper installation**:
   ```bash
   ls -l /usr/local/bin/bt_kb_send
   ```

2. **Check backend services**:
   ```bash
   systemctl status bt_hid_uinput.service
   systemctl status bt_hid_ble.service
   systemctl status bt_hid_agent.service
   ```

3. **Run diagnostics**:
   ```bash
   sudo ./scripts/diag_ble.sh
   ./scripts/diag_status.sh
   ```

4. **Check logs**:
   ```bash
   journalctl -u bt_hid_uinput.service -n 50
   journalctl -u bt_hid_ble.service -n 50
   journalctl -u bt_hid_agent.service -n 50
   ```

5. **Test helper directly**:
   ```bash
   echo "test" | /usr/local/bin/bt_kb_send "$(cat -)"
   ```

## See Also

- [SERVICES.md](../../../SERVICES.md) — Detailed service documentation
- [scripts/README.md](../../../scripts/README.md) — Setup scripts
- [Main README](../../../README.md) — Project overview

