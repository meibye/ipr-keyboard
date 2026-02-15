# scripts/rpi-debug/tools/

Windows PowerShell helpers for MCP + remote diagnostics setup.

## Files

| File | Purpose |
|---|---|
| `dbg_common.ps1` | Shared settings and profile data for other PowerShell scripts |
| `setup_ipr_mcp.ps1` | Installs/configures SSH MCP server integration and profile wiring |
| `setup_pc_copilot_dbg.ps1` | Prepares Windows-side diagnostics workspace and docs |
| `gen_mcp_whitelist.ps1` | Builds script whitelist argument from allowed `dbg_*` scripts |

## Usage

Run these from PowerShell on the development PC. They are support tools for remote diagnostics, not runtime components on the Pi.
