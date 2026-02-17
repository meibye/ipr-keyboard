# scripts/service/

Systemd service installers, service units, and monitoring tools.

## Directory Contents

### Installers and Managers

- `svc_install_bt_gatt_hid.sh`: installs BLE daemon + unified pairing agent units and executables
- `svc_install_all_services.sh`: wrapper around core service install
- `svc_install_systemd.sh`: writes/enables `ipr_keyboard.service`
- `svc_enable_services.sh`: enables unified agent, BLE daemon, and `ipr_keyboard.service`
- `svc_disable_services.sh`: disables/stops service set
- `svc_status_services.sh`: prints status for key services
- `svc_tail_all_logs.sh`: tails relevant journals
- `svc_status_monitor.py`: interactive service/status TUI

### Executables Installed by `svc_install_bt_gatt_hid.sh`

- `bin/bt_hid_agent_unified.py` -> `/usr/local/bin/bt_hid_agent_unified.py`
- `bin/bt_hid_ble_daemon.py` -> `/usr/local/bin/bt_hid_ble_daemon.py`

### Unit Files Installed by `svc_install_bt_gatt_hid.sh`

- `svc/bt_hid_agent_unified.service`
- `svc/bt_hid_ble.service`

## Current Canonical Service Set

- `ipr_keyboard.service`
- `bt_hid_agent_unified.service`
- `bt_hid_ble.service`

## Notes

- No `bt_hid_uinput.service` unit file is shipped in `scripts/service/svc/`.
