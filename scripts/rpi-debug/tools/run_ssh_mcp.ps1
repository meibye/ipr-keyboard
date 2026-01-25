# MCP SSH runner – maintained MCP server
# Uses: @fangjunjie/ssh-mcp-server
# VERSION: 2026/01/25 19:25:16
#
# This script is copied verbatim by setup_ipr_mcp.ps1 into:
#   D:\mcp\ssh-mcp\run_ssh_mcp.ps1
#
# It is intentionally kept standalone for easy correction.

param(
  [ValidateSet("dev","prod")]
  [string]$RpiProfile = "dev",
  [string]$Blacklist
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
    $argsList += @("--blacklist", $Blacklist)
  }
  & npx.cmd @fangjunjie/ssh-mcp-server @argsList
}
finally {
  Pop-Location
}
