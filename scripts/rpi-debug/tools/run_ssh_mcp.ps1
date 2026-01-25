# MCP SSH runner – maintained MCP server
# Uses: @fangjunjie/ssh-mcp-server
# VERSION: 2026/01/25 19:48:26
#
# This script is copied verbatim by setup_ipr_mcp.ps1 into:
#   D:\mcp\ssh-mcp\run_ssh_mcp.ps1
#
# It is intentionally kept standalone for easy correction.

param(
  [ValidateSet("dev","prod")]
  [string]$RpiProfile = "dev",
  [string]$Blacklist,
  [string]$Whitelist
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Allow environment override (useful for VS Code MCP)
if($env:RPI_PROFILE){
  $RpiProfile = $env:RPI_PROFILE
}

# ---- Static targets (authoritative) ----
$Targets = @{
  dev = @{
    host = "ipr-dev-pi4"
    user = "copilotdiag"
    key  = "$env:USERPROFILE\.ssh\copilotdiag_rpi"
  }
  prod = @{
    host = "ipr-prod-zero2"
    user = "copilotdiag"
    key  = "$env:USERPROFILE\.ssh\copilotdiag_rpi"
  }
}

if(-not $Targets.ContainsKey($RpiProfile)){
  throw "Unknown RPI profile: $RpiProfile"
}

$t = $Targets[$RpiProfile]

# ---- Launch MCP server ----
Push-Location "D:\mcp\ssh-mcp"
try {
  $argsList = @(
    '--host',       $t.host,
    '--port',       '22',
    '--username',   $t.user,
    '--privateKey', $t.key
  )

  if ($Blacklist) {
    $argsList += @('--blacklist', $Blacklist)
  }

  # If Whitelist is not provided, try to read from allowlist file
  if (-not $Whitelist) {
    $allowlistPath = Join-Path $PSScriptRoot '..\..\..\.vscode\mcp_allowlist.txt'
    if (Test-Path $allowlistPath) {
      $allowlistLines = Get-Content $allowlistPath | Where-Object { $_ -and -not ($_ -match '^#') }
      if ($allowlistLines.Count -gt 0) {
        $Whitelist = $allowlistLines -join ','
      }
    }
  }
  if ($Whitelist) {
    $argsList += @('--whitelist', $Whitelist)
  }
  & npx.cmd @fangjunjie/ssh-mcp-server @argsList
}
finally {
  Pop-Location
}
