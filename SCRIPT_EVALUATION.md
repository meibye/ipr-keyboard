# Script Evaluation

Evaluation aligned to repository state on 2026-02-15.

## Keep (Core)

- Provisioning pipeline: `provision/00_bootstrap.sh` .. `provision/06_verify.sh`, `provision/provision_wizard.sh`
- Service install/manage: `scripts/service/svc_install_bt_gatt_hid.sh`, `scripts/service/svc_install_systemd.sh`, `scripts/service/svc_enable_services.sh`, `scripts/service/svc_disable_services.sh`
- Bluetooth core: `scripts/ble/bt_configure_system.sh`, `scripts/ble/ble_install_helper.sh`, `scripts/ble/ble_setup_extras.sh`
- Runtime diagnostics: `scripts/diag_status.sh`, `scripts/diag_troubleshoot.sh`, `scripts/ble/diag_pairing.sh`, `scripts/ble/diag_bt_visibility.sh`
- Tests and demos: `scripts/test_smoke.sh`, `scripts/test_e2e_demo.sh`, `scripts/test_e2e_systemd.sh`

## Keep (Operational Extras)

- Headless provisioning stack in `scripts/headless/`
- Copilot/MCP debug stack in `scripts/rpi-debug/`
- BLE extras in `scripts/extras/`

## Legacy / Drift Candidates

- `scripts/service/svc_disable_all_services.sh`: legacy duplicate of `svc_disable_services.sh`
- `scripts/ble/test_bluetooth.sh`: hard-codes `bt_hid_uinput.service`
- `scripts/ble/test_pairing.sh`: retains `uinput` branch in current BLE-centric service set
- `scripts/diag_troubleshoot.sh`: backend detection fallback references non-canonical `KeyboardBackend`
- `scripts/docs/copilot/*`: mirrored prompt docs (potential duplication with `docs/copilot/*`)

## Recommendation

Do not delete legacy candidates blindly. First classify against `ARCHITECTURE.md` and confirm no production dependency chain still requires them.
