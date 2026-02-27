param(
  [string]$RpiHost = 'ipr-dev-pi4',
  [string]$RpiUser = 'meibye',
  [string]$PcHost = 'msi',
  [string]$PcUser = 'micha',
  [string]$SshKey = "$HOME/.ssh/id_ed25519_ipr_kb",
  [string]$RepoOnRpi = '/home/meibye/ipr-keyboard',
  [string]$RepoOnPc = 'D:\\sandbox\\ipr-keyboard',
  [string]$ExpectedRelativePath = 'tests/data/danish_mx_keys_all_chars.txt',
  [string]$CapturePath = 'C:\\Temp\\ble_capture_result.txt',
  [string]$ReportPath = 'C:\\Temp\\ble_capture_diff.txt',
  [int]$CaptureInactivitySeconds = 4,
  [int]$CaptureMaxSeconds = 300,
  [string]$NewlineMode = 'cr'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Ssh {
  param(
    [string]$Host,
    [string]$User,
    [string]$Command
  )

  $args = @('-i', $SshKey, "$User@$Host", $Command)
  & ssh @args
  if ($LASTEXITCODE -ne 0) {
    throw "SSH command failed on $User@$Host: $Command"
  }
}

function Wait-RemoteFile {
  param(
    [string]$Host,
    [string]$User,
    [string]$PosixPath,
    [int]$TimeoutSeconds = 30
  )

  $start = Get-Date
  while (((Get-Date) - $start).TotalSeconds -lt $TimeoutSeconds) {
    & ssh -i $SshKey "$User@$Host" "test -f '$PosixPath'"
    if ($LASTEXITCODE -eq 0) {
      return
    }
    Start-Sleep -Milliseconds 500
  }
  throw "Timed out waiting for remote file on $User@$Host: $PosixPath"
}

$pcCaptureReadyPath = 'C:\\Temp\\ble_capture.ready'
$pcCaptureDonePath = 'C:\\Temp\\ble_capture.done'

$pcCaptureScript = "$RepoOnPc\\scripts\\tests\\win_ble_capture.ps1"
$pcCompareScript = "$RepoOnPc\\scripts\\tests\\win_compare_ble_capture.ps1"
$pcExpectedPath = "$RepoOnPc\\$($ExpectedRelativePath -replace '/', '\\')"

$rpiExpectedPath = "$RepoOnRpi/$ExpectedRelativePath"
$rpiSendScript = "$RepoOnRpi/scripts/ble/bt_kb_send_file.sh"

Write-Host '[1/4] Starting capture window on PC...'
Invoke-Ssh -Host $PcHost -User $PcUser -Command @"
set -e
rm -f /mnt/c/Temp/ble_capture.ready /mnt/c/Temp/ble_capture.done
nohup powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Normal -File '$pcCaptureScript' -OutputPath '$CapturePath' -ReadyPath '$pcCaptureReadyPath' -DonePath '$pcCaptureDonePath' -InactivitySeconds $CaptureInactivitySeconds -MaxSeconds $CaptureMaxSeconds >/tmp/ble_capture_runner.log 2>&1 &
"@
Wait-RemoteFile -Host $PcHost -User $PcUser -PosixPath '/mnt/c/Temp/ble_capture.ready' -TimeoutSeconds 30

Write-Host '[2/4] Sending expected file over BLE from RPi...'
Invoke-Ssh -Host $RpiHost -User $RpiUser -Command @"
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

Write-Host '[3/4] Comparing captured content on PC...'
Wait-RemoteFile -Host $PcHost -User $PcUser -PosixPath '/mnt/c/Temp/ble_capture.done' -TimeoutSeconds ($CaptureMaxSeconds + 30)
Invoke-Ssh -Host $PcHost -User $PcUser -Command @"
set -e
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '$pcCompareScript' -ExpectedPath '$pcExpectedPath' -CapturedPath '$CapturePath' -ReportPath '$ReportPath'
"@

Write-Host '[4/4] Done.'
Write-Host "Capture file: $CapturePath"
Write-Host "Diff report : $ReportPath"
