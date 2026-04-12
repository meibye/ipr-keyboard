# scripts/tests/

End-to-end BLE keyboard verification helpers for cross-host testing.

## Files

- `run_ble_roundtrip_mcp.ps1`: coordinator that uses SSH to the test PC + RPi.
- `win_ble_capture.ps1`: opens a focused textbox window on Windows and captures typed input.
- `../tests/win_compare_ble_capture.ps1`: compares expected vs captured text and writes a mismatch report using Danish-keyboard rendered expectations.

## Expected flow

1. Start capture UI on test PC.
2. Send `tests/data/danish_mx_keys_all_chars.txt` from RPi over BLE.
3. Wait until capture completes (idle timeout).
4. Compare captured text against expected text.
5. Inspect report for mismatches.

## Run coordinator from Windows dev machine

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\tests\run_ble_roundtrip_mcp.ps1
```

## Compare locally after capture

Run this from the repo root after you have copied the captured file back locally:

```bash
python3 scripts/tests/compare_ble_capture_local.py \
  --expected tests/data/danish_mx_keys_all_chars.txt \
  --captured tests/data/reports/captured.txt \
  --report tests/data/reports/difference.txt
```

The script defaults to `--mode rendered`, which compares against the text a Danish keyboard can actually render on Windows, so dead-key output like ``´n``, `` `y``, `^æ`, `¨Ø`, `~i`, and fallback punctuation like `--` are handled consistently.

If you want a byte-for-byte Unicode comparison instead, pass `--mode exact`.

## Use via MCP SSH servers in VS Code

Use this order with your configured servers in `.vscode/mcp.json`:

1. `ipr-pc-dev-ssh`: run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\sandbox\ipr-keyboard\scripts\tests\win_ble_capture.ps1 -OutputPath C:\Temp\ble_capture_result.txt`.
2. `ipr-rpi-dev-ssh`: run `/home/meibye/ipr-keyboard/scripts/ble/bt_kb_send_file.sh --file /home/meibye/ipr-keyboard/tests/data/danish_mx_keys_all_chars.txt --newline-mode cr --debug`.
3. `ipr-pc-dev-ssh`: run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\sandbox\ipr-keyboard\tests\win_compare_ble_capture.ps1 -ExpectedPath D:\sandbox\ipr-keyboard\tests\data\danish_mx_keys_all_chars.txt -CapturedPath C:\Temp\ble_capture_result.txt -ReportPath C:\Temp\ble_capture_diff.txt`.

## Notes

- The coordinator assumes SSH connectivity to both hosts using the same key used in `.vscode/mcp.json`.
- `win_ble_capture.ps1` requires an interactive desktop session on the test PC.
- BLE daemon newline handling in `scripts/service/bin/bt_hid_ble_daemon.py` now maps FIFO `\n` to carriage return (`\r`) so multiline files produce Enter key presses.
- If a character is unsupported by the daemon keymap, it is dropped; mismatches are expected until mappings are expanded.
- Exact capture of literal combining sequences like `á`, `ǹ`, `æ̈`, and `å̃` requires the receiving Windows account to support `Alt` + hex Unicode input. Set `HKCU\Control Panel\Input Method\EnableHexNumpad=1`, then sign out and back in before running the BLE roundtrip.
- Without `EnableHexNumpad`, the daemon can still send those sequences, but Windows commonly drops the combining mark and you will capture only the base letter.
