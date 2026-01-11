
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

# IPR Keyboard – Remote Diagnostic & Recovery SOP (scripts/rpi-debug)

This directory contains the **diagnostic and recovery scripts** for safe, auditable troubleshooting of Bluetooth HID pairing and stack issues on Raspberry Pi. These tools are designed for both manual and **remote execution via GitHub Copilot (MCP agent mode)**, enabling bounded, repeatable diagnostics and recovery with minimal risk.

---

## 1. System Overview

The Bluetooth stack is managed as a coordinated unit:

1. `bluetooth` (BlueZ daemon)
2. `bt_hid_agent_unified.service` (pairing/auth agent)
3. `bt_hid_ble.service` (BLE HID backend)

All diagnostics and restarts operate on the full stack, not individual services.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Windows 11 Development PC                    │
│                                                                 │
│  ┌──────────────┐         ┌─────────────────────────────────┐   │
│  │   VS Code    │────────>│  GitHub Copilot Chat Agent      │   │
│  │              │         │  (uses MCP SSH server)          │   │
│  └──────────────┘         └──────────────┬──────────────────┘   │
│                                          │                      │
└──────────────────────────────────────────┼──────────────────────┘
                                           │ SSH over MCP
                                           │
┌──────────────────────────────────────────▼──────────────────────┐
│                    Raspberry Pi 4 Target                        │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Diagnostic Scripts (/usr/local/bin/)                   │    │
│  │                                                         │    │
│  │  • dbg_deploy.sh          - Deploy & restart service    │    │
│  │  • dbg_diag_bundle.sh     - System diagnostics          │    │
│  │  • dbg_pairing_capture.sh - Capture pairing sessions    │    │
│  │  • dbg_bt_restart.sh      - Safe Bluetooth service restart        │    │
│  │  • dbg_bt_soft_reset.sh   - Conservative BT reset       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Diagnostic Output (/var/log/ipr/)                      │    │
│  │                                                         │    │
│  │  • pairing_TIMESTAMP/ - Captured pairing sessions       │    │
│  │    - btmon.txt                                          │    │
│  │    - journal_bluetooth.txt                              │    │
│  │    - journal_service.txt                                │    │
│  │    - snapshot_before.txt                                │    │
│  │    - snapshot_after.txt                                 │    │
│  │    - highlights.txt                                     │    │
│  │  • latest -> (symlink to most recent capture)           │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Prerequisites

- Raspberry Pi OS with systemd
- Bluetooth adapter available as `hci0`
- Repo cloned for the application user (e.g. `meibye`)
- `/opt/ipr_common.env` created from `provision/common.env.example`
- SSH access enabled

---

## 3. Copilot / MCP Debug Tooling (RPi)

To enable **remote diagnostics via Copilot Agent mode**:

```bash
sudo ./provision/05_copilot_debug_tools.sh
```

This will:
- Create a diagnostics user (e.g. `copilotdiag`)
- Create a separate automation clone
- Install all `dbg_*` tools into `/usr/local/bin`
- Write `/etc/ipr_dbg.env`
- Configure a strict sudoers whitelist (only `dbg_*` scripts allowed)

---

## 4. Windows 11 – Prerequisites (PC)

- Windows 11
- Visual Studio Code with GitHub Copilot enabled
- Node.js LTS, Git, OpenSSH Client
- Repo cloned locally
- MCP server/tooling under `D:\mcp`

---

## 5. MCP Installation (PC)

Run the provided PowerShell installer as Administrator:

```powershell
D:\mcp\setup_ipr_mcp.ps1
```

This ensures all prerequisites, generates SSH keys, and writes `.vscode/mcp.json` for Copilot MCP integration.

---

## 6. Diagnostic Tooling Overview

| Script                         | Purpose                                              |
| ------------------------------ | ---------------------------------------------------- |
| `dbg_stack_status.sh`          | Fast health check of the full BT stack               |
| `dbg_diag_bundle.sh`           | Snapshot of system + services + logs                 |
| `dbg_pairing_capture.sh <sec>` | Bounded btmon + journals during pairing              |
| `dbg_bt_restart.sh`            | Safe stack restart                                   |
| `dbg_bt_soft_reset.sh`         | Adapter power cycle + restart                        |
| `dbg_bt_bond_wipe.sh <MAC>`    | **Destructive** bond removal (explicit confirmation) |
| `dbg_deploy.sh`                | Update automation clone + restart services           |

---

## 7. Recommended Diagnostic Workflow

### Step 1 – Stack health

```bash
sudo dbg_stack_status.sh
```

### Step 2 – Capture pairing attempt

```bash
sudo dbg_pairing_capture.sh 60
```

Initiate pairing from Windows during the capture window. Inspect:
- `/var/log/ipr/latest/highlights.txt`
- `journal_agent.txt`, `journal_ble.txt`, `btmon.txt`

---

## 8. Recovery Ladder

**Level 1 – Safe restart**

```bash
sudo dbg_bt_restart.sh
```

**Level 2 – Soft adapter reset**

```bash
sudo dbg_bt_soft_reset.sh
```

**Level 3 – Destructive bond wipe (last resort)**

```bash
sudo dbg_bt_bond_wipe.sh AA:BB:CC:DD:EE:FF
```

Requires explicit MAC, double confirmation, and logs to `/var/log/ipr/latest_bondwipe`.

---

## 9. Copilot Usage Guidance

**Without MCP:**
- Use Copilot for analysis only; run commands manually via SSH

**With MCP (Agent mode):**
- Allow Copilot to execute only `dbg_*` scripts
- Prefer plan-first prompts
- Avoid arbitrary sudo commands

---

## 10. Updating or Adding dbg_* Scripts

**To update:**
1. Edit `scripts/rpi-debug/dbg_<name>.sh`
2. Ensure `/etc/ipr_dbg.env` is sourced and output is bounded
3. Commit and push
4. On RPi: `sudo scripts/rpi-debug/install_dbg_tools.sh`

**To add:**
1. Create new script under `scripts/rpi-debug/`
2. Update `install_dbg_tools.sh` (install + sudoers)
3. Commit and push
4. Re-run installer on RPi

---

## 11. Safety Principles

- Never hard-reset the human/dev repo
- Never wipe bonds without confirmation
- Always restart services in this order:
  1. Stop BLE
  2. Stop Agent
  3. Restart bluetooth
  4. Start Agent
  5. Start BLE
- Keep Copilot execution bounded and auditable

---

## See Also

- [Main README](../../README.md) – Project overview
- [Bluetooth Pairing Guide](../../BLUETOOTH_PAIRING.md) – Troubleshooting
- [Scripts Documentation](../README.md) – All project scripts
- [Copilot Instructions](../../.github/copilot-instructions.md) – Coding agent guidelines

---

## Common Environment Scripts

To ensure consistency and maintainability, all diagnostic scripts in this folder use a shared environment file for configuration variables:

- **Bash scripts** (scripts/rpi-debug/*.sh):
  - Source `dbg_common.env` for shared values such as service names, log paths, and user/repo info.
  - Example usage:
    ```bash
    SCRIPT_DIR="$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)"
    source "$SCRIPT_DIR/dbg_common.env"
    ```

- **PowerShell scripts** (scripts/rpi-debug/tools/*.ps1):
  - Import `dbg_common.ps1` for shared values (hostnames, repo paths, service names, etc.).
  - Example usage:
    ```powershell
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
    . "$ScriptDir\dbg_common.ps1"
    ```

This approach ensures all scripts use the same configuration, making updates and cross-platform diagnostics easier to manage.
