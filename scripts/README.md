# scripts/

Operational scripts for installation, diagnostics, testing, and service control.

## Top-Level Scripts

| File | Purpose |
|---|---|
| `env_set_variables.sh` | Shared env defaults (`IPR_USER`, `IPR_PROJECT_ROOT`) |
| `sys_install_packages.sh` | System dependency install and optional user venv setup |
| `sys_setup_venv.sh` | Creates project venv and installs package/deps |
| `sys_sync_copilot_prompts.sh` | Sync/check no-drift mirrors for `docs/copilot/*.md` |
| `dev_run_app.sh` | Runs `python -m ipr_keyboard.main` in foreground |
| `dev_run_webserver.sh` | Runs `python -m ipr_keyboard.web.server` directly |
| `diag_status.sh` | Quick environment/service/Bluetooth/web status snapshot |
| `diag_troubleshoot.sh` | Comprehensive local diagnostics |
| `test_smoke.sh` | Script-level smoke validation |
| `test_e2e_demo.sh` | Foreground end-to-end flow test |
| `test_e2e_systemd.sh` | Systemd service end-to-end flow test |
| `usb_setup_mount.sh` | Configure persistent USB mount (fstab) |
| `usb_mount_mtp.sh` | Toggle MTP mount via `jmtpfs` |
| `usb_sync_cache.sh` | Run `ipr_keyboard.usb.mtp_sync` wrapper |
| `scmd.sh` | Interactive script launcher/menu |
| `launch_claude.ps1` | Local Windows helper for Claude launch precheck |

## Subdirectories and Their Files

### `scripts/ble/`

- `bt_configure_system.sh`
- `ble_install_helper.sh`
- `ble_setup_extras.sh`
- `bt_kb_send.sh`
- `ble_show_bt_mac_for_windows.sh`
- `diag_bt_visibility.sh`
- `diag_pairing.sh`
- `test_bluetooth.sh`
- `test_pairing.sh`

### `scripts/service/`

- installers/managers: `svc_install_bt_gatt_hid.sh`, `svc_install_all_services.sh`, `svc_install_systemd.sh`, `svc_enable_services.sh`, `svc_disable_services.sh`, `svc_disable_all_services.sh`, `svc_status_services.sh`, `svc_tail_all_logs.sh`
- monitor: `svc_status_monitor.py`
- service payloads: `bin/bt_hid_agent_unified.py`, `bin/bt_hid_ble_daemon.py`, `svc/bt_hid_agent_unified.service`, `svc/bt_hid_ble.service`

### `scripts/headless/`

- `net_provision_hotspot.sh`, `net_provision_web.py`, `net_factory_reset.sh`, `gpio_factory_reset.py`, `usb_otg_setup.sh`, `ipr-provision.service`

### `scripts/extras/`

- `ipr_ble_diagnostics.sh`
- `ipr_ble_hid_analyzer.py`

### `scripts/rpi-debug/`

- installer/config: `install_dbg_tools.sh`, `dbg_common.env`, `dbg_sudoers_list.txt`
- runtime diagnostics: `dbg_stack_status.sh`, `dbg_diag_bundle.sh`, `dbg_pairing_capture.sh`, `dbg_bt_restart.sh`, `dbg_bt_soft_reset.sh`, `dbg_bt_bond_wipe.sh`, `dbg_deploy.sh`
- Windows tooling under `scripts/rpi-debug/tools/`

### `scripts/rpi-debug/tools/`

- `dbg_common.ps1`
- `setup_ipr_mcp.ps1`
- `setup_pc_copilot_dbg.ps1`
- `gen_mcp_whitelist.ps1`

### `scripts/lib/`

- `bt_agent_unified_env.sh` shared helper for unified agent env/profile management

## Current vs Legacy Notes

- Current service design is BLE-centric (`bt_hid_ble.service` + `bt_hid_agent_unified.service`).
- Some scripts still contain legacy branches for `uinput` or `KeyboardBackend`. Keep them tagged as legacy candidates per `ARCHITECTURE.md`.
