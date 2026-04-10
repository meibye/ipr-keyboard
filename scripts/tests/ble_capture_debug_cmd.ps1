$ErrorActionPreference = 'Stop'
$log = "C:\Temp\ble_capture_start_full.log"
Remove-Item -Path "C:\Temp\ble_capture_start_full.log" -ErrorAction SilentlyContinue
try {
    "==== BEGIN 2026-04-10T14:10:07.8712822+02:00 ====" | Out-File -FilePath "C:\Temp\ble_capture_start_full.log" -Encoding UTF8 -Append
    Remove-Item -Path "C:\Temp\ble_capture.ready","C:\Temp\ble_capture.done","C:\Temp\ble_capture_result.txt" -ErrorAction SilentlyContinue | Out-String | Tee-Object -FilePath "C:\Temp\ble_capture_start_full.log" -Append | Write-Host
    Start-Process powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Normal','-File',"C:\Temp\win_ble_capture.ps1",'-OutputPath',"C:\Temp\ble_capture_result.txt",'-ReadyPath',"C:\Temp\ble_capture.ready",'-DonePath',"C:\Temp\ble_capture.done",'-InactivitySeconds',"4",'-MaxSeconds',"300" -WindowStyle Normal | Out-String | Tee-Object -FilePath "C:\Temp\ble_capture_start_full.log" -Append | Write-Host
    "==== END 2026-04-10T14:10:07.8713188+02:00 ====" | Out-File -FilePath "C:\Temp\ble_capture_start_full.log" -Encoding UTF8 -Append
} catch {
    $_ | Out-String | Tee-Object -FilePath "C:\Temp\ble_capture_start_full.log" -Append | Write-Host
    $_ | Out-File -FilePath 'C:\Temp\ble_capture_start_error.log' -Encoding UTF8
    exit 1
}
