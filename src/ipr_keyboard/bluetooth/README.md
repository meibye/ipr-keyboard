# Bluetooth Module

This module provides Bluetooth HID (Human Interface Device) keyboard functionality for sending text to paired devices.

## Overview

The bluetooth module wraps a system-level Bluetooth HID helper script to send keyboard input to paired devices. It provides a simple Python interface while delegating the actual Bluetooth communication to an external helper binary.

## Files

- **`keyboard.py`** - Main BluetoothKeyboard class
- **`__init__.py`** - Module initialization

## Related Scripts

- The Bluetooth HID helper script (`/usr/local/bin/bt_kb_send`) is installed and managed by `scripts/03_install_bt_helper.sh` in the project root. Use this script to install or update the helper as required by the Bluetooth module.

## BluetoothKeyboard Class

The `BluetoothKeyboard` class is a wrapper around the system Bluetooth HID helper.

### Key Methods

#### `__init__(helper_path: str = "/usr/local/bin/bt_kb_send")`
Initialize the Bluetooth keyboard wrapper.
- **Parameters**: 
  - `helper_path` - Path to the Bluetooth HID helper script
- **Default**: `/usr/local/bin/bt_kb_send`

#### `is_available() -> bool`
Check if the Bluetooth helper is installed and available.
- **Returns**: `True` if helper exists and responds, `False` otherwise
- **Usage**: Call before attempting to send text to gracefully handle missing helper

#### `send_text(text: str) -> bool`
Send text to the paired device via Bluetooth keyboard emulation.
- **Parameters**:
  - `text` - String to send as keyboard input
- **Returns**: `True` if successful, `False` on error
- **Behavior**: 
  - Calls external helper script with text as argument
  - Logs operation and any errors
  - Returns `False` if helper not found or exits with error

## Bluetooth Helper Script

The module relies on an external helper script (`bt_kb_send`) installed at `/usr/local/bin/bt_kb_send`. This helper handles the low-level Bluetooth HID communication.

### Helper Installation

The helper is installed by the setup scripts:
```bash
sudo ./scripts/03_install_bt_helper.sh
```

### Helper Requirements

The helper script must:
- Accept `--help` flag for availability checking
- Accept text as command-line argument
- Exit with code 0 on success
- Handle Bluetooth HID protocol communication

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
- Bluetooth HID helper script installed
- Paired Bluetooth device (typically done from the target device)
- Appropriate permissions to execute helper script
