# scripts/headless/

Permanent management hotspot and factory-reset scripts for the IPR Keyboard device.

## How it works

`ipr-provision.service` runs `net_provision_hotspot.sh` at every boot.  The script
always activates a WPA3/WPA2 secured Wi-Fi hotspot on `wlan0` so the device is
reachable without a cable.  The Flask management UI (`net_provision_web.py`) is
started automatically and served at `http://10.42.0.1/`.

On devices with a wired interface (e.g. dev RPi 4), `eth0` handles wired connectivity
while `wlan0` runs the hotspot simultaneously.

## Credentials

Generated once by `net_provision_hotspot.sh` or `provision/04_enable_services.sh`
and stored in `/etc/ipr-hotspot.secret` (mode 0600, root only):

```
SSID=ipr-setup-XXXX
PASS=<32-char random hex>
```

Run `sudo provision/07_show_info.sh` to display the current SSID and password.

## Security

- **Wi-Fi**: WPA3-SAE preferred; falls back to WPA2-RSN+CCMP+PMF if the driver
  does not support SAE in AP mode.
- **Web UI**: HTTP Basic Auth — username `ipr`, password from secret file (same
  password used to join the hotspot SSID).
- **Rate limiting**: max 5 `/connect` attempts per IP per 60 seconds.
- **GPIO gate** (optional): set `HOTSPOT_GPIO_PIN=<BCM pin>` in
  `/etc/default/ipr-provision` to require a physical button/jumper press before
  the hotspot starts.  Recommended pin: GPIO 27 (Pin 13).  GPIO 17 is reserved
  for factory reset.

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
- `/etc/ipr-hotspot.secret` — generated with a random password on first run
