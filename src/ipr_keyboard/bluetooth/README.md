# src/ipr_keyboard/bluetooth/

Bluetooth output wrapper used by the application.

## Files

- `keyboard.py`: `BluetoothKeyboard`

## Current Behavior

`BluetoothKeyboard`:
- checks helper availability at `/usr/local/bin/bt_kb_send`
- sends text by running that helper, which only writes it to the BLE
  daemon's FIFO and returns
- then waits, through `bt_progress` (`/run/ipr_bt_progress.json`), until the
  daemon has actually typed it — so "sent" means the characters reached the
  PC, and the dashboard and panel can show a live character count
- does not implement low-level Bluetooth/GATT itself

The BLE daemon (`bt_hid_ble.service`) and pairing agent
(`bt_hid_agent_unified.service`) are system services installed from
`scripts/service/`.  The typing speed reaches the daemon at runtime through
`/run/ipr_bt_key_delay` (`keydelay.py`).

## Operational Dependency

The send path requires:
- `/usr/local/bin/bt_kb_send` present and executable
- running BLE stack (`bt_hid_ble.service`, `bt_hid_agent_unified.service`)
