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

Three intervals, chosen by whether a host is actually connected — never by a
timer alone:

| Mode | Interval | When |
|---|---|---|
| fast | 40–80 ms | the first `BT_FAST_ADV_SECS` (300) after the link goes |
| medium | 150–300 ms | still no host, for as long as it takes |
| slow | 500–1000 ms | **only** while a host is connected |

BlueZ's default is over a second, so fast puts the device in the host's first
scan window rather than its twentieth.  Medium keeps it findable without
hammering the band: Wi-Fi and Bluetooth share one radio on a Pi Zero, so
advertising hard for ever costs the dashboard airtime.

**The first version of this got it wrong, and the device showed exactly how.**
It backed off straight to slow when the fast window expired, whether or not a
host had ever connected:

```
18:07:34  Registered GATT+ADV (fast, 40-80 ms)
18:12:47  Registered GATT+ADV (slow, 500-1000 ms)   <- PC still absent
          NO LINK after 532 s
```

So a device still waiting for its PC went quiet five minutes in, at the worst
possible moment.  Only a *connected* host earns the slow interval now, and a
dropped link re-arms fast — the back-off used to be one-way, so a PC that
slept was never chased.

Losing the link is noticed two ways, because one is not enough: `StopNotify`
when BlueZ calls it, and the 30 s bond-state tick, which catches the abrupt
disconnects where it does not.

All of it is env-settable in `/opt/ipr_common.env`: `BT_FAST_ADV_MIN_MS`,
`BT_FAST_ADV_MAX_MS`, `BT_MEDIUM_ADV_MIN_MS`, `BT_MEDIUM_ADV_MAX_MS`,
`BT_SLOW_ADV_MIN_MS`, `BT_SLOW_ADV_MAX_MS`, `BT_FAST_ADV_SECS`.

The journal says which is in force:

```
[ble] Registered GATT+ADV on /org/bluez/hci0 (fast, 40-80 ms)
```

### What it does not do

Advertising fast makes the device easy to **find**; it cannot make Windows
**look**.  Measured both ways on the same device within three minutes:

* host already engaged (right after a daemon restart) — reconnected in **1 s**
* host idle after a full reboot — still absent after **9 minutes**

So this shortens the gap when the host is scanning, and does nothing when it is
not.  If a PC has not come back, open its Bluetooth settings; that is not a
workaround for a device fault, it is the host deciding.

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


## Why re-pairing was the only cure

Removing the device on the PC and pairing again was the only thing that worked
after a run of daemon reinstalls — adapter power management, toggling Bluetooth
and restarting the Bluetooth service all failed.  That points at the one piece
of state a re-pair clears and nothing else does: **the host's cached copy of
our attribute database**.

A bonded LE central caches a device's handles rather than discovering them on
every connection.  BlueZ allocates handles from the order in which services,
characteristics and descriptors are registered, so a layout change moves them,
the cache goes stale, and the host talks to the wrong attributes — which
presents as "the device advertises, the PC sees it, nothing works".

### Do not add a Service Changed characteristic for this

Service Changed (`0x2A05`, in the Generic Attribute service `0x1801`) is
exactly the mechanism for telling a bonded host to discard that cache — and
**BlueZ already implements it**, in its own GATT database, and sends it when
the registered services change.  An application that registers `0x1801` is
refused:

```
org.bluez.Error.Failed: Failed to create entry in database
```

That failure is not contained.  `RegisterAdvertisement` only runs after
`RegisterApplication` succeeds, so a rejected `0x1801` means **no
advertisement at all**: the device becomes invisible to every host and the
daemon crash-loops on its retry budget.  This was tried on the production
device and did precisely that — `ActiveInstances: 0`, five restarts, the PC
unable to see the device to pair with it.

`tests/bluetooth/test_ble_daemon_advertising.py` now fails if `0x1801` comes
back.  The services BlueZ leaves to the application are HID (`1812`), Device
Information (`180a`) and Battery (`180f`), and those are the three the daemon
registers.

### So what to do about a stale cache

Nothing on the device, for now.  BlueZ sends Service Changed on its own when
the application's services change; if a host still ends up stale, the
remaining recovery is the one that works: remove the device on the PC and pair
again.  Worth investigating before building anything: whether BlueZ actually
emits the indication across a daemon restart (it rebuilds the application's
part of the database from scratch), and whether Windows honours it.  `btmon`
during a reconnect would show it.


## After reinstalling the device

**Remove "IPR Keyboard" on the PC before reinstalling the device, or straight
after.**  A bond has two halves.  A fresh install wipes the device's half, but
the PC keeps its own — and the device still has the same public address, so
the PC recognises it and tries to reconnect with keys the device no longer
has.

What it looks like, measured on 5 October 2026 after a fresh install:

* the PC's Bluetooth panel toggles between **Connected** and **Not
  connected**, for as long as you leave it;
* the device's panel says **`PC connecting…`** (it used to show the PC's MAC
  address, which BlueZ uses as the name of a device it has never bonded with);
* on the device, `bluetoothctl info <PC-MAC>` shows `Paired: no`, and the alias
  is the address itself.

The link comes up, encryption fails because only one side has a key, the link
drops, and the PC tries again.  **The device cannot fix this** — it cannot
accept a key it does not have.  Remove the device on the PC and pair again.

The panel's first-pairing state is the useful check on a fresh install: with
nothing ever paired it says `Waiting for PC…`; with a stale PC trying, it says
`PC connecting…` and never settles.

## LE Audio services are disabled

BlueZ's LE Audio servers — the `vcp`, `micp` and `bass` plugins — register
Volume Control, Audio Input Control, Volume Offset Control, Microphone Control
and Broadcast Audio Scan in the GATT database when they are loaded.  On a
device that is a keyboard and nothing else, a PC enumerating its services then
tries to set up an audio device that does not exist.  Both installers that
write bluetoothd's `--noplugin` list now include them, and the lists match:
`svc_install_bt_gatt_hid.sh` (provisioning step 04, the one in force) and
`bt_configure_system.sh` (step 01).  The post-provision audit checks both the
override (O.15) and the adapter itself (O.16).

