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
- Packages installed: `python3-rpi.gpio`, `python3-flask`, `network-manager`
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
cat /sys/class/net/eth0/operstate   # "up" or "down"

# Quick one-liner summary
printf "eth0: $(cat /sys/class/net/eth0/operstate 2>/dev/null || echo absent)  wlan0: $(cat /sys/class/net/wlan0/operstate 2>/dev/null || echo absent)\n"
```

---

## Test Cases

### 1. `net_provision_hotspot.sh` — Hotspot Auto-Activation

**Goal:** Verify hotspot `ipr-hotspot` is created when no known Wi-Fi is reachable.

**Setup:**
- Ensure no Wi-Fi connection is active: `sudo nmcli con delete <your-ssid>` (or test on a Pi with no saved networks). `<your-ssid>` is expected to be preconfigured, but the name can be obtained by `sudo nmcli con show --active`. I.e. the command is `sudo nmcli con delete preconfigured`

- Remove any existing hotspot connection: `sudo nmcli con delete ipr-hotspot` (ignore error if not found)

**Steps:**
```bash
sudo bash ~/dev/ipr-keyboard/scripts/headless/net_provision_hotspot.sh
```
- Wait up to 60 seconds for hotspot to activate

**Expected outcome:**
- Script prints SSID (`ipr-setup-XXXX`), password, and URL (`http://10.42.0.1`)
- `sudo nmcli con show` lists `ipr-hotspot` as active
- `ip addr show wlan0` shows `10.42.0.1/24`
- A second device can see and join the hotspot SSID `ipr-setup-xxxx, where xxxx is 

**Regression check:**
- Run again with a known Wi-Fi saved — hotspot should NOT activate (script exits after 45s wait)

---

### 2. `net_provision_web.py` — Wi-Fi Provisioning UI

**Goal:** Verify the Flask provisioning UI scans networks and can connect Pi to a known AP.

**Setup:**
- Hotspot must be active (run test 1 first)
- Connect a laptop/phone to the hotspot

**Steps:**
```bash
sudo python3 ~/dev/ipr-keyboard/scripts/headless/net_provision_web.py
```
- From the connected device, open `http://10.42.0.1/`

**Expected outcome:**
- Page loads with a dropdown of visible SSIDs
- Rescan button triggers a fresh network scan
- Entering valid credentials and submitting connects Pi to the target Wi-Fi
- Success page shown with SSH instructions
- `sudo nmcli con show` confirms new connection is active

**Edge cases to verify:**
- Submit with no password on a secured network → error shown
- Submit with wrong password → nmcli error displayed (HTML-escaped)
- No networks found state → UI shows "(no networks found — try rescan)"

---

### 3. `gpio_factory_reset.py` — GPIO-Triggered Wi-Fi Reset

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
- Logs indicate reset triggered
- `test-wifi` connection is deleted; `ipr-hotspot` is preserved
- Marker files created: `/var/run/ipr_gpio_reset_triggered` and `/boot/firmware/IPR_RESET_WIFI`
- Pi reboots

**Safe test variant (no reboot):**
- Comment out the `reboot` call in a local copy, verify all deletions and marker files without rebooting

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
- Run without marker file present → script exits silently, no changes made

---

### 5. `usb_otg_setup.sh` — USB OTG Gadget Ethernet

> **POSTPONED** — USB OTG cable not available. Skip this test for now; revisit when cable is on hand. Full end-to-end test requires Zero 2 W hardware regardless.

---

### 6. `ipr-provision.service` — systemd Service Unit

**Goal:** Verify the service unit installs and activates `net_provision_hotspot.sh` correctly.

**Steps:**
```bash
# Install script to expected path
sudo cp ~/dev/ipr-keyboard/scripts/headless/net_provision_hotspot.sh /usr/local/sbin/ipr-provision.sh
sudo chmod +x /usr/local/sbin/ipr-provision.sh

# Install service
sudo cp ~/headless-test/ipr-provision.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ipr-provision
sudo systemctl start ipr-provision
```

**Expected outcome:**
- `systemctl status ipr-provision` shows `active (running)` or `active (exited)` depending on timing
- Hotspot activates if no Wi-Fi is connected (same as test 1)
- After reboot: `journalctl -u ipr-provision` shows service ran at boot

---

## Test Order

Run tests in this sequence to avoid conflicts:

1. `net_provision_hotspot.sh` (standalone)
2. `net_provision_web.py` (depends on hotspot from step 1)
3. `gpio_factory_reset.py` (plants marker for step 4)
4. `net_factory_reset.sh` (consumes marker from step 3, or manually planted)
5. `ipr-provision.service` (integration test, requires reboot)
6. ~~`usb_otg_setup.sh`~~ — postponed (no USB OTG cable)

---

## Known RPi 4 Limitations

- **USB OTG (`usb_otg_setup.sh`)**: Postponed — no cable available. When cable is sourced, script logic can be validated but `usb0` interface will not appear on RPi 4; full test requires Zero 2 W.
- **`gpio_factory_reset.py`**: `RPi.GPIO` may report hardware revision warnings on RPi 4 but should function correctly.
- Boot partition path is `/boot/firmware/` on Bookworm — scripts handle this correctly.
