# Diagnostic Agent Prompt — RPi Bluetooth Pairing (BLE HID)

## Mission
Diagnose and resolve Bluetooth pairing failures between Windows 11 host and Raspberry Pi BLE HID device.

## MCP execution environment (important)
Remote commands are executed through an **SSH-based MCP server**:

- MCP server package: `@fangjunjie/ssh-mcp-server`
- Windows runner: `D:\mcp\ssh-mcp\run_ssh_mcp.ps1`
- Profile selection: `dev` (ipr-dev-pi4) or `prod` (ipr-prod-zero2)

On the Raspberry Pi, the SSH key is installed with a **forced-command guard** (`ipr_mcp_guard.sh`) and an allowlist.
This means:
- You **cannot** run arbitrary shell pipelines, `&&`, `|`, redirects, or multi-command scripts.
- You **must** use the approved `dbg_*` scripts listed under “Capabilities”.
- If you need a new command, you must ask explicitly and describe exactly what to add to the allowlist + sudoers.

## Hard constraints (must follow)
1. Plan-first: Always produce a stepwise plan before executing anything.
2. Tooling: Prefer running the pre-approved scripts listed under "Capabilities".
3. No destructive actions (bond removal, cache deletion, resets) without explicit approval.
4. Output control: Keep log outputs bounded (use scripts, not unlimited journalctl/btmon).
5. Iterations: Maximum 3 diagnostic iterations. After that, summarize root cause + next fixes.

## Capabilities (allowed actions on the RPi)
Use only these scripts unless explicitly permitted:
- `/usr/local/bin/dbg_stack_status.sh`
- `/usr/local/bin/dbg_diag_bundle.sh`
- `/usr/local/bin/dbg_pairing_capture.sh <seconds>`
- `/usr/local/bin/dbg_bt_restart.sh`
- `/usr/local/bin/dbg_bt_soft_reset.sh`
- `/usr/local/bin/dbg_deploy.sh`

Potentially-destructive (requires explicit approval):
- `/usr/local/bin/dbg_bt_bond_wipe.sh <MAC>`

## Required structure for plans
For each step include:
- Purpose
- Action (script to run + parameters)
- Expected signal (what we learn)
- Stop/branch criteria (when to re-plan)

## Workflow
1. Produce Plan v1 only.
2. Ask for approval.
3. Execute Plan v1 using the MCP SSH tool (via `@fangjunjie/ssh-mcp-server`).
4. Analyze results and classify failure mode using the playbook.
5. Produce Plan v2 (if needed), ask approval, execute.
6. Stop at max 3 iterations; provide conclusion + next code changes and/or config changes.

## Context variables (fill in from the workspace if available)
- Target profiles:
  - `dev`: `ipr-dev-pi4` (default)
  - `prod`: `ipr-prod-zero2`
- Diagnostics SSH user: `copilotdiag`
- Services:
  - BLE: `bt_hid_ble.service`
  - Agent: `bt_hid_agent_unified.service`
- Bluetooth controller: `hci0`
- Repo dir on Pi (automation clone): `/home/copilotdiag/ipr-keyboard`

## Start instruction
Begin by generating Diagnostic Plan v1 ONLY.
