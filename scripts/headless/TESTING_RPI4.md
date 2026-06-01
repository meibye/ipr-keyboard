# Testing Plan: scripts/headless/ on Raspberry Pi 4

> **Scope: development testing only — not deployed to the production device.**
> This document covers lab validation on an RPi 4; production target is Raspberry Pi Zero 2 W.

## Context

The `scripts/headless/` directory contains provisioning and recovery scripts intended for the Raspberry Pi Zero 2 W target device. This plan covers how to validate each script on a Raspberry Pi 4, noting where RPi 4 hardware differences affect behaviour.

---

## RPi 4 vs Zero 2 W Differences to Keep in Mind

| Concern | Zero 2 W | RPi 4 |
|---|---|---|
| USB OTG | Micro-USB supports g_ether | USB-C is power-only; OTG gadget mode not natively supported |
| GPIO | 40-pin, GPIO 17 available | 40-pin, GPIO 17 available — same |
| Wi-Fi | wlan0 via nmcli | wlan0 via nmcli — same |
| Boot partition | `/boot/firmware/` (Bookworm) or `/boot/` | `/boot/firmware/` (Bookworm) — same |

---

## Prerequisites

- Raspberry Pi 4 running Raspberry Pi OS Bookworm (Lite recommended)
- NetworkManager active (`sudo systemctl status NetworkManager`)
- Packages installed: `python3-rpi.gpio`, `python3-flask`, `network-manager`, `raspi-gpio`, `openssl`
- Scripts copied to RPi 4 (e.g. via `scp` or SD card mount):
  ```
  scripts/headless/ → ~/headless-test/

  # On the RPI
  cp ~/dev/ipr-keyboard/scripts/headless/* ~/headless-test/
  
  ```
- A jumper wire to ground GPIO 17 (Pin 11) for GPIO reset test
- A second device (phone or laptop) to connect to the hotspot
- SSH access to the Pi for test observation

---

## Network Interface Status Commands

Run these before and after each test to confirm interface state:

```bash
# All interfaces with IPs
ip addr show

# Wi-Fi state and active connection
nmcli device status
nmcli -f NAME,TYPE,STATE,DEVICE con show --active

# Which interface has default route (LAN vs Wi-Fi)
ip route show default
# eth0 → on wired LAN  |  wlan0 → on Wi-Fi  |  both → dual-homed

# Wi-Fi signal and SSID (if connected)
iwconfig wlan0 2>/dev/null || iw dev wlan0 link

# Ethernet link state
cat /sys/class/net/eth0/operstate

# Quick one-liner summary
printf "eth0: $(cat /sys/class/net/eth0/operstate 2>/dev/null || echo absent)  wlan0: $(cat /sys/class/net/wlan0/operstate 2>/dev/null || echo absent)\n"
```

---

## Test Cases

### 1. `net_provision_hotspot.sh` — Permanent Management Hotspot

**Goal:** Verify the permanent management hotspot starts on wlan0 and `/etc/ipr-hotspot.secret` is generated.

> The hotspot is **always-on** — it starts unconditionally at boot and is not gated on whether a known Wi-Fi is reachable. An optional GPIO gate (`HOTSPOT_GPIO_PIN` env var) can restrict startup to a held-low pin, but is not set by default.
>
> **Architecture note:** `net_provision_hotspot.sh` is a oneshot script — it sets up the NM hotspot connection and exits. Port 443 is served by `ipr_keyboard.service` (the main Flask app, which includes the `/setup/` Blueprint). `ipr-provision.service` is `Type=oneshot`/`RemainAfterExit`.

**Setup:**
- Remove any existing hotspot connection to force a clean run:
  ```bash
  sudo nmcli con delete ipr-hotspot 2>/dev/null || true
  ```
- Remove any stale secret to force credential regeneration:
  ```bash
  sudo rm -f /etc/ipr-hotspot.secret
  ```

**Steps:**
```bash
sudo bash ~/dev/ipr-keyboard/scripts/headless/net_provision_hotspot.sh
```

The script will:
1. Generate credentials in `/etc/ipr-hotspot.secret` (SSID and password)
2. Create or update the `ipr-hotspot` NetworkManager connection
3. Configure WPA2-RSN+CCMP (maximum client compatibility — iOS, Android, all laptops)
4. Exit (hotspot stays up via NetworkManager; web UI served by `ipr_keyboard.service`)

**Expected outcome:**
- `sudo nmcli con show` lists `ipr-hotspot` as active
- `ip addr show wlan0` shows `10.42.0.1/24`
- `/etc/ipr-hotspot.secret` contains `SSID=ipr-setup-XXXX` and `PASS=<hex>`
- A second device can see and join the hotspot SSID (`ipr-setup-<suffix>`)
- After joining, `https://10.42.0.1/setup/` serves the management web UI when `ipr_keyboard.service` is running

**GPIO gate variant (optional):**
```bash
# Start with GPIO gate on pin 27 (hold pin 27 LOW for 2s before running)
sudo HOTSPOT_GPIO_PIN=27 bash ~/dev/ipr-keyboard/scripts/headless/net_provision_hotspot.sh
```
- `raspi-gpio` must be installed; if absent the gate is bypassed and hotspot starts unconditionally.
- GPIO 17 is reserved for factory reset — use pin 27 or 22 for the hotspot gate.

**Re-run check:**
- Running the script again with `/etc/ipr-hotspot.secret` present reuses the existing SSID/password.
- If `ipr-hotspot` connection already exists, it is updated (not re-created).
- If port 80 is already bound, the script skips launching the web UI and exits.

---

### 2. Provisioning Web UI (`/setup/` in `ipr_keyboard.service`)

**Goal:** Verify the management web UI at `https://10.42.0.1/setup/` scans networks and can connect the Pi to a known AP.

> **Architecture:** `net_provision_web.py` is **retired** — superseded by the `/setup/` Blueprint in `src/ipr_keyboard/web/setup.py`. The web UI is now served by `ipr_keyboard.service` (the main Flask app) on port 443. `ipr-provision.service` only sets up the hotspot; it does not run a web server.

**Prerequisites:**
- Hotspot must be active (run test 1 first, or start hotspot manually)
- `ipr_keyboard.service` must be running (`sudo systemctl start ipr_keyboard`)
- Connect a laptop/phone to the hotspot

**Authentication:**
The UI requires HTTP Basic Auth:
- Username: `ipr`
- Password: the value of `PASS` from `/etc/ipr-hotspot.secret`

This is the same password used to join the hotspot SSID. A browser will prompt for credentials on first visit.

**URL:** `https://10.42.0.1/setup/` (accept the self-signed cert warning)

**Expected outcome:**
- Unauthenticated request to `/setup/` returns 401
- Authenticated request returns 200
- Page loads with a dropdown of visible SSIDs (own hotspot SSID is excluded)
- Rescan button triggers a fresh network scan
- Entering valid credentials and submitting saves the Wi-Fi profile for next boot
- `sudo nmcli con show` confirms new connection profile was created

**Edge cases to verify:**
- Submit with no password on a secured network → connection error displayed
- Submit with wrong password → nmcli error displayed (HTML-escaped)
- No networks found state → UI shows appropriate message

---

### 3. `gpio_factory_reset.py` — GPIO-Triggered Wi-Fi Reset

> **Deployment: optional/lab only.** This script is not installed by the default provisioning playbook (`04_enable_services.sh`). It is intended for lab testing and emergency recovery. For production factory reset, use `net_factory_reset.sh` (marker-file triggered).

**Goal:** Verify grounding GPIO 17 for 2 seconds triggers Wi-Fi profile deletion and reboot.

**Hardware setup:**
- Connect a jumper between GPIO 17 (Pin 11) and Ground (Pin 9 or 14) — do NOT connect until prompted

**Steps:**
```bash
# First save a dummy Wi-Fi profile to confirm deletion
sudo nmcli con add type wifi con-name "test-wifi" ssid "TestSSID"

# Run the script
sudo python3 ~/dev/ipr-keyboard/scripts/headless/gpio_factory_reset.py &

# Within a few seconds, ground GPIO 17 for ~3 seconds, then release
```

**Expected outcome:**
- Script detects pin LOW for ≥ 2 seconds
- Logs indicate reset triggered (`[ipr-gpio-reset] ✓ GPIO17 held for 2s, factory reset triggered!`)
- `test-wifi` connection is deleted; `ipr-hotspot` is preserved
- Marker files created: `/var/run/ipr_gpio_reset_triggered` and `/boot/firmware/IPR_RESET_WIFI`
- Pi reboots after a 3-second delay

**Safe test variant (no reboot):**
- Comment out the `subprocess.run(["reboot"], ...)` call in a local copy, verify all deletions and marker files without rebooting

**Notes:**
- `RPi.GPIO` must be installed (`sudo apt-get install python3-rpi.gpio`); if unavailable the script exits cleanly with a warning.
- If `/var/run/ipr_gpio_reset_triggered` already exists (from a previous run this boot), the script skips immediately.
- `RPi.GPIO` may emit hardware revision warnings on RPi 4 but should function correctly.

**After reboot — verify marker cleanup (leads into test 4):**
- `IPR_RESET_WIFI` file should be present on boot partition before test 4

---

### 4. `net_factory_reset.sh` — Marker-File-Triggered Wi-Fi Reset

**Goal:** Verify that the presence of `IPR_RESET_WIFI` on the boot partition causes Wi-Fi profiles to be wiped.

**Setup:**
```bash
# Create test Wi-Fi profile
sudo nmcli con add type wifi con-name "test-wifi" ssid "TestSSID"

# Manually plant the marker (or rely on marker from test 3)
sudo touch /boot/firmware/IPR_RESET_WIFI
```

> The boot partition at `/boot/firmware` (or `/boot`) must be a mounted filesystem. The script uses `mountpoint -q` to verify this — if the path exists but is not a mount point, the marker check is skipped.

**Steps:**
```bash
sudo bash ~/dev/ipr-keyboard/scripts/headless/net_factory_reset.sh
```

**Expected outcome:**
- `test-wifi` connection deleted
- `ipr-hotspot` connection preserved
- `/boot/firmware/IPR_RESET_WIFI` marker removed
- Pi reboots

**Safe test variant (no reboot):**
- Comment out the `reboot` line in a local copy; verify deletions and marker removal manually

**Negative test:**
- Run without marker file present → script exits silently (exit 0), no changes made

---

### 5. `usb_otg_setup.sh` — USB OTG Gadget Ethernet

> **POSTPONED** — USB OTG cable not available. Skip this test for now; revisit when cable is on hand. Full end-to-end test requires Zero 2 W hardware regardless.

---

### 6. `ipr-provision.service` — systemd Service Unit

**Goal:** Verify the service unit installs, enables, and sets up the hotspot at boot.

> **Architecture:** `ipr-provision.service` is `Type=oneshot`/`RemainAfterExit`. It runs `net_provision_hotspot.sh` once at boot to configure the NM hotspot, then exits. systemd reports the service as `active` after exit because of `RemainAfterExit=yes`. Port 443 is served by `ipr_keyboard.service` (which starts after this service completes), not by this unit.

**Steps:**
```bash
# Install script to expected path
sudo cp ~/dev/ipr-keyboard/scripts/headless/net_provision_hotspot.sh /usr/local/sbin/ipr-provision.sh
sudo chmod +x /usr/local/sbin/ipr-provision.sh

# Install service
sudo cp ~/dev/ipr-keyboard/scripts/headless/ipr-provision.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ipr-provision
sudo systemctl start ipr-provision
```

**Expected outcome:**
- `systemctl status ipr-provision` shows `active` (RemainAfterExit)
- Hotspot activates — `wlan0` has `10.42.0.1`, `ipr-hotspot` NM connection is active
- Port 443 is **not** served by this service (see `ipr_keyboard.service` for web UI)
- After reboot: `journalctl -u ipr-provision` shows service ran at boot

---

## Test Order

Run tests in this sequence to avoid conflicts:

1. `net_provision_hotspot.sh` (standalone)
2. `net_provision_web.py` (launched by step 1 automatically; test in isolation if needed)
3. `gpio_factory_reset.py` (plants marker for step 4; optional/lab only)
4. `net_factory_reset.sh` (consumes marker from step 3, or manually planted)
5. `ipr-provision.service` (integration test, requires reboot)
6. ~~`usb_otg_setup.sh`~~ — postponed (no USB OTG cable)

---

## Known RPi 4 Limitations

- **USB OTG (`usb_otg_setup.sh`)**: Postponed — no cable available. When cable is sourced, script logic can be validated but `usb0` interface will not appear on RPi 4; full test requires Zero 2 W.
- **`gpio_factory_reset.py`**: `RPi.GPIO` may report hardware revision warnings on RPi 4 but should function correctly.
- Boot partition path is `/boot/firmware/` on Bookworm — scripts handle this correctly.
