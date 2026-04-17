# ipr-keyboard

IrisPen text-file ingestion to Bluetooth keyboard output on Raspberry Pi.

## Documentation

See:
- docs/README.md
- docs/architecture/ARCHITECTURE.md
- docs/operations/device-bringup.md

## Current State

BLE HID over GATT stack using bt_hid_ble.service and bt_hid_agent_unified.service.

## Quick Start

```bash
sudo ./provision/provision_wizard.sh
```

## Directory Guide

- docs/ — all human-facing documentation
- src/ipr_keyboard/ — application
- scripts/ — operational scripts

## Notes

Start all cleanup and refactor work from docs/architecture/ARCHITECTURE.md
