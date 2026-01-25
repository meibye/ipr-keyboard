# MCP SSH runner – maintained MCP server
# Uses: @fangjunjie/ssh-mcp-server
# VERSION: 2026/01/25 14:19:21
#
# This script is copied verbatim by setup_ipr_mcp.ps1 into:
#   D:\mcp\ssh-mcp\run_ssh_mcp.ps1
#
# It is intentionally kept standalone for easy correction.

param(
  [ValidateSet("dev","prod")]
  [string]$Profile = "dev"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Allow environment override (useful for VS Code MCP)
if($env:RPI_PROFILE){
  $Profile = $env:RPI_PROFILE
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

if(-not $Targets.ContainsKey($Profile)){
  throw "Unknown RPI profile: $Profile"
}

$t = $Targets[$Profile]

# ---- Launch MCP server ----
Push-Location "D:\mcp\ssh-mcp"
try {
  & npx.cmd @fangjunjie/ssh-mcp-server `
    --host     $t.host `
    --user     $t.user `
    --identity $t.key
}
finally {
  Pop-Location
}
