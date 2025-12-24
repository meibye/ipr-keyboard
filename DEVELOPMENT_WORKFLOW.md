# IPR Keyboard - Development Workflow

This document describes the day-to-day development workflow for the ipr-keyboard project using the two-device setup (RPi 4 for development, Pi Zero 2 W for validation).

## Table of Contents

- [Overview](#overview)
- [Development Environment Setup](#development-environment-setup)
- [Daily Development Workflow](#daily-development-workflow)
- [Testing Strategy](#testing-strategy)
- [Keeping Devices in Sync](#keeping-devices-in-sync)
- [Common Tasks](#common-tasks)
- [Git Workflow](#git-workflow)
- [Troubleshooting During Development](#troubleshooting-during-development)

---

## Overview

### The Two-Device Development Model

**RPi 4 (ipr-dev-pi4)** - Primary development device
- More powerful hardware (faster compile/test cycles)
- Connected via VS Code Remote-SSH
- Real-time code editing and debugging
- Full test suite execution
- BLE testing with development laptop

**Pi Zero 2 W (ipr-target-zero2)** - Target validation device
- Actual deployment hardware
- Validate performance on target
- Test completed features iteratively
- Verify resource usage (CPU, memory)
- Final validation before release

### Development Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     Windows 11 PC                           │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  VS Code    │  │  Git         │  │  SSH Terminals   │  │
│  │  Remote-SSH │  │  (GitHub)    │  │  (both devices)  │  │
│  └──────┬──────┘  └──────┬───────┘  └──────────────────┘  │
└─────────┼─────────────────┼──────────────────────────────────┘
          │                 │
          │                 │ push/pull
          ▼                 ▼
┌──────────────────┐  ┌────────────────┐
│  RPi 4 (Dev)     │  │  GitHub        │
│  ipr-dev-pi4     │◄─┤  meibye/       │
│                  │  │  ipr-keyboard  │
│  • Edit code     │  └────────────────┘
│  • Run tests     │         │
│  • Debug         │         │ pull (periodic)
│  • BLE testing   │         ▼
│                  │  ┌────────────────┐
└──────────────────┘  │  Pi Zero 2 W   │
                      │  ipr-target-   │
   Feature complete   │  zero2         │
   ─────────────────► │                │
   Validate on target │  • Validate    │
                      │  • Performance │
                      │  • Final test  │
                      └────────────────┘
```

---

## Development Environment Setup

### Step 1: VS Code Remote-SSH Configuration

**On Windows PC**, configure SSH for both devices:

1. Edit `~/.ssh/config` (or `C:\Users\<YourName>\.ssh\config`):

```
# RPi 4 Development Device
Host ipr-dev-pi4
    HostName ipr-dev-pi4.local
    User meibye
    ForwardAgent yes
    ServerAliveInterval 60

# Pi Zero 2 W Target Device  
Host ipr-target-zero2
    HostName ipr-target-zero2.local
    User meibye
    ForwardAgent yes
    ServerAliveInterval 60
```

2. Install VS Code extensions:
   - Remote - SSH (ms-vscode-remote.remote-ssh)
   - Python (ms-python.python)
   - Pylance (ms-python.vscode-pylance)

3. Connect to RPi 4:
   - Press `F1` → "Remote-SSH: Connect to Host"
   - Select "ipr-dev-pi4"
   - Open folder: `/home/meibye/dev/ipr-keyboard`

### Step 2: Configure Python in VS Code

Once connected to RPi 4:

1. Open Command Palette (`Ctrl+Shift+P`)
2. "Python: Select Interpreter"
3. Choose: `/home/meibye/dev/ipr-keyboard/.venv/bin/python`

4. Create `.vscode/settings.json` in workspace:

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "python.terminal.activateEnvironment": true,
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests",
        "-v"
    ],
    "files.watcherExclude": {
        "**/.venv/**": true
    }
}
```

### Step 3: Terminal Setup

Keep multiple terminal windows open:

- **VS Code Terminal (RPi 4)**: Main development terminal
- **PowerShell Terminal 1**: SSH to RPi 4 for service monitoring
- **PowerShell Terminal 2**: SSH to Pi Zero for validation

---

## Daily Development Workflow

### Morning Startup Routine

**1. Check service status on both devices:**

```bash
# On RPi 4
ssh meibye@ipr-dev-pi4.local
sudo ./scripts/service/svc_status_services.sh
sudo journalctl -u ipr_keyboard.service -f  # Monitor logs

# On Pi Zero
ssh meibye@ipr-target-zero2.local
sudo systemctl status ipr_keyboard.service
```

**2. Pull latest changes (if working with team):**

```bash
# On RPi 4 (via VS Code terminal)
cd /home/meibye/dev/ipr-keyboard
git fetch --all
git pull origin main
```

**3. Activate Python environment:**

```bash
source .venv/bin/activate
```

### Feature Development Cycle (on RPi 4)

**Step 1: Create feature branch**

```bash
git checkout -b feature/your-feature-name
```

**Step 2: Edit code in VS Code**

VS Code is connected to RPi 4, edit files directly.

**Step 3: Run unit tests**

```bash
# Run specific test
pytest tests/bluetooth/test_keyboard.py -v

# Run all tests
pytest

# Run with coverage
pytest --cov=ipr_keyboard --cov-report=term-missing
```

**Step 4: Test in foreground (with logs)**

```bash
# Stop service temporarily
sudo systemctl stop ipr_keyboard

# Run in foreground
python -m ipr_keyboard.main

# Or use dev script
./scripts/dev_run_app.sh

# Ctrl+C to stop, restart service
sudo systemctl start ipr_keyboard
```

**Step 5: Test Bluetooth functionality**

```bash
# Pair your laptop with "IPR Keyboard (Dev)"
# Then test keyboard input
./scripts/test_bluetooth.sh "Test message with æøå"
```

**Step 6: Commit changes**

```bash
git add .
git commit -m "Add feature: description"
git push origin feature/your-feature-name
```

### Validation on Target (Pi Zero 2 W)

Once feature is complete and tested on RPi 4:

**Step 1: Push changes and pull on Pi Zero**

```bash
# On RPi 4
git push origin feature/your-feature-name

# On Pi Zero
cd /home/meibye/dev/ipr-keyboard
git fetch --all
git checkout feature/your-feature-name
```

**Step 2: Update Python environment**

```bash
# If dependencies changed
./scripts/sys_setup_venv.sh
```

**Step 3: Restart services**

```bash
sudo systemctl restart ipr_keyboard
sudo systemctl restart bt_hid_ble
```

**Step 4: Monitor and validate**

```bash
# Watch logs
sudo journalctl -u ipr_keyboard.service -f

# Check resource usage
htop  # or: top

# Test Bluetooth pairing and functionality
./scripts/test_bluetooth.sh "Validation test"
```

**Step 5: Performance testing**

```bash
# Check CPU usage during operation
mpstat 1 10

# Check memory usage
free -h

# Monitor service health
./scripts/diag_status.sh
```

---

## Testing Strategy

### Three-Level Testing Approach

**Level 1: Unit Tests (RPi 4)**
- Run during development: `pytest`
- Fast feedback loop
- Test individual components

**Level 2: Integration Tests (RPi 4)**
- Full application flow tests
- Service interaction tests
- Run before pushing: `pytest tests/integration/`

**Level 3: E2E Validation (Pi Zero 2 W)**
- Real hardware validation
- Performance under load
- Production-like environment
- Run before tagging release

### Running Tests

```bash
# Quick unit tests (during development)
pytest -x  # Stop on first failure

# Full test suite
pytest --cov=ipr_keyboard

# Integration tests only
pytest tests/integration/ -v

# Bluetooth-specific tests
pytest tests/bluetooth/ -v

# E2E smoke test
./scripts/test_smoke.sh

# Full E2E test
./scripts/test_e2e_demo.sh
```

---

## Keeping Devices in Sync

### Verify Both Devices Are at Same Level

**Generate verification reports:**

```bash
# On each device
sudo ./provision/05_verify.sh
```

**Compare on Windows PC:**

```powershell
scp meibye@ipr-dev-pi4.local:/opt/ipr_state/verification_report.txt dev_report.txt
scp meibye@ipr-target-zero2.local:/opt/ipr_state/verification_report.txt zero_report.txt
code --diff dev_report.txt zero_report.txt
```

### Sync Pi Zero to Match RPi 4

When RPi 4 has been updated and you need Pi Zero to match:

```bash
# On Pi Zero
cd /home/meibye/dev/ipr-keyboard

# Get exact commit from RPi 4
# (Run on RPi 4: git rev-parse HEAD)
COMMIT_HASH="<commit-hash-from-pi4>"

# Sync to same commit
git fetch --all --tags
git checkout $COMMIT_HASH

# Update Python environment
./scripts/sys_setup_venv.sh

# Restart services
sudo systemctl restart ipr_keyboard
sudo systemctl restart bt_hid_ble
sudo systemctl restart bt_hid_agent_unified
```

### Using Git Tags for Releases

**Create a release (on RPi 4 or GitHub):**

```bash
# Tag a release
git tag -a v1.0.0 -m "Release 1.0.0: Initial production release"
git push origin v1.0.0
```

**Deploy tagged release to both devices:**

```bash
# On each device
cd /home/meibye/dev/ipr-keyboard
git fetch --all --tags
git checkout v1.0.0
./scripts/sys_setup_venv.sh
sudo systemctl restart ipr_keyboard
```

---

## Common Tasks

### Update System Packages

```bash
# On each device (periodically)
sudo apt update
sudo apt -y upgrade

# If BlueZ or Python updated, may need reboot
sudo reboot
```

### Update Python Dependencies

```bash
# On each device
cd /home/meibye/dev/ipr-keyboard
./scripts/sys_setup_venv.sh
sudo systemctl restart ipr_keyboard
```

### Change Backend (BLE/uinput)

```bash
# Switch to BLE (default)
sudo ./scripts/ble_switch_backend.sh ble

# Switch to uinput (alternative)
sudo ./scripts/ble_switch_backend.sh uinput
```

### View Logs

```bash
# Real-time logs
sudo journalctl -u ipr_keyboard.service -f

# Last 100 lines
sudo journalctl -u ipr_keyboard.service -n 100

# Logs since boot
sudo journalctl -u ipr_keyboard.service -b

# All service logs
sudo journalctl -u "ipr*" -u "bt_hid*" -f
```

### Restart Services

```bash
# Restart main application
sudo systemctl restart ipr_keyboard

# Restart all BLE services
sudo systemctl restart bt_hid_ble
sudo systemctl restart bt_hid_agent_unified
sudo systemctl restart ipr_backend_manager

# Restart Bluetooth stack
sudo systemctl restart bluetooth
```

### Monitor Service Health

```bash
# Interactive TUI monitor
sudo ./scripts/service/svc_status_monitor.py

# Text status report
sudo ./scripts/service/svc_status_services.sh

# System diagnostics
./scripts/diag_status.sh

# BLE diagnostics
sudo ./scripts/diag_ble.sh
```

---

## Git Workflow

### Recommended Branch Strategy

```
main (production)
  │
  ├─ develop (integration)
  │   │
  │   ├─ feature/scan-text
  │   ├─ feature/ble-improvements
  │   └─ bugfix/pairing-issue
  │
  └─ release/v1.x (release prep)
```

### Feature Development

```bash
# Start new feature
git checkout develop
git pull origin develop
git checkout -b feature/your-feature

# Work on feature...
git add .
git commit -m "Implement feature"
git push origin feature/your-feature

# Merge to develop
git checkout develop
git merge feature/your-feature
git push origin develop
```

### Release Process

```bash
# Create release branch
git checkout -b release/v1.1.0 develop

# Version bump, final testing
# ...

# Merge to main
git checkout main
git merge release/v1.1.0
git tag -a v1.1.0 -m "Release 1.1.0"
git push origin main --tags

# Merge back to develop
git checkout develop
git merge release/v1.1.0
git push origin develop
```

---

## Troubleshooting During Development

### Code Changes Not Taking Effect

```bash
# 1. Verify you're editing the right files
pwd  # Should be /home/meibye/dev/ipr-keyboard

# 2. Check if service is using correct venv
sudo systemctl cat ipr_keyboard.service | grep ExecStart

# 3. Restart service
sudo systemctl restart ipr_keyboard

# 4. Check for Python bytecode cache issues
find . -type d -name __pycache__ -exec rm -rf {} +
```

### Bluetooth Pairing Issues

```bash
# Reset Bluetooth on Pi
sudo systemctl restart bluetooth
bluetoothctl
> power off
> power on
> discoverable on
> pairable on

# Remove old pairings
bluetoothctl
> devices
> remove <MAC>

# Run pairing diagnostics
sudo ./scripts/diag_pairing.sh
```

### Service Crashes

```bash
# Check logs
sudo journalctl -u ipr_keyboard.service -n 200

# Run in foreground to see errors
sudo systemctl stop ipr_keyboard
python -m ipr_keyboard.main

# Check Python environment
source .venv/bin/activate
python -c "import ipr_keyboard; print(ipr_keyboard.__file__)"
```

### Performance Issues on Pi Zero

```bash
# Check CPU usage
top

# Check memory usage
free -h

# Check disk I/O
iostat -x 1

# Profile Python code
python -m cProfile -o profile.stats -m ipr_keyboard.main
```

---

## Best Practices

### Do's ✓

- ✓ Always test on RPi 4 first
- ✓ Run pytest before committing
- ✓ Use feature branches
- ✓ Validate on Pi Zero before tagging releases
- ✓ Keep both devices at same Git commit for validation
- ✓ Monitor logs during development
- ✓ Use `./scripts/dev_run_app.sh` for quick testing

### Don'ts ✗

- ✗ Don't develop directly on Pi Zero (too slow)
- ✗ Don't commit untested code
- ✗ Don't mix development branches on validation device
- ✗ Don't forget to restart services after code changes
- ✗ Don't skip validation on target hardware
- ✗ Don't push to main without testing

---

## Quick Reference

### Essential Commands

| Task | Command |
|------|---------|
| **Connect VS Code** | `F1` → Remote-SSH: Connect → ipr-dev-pi4 |
| **Run tests** | `pytest` or `pytest -v` |
| **Run in foreground** | `./scripts/dev_run_app.sh` |
| **View logs** | `sudo journalctl -u ipr_keyboard -f` |
| **Restart service** | `sudo systemctl restart ipr_keyboard` |
| **Service status** | `sudo ./scripts/service/svc_status_services.sh` |
| **Test Bluetooth** | `./scripts/test_bluetooth.sh "test"` |
| **Sync to commit** | `git checkout <hash>` |
| **Verify config** | `sudo ./provision/05_verify.sh` |

---

## Additional Resources

- [DEVICE_BRINGUP.md](DEVICE_BRINGUP.md) - Initial device setup
- [TESTING_PLAN.md](TESTING_PLAN.md) - Comprehensive testing strategy
- [BLUETOOTH_PAIRING.md](BLUETOOTH_PAIRING.md) - Bluetooth troubleshooting
- [scripts/README.md](scripts/README.md) - Script documentation
- [provision/README.md](provision/README.md) - Provisioning system
