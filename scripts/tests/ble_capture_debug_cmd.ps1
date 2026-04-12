$ErrorActionPreference = 'Stop'
$log = "C:\Temp\ble_capture_start_full.log"
Remove-Item -Path "C:\Temp\ble_capture_start_full.log" -ErrorAction SilentlyContinue
try {
    "==== BEGIN 2026-04-12T14:42:01.6720325+02:00 ====" | Out-File -FilePath "C:\Temp\ble_capture_start_full.log" -Encoding UTF8 -Append
    Remove-Item -Path "C:\Temp\ble_capture.ready","C:\Temp\ble_capture.done","C:\Temp\ble_capture_result.txt" -ErrorAction SilentlyContinue | Out-String | Tee-Object -FilePath "C:\Temp\ble_capture_start_full.log" -Append | Write-Host
    $future = (Get-Date).AddSeconds(5)
    $startTime = $future.ToString("HH:mm:ss")
    $startDate = $future.ToString("dd/MM/yyyy")
    $taskName = "IPRKeyboard_BLE_Capture_Once"

    $action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"C:\Temp\win_ble_capture.ps1`" -OutputPath `"C:\Temp\ble_capture_result.txt`" -ReadyPath `"C:\Temp\ble_capture.ready`" -DonePath `"C:\Temp\ble_capture.done`" -InactivitySeconds 4 -MaxSeconds 300"

    schtasks /Create /TN "$taskName" /TR "$action" /SC ONCE /ST $startTime /SD $startDate /F | Out-String | Tee-Object -FilePath "C:\Temp\ble_capture_start_full.log" -Append | Write-Host
    schtasks /Run /TN "$taskName" | Out-String | Tee-Object -FilePath "C:\Temp\ble_capture_start_full.log" -Append | Write-Host
    "==== END 2026-04-12T14:42:01.6720658+02:00 ====" | Out-File -FilePath "C:\Temp\ble_capture_start_full.log" -Encoding UTF8 -Append

} catch {
    $_ | Out-String | Tee-Object -FilePath "C:\Temp\ble_capture_start_full.log" -Append | Write-Host
    $_ | Out-File -FilePath 'C:\Temp\ble_capture_start_error.log' -Encoding UTF8
    exit 1
}
