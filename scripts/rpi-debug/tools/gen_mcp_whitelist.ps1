# Generates a --whitelist argument for all allowed scripts in scripts/rpi-debug
# Usage: .\gen_mcp_whitelist.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$SudoersListFile = Join-Path $ScriptDir '..\dbg_sudoers_list.txt'
if (!(Test-Path $SudoersListFile)) {
    Write-Error "Missing sudoers list file: $SudoersListFile"
    exit 1
}

# Read and filter lines
$lines = Get-Content $SudoersListFile | Where-Object { $_ -and ($_ -notmatch '^#') }


# Group similar scripts for regex minimization, regardless of prefix
$scriptPattern = '^(.*[\\/])?(dbg_[a-z_]+\.sh)( \*)?$'
$grouped = @{}
$otherCmds = @()
foreach ($line in $lines) {
    if ($line -match $scriptPattern) {
        $basename = $Matches[2]
        $star = $Matches[3]
        $grouped[$basename] = $true
        if ($star) { $grouped["$basename *"] = $true }
    } else {
        $otherCmds += $line
    }
}

# If all grouped scripts have no path (i.e., in PATH), drop prefix in output
$allNoPrefix = $true
foreach ($line in $lines | Where-Object { $_ -match $scriptPattern }) {
    if ($line -match '^[\\/]') { $allNoPrefix = $false; break }
}

$groupKeys = $grouped.Keys | Sort-Object
if ($groupKeys.Count -gt 0) {
    if ($allNoPrefix) {
        $regex = 'dbg_(' + ($groupKeys -join '|').Replace('.sh','').Replace(' *','') + ')'
    } else {
        $regex = '.*dbg_(' + ($groupKeys -join '|').Replace('.sh','').Replace(' *','') + ')'
    }
    $whitelist = @($regex)
} else {
    $whitelist = @()
}

# Add other commands (strip /usr/bin/ prefix if present, since /usr/bin is in PATH)
$otherCmdsNoPrefix = $otherCmds | ForEach-Object {
    if ($_ -like '/usr/bin/*') {
        $_.Substring(9)  # remove '/usr/bin/'
    } else {
        $_
    }
}
$whitelist += $otherCmdsNoPrefix

# Output as comma-separated string for --whitelist argument
$WhitelistString = $whitelist -join ','
Write-Output $WhitelistString
