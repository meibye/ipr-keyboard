# update-version.ps1
#
# Updates the version comment and VERSION variable in a source file to the current timestamp.
#
# Usage:
#   powershell -File update-version.ps1 -FilePath <file> [-SearchLinesFromTop N] [-TimestampFormat <fmt>]
#
# Parameters:
#   FilePath            Path to the file to update (required)
#   SearchLinesFromTop  Number of lines from the top to search for version lines (default: 80)
#   TimestampFormat     .NET date format string for the timestamp (default: yyyy-MM-dd HH:mm:ss)

param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,
    [int]$SearchLinesFromTop = 80,
    [string]$TimestampFormat = "yyyy-MM-dd HH:mm:ss"
)

# Stop on all errors
$ErrorActionPreference = "Stop"

# Check if the file exists
if (-not (Test-Path -LiteralPath $FilePath)) {
    throw "File not found: $FilePath"
}

# Read the file as a single text block (preserve encoding)
$content = Get-Content -LiteralPath $FilePath -Raw -Encoding UTF8

# Detect and preserve the file's original line ending style
$lineEnding = if ($content -match "`r`n") { "`r`n" } else { "`n" }

# Split the content into lines for easier processing
$lines = [System.Collections.Generic.List[string]]::new()
$content -split "`r?`n" | ForEach-Object { [void]$lines.Add($_) }

# Exit if the file is empty
if ($lines.Count -eq 0) {
    return
}

# Only search the first N lines for version markers
$limit = [Math]::Min($SearchLinesFromTop, $lines.Count)

# Get the current timestamp in the requested format, quoted for assignment
$timestamp = Get-Date -Format $TimestampFormat
$quotedTimestamp = "'$timestamp'"

# Regex to match the version comment and variable lines
$commentRegex = '^\s*#\s*VERSION:\s*''.*''\s*$'
$variableRegex = '^\s*VERSION\s*=\s*''.*''\s*$'

# Find the line numbers for the version comment and variable (if present)
$commentIndex = $null
$variableIndex = $null

for ($i = 0; $i -lt $limit; $i++) {
    if ($null -eq $commentIndex -and $lines[$i] -match $commentRegex) {
        $commentIndex = $i
    }
    if ($null -eq $variableIndex -and $lines[$i] -match $variableRegex) {
        $variableIndex = $i
    }
}

# Update the version comment and/or variable if found
$changed = $false

if ($null -ne $commentIndex) {
    $lines[$commentIndex] = "# VERSION: $quotedTimestamp"
    $changed = $true
}

if ($null -ne $variableIndex) {
    $lines[$variableIndex] = "VERSION = $quotedTimestamp"
    $changed = $true
}

# If any changes were made, write the updated content back to the file
if ($changed) {
    $newContent = ($lines -join $lineEnding)

    # Only add a trailing newline if the original file did NOT have one
    if (-not ($newContent.EndsWith("`r`n") -or $newContent.EndsWith("`n"))) {
        $newContent += $lineEnding
    }

    # Write the updated content with UTF-8 encoding (no BOM)
    [System.IO.File]::WriteAllText($FilePath, $newContent, [System.Text.UTF8Encoding]::new($false))
}