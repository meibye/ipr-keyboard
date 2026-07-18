---
name: test-new-rpi
description: Upload and run the post-provision validation suite on a freshly provisioned RPi Zero W via MCP SSH.
---

# When to use
- Immediately after completing the full provisioning sequence on a new device
- After re-provisioning to verify nothing was missed
- As a quick smoke-check when suspecting a broken install state

# Provisioning sequence this validates

The following scripts must have been run on the Pi **before** invoking this skill:

```
sudo ./scripts/sys_install_packages.sh
./scripts/sys_setup_venv.sh
sudo ./scripts/service/svc_install_bt_gatt_hid.sh
sudo ./scripts/ble/ble_install_helper.sh
sudo ./scripts/headless/install_provision_service.sh
sudo ./scripts/deploy/deploy_full_update.sh --install-python
```

# Inputs
- None required; the target is always `ipr-rpi-dev-ssh` (dev RPi)

# Procedure

## Step 1 — Fix script permissions

Before uploading the test script, ensure the local source has the executable bit
(upload via MCP does not preserve Windows permissions):

```bash
# Run locally via ipr-rpi-dev-ssh after uploading
find /home/meibye/dev/ipr-keyboard/scripts \( -name "*.sh" -o -name "*.py" \) -exec chmod +x {} +
```

Or invoke the `fix-script-permissions` skill first.

## Step 2 — Upload the test script

Upload via `ipr-rpi-dev-ssh` upload tool:
- Local:  `scripts/headless/test_provision.sh`
- Remote: `/home/meibye/dev/ipr-keyboard/scripts/headless/test_provision.sh`

Then make it executable:
```bash
chmod +x /home/meibye/dev/ipr-keyboard/scripts/headless/test_provision.sh
```

## Step 3 — Run the validation suite

```bash
sudo bash /home/meibye/dev/ipr-keyboard/scripts/headless/test_provision.sh --auto
```

Expected output when fully provisioned:
```
Passed: N  |  Failed: 0  |  Skipped: M
✓ All automated checks passed.
  (M step(s) skipped — require manual or interactive confirmation)
```

Where M is the number of manual/J-phase checks (up to 6). All automated checks
(phases A through I) must show 0 failures.

## Step 4 — Interpret failures

| Phase | Script that should have run | Common causes |
|-------|-----------------------------|---------------|
| A — System packages | `sys_install_packages.sh` | apt failed, uv not symlinked |
| B — Python venv | `sys_setup_venv.sh` | venv not created, pip error |
| C — BLE services | `svc_install_bt_gatt_hid.sh` | script not run as root |
| D — BT helper | `ble_install_helper.sh` | script not run |
| E — Provision service | `install_provision_service.sh` | script not run, source file missing |
| F — TLS certs | `gen_ipr_ssl_cert.sh` (called by E) | openssl error, group missing |
| G — Service health | `deploy_full_update.sh` | service crash, wrong config |
| H — App health | `deploy_full_update.sh` | Flask startup error, port conflict |
| I — Script permissions | `fix-script-permissions` skill | Windows upload without chmod |

For any failure, read the service journal:
```bash
sudo journalctl -u ipr_keyboard.service -n 50 --no-pager
sudo journalctl -u bt_hid_ble.service -n 50 --no-pager
```

## Step 5 — Manual checks (J phase)

After the automated run, perform the manual J-phase checks interactively:

```bash
sudo bash /home/meibye/dev/ipr-keyboard/scripts/headless/test_provision.sh
```

(Without `--auto` the script pauses at each manual step.)

Manual steps cover:
- J.1: Hotspot SSID visible on a phone/laptop
- J.2: Setup portal reachable at https://10.42.0.1/setup/
- J.3: Setup portal login with hotspot credentials
- J.4: CA cert download + HTTPS trusted in browser
- J.5: Main dashboard accessible via https://<hostname>.local/
- J.6: Bluetooth pairing with a host device

# Quality bar
- Phases A–I: **0 failures**
- Phase J: all 6 manual checks passed (confirmed interactively)
- exit code of the script equals the failure count (0 = clean)

# Output format
- Per-phase PASS/FAIL/SKIP for each check
- Initial admin password printed when H.4 passes
- Summary line: `Passed: N | Failed: 0 | Skipped: M`
- Failure list if any failures exist

# Related skills
- deploy-dev
- fix-script-permissions
- test-on-rpi
- root-cause-analysis
