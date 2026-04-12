# ============================================================================
# IPR BLE Keyboard Roundtrip Test Script
#
# This script performs a BLE roundtrip test between a Raspberry Pi and a PC.
# It verifies connectivity, sets up capture, sends a test file, and compares results.
#
# Usage:
#   .\run_ble_roundtrip_mcp.ps1 -RpiHost <host> -RpiUser <user> -PcHost <host> -PcUser <user>
#
# Only the first four parameters are required. All other configuration variables
# are set in the script below and can be adjusted as needed.
# ============================================================================

param(
  [string]$RpiHost = 'ipr-dev-pi4',
  [string]$RpiUser = 'meibye',
  [string]$PcHost = 'msi',
  [string]$PcUser = 'micha'
)

# -----------------------------------------------------------------------------
# Configurable variables (edit as needed)
# -----------------------------------------------------------------------------
$SshKey = "$HOME/.ssh/id_ed25519_ipr_kb"
$RepoOnRpi = '/home/meibye/dev/ipr-keyboard'
$RepoOnPc = 'D:\sandbox\ipr-keyboard'
$CharsPath = 'danish_mx_keys_all_chars.txt'
$ExpectedRelativePath = "tests/data/$CharsPath"
$CapturePath = 'C:\Temp\ble_capture_result.txt'
$ReportPath = 'C:\Temp\ble_capture_diff.txt'
$ExpectedCharsPath = "C:\Temp\$CharsPath"
$CaptureInactivitySeconds = 4
$CaptureMaxSeconds = 300
$NewlineMode = 'cr'
$pcCaptureReadyPath = 'C:\Temp\ble_capture.ready'
$pcCaptureDonePath = 'C:\Temp\ble_capture.done'
$pcCaptureScript = "$RepoOnPc\scripts\tests\win_ble_capture.ps1"
$pcCompareScript = "$RepoOnPc\scripts\tests\win_compare_ble_capture.ps1"
$pcCaptureScriptRemote = 'C:\Temp\win_ble_capture.ps1'
$pcCompareScriptRemote = 'C:\Temp\win_compare_ble_capture.ps1'
$captureResultLocal = "C:\Temp\ble_capture_result.txt"
$pcExpectedPath = "$RepoOnPc\$($ExpectedRelativePath -replace '/', '\')"
$pcRemoteLog = 'C:\Temp\ble_capture_start_full.log'
$rpiExpectedPath = "$RepoOnRpi/$ExpectedRelativePath"
$rpiSendScript = "$RepoOnRpi/scripts/ble/bt_kb_send_file.sh"
$expandedRemoteCmdPath = "C:\Temp\ble_capture_debug_cmd.ps1"

# -----------------------------------------------------------------------------
# Script settings
# -----------------------------------------------------------------------------
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------
function Invoke-Ssh {
  param(
    [string]$SshHost,
    [string]$User,
    [string]$Command
  )
  $arguments = @('-i', $SshKey, "$User@$SshHost", $Command)
  & ssh @arguments
  if ($LASTEXITCODE -ne 0) {
    throw "SSH command failed on ${User}@${SshHost}: $Command"
  }
}

function Wait-RemoteFile {
  param(
    [string]$SshHost,
    [string]$User,
    [string]$Path,
    [int]$TimeoutSeconds = 30
  )
  $start = Get-Date
  $remoteCmd = 'powershell -NoProfile -Command "if (Test-Path -Path ''{0}'') {{ exit 0 }} else {{ exit 1 }}"' -f $Path
  $firstIteration = $true
  while (((Get-Date) - $start).TotalSeconds -lt $TimeoutSeconds) {
    if ($firstIteration) {
      Write-Host "SSH: $User@$SshHost -> $remoteCmd"
      $firstIteration = $false
    }
    & ssh @('-i', $SshKey, "$User@$SshHost", $remoteCmd)
    if ($LASTEXITCODE -eq 0) {
      return
    }
    Start-Sleep -Milliseconds 500
  }
  throw "Timed out waiting for remote file on ${User}@${SshHost}: $PosixPath"
}

# -----------------------------------------------------------------------------
# Step 0: Verify connectivity
# -----------------------------------------------------------------------------
Write-Host '[0/4] Verifying connectivity to RPi and PC...'
try {
  Invoke-Ssh -SshHost $RpiHost -User $RpiUser -Command 'echo "RPi reachable"' | Out-Null
  Write-Host "✓ RPi ($RpiHost) is reachable" -ForegroundColor Green
} catch {
  Write-Host "✗ Cannot reach RPi ($RpiHost). Check SSH key, host, and network." -ForegroundColor Red
  exit 1
}

try {
  Invoke-Ssh -SshHost $PcHost -User $PcUser -Command 'powershell -NoProfile -Command "Write-Host ''PC reachable''"' | Out-Null
  Write-Host "✓ PC ($PcHost) is reachable" -ForegroundColor Green
} catch {
  Write-Host "✗ Cannot reach PC ($PcHost). Check SSH key, host, and network." -ForegroundColor Red
  exit 1
}

# -----------------------------------------------------------------------------
# Step 1: Copy scripts to PC
# -----------------------------------------------------------------------------
Write-Host '[1/4] Copying scripts to PC...'
Invoke-Ssh -SshHost $PcHost -User $PcUser -Command 'powershell -NoProfile -Command "New-Item -ItemType Directory -Path ''C:\Temp'' -Force | Out-Null"'
$scpArgs1 = @('-i', $SshKey, $pcCaptureScript, "$PcUser@${PcHost}:$pcCaptureScriptRemote")
& scp @scpArgs1
if ($LASTEXITCODE -ne 0) { throw "SCP failed for $pcCaptureScript" }
$scpArgs2 = @('-i', $SshKey, $pcCompareScript, "$PcUser@${PcHost}:$pcCompareScriptRemote")
& scp @scpArgs2
if ($LASTEXITCODE -ne 0) { throw "SCP failed for $pcCompareScript" }

# -----------------------------------------------------------------------------
# Step 2: Start capture window on PC
# -----------------------------------------------------------------------------
Write-Host '[2/4] Starting capture window on PC...'
# Start-Process powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Normal','-File',"$pcCaptureScriptRemote",'-OutputPath',"$CapturePath",'-ReadyPath',"$pcCaptureReadyPath",'-DonePath',"$pcCaptureDonePath",'-InactivitySeconds',"$CaptureInactivitySeconds",'-MaxSeconds',"$CaptureMaxSeconds" -WindowStyle Normal | Out-String | Tee-Object -FilePath "$pcRemoteLog" -Append | Write-Host

# Compose the expanded PowerShell command string for remote debugging
$localDebugScript = Join-Path $PSScriptRoot 'ble_capture_debug_cmd.ps1'
$expandedRemoteCmdContent = @"
`$ErrorActionPreference = 'Stop'
`$log = "$pcRemoteLog"
Remove-Item -Path "$pcRemoteLog" -ErrorAction SilentlyContinue
try {
    "==== BEGIN $(Get-Date -Format o) ====" | Out-File -FilePath "$pcRemoteLog" -Encoding UTF8 -Append
    Remove-Item -Path "$pcCaptureReadyPath","$pcCaptureDonePath","$CapturePath" -ErrorAction SilentlyContinue | Out-String | Tee-Object -FilePath "$pcRemoteLog" -Append | Write-Host
    `$future = (Get-Date).AddSeconds(5)
    `$startTime = `$future.ToString("HH:mm:ss")
    `$startDate = `$future.ToString("dd/MM/yyyy")
    `$taskName = "IPRKeyboard_BLE_Capture_Once"

    `$action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File ```"$pcCaptureScriptRemote```" -OutputPath ```"$CapturePath```" -ReadyPath ```"$pcCaptureReadyPath```" -DonePath ```"$pcCaptureDonePath```" -InactivitySeconds $CaptureInactivitySeconds -MaxSeconds $CaptureMaxSeconds"

    schtasks /Create /TN "`$taskName" /TR "`$action" /SC ONCE /ST `$startTime /SD `$startDate /F | Out-String | Tee-Object -FilePath "$pcRemoteLog" -Append | Write-Host
    schtasks /Run /TN "`$taskName" | Out-String | Tee-Object -FilePath "$pcRemoteLog" -Append | Write-Host
    "==== END $(Get-Date -Format o) ====" | Out-File -FilePath "$pcRemoteLog" -Encoding UTF8 -Append

} catch {
    `$_ | Out-String | Tee-Object -FilePath "$pcRemoteLog" -Append | Write-Host
    `$_ | Out-File -FilePath 'C:\Temp\ble_capture_start_error.log' -Encoding UTF8
    exit 1
}
"@

# Now expand all variables to their literal values (no $var left in the script)
$expandedRemoteCmdContent = $expandedRemoteCmdContent.Replace("$pcRemoteLog", $pcRemoteLog)
$expandedRemoteCmdContent = $expandedRemoteCmdContent.Replace("$pcCaptureReadyPath", $pcCaptureReadyPath)
$expandedRemoteCmdContent = $expandedRemoteCmdContent.Replace("$pcCaptureDonePath", $pcCaptureDonePath)
$expandedRemoteCmdContent = $expandedRemoteCmdContent.Replace("$CapturePath", $CapturePath)
$expandedRemoteCmdContent = $expandedRemoteCmdContent.Replace("$pcCaptureScriptRemote", $pcCaptureScriptRemote)
$expandedRemoteCmdContent = $expandedRemoteCmdContent.Replace("$CaptureInactivitySeconds", $CaptureInactivitySeconds)
$expandedRemoteCmdContent = $expandedRemoteCmdContent.Replace("$CaptureMaxSeconds", $CaptureMaxSeconds)
Set-Content -Path $localDebugScript -Value $expandedRemoteCmdContent -Encoding UTF8

# Copy the debug script to the remote PC
$remoteCmdPath = 'C:\Temp\ble_capture_debug_cmd.ps1'
$scpArgsDebug = @('-i', $SshKey, $localDebugScript, "$PcUser@${PcHost}:$remoteCmdPath")
& scp @scpArgsDebug
if ($LASTEXITCODE -ne 0) { throw "SCP failed for $localDebugScript" }
Write-Host "Remote debug script written to $remoteCmdPath on $PcHost."

# Execute the debug script on the remote PC
Invoke-Ssh -SshHost $PcHost -User $PcUser -Command (
  'powershell -NoProfile -ExecutionPolicy Bypass -File "' + $remoteCmdPath + '"'
)

# Fetch and print the remote log file for visibility
Write-Host '--- Remote capture start log ---'
Invoke-Ssh -SshHost $PcHost -User $PcUser -Command "type $pcRemoteLog"
Write-Host '--- End of remote log ---'
Write-Host "Waiting 30 seconds for capture to be ready on PC (looking for $pcCaptureReadyPath)..."
#Wait-RemoteFile -SshHost $PcHost -User $PcUser -Path 'C:\Temp\ble_capture.ready' -TimeoutSeconds 30

# -----------------------------------------------------------------------------
# Step 3: Send expected file over BLE from RPi
# -----------------------------------------------------------------------------
Write-Host '[3/4] Sending expected file over BLE from RPi...'
Invoke-Ssh -SshHost $RpiHost -User $RpiUser -Command @"
set -e
if [ ! -f '$rpiExpectedPath' ]; then
  echo 'Expected file not found on RPi: $rpiExpectedPath' >&2
  exit 2
fi
if [ ! -x '$rpiSendScript' ]; then
  echo 'Send helper not found or not executable: $rpiSendScript' >&2
  exit 2
fi
'$rpiSendScript' --file '$rpiExpectedPath' --newline-mode '$NewlineMode' --debug
"@

# -----------------------------------------------------------------------------
# Step 4: Compare captured content and retrieve results
# -----------------------------------------------------------------------------
Write-Host '[4/4] Comparing captured content on PC and retrieved results...'
Wait-RemoteFile -SshHost $PcHost -User $PcUser -Path 'C:\Temp\ble_capture.done' -TimeoutSeconds ($CaptureMaxSeconds + 30)
Write-Host 'Copy expected result to remote PC...'
$scpArgs3 = @('-i', $SshKey, $pcExpectedPath, "$PcUser@${PcHost}:$ExpectedCharsPath")
& scp @scpArgs3
if ($LASTEXITCODE -ne 0) { throw "SCP failed for $ExpectedCharsPath" }

Write-Host 'Capture completed now comparing results...'
Invoke-Ssh -SshHost $PcHost -User $PcUser -Command (
  'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + $pcCompareScriptRemote + '" -ExpectedPath "' + $ExpectedCharsPath + '" -CapturedPath "' + $CapturePath + '" -ReportPath "' + $ReportPath + '"'
)

Write-Host "Capture file: $CapturePath"
Write-Host "Diff report : $ReportPath"

Write-Host 'Copying capture result back to local machine...'
$scpArgs4 = @('-i', $SshKey, "$PcUser@${PcHost}:$CapturePath", $captureResultLocal)
& scp @scpArgs4
if ($LASTEXITCODE -ne 0) { Write-Warning "SCP failed for $CapturePath" } else { Write-Host "Copied: $CapturePath -> $captureResultLocal" }
