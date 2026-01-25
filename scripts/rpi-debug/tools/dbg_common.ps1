# Common environment for Copilot diagnostic PowerShell scripts
# Import this file in all scripts in scripts/rpi-debug/tools/
# VERSION: 2026/01/25 13:35:42

Set-StrictMode -Version Latest

# --- Fixed local paths (per your environment) ---
$Global:RepoPath = "D:\Dev\ipr_keyboard"
$Global:McpRoot  = "D:\mcp"
$Global:McpHome  = "$Global:McpRoot\ssh-mcp"

# --- Defaults that may be overridden by profile selection ---
$Global:RpiHost  = "ipr-dev-pi4"
$Global:RpiUser  = "copilotdiag"
$Global:RpiPort  = 22
$Global:KeyPath  = "$env:USERPROFILE\.ssh\copilotdiag_rpi"

 # --- Project-specific defaults ---
$Global:ServiceName = "bt_hid_ble.service"
$Global:Hci = "hci0"
$Global:RepoDirOnPi = "/home/meibye/dev/ipr_keyboard"


# --- Profiles (dev/prod) ---
$Global:RpiProfiles = @{
  dev = @{
    host      = "ipr-dev-pi4"
    user      = "copilotdiag"
    port      = 22
    repoDirOnPi = $Global:RepoDirOnPi
  }
  prod = @{
    host      = "ipr-prod-zero2"
    user      = "copilotdiag"
    port      = 22
    repoDirOnPi = $Global:RepoDirOnPi
  }
}

function Set-RpiProfile {
  param(
    [Parameter(Mandatory = $false)]
    [ValidateSet("dev","prod")]
    [string]$ProfileName = $null
  )

  if([string]::IsNullOrWhiteSpace($ProfileName)){
    if($env:RPI_PROFILE){
      $ProfileName = $env:RPI_PROFILE
    } else {
      $ProfileName = "dev"
    }
  }

  if(-not $Global:RpiProfiles.ContainsKey($ProfileName)){
    throw "Unknown RPI profile '$ProfileName'. Valid: dev, prod"
  }

  $p = $Global:RpiProfiles[$ProfileName]

  $Global:RpiHost    = $p.host
  $Global:RpiUser    = $p.user
  $Global:RpiPort    = $p.port
  $Global:RepoDirOnPi = $p.repoDirOnPi

  # Allow env overrides (handy for ad-hoc testing)

  if($env:RPI_HOST){ $Global:RpiHost = $env:RPI_HOST }
  if($env:RPI_USER){ $Global:RpiUser = $env:RPI_USER }
  if($env:RPI_PORT){ $Global:RpiPort = [int]$env:RPI_PORT }
  if($env:RPI_KEY){  $Global:KeyPath = $env:RPI_KEY }

  $Global:RpiProfile = $ProfileName
}


function Write-Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Write-Ok($m){   Write-Host "[ OK ] $m" -ForegroundColor Green }
function Write-Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }


function New-Dir($p){
  if(!(Test-Path -LiteralPath $p)){
    New-Item -ItemType Directory -Path $p | Out-Null
  }
}


function Test-Cmd($name){
  return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}
