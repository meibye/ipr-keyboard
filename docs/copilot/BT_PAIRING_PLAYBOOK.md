# Bluetooth Pairing Playbook

Playbook for classifying BLE HID pairing failures.

## Start Here

1. `dbg_diag_bundle.sh`
2. `dbg_pairing_capture.sh 60`
3. Classify by failure mode below

## Mode A: Authentication/Authorization Failure

Signals:
- auth failures in agent or btmon logs
- pairing fails before stable connection

Actions:
- validate `bt_hid_agent_unified.service` health
- inspect recent agent journal for `RequestConfirmation`/`AuthorizeService`
- rerun bounded pairing capture

## Mode B: Pairing Succeeds then Drops

Signals:
- temporary connection then immediate disconnect
- BLE daemon exceptions or restarts

Actions:
- check `bt_hid_ble.service` restart loops
- inspect BLE daemon journal around disconnect window
- verify service dependencies and adapter readiness

## Mode C: Paired but No Input

Signals:
- connection exists but no keystrokes delivered

Actions:
- verify notify subscription behavior
- verify helper path and FIFO producer (`bt_kb_send`)
- verify BLE daemon is active and consuming FIFO

## Mode D: Device Not Discoverable

Signals:
- host cannot see device during scan

Actions:
- run `scripts/ble/diag_bt_visibility.sh`
- run with `--fix` if approved
- verify adapter powered/discoverable and service state

## Recovery Ladder

1. `dbg_bt_restart.sh`
2. `dbg_bt_soft_reset.sh`
3. `dbg_bt_bond_wipe.sh <MAC>` and re-pair (approval required)
