param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,

    [int]$SearchLinesFromTop = 80,

    [string]$TimestampFormat = "yyyy-MM-dd HH:mm:ss"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $FilePath)) {
    throw "File not found: $FilePath"
}

# Read file as a single text block
$content = Get-Content -LiteralPath $FilePath -Raw -Encoding UTF8

# Preserve the file's original line ending style where possible
$lineEnding = if ($content -match "`r`n") { "`r`n" } else { "`n" }

# Split into lines
$lines = [System.Collections.Generic.List[string]]::new()
$content -split "`r?`n" | ForEach-Object { [void]$lines.Add($_) }

if ($lines.Count -eq 0) {
    return
}

$limit = [Math]::Min($SearchLinesFromTop, $lines.Count)
$timestamp = Get-Date -Format $TimestampFormat
$quotedTimestamp = "'$timestamp'"

$commentRegex = '^\s*#\s*VERSION:\s*' + "'.*'" + '\s*$'
$variableRegex = '^\s*VERSION\s*=\s*' + "'.*'" + '\s*$'

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

$changed = $false

if ($null -ne $commentIndex) {
    $lines[$commentIndex] = "# VERSION: $quotedTimestamp"
    $changed = $true
}

if ($null -ne $variableIndex) {
    $lines[$variableIndex] = "VERSION = $quotedTimestamp"
    $changed = $true
}

if ($changed) {
    $newContent = ($lines -join $lineEnding)

    # Preserve trailing newline if the original had one
    if ($content.EndsWith("`r`n") -or $content.EndsWith("`n")) {
        $newContent += $lineEnding
    }

    [System.IO.File]::WriteAllText($FilePath, $newContent, [System.Text.UTF8Encoding]::new($false))
}