# Pairing Fix Summary

Historical context retained, updated to current implementation state.

## What Is Current

- The active agent implementation is `scripts/service/bin/bt_hid_agent_unified.py`.
- Default capability is `NoInputNoOutput` via `/etc/default/bt_hid_agent_unified` helper profile (`nowinpasskey`).
- BLE pairing behavior is driven by:
  - `RequestConfirmation` auto-accept/trust
  - `AuthorizeService` auto-accept/trust

## What Is No Longer Canonical

Older notes in this repo referenced alternate agent/service combinations and a broader backend-switching architecture (`uinput`/backend manager). Those are not the canonical current path.

## Verification Commands

```bash
systemctl status bt_hid_agent_unified.service
systemctl status bt_hid_ble.service
sudo journalctl -u bt_hid_agent_unified.service -n 200 --no-pager
sudo ./scripts/ble/diag_pairing.sh
```

## Cleanup Recommendation

Use `ARCHITECTURE.md` to flag remaining legacy pairing paths as architectural dead code candidates before adding new pairing logic.

---

## Solution Summary: Bluetoothd BT_SECURITY Error and Connection Fluctuation

### Problem
- Device fluctuates between connected/disconnected on PC.
- RPI logs repeated `setsockopt(BT_SECURITY): Invalid argument (22)` errors from bluetoothd.

### Root Cause
- BlueZ or kernel does not support the requested BT_SECURITY socket option, often triggered by GATT characteristic flags like `secure-read`/`secure-write`.
- Privacy/mode settings or plugin configuration may also cause instability.

### Actions Taken
1. **Codebase Audit:**
   - No direct socket option misuse in Python BLE/HID agent/daemon.
   - GATT flags filtered to remove unsupported `secure-read`/`secure-write`.
2. **Config Review:**
   - Confirmed `/etc/bluetooth/main.conf` sets `Privacy=off`, `ControllerMode=le`, and `Experimental=true`.
   - Systemd override disables unnecessary plugins for stability.
3. **.gitattributes Updated:**
   - Ensures all scripts/configs use LF line endings for cross-platform compatibility.

### What You Should Do Next
1. **Restart Services:**
   - Restart bluetoothd and BLE/HID services on the RPI.
2. **Test:**
   - Re-pair and test device connection from the PC.
3. **If Issues Persist:**
   - Collect new logs and share for further analysis.

### References
- See `scripts/ble/bt_configure_system.sh` and `scripts/service/bin/bt_hid_ble_daemon.py` for implementation details.
- `.gitattributes` now enforces LF endings for all relevant files.

For further troubleshooting, use the provided debug scripts in `scripts/rpi-debug/`.
