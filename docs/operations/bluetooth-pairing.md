# Bluetooth Pairing Guide

Current pairing model for `ipr-keyboard`.

## Active Pairing Stack

- Agent service: `bt_hid_agent_unified.service`
- Agent executable: `scripts/service/bin/bt_hid_agent_unified.py`
- Capability default: `NoInputNoOutput`
- BLE HID service: `bt_hid_ble.service`

## Pairing Steps

1. Ensure services are running:
   - `systemctl status bt_hid_agent_unified.service`
   - `systemctl status bt_hid_ble.service`
2. Put host device into Bluetooth add/pair mode.
3. Pair with the Raspberry Pi BLE keyboard identity.
4. Validate notification subscription and send test payload:
   - `bt_kb_send "hello"`

## Primary Diagnostics

- Full pairing diagnostics: `sudo ./scripts/ble/diag_pairing.sh`
- Visibility diagnostics: `sudo ./scripts/ble/diag_bt_visibility.sh`
- Guided pairing script: `sudo ./scripts/ble/test_pairing.sh ble`
- Status overview: `./scripts/diag_status.sh`

## Recovery Ladder

1. `sudo ./scripts/rpi-debug/dbg_bt_restart.sh`
2. `sudo ./scripts/rpi-debug/dbg_bt_soft_reset.sh`
3. `sudo ./scripts/rpi-debug/dbg_bt_bond_wipe.sh <MAC>` and remove host-side bond

## Known Legacy References

Some scripts still include `uinput` branches (`bt_hid_uinput.service` expectations). Current shipped service units are BLE-centric. Use `ble` path unless you intentionally reintroduce uinput units.
