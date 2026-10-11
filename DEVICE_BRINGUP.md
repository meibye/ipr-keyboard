# Device Bring-Up

Bring-up procedure aligned to current provisioning scripts.

## Supported Target Pattern

- Raspberry Pi OS Lite, **Trixie or later** (Python >= 3.12; checked by
  `provision/00_bootstrap.sh`) — Pi Zero 2 W (64-bit) or Pi Zero W (32-bit)
- Repo + config staged on device
- `/opt/ipr_common.env` present

## Recommended Path: From the Administrator PC

First remove "IPR Keyboard" from the PC's Bluetooth settings (a stale bond
on the PC reconnects in a loop).  Then, from Git Bash or WSL on the PC:

```bash
bash ./scripts/deploy/host_push_to_device.sh <host>
ssh -t <host> 'sudo mv /tmp/ipr_common.env /opt/ipr_common.env \
  && sudo chmod 0600 /opt/ipr_common.env \
  && sudo ~/dev/ipr-keyboard/scripts/deploy/device_bootstrap.sh --unattended'
```

`host_push_to_device.sh` packs the working tree (`make_payload.sh`) and
copies it with the environment file; `device_bootstrap.sh` checks the
prerequisites and runs `provision/provision_wizard.sh`, which drives `00`
through `06` and resumes itself across the reboots.  This is release-checklist
gate 5 (`docs/release-checklist.md`); details in `provision/README.md`.

On a device that already has the code, the wizard can be run directly:

```bash
sudo ./provision/provision_wizard.sh
```

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
- `ipr-provision.service` — the management hotspot on `wlan0`, started on
  demand (magnet menu, dashboard, a boot marker, or three quick power
  cycles); its setup portal is `https://10.42.0.1/setup/`

After step 04, `/etc/ipr-hotspot.secret` is created with a random SSID and password.
Run `sudo ./provision/07_show_info.sh` to display the hotspot credentials.

## Verification Checklist

- `systemctl status ipr_keyboard.service`
- `systemctl status bt_hid_ble.service`
- `systemctl status bt_hid_agent_unified.service`
- `curl -k https://localhost/health` (the app serves HTTPS on `LogPort`, 443)
- `bt_kb_send "smoke test"` (after pairing/notify subscription)

## Troubleshooting Entry Points

- `./scripts/diag_status.sh`
- `./scripts/diag_troubleshoot.sh`
- `sudo ./scripts/ble/diag_pairing.sh`
- `sudo ./scripts/ble/diag_bt_visibility.sh --fix`
