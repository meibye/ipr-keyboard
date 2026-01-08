# BLE Extras Scripts

This directory contains additional BLE-related diagnostic and management scripts that are installed system-wide by `ble_setup_extras.sh`.

## Scripts

### ipr_ble_diagnostics.sh
Comprehensive Bluetooth HID diagnostics script that checks:
- Bluetooth adapter status
- HID UUID exposure (0x1812)
- BLE HID daemon service status
- Agent service status
- Adapter power state
- Recent daemon logs
- FIFO existence

Installed to: `/usr/local/bin/ipr_ble_diagnostics.sh`

**Usage:**
```bash
sudo /usr/local/bin/ipr_ble_diagnostics.sh
```

### ipr_ble_hid_analyzer.py
Debug tool for BLE HID that monitors GATT characteristics and logs HID report changes.

Installed to: `/usr/local/bin/ipr_ble_hid_analyzer.py`

**Usage:**
```bash
sudo /usr/local/bin/ipr_ble_hid_analyzer.py
```

## Installation

These scripts are automatically installed by running:
```bash
sudo ./scripts/ble/ble_setup_extras.sh
```

The setup script copies these files to `/usr/local/bin/` and makes them executable system-wide.

## Direct Access

After installation, you can run these tools directly:
```bash
# BLE diagnostics
sudo /usr/local/bin/ipr_ble_diagnostics.sh

# BLE HID analyzer
sudo /usr/local/bin/ipr_ble_hid_analyzer.py
```

**Note**: The wrapper scripts `diag_ble.sh` and `diag_ble_analyzer.sh` have been removed. Use the direct paths above instead.
