# IPR Keyboard – MCP Setup (SSH, maintained MCP server)
# MCP server: @fangjunjie/ssh-mcp-server
# VERSION: 2026-01-25
#
# This script:
#  - Installs the maintained SSH-based MCP server locally
#  - Prepares SSH access to Raspberry Pi targets
#  - Copies a canonical MCP runner script
#  - Creates .vscode/mcp.json for VS Code integration

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " IPR Keyboard - MCP Setup (SSH)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------------
# Import shared environment
# ------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
. "$ScriptDir\dbg_common.ps1"

param(
  [ValidateSet("dev","prod")]
  [string]$Profile = "dev"
)

Set-RpiProfile -ProfileName $Profile

Write-Info "Selected RPI profile : $Profile"
Write-Info "Target host          : $($Global:RpiHost)"
Write-Info "Target user          : $($Global:RpiUser)"
Write-Info "SSH key              : $($Global:KeyPath)"
Write-Host ""

$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..") |
  Select-Object -ExpandProperty Path

$McpPackage = "@fangjunjie/ssh-mcp-server"

# ------------------------------------------------------------------
# Ensure MCP directories
# ------------------------------------------------------------------
Write-Info "Preparing MCP directory layout..."
Write-Info "  MCP root : $($Global:McpRoot)"
Write-Info "  MCP home : $($Global:McpHome)"

New-Dir $Global:McpRoot
New-Dir $Global:McpHome

Write-Ok "MCP directories ready"
Write-Host ""

# ------------------------------------------------------------------
# Prerequisites
# ------------------------------------------------------------------
Write-Info "Checking prerequisites (Node.js, npm, OpenSSH)..."

if(!(Test-Cmd node) -or !(Test-Cmd npm)){
  Write-Warn "Node.js or npm not found – installing Node.js LTS"
  winget install --id OpenJS.NodeJS.LTS -e `
    --accept-package-agreements `
    --accept-source-agreements | Out-Null
}

if(!(Test-Cmd ssh)){
  Write-Warn "OpenSSH client not found – enabling Windows capability"
  $cap = Get-WindowsCapability -Online |
    Where-Object Name -like "OpenSSH.Client*"
  if($cap.State -ne "Installed"){
    Add-WindowsCapability -Online -Name $cap.Name | Out-Null
  }
}

Write-Ok "Prerequisites satisfied"
Write-Host ""

# ------------------------------------------------------------------
# SSH key
# ------------------------------------------------------------------
Write-Info "Ensuring SSH key exists..."

New-Dir (Split-Path $Global:KeyPath)

if(!(Test-Path $Global:KeyPath)){
  Write-Info "Generating new SSH key (ed25519)"
  ssh-keygen -t ed25519 -f $Global:KeyPath -N "" | Out-Null
  Write-Ok "SSH key generated"
}else{
  Write-Ok "SSH key already present"
}

Write-Host ""

# ------------------------------------------------------------------
# Install MCP server locally
# ------------------------------------------------------------------
Write-Info "Installing MCP server package"
Write-Info "  npm package : $McpPackage"
Write-Info "  install dir : $($Global:McpHome)"

Push-Location $Global:McpHome

if(!(Test-Path "package.json")){
  Write-Info "Initializing local npm project"
  npm init -y | Out-Null
}

npm install --save-exact $McpPackage | Out-Null

if(!(Test-Path "node_modules\@fangjunjie\ssh-mcp-server")){
  throw "MCP server installation failed"
}

Pop-Location

Write-Ok "MCP server installed successfully"
Write-Host ""

# ------------------------------------------------------------------
# Copy MCP runner (external canonical file)
# ------------------------------------------------------------------
Write-Info "Deploying MCP runner script..."

$SourceRunner = Join-Path $ScriptDir "run_ssh_mcp.ps1"
$TargetRunner = Join-Path $Global:McpHome "run_ssh_mcp.ps1"

Write-Info "  Source : $SourceRunner"
Write-Info "  Target : $TargetRunner"

if(!(Test-Path $SourceRunner)){
  throw "Missing MCP runner template: $SourceRunner"
}

Copy-Item -Force $SourceRunner $TargetRunner

Write-Ok "MCP runner deployed"
Write-Host ""

# ------------------------------------------------------------------
# VS Code MCP configuration
# ------------------------------------------------------------------
Write-Info "Creating VS Code MCP configuration..."

$vscodeDir = Join-Path $RepoRoot ".vscode"
New-Dir $vscodeDir

$mcpJson = Join-Path $vscodeDir "mcp.json"

@"
{
  "servers": {
    "ipr-rpi-dev-ssh": {
      "command": "powershell",
      "args": [
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "D:\\\\mcp\\\\ssh-mcp\\\\run_ssh_mcp.ps1",
        "-Profile", "dev"
      ]
    },
    "ipr-rpi-prod-ssh": {
      "command": "powershell",
      "args": [
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "D:\\\\mcp\\\\ssh-mcp\\\\run_ssh_mcp.ps1",
        "-Profile", "prod"
      ]
    }
  }
}
"@ | Out-File -Encoding utf8 -Force $mcpJson

Write-Ok "VS Code MCP configuration written"
Write-Host ""

# ------------------------------------------------------------------
# Connectivity test
# ------------------------------------------------------------------
Write-Info "Performing SSH connectivity test..."
ssh -i $Global:KeyPath "$($Global:RpiUser)@$($Global:RpiHost)" "echo MCP_OK" | Out-Null
Write-Ok "SSH connectivity verified"
Write-Host ""

# ------------------------------------------------------------------
# Final operator guidance
# ------------------------------------------------------------------
Write-Host "============================================================" -ForegroundColor Green
Write-Host " MCP setup completed successfully" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Ensure the SSH public key is installed on the Pi"
Write-Host "  2. Open this repo in VS Code"
Write-Host "  3. Run 'MCP: Restart Servers' from the Command Palette"
Write-Host "  4. Use Copilot Chat / Agent with MCP-enabled diagnostics"
Write-Host ""
