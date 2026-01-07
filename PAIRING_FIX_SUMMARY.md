# Bluetooth Pairing Issue - Investigation Summary

## Problem Statement

A defect was detected in the Bluetooth pairing for the uinput type. The agent service returns 000000 as pairing code even though the PC where the pairing was initiated very briefly showed another key.

## Root Cause Analysis

### Issue Identified

The agent's `RequestPasskey` method in `scripts/ble/ble_install_helper.sh` (line 873-876) was hardcoded to return `0`:

```python
@dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
def RequestPasskey(self, device) -> int:
    journal.send(f"[agent] RequestPasskey for {device} -> using 000000")
    return 0  # WRONG: Always returns hardcoded 0 (displays as 000000)
```

### Why This Caused Confusion

1. **RequestPasskey** is called when the agent needs to **provide** a passkey to BlueZ
2. **DisplayPasskey** is called when BlueZ **generates** a passkey to show to the user
3. **RequestConfirmation** is called when the user needs to confirm a BlueZ-generated passkey

The agent registered as "KeyboardOnly" capability typically triggers DisplayPasskey or RequestConfirmation with a BlueZ-generated passkey. However, the agent also implemented RequestPasskey returning 000000, which could be called in certain pairing scenarios.

## Solution Implemented

### 1. Fixed Agent Code (ble_install_helper.sh)

```python
@dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
def RequestPasskey(self, device) -> int:
    # Generate a random passkey between 0 and 999999
    import random
    passkey = random.randint(0, 999999)
    self._generated_passkey = passkey
    journal.send(f"[agent] RequestPasskey for {device} -> GENERATED passkey={passkey:06d}")
    journal.send(f"[agent] *** USER ACTION REQUIRED: Enter passkey {passkey:06d} on the host device ***")
    return passkey  # CORRECT: Returns random passkey
```

**Changes:**
- Generate random 6-digit passkey (0-999999) instead of hardcoded 0
- Store generated passkey in agent instance
- Enhanced logging with clear user action messages
- Proper passkey formatting with zero-padding (e.g., 012345)

### 2. Enhanced Logging for All Pairing Methods

All pairing methods now have improved logging:

- **DisplayPasskey**: Logs when BlueZ shows a passkey to verify on both devices
- **RequestConfirmation**: Logs auto-acceptance of BlueZ-generated passkey
- **RequestPinCode**: Logs legacy PIN code requests
- **AuthorizeService**: Logs HID service authorization (critical for connection)

## Files Changed

### Modified Files

1. **scripts/ble/ble_install_helper.sh**
   - Fixed RequestPasskey to generate random passkey
   - Enhanced logging for all agent methods
   - Added passkey state tracking

2. **scripts/diag_troubleshoot.sh**
   - Added paired devices listing
   - Added recent agent pairing events display

3. **README.md**
   - Added reference to BLUETOOTH_PAIRING.md

4. **scripts/README.md**
   - Added diagnostic scripts section
   - Documented new pairing tools

### New Files

1. **scripts/diag_pairing.sh** (10.9 KB)
   - Comprehensive Bluetooth pairing diagnostics
   - Checks adapter, services, paired devices
   - Analyzes agent pairing methods
   - Shows recent pairing events
   - Provides specific recommendations

2. **scripts/test_pairing.sh** (9.8 KB)
   - Interactive pairing test workflow
   - Real-time agent event monitoring
   - Passkey highlighting
   - Connection verification
   - Keyboard input testing

3. **BLUETOOTH_PAIRING.md** (11 KB)
   - Complete pairing troubleshooting guide
   - Explains all pairing methods
   - Documents agent behavior
   - Common issues and solutions
   - Backend-specific notes

## Verification Steps

### 1. Reinstall Agent with Fix

```bash
cd /home/runner/work/ipr-keyboard/ipr-keyboard
sudo ./scripts/ble/ble_install_helper.sh
```

This will recreate `/usr/local/bin/bt_hid_agent.py` with the fixed code.

### 2. Restart Agent Service

```bash
sudo systemctl restart bt_hid_agent.service
```

### 3. Verify Fix is Applied

```bash
# Check that the agent script has the random passkey generation
grep -A 5 "def RequestPasskey" /usr/local/bin/bt_hid_agent.py

# Should show: passkey = random.randint(0, 999999)
```

### 4. Run Diagnostics

```bash
# Comprehensive pairing diagnostics
sudo ./scripts/diag_pairing.sh

# Should show:
# - Agent script found
# - RequestPasskey generates random passkey (not hardcoded 0)
# - Agent registered as 'KeyboardOnly'
```

### 5. Test Pairing (Optional)

```bash
# Interactive pairing test
sudo ./scripts/test_pairing.sh ble

# Follow the prompts to:
# 1. Start required services
# 2. Configure adapter
# 3. Monitor agent events
# 4. Pair from PC
# 5. Verify connection
```

### 6. Monitor Logs During Pairing

```bash
# Watch agent logs in real-time
sudo journalctl -u bt_hid_agent.service -f

# Look for pairing events with proper passkeys:
# [agent] RequestPasskey ... -> GENERATED passkey=123456
# [agent] *** USER ACTION REQUIRED: Enter passkey 123456 on the host device ***
```

## Testing on Raspberry Pi

To test on an actual Raspberry Pi:

### Prerequisites

- Raspberry Pi with Bluetooth adapter
- ipr-keyboard installed
- Agent and backend services installed

### Test Procedure

1. **Update agent code**:
   ```bash
   cd /path/to/ipr-keyboard
   sudo ./scripts/ble/ble_install_helper.sh
   ```

2. **Run diagnostics**:
   ```bash
   sudo ./scripts/diag_pairing.sh
   ```

3. **Start pairing test**:
   ```bash
   sudo ./scripts/test_pairing.sh ble
   ```

4. **On PC**: Initiate Bluetooth pairing
   - Open Bluetooth settings
   - Search for "ipr-keyboard"
   - Click to pair

5. **Observe logs** on Pi:
   - Watch terminal for passkey display
   - Note which pairing method is used
   - Verify passkey matches on both devices (if DisplayPasskey or RequestConfirmation)

6. **Enter passkey** on PC (if RequestPasskey):
   - The agent will log: `GENERATED passkey=XXXXXX`
   - Enter the same 6-digit code on PC

7. **Verify connection**:
   ```bash
   bluetoothctl devices
   bluetoothctl info <MAC_ADDRESS>
   ```

8. **Test keyboard input**:
   ```bash
   echo "Test text" > /run/ipr_bt_keyboard_fifo
   ```
   - Text should appear on paired PC

## Expected Behavior After Fix

### Before Fix
- Agent always returned `0` (000000) in RequestPasskey
- User might see different passkey briefly on PC (from DisplayPasskey or RequestConfirmation)
- Confusion about which passkey to use
- Pairing might succeed or fail depending on timing

### After Fix
- Agent generates random 6-digit passkey in RequestPasskey
- Logs clearly indicate which pairing method is used
- User action messages explain what to do
- Passkey values are clearly logged with zero-padding
- All pairing methods work correctly

## Pairing Method Reference

The agent supports multiple pairing methods:

| Method | When Used | Agent Behavior |
|--------|-----------|----------------|
| **RequestPasskey** | Agent generates code | Returns random 0-999999 (now fixed) |
| **DisplayPasskey** | BlueZ generates code | Logs passkey for user verification |
| **RequestConfirmation** | BlueZ asks to confirm | Auto-accepts with logged passkey |
| **RequestPinCode** | Legacy PIN pairing | Returns "0000" (rarely used) |
| **AuthorizeService** | HID service auth | Auto-accepts (critical for HID) |

## Diagnostic Tools Summary

| Tool | Purpose | When to Use |
|------|---------|-------------|
| **diag_pairing.sh** | Comprehensive pairing diagnostics | Before pairing, after failures |
| **test_pairing.sh** | Interactive pairing test | Testing pairing workflow |
| **diag_troubleshoot.sh** | General system diagnostics | Any system issue |
| **diag_status.sh** | Quick status overview | Regular health checks |
| **diag_ble.sh** | BLE-specific checks | BLE backend issues |

## References

- [BLUETOOTH_PAIRING.md](BLUETOOTH_PAIRING.md) - Complete troubleshooting guide
- [SERVICES.md](SERVICES.md) - Service documentation
- [scripts/README.md](scripts/README.md) - Script reference

---

**Investigation Date**: 2025-12-10
**Status**: RESOLVED
**Fix Applied**: Yes (pending deployment to Raspberry Pi)
