# Diagnostic PowerShell Scripts for Copilot/MCP (tools)

This folder contains PowerShell scripts used for Windows-side diagnostics, setup, and integration with the Copilot/MCP remote troubleshooting workflow. All scripts import a shared environment file for configuration values.

## Common Environment

- All scripts import `dbg_common.ps1` for shared values (hostnames, repo paths, service names, etc.).
- Example usage:
  ```powershell
  $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
  . "$ScriptDir\dbg_common.ps1"
  ```

## Scripts Overview

- **setup_ipr_mcp.ps1**
  - Installs prerequisites and sets up the SSH MCP server locally under `D:\mcp\ssh-mcp`.
  - Preconfigured for repo path, RPi hostname, and diagnostics user.
  - Generates SSH keys and writes MCP config files for Copilot integration.

- **setup_pc_copilot_dbg.ps1**
  - Prepares the Windows PC for Copilot diagnostics.
  - Creates required directories, config files, and documentation for Copilot agent use.
  - Uses shared environment variables for all configuration.

## Usage

Run each script from PowerShell, ensuring you have the required permissions. Scripts will automatically use the shared configuration from `dbg_common.ps1`.

## See Also
- [../README.md](../README.md) – Main diagnostic SOP and architecture
- [../../README.md](../../README.md) – Project overview
