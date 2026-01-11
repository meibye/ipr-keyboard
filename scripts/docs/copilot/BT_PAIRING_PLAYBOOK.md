# Bluetooth Pairing Playbook (Windows 11 ↔ RPi BLE HID)

This playbook helps classify pairing failures and choose the next diagnostic action.

## Always start
1) Run /usr/local/bin/dbg_diag_bundle.sh
2) Run /usr/local/bin/dbg_pairing_capture.sh 60 while user attempts pairing on Windows
3) Classify failure mode using the sections below

---

## Failure mode A — Pairing rejected / auth failure
Signals:
- Logs mention: "AuthenticationFailed", "Insufficient authentication", "Insufficient encryption"
- btmon shows pairing/encryption negotiation fails

Next actions:
1) Verify btmgmt settings: bondable, secure-conn, ssp, privacy
2) Confirm agent behavior: passkey confirmation / JustWorks mismatch
3) Ensure GATT characteristic security/permissions match Windows expectations
4) Re-test with capture

Likely fixes:
- Adjust security flags on characteristics
- Ensure BlueZ agent handles the pairing method Windows uses
- Ensure device is bondable + secure connections align with Windows

---

## Failure mode B — Pairs, then immediately disconnects
Signals:
- Windows shows paired briefly then fails
- btmon shows disconnect reason shortly after pairing

Next actions:
1) Confirm service stays up during pairing (systemd restart loops?)
2) Look for exceptions in bt_hid_ble service logs
3) Confirm advertising/connection parameters stable
4) Re-run capture with longer duration (90s)

Likely fixes:
- Fix crash in GATT callbacks
- Ensure characteristics exist as expected (Attribute Not Found errors)
- Ensure CCCD/notify subscription works

---

## Failure mode C — Pairing succeeds, but HID input never works
Signals:
- Windows says connected/paired
- No StartNotify in service logs
- Notify works on other devices but not Windows

Next actions:
1) Verify Report Map, Report Reference descriptors, CCCD behavior
2) Confirm notify property and permissions for Input Report characteristic
3) Confirm correct HID service UUID and characteristic UUIDs

Likely fixes:
- Correct characteristic flags (read/notify + security)
- Ensure CCCD is present and handled correctly
- Ensure report IDs/types match HID over GATT expectations

---

## Failure mode D — Windows can't discover / can't see device
Signals:
- Not visible in scan
- Advertising not active, or device name missing

Next actions:
1) btmgmt advertising status and LE settings
2) bluetoothd running and not blocked by rfkill
3) verify adapter powered + discoverable

Likely fixes:
- fix advertising setup, local name, intervals
- ensure no conflicting services own the adapter

---

## Safe recovery ladder (increasing impact)
1) /usr/local/bin/dbg_bt_restart.sh
2) /usr/local/bin/dbg_bt_soft_reset.sh
3) (ONLY with approval) bond wipe on Pi and Windows + re-pair

Stop after 3 iterations: deliver most likely cause + recommended code/config change.
