# ipr_keyboard - Main Application Module

This directory contains the core implementation of the ipr-keyboard application, which bridges IrisPen USB scanner output to a paired device via Bluetooth HID keyboard emulation.

## Component Dependency Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ipr_keyboard Package                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                        main.py                                    │    │
│  │                    (Entry Point)                                 │    │
│  │                                                                   │    │
│  │   - Initializes all components                                   │    │
│  │   - Starts web server thread                                     │    │
│  │   - Starts USB/BT monitor thread                                 │    │
│  │   - Handles graceful shutdown                                    │    │
│  └────────────────────────────┬──────────────────────────────────────┘    │
│                               │                                          │
│         ┌─────────────────────┼─────────────────────┐                    │
│         │                     │                     │                    │
│         ▼                     ▼                     ▼                    │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────────┐          │
│  │   config/   │      │  logging/   │      │      web/       │          │
│  ├─────────────┤      ├─────────────┤      ├─────────────────┤          │
│  │ manager.py  │◄─────│ logger.py   │      │ server.py       │          │
│  │ AppConfig   │      │ get_logger()│◄─────│ create_app()    │          │
│  │ ConfigMgr   │      │ log_path()  │      │ Flask blueprints│          │
│  │             │      │             │      │                 │          │
│  │ web.py      │─────>│ web.py      │─────>│ /config/        │          │
│  │ (Blueprint) │      │ (Blueprint) │      │ /logs/          │          │
│  └──────┬──────┘      └──────┬──────┘      │ /health         │          │
│         │                    │             └────────┬────────┘          │
│         │                    │                      │                    │
│         └─────────────┬──────┴──────────────────────┘                    │
│                       │                                                  │
│                       ▼                                                  │
│              ┌─────────────┐                                             │
│              │   utils/    │                                             │
│              ├─────────────┤                                             │
│              │ helpers.py  │                                             │
│              │             │                                             │
│              │ project_root()                                            │
│              │ config_path()                                             │
│              │ load_json()  │                                            │
│              │ save_json()  │                                            │
│              └──────┬──────┘                                             │
│                     │                                                    │
│         ┌───────────┴───────────┐                                        │
│         │                       │                                        │
│         ▼                       ▼                                        │
│  ┌─────────────┐       ┌─────────────────┐                               │
│  │    usb/     │       │   bluetooth/    │                               │
│  ├─────────────┤       ├─────────────────┤                               │
│  │ detector.py │       │ keyboard.py     │                               │
│  │ reader.py   │       │ BluetoothKeyboard                               │
│  │ deleter.py  │──────>│ send_text()     │                               │
│  │ mtp_sync.py │       │ is_available()  │                               │
│  └─────────────┘       └────────┬────────┘                               │
│                                 │                                        │
│                                 │ subprocess.run()                       │
│                                 ▼                                        │
│                        ┌────────────────────┐                            │
│                        │ /usr/local/bin/    │                            │
│                        │ bt_kb_send         │                            │
│                        │ (System helper)    │                            │
│                        └────────────────────┘                            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

Legend:
  ──────>  Uses / Depends on
  ◄──────  Provides configuration to
```


## Structure

## BLE Setup, Diagnostics, and Pairing

- **BLE/uinput backend install & management**: See `scripts/ble_install_helper.sh`, which creates and enables:
  - `bt_hid_uinput.service` (uinput backend)
  - `bt_hid_ble.service` (BLE backend)
  - `bt_hid_agent.service` (pairing agent)
- **BLE extras (diagnostics, pairing wizard, backend manager)**: See `scripts/ble_setup_extras.sh` (creates `ipr_backend_manager.service`).
- **Agent service**: `bt_hid_agent.service` (handles pairing/authorization).
- **Web pairing wizard**: `/pairing` endpoint (see web server docs).
- **BLE diagnostics**: `ipr_ble_diagnostics.sh`, `ipr_ble_hid_analyzer.py`.

You can create local scripts to call these helpers, e.g.:

```bash
# Run BLE diagnostics
./scripts/ipr_ble_diagnostics.sh

# Start pairing wizard (web)
curl http://localhost:8080/pairing/start

# Switch backend
echo ble | sudo tee /etc/ipr-keyboard/backend
sudo systemctl disable bt_hid_uinput.service
sudo systemctl enable bt_hid_ble.service
sudo systemctl restart bt_hid_ble.service

# Switch to uinput backend
echo uinput | sudo tee /etc/ipr-keyboard/backend
sudo systemctl disable bt_hid_ble.service
sudo systemctl enable bt_hid_uinput.service
sudo systemctl restart bt_hid_uinput.service
```

## Application Flow
| BLE Setup/Extras | `scripts/ble_install_helper.sh`, `scripts/ble_setup_extras.sh` | Backend install, diagnostics, pairing wizard, agent |

## Entry Point
Run as:
```bash
python -m ipr_keyboard.main
4. **BLE/Backend Management**: Use BLE setup/diagnostic scripts and agent for backend switching, diagnostics, and pairing.
```
Entry point is defined in `pyproject.toml`.

## See Also
- [bluetooth/README.md](bluetooth/README.md)
- [config/README.md](config/README.md)
- [logging/README.md](logging/README.md)
- [usb/README.md](usb/README.md)
- [utils/README.md](utils/README.md)
- [web/README.md](web/README.md)
