# scripts/ble/

Bluetooth-specific scripts.

## Files

| File | Purpose |
|---|---|
| `bt_configure_system.sh` | Configures `/etc/bluetooth/main.conf` and bluetoothd override for BLE HID operation |
| `ble_install_helper.sh` | Installs helper dependencies and `/usr/local/bin/bt_kb_send` |
| `ble_setup_extras.sh` | Installs BLE diagnostics/analyzer tools and validates pairing web route/template wiring |
| `bt_kb_send.sh` | Source helper script copied to `/usr/local/bin/bt_kb_send` |
| `bt_kb_send_file.sh` | Sends full file content into BLE FIFO for end-to-end text validation |
| `ble_show_bt_mac_for_windows.sh` | Shows BT MAC in Linux + Windows-friendly format |
| `diag_bt_visibility.sh` | BLE visibility diagnostics with optional `--fix` |
| `diag_pairing.sh` | Pairing diagnostics and event analysis |
| `test_bluetooth.sh` | Manual Bluetooth send test for BLE service stack |
| `test_pairing.sh` | Interactive pairing flow test for BLE backend |

## Important Split of Responsibilities

- `ble_install_helper.sh` installs the helper script (`bt_kb_send`) and package prerequisites.
- `scripts/service/svc_install_bt_gatt_hid.sh` installs BLE daemon + agent services.

## Typical BLE Bring-Up Order

```bash
sudo ./scripts/ble/bt_configure_system.sh
sudo ./scripts/service/svc_install_bt_gatt_hid.sh
sudo ./scripts/ble/ble_install_helper.sh
sudo ./scripts/ble/ble_setup_extras.sh
sudo ./scripts/service/svc_enable_services.sh
```

## Runtime Notes

Scripts in this directory target the BLE service stack (`bt_hid_ble.service` + `bt_hid_agent_unified.service`).
