# ipr-keyboard Setup Scripts

This directory contains installation and setup scripts for deploying the ipr-keyboard application on a Raspberry Pi.

## Overview

The scripts automate the complete setup process from system configuration to service installation. They handle:
- System package installation
- Bluetooth configuration
- Python environment setup with uv
- Systemd service installation
- USB mount configuration
- Testing and diagnostics

## Script Organization

Scripts are numbered to indicate the recommended execution order:
- `00_` - Environment configuration
- `01-05_` - Core installation scripts (run in order)
- `06_` - Optional USB mount setup
- `07-09_` - Testing and demo scripts
- `10_` - Diagnostic tools
- `run_dev.sh` - Development helper

## Environment Configuration

Before running any scripts, configure the environment variables.

### Option 1: Edit the environment script (Recommended)
Edit `scripts/00_set_env.sh` and set:
- `IPR_USER`: Your username (default: meibye)
- `IPR_PROJECT_ROOT`: Your development directory path (default: /home/meibye/dev)

### Option 2: Export in your shell profile
Add these to your `~/.bashrc` or `~/.bash_profile`:
```bash
export IPR_USER="your_username"
export IPR_PROJECT_ROOT="/your/dev/path"
```

## Installation Scripts

### Core Installation (Run in Order)

#### 1. System Setup
```bash
sudo ./scripts/01_system_setup.sh
```
- Installs system packages (Python, Bluetooth tools, etc.)
- Updates package lists
- Prepares base system dependencies

#### 2. Bluetooth Configuration
```bash
sudo ./scripts/02_configure_bluetooth.sh
```
- Configures Bluetooth HID settings
- Sets up Bluetooth pairing
- Prepares system for keyboard emulation

#### 3. Install Bluetooth Helper
```bash
sudo ./scripts/03_install_bt_helper.sh
```
- Installs Bluetooth HID helper script at `/usr/local/bin/bt_kb_send`
- Sets up keyboard emulation utilities
- May be a placeholder that needs customization

#### 4. Setup Python Virtual Environment
```bash
./scripts/04_setup_venv.sh
```
- Creates Python virtual environment using uv
- Installs Python dependencies
- Run as regular user (not root)

#### 5. Install Systemd Service
```bash
sudo ./scripts/05_install_service.sh
```
- Installs systemd service file
- Enables service to start on boot
- Starts the service

### Optional Setup

#### 6. Setup IrisPen USB Mount
```bash
sudo ./scripts/06_setup_irispen_mount.sh /dev/sda1
```
- Mounts IrisPen USB device
- Configure mount point
- Requires device node (check with `lsblk -fp`)

## Testing Scripts

### 7. Smoke Test
```bash
./scripts/07_smoke_test.sh
```
- Basic functionality test
- Verifies installation
- Run as regular user

### 8. End-to-End Demo
```bash
./scripts/08_e2e_demo.sh
```
- Demonstrates full workflow
- Tests file detection and processing
- Requires manual setup of test files

### 9. End-to-End Systemd Demo
```bash
./scripts/09_e2e_systemd_demo.sh
```
- Tests systemd service functionality
- Verifies service is running correctly
- End-to-end test with service

## Diagnostic Tools

### 10. Diagnose Failure
```bash
./scripts/10_diagnose_failure.sh
```
- Diagnostic script for troubleshooting
- Checks system state
- Identifies common issues

## Development Helper

### run_dev.sh
```bash
./scripts/run_dev.sh
```
- Runs application in foreground for debugging
- Alternative to systemd service
- Useful during development
- Press Ctrl+C to stop

## Complete Installation Flow

### Quick Start (Recommended Order)

```bash
# Navigate to project directory
cd ${IPR_PROJECT_ROOT}/ipr-keyboard

# 1. System setup (requires root)
sudo ./scripts/01_system_setup.sh
sudo ./scripts/02_configure_bluetooth.sh
sudo ./scripts/03_install_bt_helper.sh

# 2. Python environment (as user)
./scripts/04_setup_venv.sh

# 3. Optional: Mount IrisPen USB (requires root, adjust device as needed)
sudo ./scripts/06_setup_irispen_mount.sh /dev/sda1

# 4. Smoke test (as user)
./scripts/07_smoke_test.sh

# 5. Install and start service (requires root)
sudo ./scripts/05_install_service.sh
```

## Testing Individual Features

### Configuration Management
```bash
# Unit tests
pytest tests/config

# Web API test
curl http://localhost:8080/config/
curl -X POST http://localhost:8080/config/ -H "Content-Type: application/json" -d '{"DeleteFiles": false}'
```

### USB File Handling
1. Plug in USB stick and mount it (e.g., `/mnt/irispen`)
2. Set `IrisPenFolder` to mount path in `config.json`
3. Test file detection by creating files in the folder
4. Use IrisPen to scan and create files

### Bluetooth Keyboard
1. Pair PC with Raspberry Pi (from PC side, see Pi as "Keyboard")
2. Test from Python REPL:
   ```python
   from ipr_keyboard.bluetooth.keyboard import BluetoothKeyboard
   kb = BluetoothKeyboard()
   kb.send_text("Hello world")
   ```
3. Verify text appears on paired PC

### Logging
1. Start application: `python -m ipr_keyboard.main`
2. Check log file: `cat logs/ipr_keyboard.log`
3. View via web API: `curl http://localhost:8080/logs/tail?lines=50`

### End-to-End
1. Configure `config.json` with correct `IrisPenFolder`
2. Ensure systemd service is running: `sudo systemctl status ipr-keyboard`
3. Complete workflow:
   - Scan with IrisPen → File created → Pi detects file → Reads content
   - Forwards text via Bluetooth → Optionally deletes file → Logs visible in web UI

## Prerequisites

- Raspberry Pi with Raspbian/Raspberry Pi OS
- Network connectivity for package installation
- Root access (via sudo)
- IrisPen scanner device
- Basic familiarity with Linux command line

## Script Permissions

Make scripts executable:
```bash
chmod +x scripts/*.sh
```

## Troubleshooting

If installation fails:
1. Check environment variables are set correctly
2. Ensure you have internet connectivity
3. Run diagnostic script: `./scripts/10_diagnose_failure.sh`
4. Check logs: `cat logs/ipr_keyboard.log`
5. Verify systemd service status: `sudo systemctl status ipr-keyboard`

## Notes

- Scripts use `set -euo pipefail` for safety (exit on error)
- All scripts source `00_set_env.sh` for consistent configuration
- Some scripts require root privileges (use `sudo`)
- Python environment uses `uv` for dependency management
- The Bluetooth helper (`bt_kb_send`) may need customization for your setup

## See Also

- [Main README](../README.md) - Project overview
- [Source Code Documentation](../src/ipr_keyboard/README.md) - Code structure
- [Testing Documentation](../tests/README.md) - Running tests
