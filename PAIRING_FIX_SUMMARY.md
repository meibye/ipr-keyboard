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
