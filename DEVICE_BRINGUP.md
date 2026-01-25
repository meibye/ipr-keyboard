# IPR Keyboard - Device Bring-Up Procedure

This document describes the step-by-step procedure for bringing up a new Raspberry Pi device for the ipr-keyboard project. It covers SD card flashing, provisioning, configuration, and verification. The process is fully automated using the provisioning scripts in the repository. Both RPi 4 and Pi Zero 2 W are supported and configured identically except for device-specific settings.

## Overview

**Goal**: Configure both RPis identically except for device-specific settings (hostname, Bluetooth name).

**Time Estimate**:
- RPi 4: ~45 minutes
- RPi Zero 2 W: ~60 minutes (slower hardware)

**Result**: Both devices will have:
- Raspberry Pi OS Lite (64-bit) Bookworm
- All system packages and dependencies installed
- Python environment configured with uv
- ipr-keyboard application installed and running
- Bluetooth HID backend services configured
- Device-specific hostname and Bluetooth name

## Quick Start

1. Flash SD card with Raspberry Pi OS Lite (64-bit) Bookworm
2. Boot Pi and connect via SSH
3. Transfer and run the provisioning wizard (`provision/00_provision_wizard.sh`)
4. Follow prompts to configure device and run all provisioning scripts
5. Reboot as instructed
6. Verify device with `provision/05_verify.sh` and compare reports

## Provisioning Workflow

The provisioning system in `provision/` automates all setup steps:

## Device Verification

After provisioning, run the verification script and compare reports between devices:

## Troubleshooting

If provisioning fails:

## Troubleshooting

If provisioning fails:
- Check `/opt/ipr_state/` for logs and reports
- Ensure network connectivity
- Re-run failed script or start over with the wizard

## See Also

- [provision/README.md](provision/README.md) - Provisioning system
- [README.md](README.md) - Project overview
- [scripts/README.md](scripts/README.md) - Script documentation


## Prerequisites

### Hardware

- [ ] Raspberry Pi 4 Model B (4GB RAM recommended)
- [ ] Raspberry Pi Zero 2 W
- [ ] 2x microSD cards (16GB minimum, 32GB recommended)
- [ ] SD card reader
- [ ] Power supplies for both Pis
- [ ] (Optional) Ethernet cable for RPi 4
- [ ] (Optional) USB cable for Pi Zero OTG provisioning

### Software (Windows 11 PC)

- [ ] [Raspberry Pi Imager](https://www.raspberrypi.com/software/) (latest version)
- [ ] SSH client (Windows 11 has built-in OpenSSH)
- [ ] Git for Windows (if you want to manage repo from Windows)
- [ ] VS Code with Remote-SSH extension (for development)

### Network

- [ ] Wi-Fi network with 2.4 GHz support (for Pi Zero compatibility)
- [ ] Wi-Fi SSID and password
- [ ] (Optional) Ethernet network for RPi 4

---

## Phase 1: SD Card Preparation (Windows 11)

Prepare **both** SD cards identically using Raspberry Pi Imager.

### Step 1.1: Launch Raspberry Pi Imager

```powershell
# Download and install from: https://www.raspberrypi.com/software/
# Or install via winget:
winget install --id=RaspberryPiFoundation.RaspberryPiImager
```

### Step 1.2: Configure OS and Settings

**For BOTH cards**, use these exact settings:

1. **Choose OS**: Raspberry Pi OS (other) → **Raspberry Pi OS Lite (64-bit)**
   - Version: Bookworm (Debian 12)

2. **Choose Storage**: Select your SD card

3. **Click the gear icon** ⚙️ (Advanced options)

4. **Configure settings**:
   
   ```
   ✓ Enable SSH
     Authentication method: password
   
   ✓ Set username and password
     Username: meibye
     Password: <your secure password>
   
   ✓ Configure wireless LAN
     SSID: <your Wi-Fi SSID>
     Password: <your Wi-Fi password>
     Wireless LAN country: <your country, e.g., DK>
   
   ✓ Set locale settings
     Time zone: Europe/Copenhagen
     Keyboard layout: dk (or your preference)
   ```

5. **Click "Save"**

6. **Click "Write"** and wait for completion

### Step 1.3: Label the Cards

Physically label the SD cards:
- **Card 1**: "RPi 4 Dev"
- **Card 2**: "Pi Zero Target"

---

## Phase 2: First Boot and Basic Configuration

Perform these steps **on each Pi separately**.

### Step 2.1: Initial Boot

1. Insert SD card into Pi
2. Connect power
3. Wait ~60 seconds for first boot
4. Pi should connect to Wi-Fi automatically

### Step 2.2: Find the Pi on Network

From Windows PowerShell:

```powershell
# Initial hostname is "raspberrypi"
ssh meibye@raspberrypi.local
```

If multiple Pis or connection fails:
```powershell
# Scan network for Raspberry Pis
nmap -sn 192.168.1.0/24 | grep -B 2 "Raspberry"

# Or use IP scanner tool
```

### Step 2.3: Initial System Update

```bash
# Run full system upgrade
sudo apt update
sudo apt -y full-upgrade

# This may take 10-30 minutes depending on device and connection
```

### Step 2.4: Set Device-Specific Hostname

**On RPi 4**:
```bash
sudo hostnamectl set-hostname ipr-dev-pi4
sudo sed -i 's/127.0.1.1.*/127.0.1.1\tipr-dev-pi4/' /etc/hosts
sudo reboot
```

**On Pi Zero 2 W**:
```bash
sudo hostnamectl set-hostname ipr-target-zero2
sudo sed -i 's/127.0.1.1.*/127.0.1.1\tipr-target-zero2/' /etc/hosts
sudo reboot
```

### Step 2.5: Reconnect with New Hostname

After reboot (~30 seconds), reconnect:

**RPi 4**:
```powershell
ssh meibye@ipr-dev-pi4.local
```

**Pi Zero 2 W**:
```powershell
ssh meibye@ipr-target-zero2.local
```

---

## Phase 3: Headless Provisioning Setup (Optional)

This phase is **optional** but **highly recommended** for the Pi Zero 2 W to enable recovery if you lose Wi-Fi access.

### Step 3.1: USB OTG Setup (Pi Zero 2 W Only)

On Pi Zero 2 W:

```bash
# Clone repo first (needed for scripts)
mkdir -p /home/meibye/dev
cd /home/meibye/dev
git clone https://github.com/meibye/ipr-keyboard.git
cd ipr-keyboard

# Run USB OTG setup
sudo ./scripts/headless/usb_otg_setup.sh

# Reboot to activate
sudo reboot
```

**Test USB OTG access**:
1. Connect Pi Zero's USB port (not PWR) to laptop
2. Wait for USB Ethernet adapter to appear
3. SSH to: `ssh meibye@192.168.7.1`

### Step 3.2: Wi-Fi Hotspot Provisioning (Both Devices - Optional)

This enables auto-hotspot mode when Wi-Fi is unavailable.

Installation handled automatically by provisioning scripts in Phase 4.

---

## Phase 4: Automated Provisioning

Now we'll use the automated provisioning scripts to configure everything consistently.

### Step 4.1: Clone Repository

On **each device**:

```bash
mkdir -p /home/meibye/dev
cd /home/meibye/dev
git clone https://github.com/meibye/ipr-keyboard.git
cd ipr-keyboard

# Pin to a specific version for reproducibility
git fetch --all --tags
git checkout main  # Or use a specific tag like "v1.0.0"
```

### Step 4.2: Create Device-Specific Configuration

On **each device**, create the provisioning configuration:

```bash
cd /home/meibye/dev/ipr-keyboard
cp provision/common.env.example provision/common.env
nano provision/common.env
```

**For RPi 4**, edit these values:
```bash
DEVICE_TYPE="dev"
HOSTNAME="ipr-dev-pi4"
BT_DEVICE_NAME="IPR Keyboard (Dev)"
```

**For Pi Zero 2 W**, edit these values:
```bash
DEVICE_TYPE="target"
HOSTNAME="ipr-target-zero2"
BT_DEVICE_NAME="IPR Keyboard"
```

Install the configuration:
```bash
sudo cp provision/common.env /opt/ipr_common.env
```

### Step 4.3: Run Provisioning Scripts

On **each device**, run these scripts **in order**:

```bash
cd /home/meibye/dev/ipr-keyboard

# Step 1: Bootstrap (installs base tools, sets up repo)
sudo ./provision/00_bootstrap.sh

# Step 2: OS baseline (installs packages, configures Bluetooth)
sudo ./provision/01_os_base.sh

# REBOOT after OS baseline
sudo reboot
```

After reboot, reconnect and continue:

```bash
cd /home/meibye/dev/ipr-keyboard

# Step 3: Device identity (sets hostname, BT name)
sudo ./provision/02_device_identity.sh

# REBOOT after device identity
sudo reboot
```

After reboot, reconnect and continue:

```bash
cd /home/meibye/dev/ipr-keyboard

# Step 4: Application install (Python venv, dependencies)
sudo ./provision/03_app_install.sh

# Step 5: Enable services (systemd, BLE backend)
sudo ./provision/04_enable_services.sh
```

### Step 4.4: Run Verification

```bash
# Step 6: Verify configuration
sudo ./provision/05_verify.sh
```

Review the verification report:
```bash
cat /opt/ipr_state/verification_report.txt
```

---

## Phase 5: Verification

### Step 5.1: Verify Both Devices Match

Copy verification reports from both devices to your PC:

```powershell
# From Windows PowerShell
scp meibye@ipr-dev-pi4.local:/opt/ipr_state/verification_report.txt ./dev_report.txt
scp meibye@ipr-target-zero2.local:/opt/ipr_state/verification_report.txt ./zero_report.txt

# Compare them
code --diff dev_report.txt zero_report.txt
```

**What to check**:
- ✓ OS versions match (same Debian version, same kernel major.minor)
- ✓ BlueZ versions match
- ✓ Python versions match
- ✓ Same Git commit hash
- ✓ Same services enabled (ipr_keyboard, bt_hid_ble, bt_hid_agent_unified)
- Hostnames differ (expected - device-specific)
- Bluetooth names differ (expected - device-specific)

### Step 5.2: Verify Services Are Running

On **each device**:

```bash
# Check service status
sudo systemctl status ipr_keyboard.service
sudo systemctl status bt_hid_ble.service
sudo systemctl status bt_hid_agent_unified.service
sudo systemctl status ipr_backend_manager.service

# Quick status check
sudo ./scripts/service/svc_status_services.sh
```

All services should show "active (running)".

### Step 5.3: Verify Bluetooth

On **each device**:

```bash
# Check Bluetooth adapter
bluetoothctl show

# Verify device name
bluetoothctl show | grep "Name:"
```

Expected output:
- **RPi 4**: `Name: IPR Keyboard (Dev)`
- **Pi Zero 2 W**: `Name: IPR Keyboard`

### Step 5.4: Test Bluetooth Pairing (Optional)

From your laptop/PC:
1. Open Bluetooth settings
2. Scan for devices
3. You should see "IPR Keyboard (Dev)" and/or "IPR Keyboard"
4. Pair with one device
5. Test by running: `./scripts/test_bluetooth.sh "Test message"`

---

## Troubleshooting

### SSH Connection Issues

**Problem**: Can't connect to `hostname.local`

**Solutions**:
```powershell
# 1. Check if mDNS is working
ping ipr-dev-pi4.local

# 2. Find IP address and connect directly
# Use IP scanner or router admin page
ssh meibye@192.168.1.xxx

# 3. Check if Pi is on network
nmap -sn 192.168.1.0/24
```

### Service Not Starting

**Problem**: Service shows "failed" or "inactive"

**Solutions**:
```bash
# Check logs
sudo journalctl -u ipr_keyboard.service -n 100

# Check Python environment
source /home/meibye/dev/ipr-keyboard/.venv/bin/activate
python -m ipr_keyboard.main  # Run in foreground

# Reinstall services
sudo ./scripts/service/svc_install_systemd.sh
sudo ./scripts/ble/ble_install_helper.sh
sudo ./scripts/service/svc_enable_ble_services.sh
```

### Bluetooth Not Working

**Problem**: Bluetooth adapter not found or pairing fails

**Solutions**:
```bash
# Check Bluetooth status
sudo systemctl status bluetooth
bluetoothctl show

# Restart Bluetooth
sudo systemctl restart bluetooth

# Check BlueZ configuration
cat /etc/bluetooth/main.conf | grep -E "(Experimental|Name)"

# Run diagnostics
sudo /usr/local/bin/ipr_ble_diagnostics.sh
```

### Devices at Different Levels

**Problem**: Verification shows different versions

**Solutions**:
```bash
# On both devices, sync to same commit
cd /home/meibye/dev/ipr-keyboard
git fetch --all --tags
git checkout <same-commit-hash>

# Reinstall Python environment
./scripts/sys_setup_venv.sh

# Restart services
sudo systemctl restart ipr_keyboard
sudo systemctl restart bt_hid_ble
```

### USB OTG Not Working (Pi Zero)

**Problem**: Can't connect via USB

**Check**:
```bash
# Verify boot config
cat /boot/firmware/config.txt | grep dwc2
cat /boot/firmware/cmdline.txt | grep "modules-load"

# Re-run setup if missing
sudo ./scripts/headless/usb_otg_setup.sh
sudo reboot
```

### Factory Reset (Wi-Fi)

If you need to reset Wi-Fi and enter provisioning mode:

**Method 1**: Marker file
1. Remove SD card
2. Mount boot partition on PC
3. Create empty file named `IPR_RESET_WIFI`
4. Reinsert SD and boot

**Method 2**: GPIO jumper (if enabled)
1. Connect GPIO17 (Pin 11) to GND (Pin 9)
2. Power on Pi
3. Wait for 2 seconds with jumper in place
4. Remove jumper

---

## Next Steps

Once both devices are provisioned and verified:

1. Read [DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md) for development procedures
2. Set up VS Code Remote-SSH to RPi 4 for development
3. Test IrisPen scanner functionality
4. Begin iterative development cycle

---

## Reference

- [Main README](README.md) - Project overview
- [DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md) - Development procedures
- [scripts/README.md](scripts/README.md) - Script documentation
- [provision/README.md](provision/README.md) - Provisioning system details
