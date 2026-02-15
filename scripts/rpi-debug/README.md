# scripts/rpi-debug/

Remote diagnostics toolkit for Raspberry Pi operations (local and MCP-driven usage).

## Files in This Directory

| File | Purpose |
|---|---|
| `install_dbg_tools.sh` | Installs `dbg_*` scripts to `/usr/local/bin`, writes `/etc/ipr_dbg.env`, configures sudoers whitelist |
| `dbg_common.env` | Shared environment defaults for `dbg_*` scripts |
| `dbg_stack_status.sh` | Quick stack/service health snapshot |
| `dbg_diag_bundle.sh` | Collects bounded diagnostic bundle |
| `dbg_pairing_capture.sh` | Captures bounded pairing window artifacts |
| `dbg_bt_restart.sh` | Ordered Bluetooth stack restart |
| `dbg_bt_soft_reset.sh` | Adapter-level soft reset path |
| `dbg_bt_bond_wipe.sh` | Destructive bond removal helper |
| `dbg_deploy.sh` | Updates automation clone and restarts services |
| `dbg_sudoers_list.txt` | Installed whitelist entries |
| `tools/*` | Windows PowerShell MCP setup helpers |

## Installed Runtime Command Names

After installation via `install_dbg_tools.sh`, run:
- `dbg_stack_status.sh`
- `dbg_diag_bundle.sh`
- `dbg_pairing_capture.sh <seconds>`
- `dbg_bt_restart.sh`
- `dbg_bt_soft_reset.sh`
- `dbg_bt_bond_wipe.sh <MAC>`
- `dbg_deploy.sh`

## Safety

Treat `dbg_bt_bond_wipe.sh` as destructive and approval-gated in automated workflows.
