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

## Symptom: send hangs and never returns

`bt_kb_send`, `test_smoke.sh`, or a USB→BT transfer stops after
`Sending text via BLE HID keyboard` and never completes.

**Cause.** Text was written to the FIFO while no BLE host had notifications
enabled. The daemon's FIFO worker holds that text in its queue and, until it
drains, does not reopen the FIFO for reading. With no reader attached, the next
writer blocks in `open(O_WRONLY)` indefinitely — so one undeliverable send wedges
every later send until the service is restarted.

**Confirm it.** The worker thread sits in `nanosleep` with no FIFO reader:

```bash
P=$(pgrep -f bin/bt_hid_ble_daemon.py | head -1)
for t in /proc/$P/task/*; do echo "$(basename $t) $(sudo cat $t/wchan)"; done
sudo fuser -v /run/ipr_bt_keyboard_fifo    # empty output = no reader
```

A healthy idle worker shows `wait_for_partner` (blocked in `open()` for reading);
a wedged one shows `hrtimer_nanosleep`.

**Recover.** `sudo systemctl restart bt_hid_ble.service`

**Mitigations now in place.** The worker's pre-drain wait is bounded by
`BLE_QUEUE_DRAIN_WAIT_SECS` (default 5) and its queue by `BLE_QUEUE_MAX_CHARS`
(default 4096), so it always returns to reading. `bt_kb_send` /
`bt_kb_send_file` bound their writes with `BT_KB_WRITE_TIMEOUT_SECS` (default 5 /
30), and `BluetoothKeyboard.send_text()` bounds the helper at 30 s, reporting
`BT send timed out` rather than blocking its thread.

## Recovery Ladder

1. `sudo ./scripts/rpi-debug/dbg_bt_restart.sh`
2. `sudo ./scripts/rpi-debug/dbg_bt_soft_reset.sh`
3. `sudo ./scripts/rpi-debug/dbg_bt_bond_wipe.sh <MAC>` and remove host-side bond

## Known Legacy References

Some scripts still include `uinput` branches (`bt_hid_uinput.service` expectations). Current shipped service units are BLE-centric. Use `ble` path unless you intentionally reintroduce uinput units.
