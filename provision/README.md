# IPR Keyboard - Provisioning System

This directory contains automated provisioning scripts for setting up Raspberry Pi devices for the ipr-keyboard project. These scripts ensure both devices (RPi 4 and Pi Zero 2 W) are configured identically except for device-specific settings.

## Overview

The provisioning system provides:
- **Automated setup** from fresh OS install to running application
- **Reproducible configuration** across multiple devices
- **Version tracking** of OS, packages, and application code
- **Device-specific customization** (hostnames, Bluetooth names)
- **Verification reports** for comparing device configurations


## Quick Start

### Prerequisites

1. Fresh Raspberry Pi OS Lite (64-bit) Bookworm installation
2. SSH access to the device
3. Device-specific configuration values ready

### Essential First Step: Transfer and Run the Provisioning Wizard

The recommended workflow is to use the interactive provisioning wizard script, which guides you through all steps, handles reboots, and resumes automatically:

#### 1. Transfer the Wizard Script

Before cloning the repository, copy provision/00_provision_wizard.sh from your local machine to the target device (e.g. via scp):

```bash
# On your local machine (from the repo folder):
scp provision/00_provision_wizard.sh meibye@ipr-target-zero2:/home/meibye/00_provision_wizard.sh
scp provision/00_provision_wizard.sh meibye@ipr-dev-pi4:/home/meibye/00_provision_wizard.sh
```

#### 2. Run the Wizard

SSH into the device and run:

```bash
sudo bash /home/meibye/00_provision_wizard.sh
```

The wizard will:
- Install git
- Clone the repository
- Guide you through device config creation
- Set up SSH keys
- Run all provisioning scripts in order
- Handle required reboots and resume automatically
- Color-code each step and prompt to continue or quit

You can always start over by choosing the option at the beginning of the wizard.

---

### Manual Installation Steps (if not using the wizard)

```bash
# 1. Install git (required to clone the repository)
sudo apt-get update
sudo apt-get install -y git

# 2. Clone the repository
mkdir -p /home/meibye/dev
cd /home/meibye/dev
git clone https://github.com/meibye/ipr-keyboard.git
cd ipr-keyboard

# 3. Create device configuration
cp provision/common.env.example provision/common.env
nano provision/common.env  # Edit device-specific values
sudo cp provision/common.env /opt/ipr_common.env

# 4. Run provisioning scripts in order
chmod +x ./provision/*.sh
sudo ./provision/00_bootstrap.sh

# 5. Follow the instructions for setting up and testing GitHub SSH keys
git remote set-url origin git@github.com:meibye/ipr-keyboard.git
ssh -T git@github.com      # Test connection: answer "yes" when asked to continue

# 6. Continue provisioning scripts in order
sudo ./provision/01_os_base.sh
sudo reboot  # Required after OS base

# After reboot:
cd /home/meibye/dev/ipr-keyboard
sudo ./provision/02_device_identity.sh
sudo reboot  # Required after identity

# After reboot:
cd /home/meibye/dev/ipr-keyboard
sudo ./provision/03_app_install.sh  # (Python venv setup will run as APP_USER automatically)
sudo ./provision/04_enable_services.sh
sudo ./provision/05_verify.sh
```
### Wizard Script Reference

#### provision/00_provision_wizard.sh

**Purpose**: Interactive, stepwise provisioning for ipr-keyboard. Guides the user through all required steps, including package install, repo clone, config creation, SSH key setup, and all provisioning scripts. Handles required reboots and resumes automatically. Color-codes each step and prompts to continue or quit. Optionally allows starting over from the beginning.

**Usage**:
1. Transfer the script to the device before cloning the repo (see above).
2. Run with `sudo bash /home/pi/00_provision_wizard.sh`.
3. Follow the prompts and guidance.

**Features**:
- Stepwise guidance for all provisioning steps
- Color-coded status for each step
- Interactive continue/quit prompts
- Handles required reboots and resumes automatically
- Option to start over from the beginning

**Recommended**: Use this wizard for all new device setups for maximum reliability and ease of use.

---

## Script Reference

### 00_bootstrap.sh

**Purpose**: Initialize repository and install base tools

**What it does**:
- Validates `common.env` configuration
- Installs base system tools (git, curl, python3, etc.)
- Clones repository to configured location
- Checks out specified Git ref
- Creates state directory for tracking

**Requires**: 
- `/opt/ipr_common.env` must exist
- Internet connection

**Reboot required**: No

**Execution time**: ~5 minutes

---



### 01_os_base.sh

**Purpose**: Configure OS baseline and install system packages

**What it does**:
- Runs full system upgrade (`apt full-upgrade`)
- Executes `scripts/sys_install_packages.sh --system-only` as root (installs bluez, python3-dbus, uv, etc.)
- Executes `scripts/sys_install_packages.sh --user-venv-setup` as APP_USER (creates Python venv and installs project dependencies)
- Executes `scripts/ble/bt_configure_system.sh` (configures Bluetooth for HID)
- Enables essential services (dbus, bluetooth)
- Records baseline versions to `/opt/ipr_state/baseline_versions.txt`

**Requires**:
- `00_bootstrap.sh` completed
- Internet connection

**Reboot required**: **Yes** (after Bluetooth configuration)

**Execution time**: ~15-30 minutes (depends on updates)

---

### 02_device_identity.sh

**Purpose**: Set device-specific hostname and Bluetooth name

**What it does**:
- Sets hostname via `hostnamectl`
- Updates `/etc/hosts` with new hostname
- Configures Bluetooth device name in `/etc/bluetooth/main.conf`
- Restarts Bluetooth service
- Verifies Bluetooth name is applied

**Requires**:
- `01_os_base.sh` completed and rebooted
- Device-specific values in `common.env`

**Reboot required**: **Yes** (for hostname to fully take effect)

**Execution time**: ~1 minute

**Device-specific values**:
- RPi 4: `HOSTNAME="ipr-dev-pi4"`, `BT_DEVICE_NAME="IPR Keyboard (Dev)"`
- Pi Zero: `HOSTNAME="ipr-target-zero2"`, `BT_DEVICE_NAME="IPR Keyboard"`

---


### 03_app_install.sh

**Purpose**: Create Python environment and install dependencies

**What it does**:
- Executes `sys_setup_venv.sh` as APP_USER (creates venv with uv)
- Installs Python packages from `pyproject.toml`
- Verifies Python environment
- Records installed packages to `/opt/ipr_state/python_packages.txt`

**Requires**:
- `02_device_identity.sh` completed and rebooted
- Repository present at configured location

**Reboot required**: No

**Execution time**: ~5-10 minutes (Pi Zero slower)

---


### 04_enable_services.sh

**Purpose**: Install and enable systemd services

**What it does**:
- Executes `scripts/service/svc_install_systemd.sh` (installs ipr_keyboard.service)
- Executes `scripts/ble/ble_setup_extras.sh` (installs backend manager, diagnostics)
- Executes `scripts/ble/ble_install_helper.sh` (installs BLE/uinput services and agent)
- Executes `scripts/service/svc_enable_ble_services.sh` (enables BLE backend)
- Updates `config.json` to set backend to "ble"
- Records enabled services to `/opt/ipr_state/service_status.txt`

**Requires**:
- `03_app_install.sh` completed
- Python environment functional

**Reboot required**: No (services start automatically)

**Execution time**: ~2-5 minutes

**Services enabled**:
- `ipr_keyboard.service` - Main application
- `bt_hid_ble.service` - BLE HID backend
- `bt_hid_agent_unified.service` - Bluetooth pairing agent
- `ipr_backend_manager.service` - Backend switcher
- `ipr-provision.service` - Headless Wi-Fi provisioning hotspot (auto-starts if Wi-Fi is not connected)

---

### 05_verify.sh

**Purpose**: Verify configuration and generate comparison report

**What it does**:
- Generates comprehensive verification report
- Checks device identity (hostname, Bluetooth name)
- Verifies OS version, kernel, hardware
- Checks Python environment
- Verifies Git commit and branch
- Checks service status
- Reviews backend configuration
- Captures recent logs
- Produces summary with errors/warnings

**Requires**:
- All previous provisioning steps **completed**

**Reboot required**: No

**Execution time**: ~1 minute

**Output**: `/opt/ipr_state/verification_report.txt`

---

## Configuration File (common.env)

### Required Variables

| Variable | Description | Example (RPi 4) | Example (Pi Zero) |
|----------|-------------|-----------------|-------------------|
| `REPO_URL` | GitHub repository URL | `https://github.com/meibye/ipr-keyboard.git` | (same) |
| `REPO_DIR` | Repository location | `/home/meibye/dev/ipr-keyboard` | (same) |
| `APP_USER` | Application user | `meibye` | (same) |
| `APP_GROUP` | Application group | `meibye` | (same) |
| `GIT_REF` | Git branch/tag to checkout | `main` or `v1.0.0` | (same) |
| `DEVICE_TYPE` | Device type identifier | `dev` | `target` |
| `HOSTNAME` | Device hostname | `ipr-dev-pi4` | `ipr-target-zero2` |
| `BT_DEVICE_NAME` | Bluetooth name | `IPR Keyboard (Dev)` | `IPR Keyboard` |
| `BT_BACKEND` | Backend type | `ble` | `ble` |

### Configuration Template

See [common.env.example](common.env.example) for full template with documentation.

---

## State Tracking

Provisioning progress and system state is tracked in `/opt/ipr_state/`:

| File | Content | Created By |
|------|---------|------------|
| `bootstrap_info.txt` | Provisioning timeline and Git info | All scripts (append) |
| `baseline_versions.txt` | OS, kernel, packages, Python versions | `01_os_base.sh` |
| `python_packages.txt` | Installed Python packages | `03_app_install.sh` |
| `service_status.txt` | Enabled services and status | `04_enable_services.sh` |
| `verification_report.txt` | Comprehensive system report | `05_verify.sh` |

### Viewing State

```bash
# View provisioning timeline
cat /opt/ipr_state/bootstrap_info.txt

# View installed packages
cat /opt/ipr_state/baseline_versions.txt

# View full verification report
cat /opt/ipr_state/verification_report.txt
```

---

## Comparing Devices

To verify both devices are at the same level:

```bash
# On each device, generate verification report
sudo ./provision/05_verify.sh

# On Windows PC, download both reports
scp meibye@ipr-dev-pi4.local:/opt/ipr_state/verification_report.txt dev_report.txt
scp meibye@ipr-target-zero2.local:/opt/ipr_state/verification_report.txt zero_report.txt

# Compare
diff -u dev_report.txt zero_report.txt
# Or use VS Code
code --diff dev_report.txt zero_report.txt
```

**What should match**:
- ✓ OS version (Debian, kernel major.minor)
- ✓ BlueZ version
- ✓ Python version
- ✓ Git commit hash
- ✓ List of installed packages
- ✓ Services enabled

**What should differ** (device-specific):
- Hostname (`ipr-dev-pi4` vs `ipr-target-zero2`)
- Bluetooth name (`IPR Keyboard (Dev)` vs `IPR Keyboard`)
- Hardware info (RPi 4 vs Pi Zero 2 W)

---


## Updating Devices

### Sync to New Git Commit

```bash
cd /home/meibye/dev/ipr-keyboard

# Get latest code
git fetch --all --tags
git checkout <tag-or-branch>

# Update Python environment (venv setup will run as APP_USER automatically)
sudo ./provision/03_app_install.sh

# Restart services
sudo systemctl restart ipr_keyboard
sudo systemctl restart bt_hid_ble
```

### Re-run Full Provisioning

If configuration has changed significantly:

```bash
# Update common.env with new values
sudo nano /opt/ipr_common.env

# Re-run from desired step
# (Usually start from 03 or 04 to avoid OS updates)
sudo ./provision/03_app_install.sh
sudo ./provision/04_enable_services.sh
sudo ./provision/05_verify.sh
```

---

## Troubleshooting

### Script Fails with "Environment file not found"

**Problem**: `/opt/ipr_common.env` doesn't exist

**Solution**:
```bash
cp provision/common.env.example provision/common.env
nano provision/common.env  # Edit values
sudo cp provision/common.env /opt/ipr_common.env
```

### Repository Not Found

**Problem**: Git clone fails or repo directory missing

**Solution**:
```bash
# Verify network connection
ping github.com

# Clone manually
mkdir -p /home/meibye/dev
cd /home/meibye/dev
git clone https://github.com/meibye/ipr-keyboard.git
```

### Services Not Starting

**Problem**: Services show "failed" after `04_enable_services.sh`

**Solution**:
```bash
# Check logs
sudo journalctl -u ipr_keyboard.service -n 100

# Verify Python environment
ls -la /home/meibye/dev/ipr-keyboard/.venv

# Re-run app install
sudo ./provision/03_app_install.sh

# Re-run service install
sudo ./provision/04_enable_services.sh
```

### Bluetooth Name Not Applied

**Problem**: `bluetoothctl show` shows wrong name

**Solution**:
```bash
# Check configuration
cat /etc/bluetooth/main.conf | grep "Name ="

# Restart Bluetooth
sudo systemctl restart bluetooth

# Verify
bluetoothctl show | grep "Name:"

# If still wrong, re-run identity script
sudo ./provision/02_device_identity.sh
sudo reboot
```

---

## Advanced Usage

### Custom Git Repository

To use a fork or different repository:

```bash
# Edit common.env before running bootstrap
REPO_URL="https://github.com/yourusername/ipr-keyboard.git"
GIT_REF="your-branch"
```

### Pin to Specific Release

For production deployments:

```bash
# In common.env
GIT_REF="v1.0.0"  # Use tagged release

# Bootstrap will checkout this exact version
sudo ./provision/00_bootstrap.sh
```

### Different Installation Path

```bash
# In common.env
REPO_DIR="/opt/ipr-keyboard"
APP_VENV_DIR="/opt/ipr-keyboard/.venv"

# Ensure user has permissions
sudo chown -R meibye:meibye /opt
```

---

## Integration with Existing Scripts

Provisioning scripts leverage existing setup scripts from `scripts/` directory:

| Provisioning Script | Calls Existing Script |
|---------------------|----------------------|
| `01_os_base.sh` | → `scripts/sys_install_packages.sh`<br>→ `scripts/ble/bt_configure_system.sh` |
| `03_app_install.sh` | → `scripts/sys_setup_venv.sh` |
| `04_enable_services.sh` | → `scripts/service/svc_install_systemd.sh`<br>→ `scripts/ble/ble_setup_extras.sh`<br>→ `scripts/ble/ble_install_helper.sh`<br>→ `scripts/service/svc_enable_ble_services.sh` |

This ensures provisioning uses the same tested installation procedures as manual setup.

---

## See Also

- [DEVICE_BRINGUP.md](../DEVICE_BRINGUP.md) - Complete bring-up procedure
- [DEVELOPMENT_WORKFLOW.md](../DEVELOPMENT_WORKFLOW.md) - Daily development workflow
- [scripts/README.md](../scripts/README.md) - Script documentation
- [README.md](../README.md) - Project overview
