# src/ipr_keyboard/bluetooth/

Bluetooth output wrapper used by the application.

## Files

- `keyboard.py`
- `__init__.py`

## Current Behavior

`BluetoothKeyboard`:
- checks helper availability at `/usr/local/bin/bt_kb_send`
- sends text by running helper as subprocess
- does not implement low-level Bluetooth/GATT directly

The BLE daemon and pairing agent are external system services installed from `scripts/service/`.

## Operational Dependency

The send path requires:
- `/usr/local/bin/bt_kb_send` present and executable
- running BLE stack (`bt_hid_ble.service`, `bt_hid_agent_unified.service`)

Legacy references to `uinput` in other docs/scripts are not defined in this package.
