# Diagnostic Scripts for Remote Bluetooth Troubleshooting

This directory contains diagnostic scripts designed to enable remote troubleshooting of Bluetooth pairing issues on Raspberry Pi via GitHub Copilot Chat using an MCP (Model Context Protocol) SSH server.

## Overview

These scripts provide bounded, safe diagnostic operations that can be executed remotely to investigate Bluetooth HID pairing failures between Windows 11 and Raspberry Pi BLE HID devices. They are designed to work with GitHub Copilot's diagnostic agent mode.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Windows 11 Development PC                    │
│                                                                 │
│  ┌──────────────┐         ┌─────────────────────────────────┐  │
│  │   VS Code    │────────>│  GitHub Copilot Chat Agent      │  │
│  │              │         │  (uses MCP SSH server)          │  │
│  └──────────────┘         └──────────────┬──────────────────┘  │
│                                          │                      │
└──────────────────────────────────────────┼──────────────────────┘
                                           │ SSH over MCP
                                           │
┌──────────────────────────────────────────▼──────────────────────┐
│                    Raspberry Pi 4 Target                        │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Diagnostic Scripts (/usr/local/bin/)                   │   │
│  │                                                          │   │
│  │  • dbg_deploy.sh          - Deploy & restart service    │   │
│  │  • dbg_diag_bundle.sh     - System diagnostics          │   │
│  │  • dbg_pairing_capture.sh - Capture pairing attempts    │   │
│  │  • dbg_bt_restart.sh      - Safe service restart        │   │
│  │  • dbg_bt_soft_reset.sh   - Conservative BT reset       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Diagnostic Output (/var/log/ipr/)                      │   │
│  │                                                          │   │
│  │  • pairing_TIMESTAMP/ - Captured pairing sessions       │   │
│  │    - btmon.txt                                           │   │
│  │    - journal_bluetooth.txt                               │   │
│  │    - journal_service.txt                                 │   │
│  │    - snapshot_before.txt                                 │   │
│  │    - snapshot_after.txt                                  │   │
│  │    - highlights.txt                                      │   │
│  │  • latest -> (symlink to most recent capture)           │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Scripts

### `dbg_deploy.sh`
**Purpose:** Deploy latest code from GitHub and restart the BLE HID service.

**Usage:**
```bash
sudo /usr/local/bin/dbg_deploy.sh
```

**What it does:**
1. Navigates to repository directory
2. Fetches latest changes from GitHub
3. Performs hard reset to origin/main
4. Restarts bt_hid_ble.service
5. Shows service status

**Configuration:**
Edit these variables at the top of the script:
- `REPO_DIR`: Path to repository on Pi (default: `/home/copilotdiag/ipr-keyboard`)
- `BRANCH`: Git branch to deploy (default: `main`)
- `SERVICE_BT`: Systemd service name (default: `bt_hid_ble.service`)

---

### `dbg_diag_bundle.sh`
**Purpose:** Collect comprehensive system diagnostics for initial troubleshooting.

**Usage:**
```bash
sudo /usr/local/bin/dbg_diag_bundle.sh
```

**What it collects:**
- System information (uname, uptime, OS version)
- Bluetooth controller status (btmgmt, hciconfig)
- BlueZ and bluetoothd version and status
- BLE HID service status
- Recent logs from bluetooth.service (last 60 minutes, max 300 lines)
- Recent logs from bt_hid_ble.service (last 60 minutes, max 500 lines)
- Bluetooth-related kernel messages (last 200 lines)

**Output:** Prints to stdout (redirect or pipe as needed)

---

### `dbg_pairing_capture.sh`
**Purpose:** Capture a bounded pairing window with btmon and journal logs.

**Usage:**
```bash
sudo /usr/local/bin/dbg_pairing_capture.sh [duration_seconds]
```

**Examples:**
```bash
# Capture 60-second pairing window (default)
sudo /usr/local/bin/dbg_pairing_capture.sh

# Capture 90-second pairing window
sudo /usr/local/bin/dbg_pairing_capture.sh 90
```

**What it does:**
1. Creates timestamped output directory in `/var/log/ipr/pairing_TIMESTAMP/`
2. Updates `/var/log/ipr/latest` symlink for convenience
3. Captures system snapshot before pairing attempt
4. Starts bounded btmon capture on hci0
5. Captures bluetooth.service and bt_hid_ble.service journal logs in real-time
6. Waits for specified duration (user initiates pairing during this time)
7. Captures system snapshot after pairing attempt
8. Extracts highlights (errors, failures, authentication issues) from all logs

**Output files:**
- `snapshot_before.txt` - System state before pairing
- `btmon.txt` - Bluetooth monitor protocol trace
- `journal_bluetooth.txt` - bluetooth.service logs
- `journal_service.txt` - bt_hid_ble.service logs
- `snapshot_after.txt` - System state after pairing
- `highlights.txt` - Extracted potential errors and issues

**Workflow:**
1. Run the script with desired duration
2. When script shows "RUNNING", initiate pairing from Windows
3. Script automatically stops after duration and saves all artifacts
4. Examine `/var/log/ipr/latest/highlights.txt` for quick issue summary

---

### `dbg_bt_restart.sh`
**Purpose:** Safe restart of Bluetooth services without reset or bond wipe.

**Usage:**
```bash
sudo /usr/local/bin/dbg_bt_restart.sh
```

**What it does:**
1. Restarts bluetooth.service
2. Restarts bt_hid_ble.service
3. Shows status of both services

**When to use:**
- After configuration changes
- When service appears hung but bonds are working
- As first recovery step before more invasive resets

---

### `dbg_bt_soft_reset.sh`
**Purpose:** Conservative Bluetooth reset without destroying bond information.

**Usage:**
```bash
sudo /usr/local/bin/dbg_bt_soft_reset.sh
```

**What it does:**
1. Stops bt_hid_ble.service
2. Restarts bluetooth.service
3. Powers off Bluetooth controller (hci0)
4. Waits 1 second
5. Powers on Bluetooth controller
6. Starts bt_hid_ble.service
7. Shows controller and service status

**When to use:**
- When pairing is stuck but you want to preserve existing bonds
- After `dbg_bt_restart.sh` doesn't resolve the issue
- Before considering bond wipe as last resort

**Note:** This does NOT remove paired devices. For bond wipe, manual approval is required.

---

## Installation

These scripts are designed to be installed in `/usr/local/bin/` on the Raspberry Pi and made executable.

### Automated Installation

Use the provided installation script (recommended):

```bash
cd /home/runner/work/ipr-keyboard/ipr-keyboard
sudo cp scripts/rpi-debug/*.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/dbg_*.sh
```

### Manual Installation

```bash
# Copy each script
sudo cp scripts/rpi-debug/dbg_deploy.sh /usr/local/bin/
sudo cp scripts/rpi-debug/dbg_diag_bundle.sh /usr/local/bin/
sudo cp scripts/rpi-debug/dbg_pairing_capture.sh /usr/local/bin/
sudo cp scripts/rpi-debug/dbg_bt_restart.sh /usr/local/bin/
sudo cp scripts/rpi-debug/dbg_bt_soft_reset.sh /usr/local/bin/

# Make executable
sudo chmod +x /usr/local/bin/dbg_*.sh
```

### Create Log Directory

```bash
sudo mkdir -p /var/log/ipr
sudo chown root:adm /var/log/ipr
sudo chmod 2775 /var/log/ipr
```

---

## Sudoers Configuration

For secure remote execution, create a dedicated user with limited sudo privileges.

### Create Diagnostic User

```bash
# On Raspberry Pi
sudo adduser copilotdiag
sudo usermod -aG bluetooth,adm copilotdiag
```

### Configure SSH Key (on Windows PC)

```powershell
# Generate SSH key
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\copilotdiag_rpi -C "copilotdiag@rpi"

# Copy public key to Pi
type $env:USERPROFILE\.ssh\copilotdiag_rpi.pub | ssh pi@ipr-dev-pi4 "sudo -u copilotdiag mkdir -p ~/.ssh && sudo -u copilotdiag tee -a ~/.ssh/authorized_keys"
```

### Create Sudoers Whitelist

Create `/etc/sudoers.d/copilotdiag-ipr` on the Raspberry Pi:

```bash
sudo tee /etc/sudoers.d/copilotdiag-ipr >/dev/null <<'EOF'
copilotdiag ALL=(root) NOPASSWD: \
  /usr/local/bin/dbg_deploy.sh, \
  /usr/local/bin/dbg_diag_bundle.sh, \
  /usr/local/bin/dbg_pairing_capture.sh *, \
  /usr/local/bin/dbg_bt_restart.sh, \
  /usr/local/bin/dbg_bt_soft_reset.sh, \
  /usr/bin/systemctl restart bluetooth, \
  /usr/bin/systemctl restart bt_hid_ble.service, \
  /usr/bin/systemctl stop bt_hid_ble.service, \
  /usr/bin/systemctl start bt_hid_ble.service, \
  /usr/bin/journalctl -u bluetooth *, \
  /usr/bin/journalctl -u bt_hid_ble.service *, \
  /usr/bin/btmgmt *
EOF

# Validate sudoers file
sudo visudo -cf /etc/sudoers.d/copilotdiag-ipr
```

---

## GitHub Copilot Integration

### Copilot Documentation

The Copilot agent uses two key documentation files:

1. **`docs/copilot/DIAG_AGENT_PROMPT.md`** - Agent instructions and workflow
2. **`docs/copilot/BT_PAIRING_PLAYBOOK.md`** - Failure classification guide

### MCP Configuration

Create `.vscode/mcp.json` in your workspace (adjust paths as needed):

```json
{
  "servers": {
    "rpi-ssh": {
      "command": "node",
      "args": ["C:\\mcp\\ssh-mcp\\dist\\index.js"],
      "env": {
        "RPI_HOST": "ipr-dev-pi4",
        "RPI_USER": "copilotdiag",
        "RPI_KEY": "C:\\Users\\YourUsername\\.ssh\\copilotdiag_rpi"
      }
    }
  }
}
```

### Using Copilot for Diagnostics

**Step 1: Start diagnostic session**

In GitHub Copilot Chat, use this prompt:

```
Use docs/copilot/DIAG_AGENT_PROMPT.md and docs/copilot/BT_PAIRING_PLAYBOOK.md as the operating procedure. Start by producing Plan v1 only.
```

**Step 2: Copilot produces plan**

Copilot will generate a diagnostic plan (typically):
1. Run `dbg_diag_bundle.sh` to collect baseline diagnostics
2. Run `dbg_pairing_capture.sh 60` for bounded pairing capture
3. Classify failure mode from captured logs
4. Propose next steps or Plan v2

**Step 3: Approve execution**

Review the plan and approve execution. Copilot will run scripts via MCP SSH.

**Step 4: Attempt pairing**

When `dbg_pairing_capture.sh` is running, open Windows Bluetooth settings and attempt to pair with the Raspberry Pi device.

**Step 5: Review results**

Copilot analyzes `/var/log/ipr/latest/highlights.txt` and other captured logs to classify the failure mode.

**Step 6: Iterate or conclude**

- If issue is unclear, Copilot produces Plan v2 (max 3 iterations)
- If issue is identified, Copilot proposes code/config fixes

### Compact Prompt (Reusable)

For quick diagnostics:

```
Diagnose Windows↔RPi BLE HID pairing failure using the repo playbooks. Plan-first, max 3 iterations. Start with dbg_diag_bundle.sh then dbg_pairing_capture.sh 60.
```

---

## Troubleshooting

### Scripts not found
Ensure scripts are installed in `/usr/local/bin/` and are executable:
```bash
ls -la /usr/local/bin/dbg_*.sh
```

### Permission denied
Check sudoers configuration:
```bash
sudo visudo -cf /etc/sudoers.d/copilotdiag-ipr
```

### Log directory errors
Create log directory with correct permissions:
```bash
sudo mkdir -p /var/log/ipr
sudo chown root:adm /var/log/ipr
sudo chmod 2775 /var/log/ipr
```

### Service not found
Adjust service name in scripts if using different service:
```bash
# Edit SERVICE_BT variable in each script
sudo nano /usr/local/bin/dbg_diag_bundle.sh
```

### btmon timeout errors
If capture duration is too long:
```bash
# Use shorter duration
sudo /usr/local/bin/dbg_pairing_capture.sh 30
```

---

## Safety Considerations

### What these scripts DO:
- ✅ Collect read-only diagnostic information
- ✅ Restart services safely
- ✅ Power cycle Bluetooth controller
- ✅ Create bounded log captures with automatic timeouts

### What these scripts DO NOT do:
- ❌ Remove paired devices (bonds)
- ❌ Delete configuration files
- ❌ Modify system packages
- ❌ Change network settings
- ❌ Run indefinite captures

### Destructive Operations

For operations like bond removal, manual approval is required. These are NOT included in the automated scripts.

---

## See Also

- [Main README](../../README.md) - Project overview
- [Bluetooth Pairing Guide](../../BLUETOOTH_PAIRING.md) - Detailed pairing troubleshooting
- [Scripts Documentation](../README.md) - All project scripts
- [Copilot Instructions](../../.github/copilot-instructions.md) - Coding agent guidelines
