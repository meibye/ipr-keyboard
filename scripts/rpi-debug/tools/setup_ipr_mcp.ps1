# IPR Keyboard – Windows MCP Setup Script
# Installs prerequisites + installs the SSH MCP server locally under D:\mcp\ssh-mcp
# Preconfigured for:
#   Repo: D:\Dev\ipr_keyboard
#   RPi : ipr-dev-pi4
#   User: copilotdiag

$ErrorActionPreference = "Stop"

# -----------------------------
# Fixed defaults (per your request)
# -----------------------------

# Import common environment
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
. "$ScriptDir\dbg_common.ps1"

# MCP server package (installed locally in $McpHome)
$McpNpmPackage = "ssh-mcp"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){   Write-Host "[ OK ] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }

function New-Dir($p){
  if(!(Test-Path -LiteralPath $p)){
    New-Item -ItemType Directory -Path $p | Out-Null
  }
}

function Test-Cmd($name){
  return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Install-WingetPackage($id){
  if(!(Test-Cmd "winget")){
    Warn "winget not found. Please install '$id' manually."
    return
  }
  Info "Installing: $id"
  winget install --id $id -e --accept-package-agreements --accept-source-agreements | Out-Null
}

# -----------------------------
# Validate repo path
# -----------------------------
if(!(Test-Path -LiteralPath $RepoPath)){
  throw "RepoPath does not exist: $RepoPath"
}

# -----------------------------
# Ensure folders
# -----------------------------
Info "Ensuring MCP folder layout..."
New-Dir $McpRoot
New-Dir $McpHome
Ok "Folders ready: $McpHome"

# -----------------------------
# Install prerequisites
# -----------------------------
Info "Ensuring prerequisites..."

# Node.js LTS (provides node + npm)
if(!(Test-Cmd "node") -or !(Test-Cmd "npm")){
  Install-WingetPackage "OpenJS.NodeJS.LTS"
}
if(Test-Cmd "node"){ Ok ("Node: " + (& node -v)) } else { Warn "node not found after install attempt." }
if(Test-Cmd "npm"){  Ok ("npm : " + (& npm -v)) }  else { Warn "npm not found after install attempt." }

# Git (optional but useful)
if(!(Test-Cmd "git")){
  Install-WingetPackage "Git.Git"
}
if(Test-Cmd "git"){ Ok (& git --version) } else { Warn "git not found after install attempt." }

# OpenSSH Client capability (Windows)
try{
  $cap = Get-WindowsCapability -Online | Where-Object Name -like "OpenSSH.Client*"
  if($cap -and $cap.State -ne "Installed"){
    Info "Installing OpenSSH Client capability..."
    Add-WindowsCapability -Online -Name $cap.Name | Out-Null
  }
  if(Test-Cmd "ssh"){ Ok "OpenSSH Client available (ssh found)." } else { Warn "ssh not found in PATH." }
}catch{
  Warn "Could not verify/install OpenSSH Client automatically. Ensure 'ssh' works."
}

# -----------------------------
# Generate SSH key if missing
# -----------------------------
Info "Ensuring SSH key exists..."
New-Dir (Split-Path -Parent $KeyPath)

if(!(Test-Path -LiteralPath $KeyPath)){
  & ssh-keygen -t ed25519 -f $KeyPath -N "" | Out-Null
  Ok "Generated SSH key: $KeyPath"
}else{
  Ok "SSH key already exists: $KeyPath"
}

if(!(Test-Path -LiteralPath "$KeyPath.pub")){
  throw "Missing public key: $KeyPath.pub"
}

# -----------------------------
# Install the MCP server locally (D:\mcp\ssh-mcp\node_modules\...)
# -----------------------------
if(!(Have-Cmd "npm")){
  throw "npm is required but was not found. Install Node.js LTS and re-run."
}

Info "Installing MCP server package locally: $McpNpmPackage"

Push-Location $McpHome
try{
  if(!(Test-Path -LiteralPath ".\package.json")){
    Info "Initializing local npm project in $McpHome"
    & npm init -y | Out-Null
  }

  # Install with exact version pin to avoid surprise upgrades once installed
  # (You can update intentionally later with npm update + commit package-lock.json.)
  & npm install --save-exact $McpNpmPackage | Out-Null

  if(!(Test-Path -LiteralPath ".\node_modules\$McpNpmPackage")){
    throw "MCP server package did not install as expected: node_modules\$McpNpmPackage"
  }

  Ok "Installed MCP server locally under: $McpHome\node_modules"
}finally{
  Pop-Location
}

# -----------------------------
# Create MCP runtime config (no secrets beyond host/user/key path)
# -----------------------------
$configPath = Join-Path $McpHome "ssh-mcp.config.json"
$configObj = @{
  host        = $RpiHost
  port        = $RpiPort
  user        = $RpiUser
  key         = $KeyPath
  timeout     = 60000
  maxChars    = "none"
  disableSudo = $true  # prefer running only dbg_* via sudoers on the Pi
}

($configObj | ConvertTo-Json -Depth 5) | Out-File -Encoding utf8 -Force $configPath
Ok "Wrote MCP config: $configPath"

# -----------------------------
# MCP launcher: runs LOCAL install (no network) via npx from local project
# -----------------------------
$launcherPath = Join-Path $McpHome "run_ssh_mcp.ps1"
@'
param(
  [Parameter(Mandatory=$false)]
  [string]$ConfigPath = "D:\mcp\ssh-mcp\ssh-mcp.config.json"
)

$ErrorActionPreference = "Stop"
if(!(Test-Path -LiteralPath $ConfigPath)){ throw "Missing config file: $ConfigPath" }

$cfg = Get-Content -Raw -LiteralPath $ConfigPath | ConvertFrom-Json

Push-Location "D:\mcp\ssh-mcp"
try {
  # Uses the locally installed package in node_modules via npx resolution
  $args = @(
    "ssh-mcp","--",
    "--host=$($cfg.host)",
    "--port=$($cfg.port)",
    "--user=$($cfg.user)",
    "--key=$($cfg.key)",
    "--timeout=$($cfg.timeout)",
    "--maxChars=$($cfg.maxChars)"
  )
  if($cfg.disableSudo -eq $true){ $args += "--disableSudo" }

  & npx @args
} finally {
  Pop-Location
}
'@ | Out-File -Encoding utf8 -Force $launcherPath
Ok "Wrote MCP launcher: $launcherPath"

# -----------------------------
# Write VS Code workspace MCP config
# -----------------------------
$vscodeDir = Join-Path $RepoPath ".vscode"
New-Dir $vscodeDir

$mcpJsonPath = Join-Path $vscodeDir "mcp.json"
@"
{
  "servers": {
    "ipr-rpi-ssh": {
      "command": "powershell",
      "args": [
        "-NoProfile",
        "-ExecutionPolicy","Bypass",
        "-File","D:\\\\mcp\\\\ssh-mcp\\\\run_ssh_mcp.ps1"
      ]
    }
  }
}
"@ | Out-File -Encoding utf8 -Force $mcpJsonPath
Ok "Wrote workspace MCP config: $mcpJsonPath"

# -----------------------------
# Final instructions
# -----------------------------
Write-Host ""
Ok "PC MCP setup complete."
Write-Host ""
Write-Host "NEXT (manual step on RPi):" -ForegroundColor Yellow
Write-Host "Add this public key to /home/$RpiUser/.ssh/authorized_keys:"
Write-Host ""
Get-Content -LiteralPath "$KeyPath.pub"
Write-Host ""
Write-Host "Then test from PC:"
Write-Host "  ssh -i `"$KeyPath`" $RpiUser@$RpiHost -p $RpiPort"
Write-Host ""
Write-Host "Then open VS Code in: $RepoPath"
Write-Host "Copilot Chat (Agent mode) should be able to use MCP server: ipr-rpi-ssh"
