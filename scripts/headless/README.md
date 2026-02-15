# scripts/headless/

Headless network provisioning and recovery scripts.

## Files

| File | Purpose |
|---|---|
| `net_provision_hotspot.sh` | Creates provisioning hotspot when normal Wi-Fi is unavailable |
| `net_provision_web.py` | Flask provisioning UI served while hotspot is active |
| `net_factory_reset.sh` | Resets Wi-Fi profiles when `IPR_RESET_WIFI` marker is present |
| `gpio_factory_reset.py` | Optional GPIO-triggered Wi-Fi reset path |
| `usb_otg_setup.sh` | Configures USB OTG ethernet path (Pi Zero class devices) |
| `ipr-provision.service` | Service unit running `/usr/local/sbin/ipr-provision.sh` |

## Installation Path Used by Provisioning

`provision/04_enable_services.sh` installs:
- `/usr/local/sbin/ipr-provision.sh` from `net_provision_hotspot.sh`
- `/etc/systemd/system/ipr-provision.service` from `ipr-provision.service`

Other scripts in this folder are available for extended recovery workflows.
