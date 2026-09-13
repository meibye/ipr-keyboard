# scripts/headless/

Permanent management hotspot and factory-reset scripts for the IPR Keyboard device.

## How it works

`ipr-provision.service` runs `net_provision_hotspot.sh` at every boot **and**
whenever the hotspot is requested later.  The script brings up a WPA2-secured
Wi-Fi hotspot on `wlan0`; the setup UI is served by `ipr_keyboard.service` at
`https://10.42.0.1/setup/`.

### Default behaviour — hotspot on demand

`HOTSPOT_MODE=on-demand` (the default) keeps the device invisible: the hotspot
only starts when one of these triggers is present, evaluated in this order:

| Trigger | How | When |
|---|---|---|
| Request file `/run/ipr-hotspot.request` | written by `ipr_hotspot_ctl.sh start` | **any time** — the magnet (held ≥ 3 s, via `gpio_monitor`) and administrators use this |
| Boot marker `IPR_SETUP` on `/boot/firmware` | create the file from any PC | last resort, needs an SD-card reader |
| Triple power-cycle | 3 boots within 120 s | magnet not available |
| `HOTSPOT_GPIO_PIN` in `/etc/default/ipr-provision` | pin held LOW at boot | legacy hardware gate |
| `HOTSPOT_MODE=always` | `/etc/default/ipr-provision` | dev / lab devices |

Stopping: `systemctl stop ipr-provision.service` runs `ipr-provision.sh --stop`
(`ExecStop`), which takes the `ipr-hotspot` connection down; NetworkManager
then re-activates the home Wi-Fi profile.  Holding the magnet ≥ 3 s again does
the same through the helper.

### Starting and stopping from the command line

```bash
sudo ipr_hotspot_ctl.sh start     # any time; blocks until the AP is up
sudo ipr_hotspot_ctl.sh stop
sudo ipr_hotspot_ctl.sh status    # prints up/down, exit 0/1
```

Do **not** use a plain `systemctl start ipr-provision.service`: the oneshot
unit is already "active" after boot (`RemainAfterExit=yes`), so `start` is a
no-op, and a `restart` without a trigger exits without starting anything.
The helper handles both.

### Network exposure — production / development mode

`install_firewall.sh` installs an nftables policy (`inet ipr_fw`, input
DROP) driven by `/var/lib/ipr-keyboard/mode` and the hotspot state.  In
**production** nothing is reachable on the home network and only the setup
portal (443) on the hotspot; in **development** SSH, the dashboard and mDNS
are reachable.  Switch with `sudo ipr_mode_ctl.sh production|development` or
the magnet held 6 s.  Provisioning seeds *development*; commissioning ends
by switching to production.  See `docs/operations/network-modes.md`.

### Status LED

The RGB LED shows the boot (white solid → white blink), the operational status
(green / amber / red) and the hotspot (blue).  `install_gpio_support.sh`
installs the pieces: a `gpio=` line in `config.txt`, `ipr-led-boot.service`
for the early blink, a systemd drop-in that hands the pins to the app, the
`ipr_hotspot_ctl.sh` helper with its sudoers entry, and the GPIO packages.
See `docs/hardware/gpio-wiring.md` for the colour map and gestures.

## Credentials

Generated once by `net_provision_hotspot.sh` or `provision/04_enable_services.sh`
and stored in `/etc/ipr-hotspot.secret` (mode 0600, root only):

```
SSID=ipr-setup-XXXX
PASS=<12-char random password>
```

Run `sudo provision/07_show_info.sh` to display the current SSID and password.

## Security

- **Wi-Fi**: WPA3-SAE preferred; falls back to WPA2-RSN+CCMP+PMF if the driver
  does not support SAE in AP mode.
- **Web UI**: HTTP Basic Auth — username `ipr`, password from secret file (same
  password used to join the hotspot SSID).
- **Rate limiting**: max 5 `/connect` attempts per IP per 60 seconds.
- **GPIO gate** (optional): when `HOTSPOT_GPIO_PIN` is unset the hotspot starts at
  every boot.  Set it to a BCM pin number in `/etc/default/ipr-provision` to require
  that pin held LOW for ≥ 2 s before the hotspot activates — see
  [GPIO gate](#gpio-gate--hotspot-on-demand) above.  Recommended pin: GPIO 27 (Pin 13).
  GPIO 17 is reserved for factory reset.

## Files

### Installed to the device by `provision/04_enable_services.sh` / `deploy_full_update.sh`

| File | Installed as | Purpose |
|---|---|---|
| `net_provision_hotspot.sh` | `/usr/local/sbin/ipr-provision.sh` | On-demand hotspot; `--stop` mode for `ExecStop` |
| `ipr-provision.service` | `/etc/systemd/system/` | Runs the script at boot and on request; `ExecStop` takes the AP down |
| `ipr_hotspot_ctl.sh` | `/usr/local/bin/` | Root helper: `start`/`stop`/`status`/`factory-reset` (sudoers for the app user) |
| `ipr_led_boot.sh` | `/usr/local/sbin/ipr-led-boot.sh` | White blink during OS boot (`gpioset`, `pinctrl` fallback) |
| `ipr-led-boot.service` | `/etc/systemd/system/` | Early unit for the boot blink; stopped by `ipr_keyboard.service` via `Conflicts=` |
| `install_gpio_support.sh` | — | Installs everything the LED and magnet need (idempotent) |
| `ipr_fw_ctl.sh` | `/usr/local/sbin/ipr-firewall.sh` | nftables input policy from mode + hotspot state (`apply`/`status`/`off`) |
| `ipr_mode_ctl.sh` | `/usr/local/bin/ipr_mode_ctl.sh` | Production/development switch (sudoers for the app user; magnet 6 s) |
| `ipr-firewall.service` | `/etc/systemd/system/` | Applies the policy at boot before networking |
| `90-ipr-firewall` | `/etc/NetworkManager/dispatcher.d/` | Re-applies on every connection up/down |
| `install_firewall.sh` | — | Installs the above, seeds the mode file (development), sudoers |
| `irispen-mount.service` | `/etc/systemd/system/` | `jmtpfs` mount of the IrisPen on plug-in (udev `dev-irispen.device`); unmounts on unplug |
| `install_irispen_mount.sh` | — | Installs the udev rule + unit, creates `/mnt/irispen`, installs `jmtpfs` |
| `install_observability.sh` | — | Persistent capped journal; `ipr-failure@.service` + `OnFailure=` drop-ins → `/var/lib/ipr-keyboard/incidents.log` |
| `install_provision_service.sh` | — | Installs the hotspot script, unit, cert generation and renewal |
| `gen_ipr_ssl_cert.sh`, `ipr-cert-renew.*` | `/usr/local/sbin/`, systemd | TLS certificates and renewal |
| `net_factory_reset.sh` | `/usr/local/sbin/ipr-factory-reset.sh` | Resets Wi-Fi profiles when `IPR_RESET_WIFI` boot marker is present |
| `test_provision.sh` | — | Post-provision validation (phase K covers the LED / magnet pieces) |
| `test_gpio_led_reed.sh` | — | Hardware test of the LED and reed switch outside the application |

### Development / lab only — **not installed to production device**

| File | Notes |
|---|---|
| `net_provision_web.py` | Retired standalone setup UI; the setup pages live in `ipr_keyboard.web.setup` |
| `gpio_factory_reset.py` | Optional GPIO-triggered reset; for lab testing and emergency recovery |
| `usb_otg_setup.sh` | USB OTG ethernet (Pi Zero 2 W only); postponed — requires USB OTG cable |
| `TESTING_RPI4.md` | RPi 4 lab testing plan |

## Installation

`provision/04_enable_services.sh` installs:

- `/usr/local/sbin/ipr-provision.sh` ← `net_provision_hotspot.sh`
- `/etc/systemd/system/ipr-provision.service` ← `ipr-provision.service`
- `/etc/default/ipr-provision` — optional provisioning defaults with a commented `HOTSPOT_GPIO_PIN` example
- `/etc/ipr-hotspot.secret` — generated with a random password on first run
- via `install_gpio_support.sh`: `/usr/local/bin/ipr_hotspot_ctl.sh`, `/etc/sudoers.d/<user>-ipr-gpio`, `/usr/local/sbin/ipr-led-boot.sh`, `ipr-led-boot.service`, `/etc/systemd/system/ipr_keyboard.service.d/10-led-boot.conf`, `/etc/default/ipr-led`, and the `gpio=` block in `/boot/firmware/config.txt`
