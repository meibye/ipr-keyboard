param(
  [Parameter(Mandatory = $true)]
  [string]$ExpectedPath,
  [Parameter(Mandatory = $true)]
  [string]$CapturedPath,
  [string]$ReportPath = "$env:TEMP\\ble_capture_diff.txt"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Normalize-Text {
  param([string]$Text)
  if ($null -eq $Text) { return '' }
  $t = $Text -replace "`r`n", "`n"
  $t = $t -replace "`r", "`n"
  return $t
}

function Context-At {
  param(
    [string]$Text,
    [int]$Index,
    [int]$Radius = 20
  )

  if ([string]::IsNullOrEmpty($Text)) { return '' }
  $start = [Math]::Max(0, $Index - $Radius)
  $length = [Math]::Min($Text.Length - $start, ($Radius * 2) + 1)
  $snippet = $Text.Substring($start, $length)
  return $snippet.Replace("`n", '<LF>')
}

if (-not (Test-Path -LiteralPath $ExpectedPath)) {
  throw "Expected file not found: $ExpectedPath"
}
if (-not (Test-Path -LiteralPath $CapturedPath)) {
  throw "Captured file not found: $CapturedPath"
}

$expectedRaw = Get-Content -LiteralPath $ExpectedPath -Raw -Encoding UTF8
$capturedRaw = Get-Content -LiteralPath $CapturedPath -Raw -Encoding UTF8

$expected = Normalize-Text -Text $expectedRaw
$captured = Normalize-Text -Text $capturedRaw

$max = [Math]::Min($expected.Length, $captured.Length)
$firstMismatch = -1
for ($i = 0; $i -lt $max; $i++) {
  if ($expected[$i] -ne $captured[$i]) {
    $firstMismatch = $i
    break
  }
}
if ($firstMismatch -eq -1 -and $expected.Length -ne $captured.Length) {
  $firstMismatch = $max
}

$lineDiffs = New-Object System.Collections.Generic.List[string]
$expectedLines = $expected -split "`n", -1
$capturedLines = $captured -split "`n", -1
$lineMax = [Math]::Max($expectedLines.Count, $capturedLines.Count)

for ($line = 0; $line -lt $lineMax; $line++) {
  $e = if ($line -lt $expectedLines.Count) { $expectedLines[$line] } else { '<MISSING>' }
  $c = if ($line -lt $capturedLines.Count) { $capturedLines[$line] } else { '<MISSING>' }
  if ($e -ne $c) {
    $lineDiffs.Add(("Line {0}" -f ($line + 1)))
    $lineDiffs.Add(("  expected: {0}" -f $e))
    $lineDiffs.Add(("  captured: {0}" -f $c))
  }
}

$match = ($expected -ceq $captured)
$expectedChar = if ($firstMismatch -ge 0 -and $firstMismatch -lt $expected.Length) { [int][char]$expected[$firstMismatch] } else { $null }
$capturedChar = if ($firstMismatch -ge 0 -and $firstMismatch -lt $captured.Length) { [int][char]$captured[$firstMismatch] } else { $null }

$reportLines = New-Object System.Collections.Generic.List[string]
$reportLines.Add(("Match: {0}" -f $match))
$reportLines.Add(("Expected length: {0}" -f $expected.Length))
$reportLines.Add(("Captured length: {0}" -f $captured.Length))
$reportLines.Add(("First mismatch index: {0}" -f $firstMismatch))

if ($firstMismatch -ge 0) {
  $reportLines.Add(("Expected char code at mismatch: {0}" -f $expectedChar))
  $reportLines.Add(("Captured char code at mismatch: {0}" -f $capturedChar))
  $reportLines.Add(("Expected context: {0}" -f (Context-At -Text $expected -Index $firstMismatch)))
  $reportLines.Add(("Captured context: {0}" -f (Context-At -Text $captured -Index $firstMismatch)))
}

$reportLines.Add('')
$reportLines.Add('Line-by-line differences:')
if ($lineDiffs.Count -eq 0) {
  $reportLines.Add('  none')
} else {
  foreach ($l in $lineDiffs) {
    $reportLines.Add($l)
  }
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$null = New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($ReportPath)) -Force -ErrorAction SilentlyContinue
[IO.File]::WriteAllLines($ReportPath, $reportLines, $utf8NoBom)

$result = [PSCustomObject]@{
  match = $match
  expected_length = $expected.Length
  captured_length = $captured.Length
  first_mismatch_index = $firstMismatch
  report_path = $ReportPath
}

$result | ConvertTo-Json -Depth 3

if ($match) {
  exit 0
}
exit 1
