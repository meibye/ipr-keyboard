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


## Getting the PC back after a restart

A reboot, or a restart of `bt_hid_ble.service`, takes the radio down and the
BLE link with it.  The device is a **peripheral**: it advertises and waits, and
the **host decides** when to come back.  Nothing on the device can call the PC.

Measured once on a Zero 2 W: after a restart from the magnet menu, a Windows
host took **26 minutes** to reconnect on its own.

### What the device does about it

It advertises **fast** while no host is connected — 40–80 ms instead of
BlueZ's default of over a second — so the host finds it in its first scan
window rather than its twentieth.  It backs off to 500–1000 ms as soon as a
host subscribes, or after `BT_FAST_ADV_SECS` (default 300) without one,
because Wi-Fi and Bluetooth share one radio on a Pi Zero and advertising hard
forever costs the dashboard airtime.

All four values are env-settable in `/opt/ipr_common.env`:
`BT_FAST_ADV_MIN_MS`, `BT_FAST_ADV_MAX_MS`, `BT_SLOW_ADV_MIN_MS`,
`BT_SLOW_ADV_MAX_MS`, plus `BT_FAST_ADV_SECS`.

The journal says which is in force:

```
[ble] Registered GATT+ADV on /org/bluez/hci0 (fast, 40-80 ms)
```

**Directed advertising is what the spec offers for this, and BlueZ does not
expose it.**  `ADV_DIRECT_IND` aimed at the bonded peer is exactly the right
mechanism, but `org.bluez.LEAdvertisement1` has no peer-address property — in
5.82 the strings `PeerAddress` and `Directed` do not appear in the daemon
binary at all.  Driving it by raw HCI while `bluetoothd` owns the adapter would
fight with it, so fast advertising is the supported approximation.  If a future
BlueZ gains the property, the advertisement object is where to add it.

### What the panel says

While no host is connected the PC line distinguishes two cases, because the
user's next move differs:

| Panel | Meaning | What to do |
|---|---|---|
| `Reconnect from PC` | a PC is paired, but away | open Bluetooth on the PC |
| `Waiting for PC…` | nothing has ever been paired | pair one |

The hint needs to know whether a bond exists, and BlueZ keeps bonds in
`/var/lib/bluetooth`, which is `0700 root` — unreadable by the application.
The daemon therefore publishes the bond state to `/run/ipr_bt_link.json`, the
same way it publishes typing progress, and `ipr_keyboard/bt_link.py` reads it.
An older daemon publishes nothing, and the panel then keeps saying
`Waiting for PC…`.

Neither case is `NOT READY`: a PC that is simply switched off is not a fault,
and crying wolf would make the warning tier worthless.

### If the PC still will not come back

1. Open **Settings → Bluetooth & devices** on the PC.  Opening the page is
   usually enough.
2. Toggle Bluetooth off and on.
3. Remove the device on the PC and pair again.  The bond on the device side
   survives a reboot (`bluetoothctl info <mac>` shows `Bonded: yes`), so if the
   PC has forgotten it, that is a host-side state problem.

