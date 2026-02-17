# Diagnostic Agent Prompt (RPi BLE HID)

Use this when investigating pairing/service failures.

## Mission

Diagnose and resolve Bluetooth HID pairing or runtime failures for current BLE architecture.

## Hard Constraints

1. Plan first, then execute.
2. Prefer bounded diagnostic scripts over ad-hoc unbounded shell output.
3. No destructive action without explicit approval.
4. Stop after 3 iterations and summarize root cause + corrective action.

## Canonical Current Services

- `bt_hid_agent_unified.service`
- `bt_hid_ble.service`
- `ipr_keyboard.service`

## Preferred Commands

- `dbg_stack_status.sh`
- `dbg_diag_bundle.sh`
- `dbg_pairing_capture.sh 60`
- `dbg_bt_restart.sh`
- `dbg_bt_soft_reset.sh`

Approval-gated destructive command:
- `dbg_bt_bond_wipe.sh <MAC>`

## Architecture Alignment Rule

When cleanup/refactor questions appear, compare findings against `ARCHITECTURE.md` and flag legacy/deprecated implementations as architectural dead code candidates.
