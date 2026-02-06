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

function Get-WhitelistRegex {
    param (
        [Parameter(Mandatory=$true)]
        [string]$Command
    )

    # 1. Split the command to isolate the binary from arguments
    $parts = $Command -split ' ', 2
    $binary = $parts[0]
    $args = if ($parts.Count -gt 1) { " $($parts[1])" } else { "" }

    # Check for trailing '*' wildcard (meaning: any arguments allowed)
    $hasWildcard = $Command.TrimEnd().EndsWith(' *')
    if ($hasWildcard) {
        # Remove the trailing ' *' for regex construction
        $Command = $Command.Substring(0, $Command.Length - 2).TrimEnd()
    }

    # 2. Locate the last directory separator in the binary name
    $lastSlashIndex = $binary.LastIndexOf('/')

    if ($lastSlashIndex -ge 0) {
        # Extract the parent path (e.g., /usr/bin/)
        $pathPart = $binary.Substring(0, $lastSlashIndex + 1)
        # Extract the rest (binary name + arguments)
        $restOfCmd = $binary.Substring($lastSlashIndex + 1) + $args

        # Remove trailing '*' from restOfCmd if wildcard is present
        if ($hasWildcard -and $restOfCmd.EndsWith(' *')) {
            $restOfCmd = $restOfCmd.Substring(0, $restOfCmd.Length - 2).TrimEnd()
        }

        # 3. Construct the regex with an optional escaped path
        $escapedPath = [regex]::Escape($pathPart)
        $escapedRest = [regex]::Escape($restOfCmd)

        if ($hasWildcard) {
            # If wildcard, match any trailing arguments (not literal asterisk)
            return "(?:$escapedPath)?$escapedRest(\s+.*)?$"
        } else {
            # Allow for additional parameters and optional piping to another command
            return "(?:$escapedPath)?$escapedRest(\s+.*)?(\s*\|\s*.+)?$"
        }
    } else {
        # If no path exists, just return the escaped command anchored
        $escapedCmd = [regex]::Escape($Command)
        if ($hasWildcard) {
            return "$escapedCmd(\s+.*)?$"
        } else {
            return "$escapedCmd(\s+.*)?(\s*\|\s*.+)?$"
        }
    }
}

# Read dbg_common.env for variable substitution
$envFile = Join-Path $ScriptDir '..\dbg_common.env'
if (!(Test-Path $envFile)) {
    Write-Error "Missing environment file: $envFile"
    exit 1
}

# Load env vars into a hashtable
$envVars = @{}
foreach ($envLine in Get-Content $envFile) {
    if ($envLine -match '^\s*([A-Za-z0-9_]+)\s*=\s*(.+?)\s*$') {
        $envVars[$matches[1]] = $matches[2]
        # Write-Host "Loaded env var: $($matches[1]) = $($matches[2])"
    }
}

# Initialize whitelist array to hold regex patterns for allowed commands
$whitelist = @()
foreach ($line in $lines) {
    $cmd = $line.Trim()
    
    # Replace any ${VAR} in $cmd with value from dbg_common.env
    if ($cmd -match '\$\{([A-Za-z0-9_]+)\}') {
        # Write-Host "Substituting variables in: $cmd"
        
        $evaluator = {
            param($match) # Explicitly naming the match object for clarity
            $varName = $match.Groups[1].Value
            
            if ($envVars.ContainsKey($varName)) {
                # Write-Host "  -> Replacing `${$varName}` with '$($envVars[$varName])'"
                return $envVars[$varName]
            } else {
                # Write-Host "  -> No value for `${$varName}`, leaving as-is"
                return $match.Value
            }
        }

        # Using [regex]::Replace ensures compatibility with PS 5.1 AND PS 7
        $cmd = [regex]::Replace($cmd, '\$\{([A-Za-z0-9_]+)\}', $evaluator)
        
        # Write-Host "  Result after substitution: $cmd"
    }
    $cmd = Get-WhitelistRegex -Command $cmd
    $whitelist += $cmd
}

# Output as comma-separated string for --whitelist argument
$WhitelistString = $whitelist -join ','
Write-Output $WhitelistString
