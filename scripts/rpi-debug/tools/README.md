
# Diagnostic PowerShell Scripts for Copilot/MCP (tools)

This folder contains PowerShell scripts for Windows-side diagnostics, setup, and integration with the Copilot/MCP remote troubleshooting workflow. All scripts import a shared environment file for configuration values.

## Common Environment

- All scripts import `dbg_common.ps1` for shared values (hostnames, repo paths, service names, etc.).
- Example usage:
  ```powershell
  $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
  . "$ScriptDir\dbg_common.ps1"
  ```

## Scripts Overview

- **dbg_common.ps1**
  - Shared environment and configuration for all scripts in this folder.
  - Defines repo paths, MCP directories, RPi host/user, SSH key, and service names.

- **setup_ipr_mcp.ps1**
  - Installs prerequisites and sets up the SSH MCP server locally under `D:\mcp\ssh-mcp`.
  - Preconfigured for repo path, RPi hostname, and diagnostics user.
  - Generates SSH keys and writes MCP config files for Copilot integration.
  - Calls `gen_mcp_whitelist.ps1` to generate a whitelist of allowed scripts and updates `.vscode/mcp.json` accordingly.

- **setup_pc_copilot_dbg.ps1**
  - Prepares the Windows PC for Copilot diagnostics.
  - Creates required directories, config files, and documentation for Copilot agent use.
  - Uses shared environment variables for all configuration.

- **gen_mcp_whitelist.ps1**
  - Scans the `scripts/rpi-debug` folder for all allowed diagnostic scripts.
  - Generates a comma-separated whitelist string for use as the `--whitelist` argument in MCP server configuration.

## Usage

Run each script from PowerShell, ensuring you have the required permissions. Scripts will automatically use the shared configuration from `dbg_common.ps1`.

## See Also
- [../README.md](../README.md) – Main diagnostic SOP and architecture
- [../../README.md](../../README.md) – Project overview
