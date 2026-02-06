# IPR Keyboard – MCP Setup (SSH, maintained MCP server)
# MCP server: @fangjunjie/ssh-mcp-server
# VERSION: 2026/02/04 19:23:20
#
# This script:
#  - Installs the maintained SSH-based MCP server locally
#  - Prepares SSH access to Raspberry Pi targets
#  - Creates .vscode/mcp.json for VS Code integration

param(
  [ValidateSet("dev","prod")]
  [string]$RpiProfile = "dev"
  [switch]$GenerateWhitelist = $false
)


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

Set-RpiProfile -ProfileName $RpiProfile

Write-Info "Selected RPI profile : $RpiProfile"
Write-Info "Target host          : $($Global:RpiHost)"
Write-Info "Target user          : $($Global:RpiUser)"
Write-Info "SSH key              : $($Global:KeyPath)"
Write-Host ""

# Use git to find the actual repo root
$RepoRoot = git -C $ScriptDir rev-parse --show-toplevel 2>$null
if (-not $RepoRoot) {
  throw "Could not determine repository root. Ensure this script is inside a git repository."
}
$RepoRoot = $RepoRoot.Trim()

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
  Write-Warn "Node.js or npm not found - installing Node.js LTS"
  winget install --id OpenJS.NodeJS.LTS -e `
    --accept-package-agreements `
    --accept-source-agreements | Out-Null
}

if(!(Test-Cmd ssh)){
  Write-Warn "OpenSSH client not found - enabling Windows capability"
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
# Transfer public key to RPI for Copilot diagnostics
# ------------------------------------------------------------------
$PubKeyPath = "$($Global:KeyPath).pub"
$TempPubKey = "$env:TEMP\copilot_pubkey.txt"
Copy-Item -Force $PubKeyPath $TempPubKey
Write-Info "Transferring public key to RPI for Copilot diagnostics..."
$scpCmd = "scp -i $($Global:KeyPath) $TempPubKey $($Global:RpiUser)@$($Global:RpiHost):/tmp/copilot_pubkey.txt"
Invoke-Expression $scpCmd
Write-Ok "Public key transferred to /tmp/copilot_pubkey.txt on RPI"
Write-Host ""
Write-Host "On the RPI, run:"
Write-Host "  export COPILOT_PUBKEY_FILE=/tmp/copilot_pubkey.txt" -ForegroundColor Yellow
Write-Host "  sudo ./provision/05_copilot_debug_tools.sh" -ForegroundColor Yellow
Write-Host "This will install the Copilot diagnostics SSH key automatically."
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
# VS Code MCP configuration
# ------------------------------------------------------------------
Write-Info "Creating VS Code MCP configuration..."

$vscodeDir = Join-Path $RepoRoot ".vscode"
New-Dir $vscodeDir

$mcpJson = Join-Path $vscodeDir "mcp.json"

@"
// -----------------------------------------------------------------------------
// mcp.json - MCP Remote Server Profile Configuration
//
// This file defines remote server profiles for the Model Context Protocol (MCP)
// integration in VS Code. It specifies SSH connection details, command arguments,
// and command blacklists for safe remote execution (e.g., for Copilot diagnostics).
//
// - Each profile includes host, port, username, and private key.
// - The blacklist prevents dangerous commands (rm, shutdown, reboot, etc).
// - Debug profiles may include extra arguments for troubleshooting.
//
// Edit with care. See project docs for details.
// -----------------------------------------------------------------------------

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
    },
    "ipr-rpi-dev-ssh-debug": {
      "command": "node",
      "args": [
        "D:\\mcp\\ssh-mcp\\node_modules\\@fangjunjie\\ssh-mcp-server\\build\\index.js",
        "--host", "ipr-dev-pi4",
        "--port", "22",
        "--username", "copilotdiag",
        "--privateKey", "~/.ssh/copilotdiag_rpi",
        "--blacklist", "^rm .*,^shutdown.*,^reboot.*"
      ],
      "dev": {
        "debug": { "type": "node" }
      }
    },
     "ipr-rpi-prod-ssh": {
      "command": "npx",
      "args": [
        "-y",
        "@fangjunjie/ssh-mcp-server",
        "--host", "ipr-prod-zero2",
        "--port", "22",
        "--username", "copilotdiag",
        "--privateKey", "~/.ssh/copilotdiag_rpi",
        "--blacklist", "^rm .*,^shutdown.*,^reboot.*"
      ]
    }
  }
}
"@ | Out-File -Encoding utf8 -Force $mcpJson


Write-Ok "VS Code MCP configuration written"
Write-Host ""

# ------------------------------------------------------------------
# Update MCP config with whitelist for allowed scripts
# ------------------------------------------------------------------
Write-Info "Whitelist generation enabled: $($GenerateWhitelist.IsPresent)"

if ($GenerateWhitelist) {
  Write-Info "Updating MCP config with whitelist for allowed scripts..."
  $Whitelist = & (Join-Path $ScriptDir 'gen_mcp_whitelist.ps1')
  Write-Info "Generated whitelist: $Whitelist"

  if (Test-Path $mcpJson) {
    $mcpObj = Get-Content $mcpJson -Raw | ConvertFrom-Json
    $servers = $mcpObj.servers
    foreach ($srv in $servers.PSObject.Properties) {
      $args = $srv.Value.args
      if ($args -is [System.Collections.IList]) {
        $isFangjunjie = $args -contains "@fangjunjie/ssh-mcp-server" -or ($args | Where-Object { $_ -like "*ssh-mcp-server*" })
        if ($isFangjunjie) {
          $hasWhitelist = $false
          for ($i=0; $i -lt $args.Count; $i++) {
            if ($args[$i] -eq "--whitelist") {
              $args[$i+1] = $Whitelist
              $hasWhitelist = $true
              break
            }
          }
          if (-not $hasWhitelist) {
            $args += "--whitelist"
            $args += $Whitelist
          }
          $srv.Value.args = $args
        }
      }
    }
    $mcpObj | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $mcpJson
    Write-Ok "MCP config updated with whitelist."
    Write-Host ""
  }
} else {
  Write-Info "Whitelist generation skipped (default)."
}

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
