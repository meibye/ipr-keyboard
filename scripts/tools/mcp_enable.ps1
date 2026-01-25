# Enable SSH MCP server (manual run)
# VERSION: 2026/01/25 14:03:07

param(
  [Parameter(Mandatory=$false)]
  [ValidateSet("dev","prod")]
  [string]$Profile = "dev"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Runner = "D:\mcp\ssh-mcp\run_ssh_mcp.ps1"
if(!(Test-Path -LiteralPath $Runner)){
  throw "Missing runner: $Runner (run scripts\rpi-debug\tools\setup_ipr_mcp.ps1 first)"
}

Write-Host "[INFO] Starting SSH MCP runner (Profile=$Profile)..." -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File $Runner -Profile $Profile
