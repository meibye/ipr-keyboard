# Device Bring-Up

Bring-up procedure aligned to current provisioning scripts.

## Supported Target Pattern

- Raspberry Pi OS Lite (Bookworm)
- Repo + config staged on device
- `/opt/ipr_common.env` present

## Recommended Path: Provisioning Wizard

```bash
sudo ./provision/provision_wizard.sh
```

The wizard drives `00` through `06`, including reboot checkpoints.

## Manual Bring-Up

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

## Expected Services After Step 04

- `ipr_keyboard.service`
- `bt_hid_ble.service`
- `bt_hid_agent_unified.service`
- `ipr-provision.service`

## Verification Checklist

- `systemctl status ipr_keyboard.service`
- `systemctl status bt_hid_ble.service`
- `systemctl status bt_hid_agent_unified.service`
- `curl http://localhost:8080/health`
- `bt_kb_send "smoke test"` (after pairing/notify subscription)

## Troubleshooting Entry Points

- `./scripts/diag_status.sh`
- `./scripts/diag_troubleshoot.sh`
- `sudo ./scripts/ble/diag_pairing.sh`
- `sudo ./scripts/ble/diag_bt_visibility.sh --fix`
