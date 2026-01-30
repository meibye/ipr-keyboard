
# Import common environment
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
. "$ScriptDir\dbg_common.ps1"

$ErrorActionPreference = "Stop"

function New-DirectoryIfMissing($path) {
  if (-not (Test-Path $path)) {
    New-Item -ItemType Directory -Path $path | Out-Null
    Write-Host "Created directory: $path"
  } else {
    Write-Host "Directory already exists: $path"
  }
}


# Determine RepoRoot based on ScriptDir
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..") | Select-Object -ExpandProperty Path
$docsDir = Join-Path $RepoRoot "docs\copilot"
$vscodeDir = Join-Path $RepoRoot ".vscode"

New-DirectoryIfMissing $docsDir
New-DirectoryIfMissing $vscodeDir

# --- docs/copilot/DIAG_AGENT_PROMPT.md ---
$diagAgentPrompt = @"
# Diagnostic Agent Prompt — RPi Bluetooth Pairing (BLE HID)

## Mission
Diagnose and resolve Bluetooth pairing failures between Windows 11 host and Raspberry Pi BLE HID device.

## MCP execution environment (important)

Remote commands are executed through an **SSH-based MCP server**:

- MCP server package: `@fangjunjie/ssh-mcp-server`
- VS Code integration via `.vscode/mcp.json` (uses `npx` or `node` to launch the MCP server)
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
- Target profiles (from `.vscode/mcp.json`):
  - `dev`: `ipr-dev-pi4` (default)
  - `prod`: `ipr-prod-zero2`
- Diagnostics SSH user: `copilotdiag`
- MCP server launch: via `npx @fangjunjie/ssh-mcp-server` or `node` (see `.vscode/mcp.json`)
- Services:
  - BLE: `bt_hid_ble.service`
  - Agent: `bt_hid_agent_unified.service`
- Bluetooth controller: `hci0`
- Repo dir on Pi (automation clone): `/home/copilotdiag/ipr-keyboard`

## Start instruction
Begin by generating Diagnostic Plan v1 ONLY.
"@

Set-Content -Path (Join-Path $docsDir "DIAG_AGENT_PROMPT.md") -Value $diagAgentPrompt -Encoding UTF8

# --- docs/copilot/BT_PAIRING_PLAYBOOK.md ---
$playbook = @"
# Bluetooth Pairing Playbook (Windows 11 ↔ RPi BLE HID)

This playbook helps classify pairing failures and choose the next diagnostic action.

## Always start
1) Run `/usr/local/bin/dbg_diag_bundle.sh`
2) Run `/usr/local/bin/dbg_pairing_capture.sh 60` while user attempts pairing on Windows
3) Classify failure mode using the sections below

---

## Failure mode A — Pairing rejected / auth failure
Signals:
- Logs mention: "AuthenticationFailed", "Insufficient authentication", "Insufficient encryption"
- btmon shows pairing/encryption negotiation fails

Next actions:
1) Verify btmgmt settings: bondable, secure-conn, ssp, privacy
2) Confirm agent behavior: passkey confirmation / JustWorks mismatch
3) Ensure GATT characteristic security/permissions match Windows expectations
4) Re-test with capture

Likely fixes:
- Adjust security flags on characteristics
- Ensure BlueZ agent handles the pairing method Windows uses
- Ensure device is bondable + secure connections align with Windows

---

## Failure mode B — Pairs, then immediately disconnects
Signals:
- Windows shows paired briefly then fails
- btmon shows disconnect reason shortly after pairing

Next actions:
1) Confirm service stays up during pairing (systemd restart loops?)
2) Look for exceptions in bt_hid_ble service logs
3) Confirm advertising/connection parameters stable
4) Re-run capture with longer duration (90s)

Likely fixes:
- Fix crash in GATT callbacks
- Ensure characteristics exist as expected (Attribute Not Found errors)
- Ensure CCCD/notify subscription works

---

## Failure mode C — Pairing succeeds, but HID input never works
Signals:
- Windows says connected/paired
- No `StartNotify` in service logs
- Notify works on other devices but not Windows

Next actions:
1) Verify Report Map, Report Reference descriptors, CCCD behavior
2) Confirm notify property and permissions for Input Report characteristic
3) Confirm correct HID service UUID and characteristic UUIDs

Likely fixes:
- Correct characteristic flags (read/notify + security)
- Ensure CCCD is present and handled correctly
- Ensure report IDs/types match HID over GATT expectations

---

## Failure mode D — Windows can't discover / can't see device
Signals:
- Not visible in scan
- Advertising not active, or device name missing

Next actions:
1) btmgmt advertising status and LE settings
2) bluetoothd running and not blocked by rfkill
3) verify adapter powered + discoverable

Likely fixes:
- fix advertising setup, local name, intervals
- ensure no conflicting services own the adapter

---

## Safe recovery ladder (increasing impact)
1) `/usr/local/bin/dbg_bt_restart.sh`
2) `/usr/local/bin/dbg_bt_soft_reset.sh`
3) (ONLY with approval) bond wipe on Pi and Windows + re-pair

Stop after 3 iterations: deliver most likely cause + recommended code/config change.
"@

Set-Content -Path (Join-Path $docsDir "BT_PAIRING_PLAYBOOK.md") -Value $playbook -Encoding UTF8

# --- docs/copilot/LOCAL_ONLY_PROMPT.md ---
$localOnly = @"
## Local-only Copilot Mode

Constraints:
- Do not use MCP (as defined in `.vscode/mcp.json`, which launches via `npx` or `node`)
- Do not execute commands
- Do not propose SSH or remote actions
- Do not use or reference any remote diagnostic scripts or profiles
- Base all reasoning on repository files and chat context only

**Usage Instruction Update:**
This prompt should always be used in local-only Copilot mode; the mode does not change based on the prompt. Actions involving the Raspberry Pi (RPI) through the MCP (as configured in `.vscode/mcp.json`) or any remote scripts are only executed when it is explicitly stated in the prompt that actions should be conducted on the RPI. Otherwise, all actions are performed locally and not on the RPI.
"@
Set-Content -Path (Join-Path $docsDir "LOCAL_ONLY_PROMPT.md") -Value $localOnly -Encoding UTF8

# --- .vscode/mcp.json (template) ---
# This is a template. Adjust to your chosen SSH MCP server's required config.
$mcpJson = @"
{
  "servers": {
    "ipr-rpi-dev-ssh": {
      "command": "npx",
      "args": [
        "-y",
        "@fangjunjie/ssh-mcp-server",
        "--host", "ipr-dev-pi4",
        "--port", "22",
        "--username", "copilotdiag",
        "--privateKey", "~/.ssh/copilotdiag_rpi",
        "--blacklist", "^rm .*,^shutdown.*,^reboot.*"
      ]
    }
}
"@
Set-Content -Path (Join-Path $vscodeDir "mcp.json") -Value $mcpJson -Encoding UTF8

Write-Host "Generated:"
Write-Host " - docs/copilot/DIAG_AGENT_PROMPT.md"
Write-Host " - docs/copilot/BT_PAIRING_PLAYBOOK.md"
Write-Host " - docs/copilot/LOCAL_ONLY_PROMPT.md"
Write-Host " - .vscode/mcp.json (template)"
