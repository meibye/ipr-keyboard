# Generates a --whitelist argument for all allowed scripts in scripts/rpi-debug
# Usage: .\gen_mcp_whitelist.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RpiDebugDir = Join-Path $ScriptDir '..'
$Whitelist = @()

# Get all executable scripts in scripts/rpi-debug (not subfolders)
Get-ChildItem -Path $RpiDebugDir -File -Filter '*.sh' | ForEach-Object {
    $Whitelist += "/usr/local/bin/$($_.Name)"
}

# Output as comma-separated string for --whitelist argument
$WhitelistString = $Whitelist -join ','
Write-Output $WhitelistString

# For use in setup_ipr_mcp.ps1:
#   $whitelist = & (Join-Path $ScriptDir 'gen_mcp_whitelist.ps1')
#   ... add --whitelist, $whitelist to args if not present ...
