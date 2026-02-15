# ipr-keyboard

IrisPen text-file ingestion to Bluetooth keyboard output on Raspberry Pi.

## Current State (audited 2026-02-15)

The implementation currently runs a BLE HID over GATT stack:
- Python app entry point: `src/ipr_keyboard/main.py`
- Bluetooth send helper used by app: `/usr/local/bin/bt_kb_send`
- Active backend service design: `bt_hid_ble.service` + `bt_hid_agent_unified.service`
- Main app service: `ipr_keyboard.service`
- Headless hotspot service: `ipr-provision.service`

The app itself does not implement backend switching in `config.json`; it only persists:
- `IrisPenFolder`
- `DeleteFiles`
- `Logging`
- `MaxFileSize`
- `LogPort`

## Runtime Flow

1. `ipr_keyboard.main` starts:
   - Flask API thread (`/health`, `/status`, `/config/`, `/logs/`, `/pairing`)
   - USB watch loop thread (folder polling)
2. New file is detected in `IrisPenFolder`
3. File content is read and sent via `BluetoothKeyboard.send_text()`
4. `BluetoothKeyboard` shells out to `/usr/local/bin/bt_kb_send`
5. `bt_hid_ble_daemon.py` consumes FIFO payload and emits BLE HID reports

## Quick Start

### Provisioning (recommended)

Use `provision/provision_wizard.sh` or run steps manually:

```bash
sudo ./provision/00_bootstrap.sh
sudo ./provision/01_os_base.sh
sudo reboot
sudo ./provision/02_device_identity.sh
sudo reboot
sudo ./provision/03_app_install.sh
sudo ./provision/04_enable_services.sh
sudo ./provision/05_copilot_debug_tools.sh   # optional
sudo ./provision/06_verify.sh
```

### Local Development

```bash
./scripts/sys_setup_venv.sh
./scripts/dev_run_app.sh
pytest
```

## Directory Guide

- `ARCHITECTURE.md`: canonical module/state map, including legacy/deprecated patterns
- `provision/`: end-to-end device bootstrap flow
- `scripts/`: install, diagnostic, test, service management scripts
- `src/ipr_keyboard/`: Python application package
- `tests/`: pytest suite
- `docs/copilot/`: agent prompts and troubleshooting playbooks

## Important Notes

- Current service units shipped in repo do **not** include `bt_hid_uinput.service`.
- Some diagnostic scripts still contain legacy branches for `uinput` or `KeyboardBackend`; treat those as historical compatibility paths.
- `src/ipr_keyboard/web/pairing_routes.py` includes `/pairing/activate-ble` that calls `ipr_backend_manager.service`, which is not shipped in current service units.

For cleanup/refactor work, start from `ARCHITECTURE.md`.
