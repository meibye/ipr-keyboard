# scripts/headless/

Permanent management hotspot and factory-reset scripts for the IPR Keyboard device.

## How it works

`ipr-provision.service` runs `net_provision_hotspot.sh` at every boot.  The script
activates a WPA2-secured Wi-Fi hotspot on `wlan0` and starts the Flask management UI
(`net_provision_web.py`) at `https://10.42.0.1/`.

On devices with a wired interface (e.g. dev RPi 4), `eth0` handles wired connectivity
while `wlan0` runs the hotspot simultaneously.

### Default behaviour — hotspot always on

When `HOTSPOT_GPIO_PIN` is **not** set (the default after provisioning), the hotspot
and management UI start unconditionally at every boot.  This is the safest default for
accessibility: the device is always reachable without a cable, regardless of which
network it is on or whether it has joined any network at all.

### GPIO gate — hotspot on demand

Setting `HOTSPOT_GPIO_PIN` in `/etc/default/ipr-provision` adds a physical security
control.  The hotspot will **not** start unless the configured GPIO pin is held LOW for
at least 2 seconds during boot.  This means:

- Under normal operation the device broadcasts no management AP and the web UI is
  unreachable from Wi-Fi.
- To open the management interface, an admin must be physically present, hold the
  button, and reboot the device.
- On the next normal reboot (button not pressed) the hotspot stays dark again.

This is useful when the device is deployed in a shared or semi-public space where an
always-on AP is undesirable.

**Recommended pin: GPIO 27 (Pin 13).**  GPIO 17 is already reserved for factory reset
(`net_factory_reset.sh`) — use a separate button for each function.

To enable the GPIO gate, edit `/etc/default/ipr-provision` and uncomment:

```
HOTSPOT_GPIO_PIN=27
```

To return to always-on behaviour, comment the line out again and reboot.

## Credentials

Generated once by `net_provision_hotspot.sh` or `provision/04_enable_services.sh`
and stored in `/etc/ipr-hotspot.secret` (mode 0600, root only):

```
IPR_SSID=ipr-setup-XXXX
IPR_PASS=<32-char random hex>
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

### Installed to production device by `provision/04_enable_services.sh`

| File | Purpose |
|---|---|
| `net_provision_hotspot.sh` | Always-on management hotspot; WPA3→WPA2 fallback; secure credentials |
| `net_provision_web.py` | Flask management UI with Basic Auth and rate limiting |
| `net_factory_reset.sh` | Resets Wi-Fi profiles when `IPR_RESET_WIFI` boot marker is present |
| `ipr-provision.service` | systemd unit running `/usr/local/sbin/ipr-provision.sh` at boot |

### Development / lab only — **not installed to production device**

| File | Notes |
|---|---|
| `gpio_factory_reset.py` | Optional GPIO-triggered reset; for lab testing and emergency recovery |
| `usb_otg_setup.sh` | USB OTG ethernet (Pi Zero 2 W only); postponed — requires USB OTG cable |
| `TESTING_RPI4.md` | RPi 4 lab testing plan |

## Installation

`provision/04_enable_services.sh` installs:

- `/usr/local/sbin/ipr-provision.sh` ← `net_provision_hotspot.sh`
- `/usr/local/sbin/ipr-provision-web.py` ← `net_provision_web.py`
- `/etc/systemd/system/ipr-provision.service` ← `ipr-provision.service`
- `/etc/default/ipr-provision` — optional provisioning defaults with a commented `HOTSPOT_GPIO_PIN` example
- `/etc/ipr-hotspot.secret` — generated with a random password on first run
