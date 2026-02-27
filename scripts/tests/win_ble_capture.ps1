param(
  [Parameter(Mandatory = $true)]
  [string]$OutputPath,
  [string]$ReadyPath = "$env:TEMP\\ble_capture.ready",
  [string]$DonePath = "$env:TEMP\\ble_capture.done",
  [int]$InactivitySeconds = 3,
  [int]$MaxSeconds = 300,
  [switch]$KeepWindowOpen
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([Threading.Thread]::CurrentThread.ApartmentState -ne 'STA') {
  $argList = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-Sta',
    '-File', "`"$PSCommandPath`"",
    '-OutputPath', "`"$OutputPath`"",
    '-ReadyPath', "`"$ReadyPath`"",
    '-DonePath', "`"$DonePath`"",
    '-InactivitySeconds', "$InactivitySeconds",
    '-MaxSeconds', "$MaxSeconds"
  )

  if ($KeepWindowOpen) {
    $argList += '-KeepWindowOpen'
  }

  $proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $argList -PassThru -Wait
  exit $proc.ExitCode
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$null = New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($OutputPath)) -Force -ErrorAction SilentlyContinue
$null = New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($ReadyPath)) -Force -ErrorAction SilentlyContinue
$null = New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($DonePath)) -Force -ErrorAction SilentlyContinue

$form = New-Object System.Windows.Forms.Form
$form.Text = 'IPR BLE Keyboard Capture'
$form.Width = 1000
$form.Height = 720
$form.StartPosition = 'CenterScreen'
$form.TopMost = $true

$label = New-Object System.Windows.Forms.Label
$label.AutoSize = $true
$label.Location = New-Object System.Drawing.Point(12, 12)
$label.Text = "Capture is active. Click textbox and keep focus there. Ctrl+Shift+S saves immediately."
$form.Controls.Add($label)

$status = New-Object System.Windows.Forms.Label
$status.AutoSize = $true
$status.Location = New-Object System.Drawing.Point(12, 34)
$status.Text = "Waiting for first keystroke..."
$form.Controls.Add($status)

$textBox = New-Object System.Windows.Forms.TextBox
$textBox.Multiline = $true
$textBox.AcceptsReturn = $true
$textBox.AcceptsTab = $true
$textBox.ScrollBars = 'Both'
$textBox.WordWrap = $false
$textBox.Font = New-Object System.Drawing.Font('Consolas', 11)
$textBox.Location = New-Object System.Drawing.Point(12, 62)
$textBox.Size = New-Object System.Drawing.Size(960, 590)
$form.Controls.Add($textBox)

$script:startUtc = [DateTime]::UtcNow
$script:lastInputUtc = $null
$script:startedTyping = $false
$script:forceFinish = $false

$textBox.Add_TextChanged({
  $script:lastInputUtc = [DateTime]::UtcNow
  if (-not $script:startedTyping) {
    $script:startedTyping = $true
  }
})

$form.Add_Shown({
  $form.Activate()
  $textBox.Focus() | Out-Null
  [IO.File]::WriteAllText($ReadyPath, ([DateTime]::UtcNow.ToString('o')), $utf8NoBom)
})

$form.Add_KeyPreviewChanged({})
$form.KeyPreview = $true
$form.Add_KeyDown({
  param($sender, $e)
  if ($e.Control -and $e.Shift -and $e.KeyCode -eq [System.Windows.Forms.Keys]::S) {
    $script:forceFinish = $true
    $e.SuppressKeyPress = $true
  }
})

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 250
$timer.Add_Tick({
  $nowUtc = [DateTime]::UtcNow
  $elapsed = ($nowUtc - $script:startUtc).TotalSeconds

  if ($script:startedTyping -and $script:lastInputUtc -ne $null) {
    $idle = ($nowUtc - $script:lastInputUtc).TotalSeconds
    $status.Text = "Typing started. Idle: {0:N1}s / {1}s" -f $idle, $InactivitySeconds

    if ($idle -ge $InactivitySeconds) {
      $script:forceFinish = $true
    }
  } else {
    $status.Text = "Waiting for first keystroke... elapsed {0:N1}s / {1}s" -f $elapsed, $MaxSeconds
  }

  if ($elapsed -ge $MaxSeconds) {
    $script:forceFinish = $true
  }

  if ($script:forceFinish) {
    $timer.Stop()
    $form.Close()
  }
})

$timer.Start()
[void]$form.ShowDialog()

$captureText = $textBox.Text
[IO.File]::WriteAllText($OutputPath, $captureText, $utf8NoBom)
[IO.File]::WriteAllText($DonePath, ([DateTime]::UtcNow.ToString('o')), $utf8NoBom)

if ($KeepWindowOpen) {
  Write-Host "Saved capture to $OutputPath"
  Write-Host "Press Enter to exit."
  [void][Console]::ReadLine()
}
