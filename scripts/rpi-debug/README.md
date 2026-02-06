# IPR Keyboard – Remote Diagnostic & Recovery SOP (scripts/rpi-debug)


This directory contains the **diagnostic and recovery scripts** for safe, auditable troubleshooting of Bluetooth HID pairing and stack issues on Raspberry Pi. These tools are designed for both manual and **remote execution via GitHub Copilot (MCP agent mode)**, enabling bounded, repeatable diagnostics and recovery with minimal risk.

**IMPORTANT:** When executing these scripts via the MCP server, use the names as installed in `/usr/local/bin/` (e.g., `dbg_stack_status.sh`, `dbg_bt_restart.sh`). Do **not** use the `scripts/rpi-debug/` path. The MCP server only allows execution of whitelisted scripts by their installed names.


## Script Overview

### Top-level diagnostic scripts (installed to /usr/local/bin on the Pi):

- **dbg_stack_status.sh** — Fast health check of the full Bluetooth stack
- **dbg_diag_bundle.sh** — Collects a full system/service/log snapshot for diagnostics
- **dbg_pairing_capture.sh <seconds>** — Captures a bounded pairing session (btmon + journals)
- **dbg_bt_restart.sh** — Safely restarts the Bluetooth stack and related services
- **dbg_bt_soft_reset.sh** — Performs a conservative Bluetooth adapter reset
- **dbg_bt_bond_wipe.sh <MAC>** — (Destructive) Removes a specific Bluetooth bond (explicit confirmation required)
- **dbg_deploy.sh** — Updates the automation clone and restarts services

All these scripts are designed to be called directly or via the MCP server for remote diagnostics. Only these are allowed in the Copilot MCP server whitelist.

**When using the MCP server, always invoke scripts by their installed name (e.g., `dbg_stack_status.sh`), not by their path in this directory.**

### Tools subfolder (scripts/rpi-debug/tools)

This folder contains PowerShell scripts for Windows-side setup, configuration, and integration with the Copilot/MCP remote diagnostic workflow:

- **dbg_common.ps1** — Shared environment/configuration for all PowerShell scripts in this folder
  - **setup_ipr_mcp.ps1** — Installs prerequisites, prepares SSH access, generates SSH keys, writes `.vscode/mcp.json`, and calls `gen_mcp_whitelist.ps1` to update the MCP server whitelist for allowed scripts
- **setup_pc_copilot_dbg.ps1** — Prepares the Windows PC for Copilot diagnostics (directories, config, docs)
- **gen_mcp_whitelist.ps1** — Scans the `scripts/rpi-debug` folder for all allowed diagnostic scripts and generates a comma-separated whitelist string for use as the `--whitelist` argument in MCP server configuration

All PowerShell scripts import `dbg_common.ps1` for shared values (hostnames, repo paths, service names, etc.).

---

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
┌──────────────────────────────────────────▼──────────────────────────┐
│                    Raspberry Pi 4 Target                            │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Diagnostic Scripts (/usr/local/bin/)                      │     │
│  │                                                            │     │
│  │  • dbg_deploy.sh          - Deploy & restart service       │     │
│  │  • dbg_diag_bundle.sh     - System diagnostics             │     │
│  │  • dbg_pairing_capture.sh - Capture pairing sessions       │     │
│  │  • dbg_bt_restart.sh      - Safe Bluetooth service restart │     │
│  │  • dbg_bt_soft_reset.sh   - Conservative BT reset          │     │
│  └────────────────────────────────────────────────────────────┘     │
│                            │                                        │
│                            ▼                                        │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Diagnostic Output (/var/log/ipr/)                         │     │
│  │                                                            │     │
│  │  • pairing_TIMESTAMP/ - Captured pairing sessions          │     │
│  │    - btmon.txt                                             │     │
│  │    - journal_bluetooth.txt                                 │     │
│  │    - journal_service.txt                                   │     │
│  │    - snapshot_before.txt                                   │     │
│  │    - snapshot_after.txt                                    │     │
│  │    - highlights.txt                                        │     │
│  │  • latest -> (symlink to most recent capture)              │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
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

**Local:**
```bash
sudo ./dbg_stack_status.sh
```

**Remote (MCP):**
```
dbg_stack_status.sh
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


## 10. Updating or Adding Diagnostic Scripts

**To update:**
1. Edit `scripts/rpi-debug/dbg_<name>.sh` (for Pi-side diagnostics) or `scripts/rpi-debug/tools/*.ps1` (for Windows-side setup)
2. Ensure `/etc/ipr_dbg.env` is sourced and output is bounded (for Pi-side scripts)
3. Commit and push
4. On RPi: `sudo scripts/rpi-debug/install_dbg_tools.sh`

**To add:**
1. Create new script under `scripts/rpi-debug/` (for Pi) or `scripts/rpi-debug/tools/` (for Windows)
2. For Pi-side scripts, update `install_dbg_tools.sh` (install + sudoers)
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
