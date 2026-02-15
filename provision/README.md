# Provisioning

Provisioning scripts for Raspberry Pi setup and verification.

## Files in This Directory

| File | Purpose |
|---|---|
| `00_bootstrap.sh` | Validates `/opt/ipr_common.env`, installs base tools, clones/checks out repo |
| `01_os_base.sh` | Installs OS/system dependencies and Bluetooth baseline |
| `02_device_identity.sh` | Applies hostname and Bluetooth name identity |
| `03_app_install.sh` | Creates/validates Python app environment |
| `04_enable_services.sh` | Installs/enables app, BLE, and headless provisioning services |
| `05_copilot_debug_tools.sh` | Optional MCP/Copilot diagnostics tooling setup |
| `06_verify.sh` | Produces verification report and service checks |
| `provision_wizard.sh` | Interactive orchestration for steps `00`..`06` with resume points |
| `common.env.example` | Template for `/opt/ipr_common.env` |

## Typical Sequence

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

## Generated Artifacts

- `/opt/ipr_common.env` (input config)
- `/opt/ipr_state/*` (state and verification outputs)
- Installed services and binaries under `/etc/systemd/system` and `/usr/local/bin`

See `ARCHITECTURE.md` for canonical current/legacy classification.
