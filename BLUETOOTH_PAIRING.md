# Bluetooth Pairing Troubleshooting Guide

This guide explains the Bluetooth pairing process for ipr-keyboard and how to diagnose and fix pairing issues for both uinput and BLE backends.

## Table of Contents

1. [Understanding Bluetooth Pairing](#understanding-bluetooth-pairing)
2. [Pairing Methods](#pairing-methods)
3. [Agent Behavior](#agent-behavior)
4. [Diagnostic Tools](#diagnostic-tools)
5. [Common Issues](#common-issues)
6. [Backend-Specific Notes](#backend-specific-notes)

## Understanding Bluetooth Pairing

The ipr-keyboard system uses a BlueZ agent to handle Bluetooth pairing requests automatically. The agent is implemented in `bt_hid_agent.py` and runs as the `bt_hid_agent.service` systemd service.

### Pairing Flow

1. **Discovery**: Host device (PC/phone) scans for Bluetooth devices
2. **Connection Request**: Host initiates connection to "ipr-keyboard"
3. **Pairing Request**: BlueZ invokes agent methods to handle authentication
4. **Service Authorization**: Agent approves HID profile connection
5. **Connection Established**: Devices are paired and ready for use

## Pairing Methods

BlueZ supports several pairing methods. The agent capability determines which methods are used:

### Agent Capabilities

The ipr-keyboard agent is registered with **"KeyboardOnly"** capability, which means:

- **DisplayPasskey**: BlueZ generates a 6-digit passkey that should be displayed to the user
- **RequestConfirmation**: BlueZ generates a passkey and asks for confirmation
- **RequestPasskey**: Agent generates a 6-digit passkey for the user to enter on the host

### Method Details

#### DisplayPasskey (Most Common for Keyboards)

```python
def DisplayPasskey(self, device, passkey: int) -> None:
    # BlueZ tells us what passkey to show the user
    journal.send(f"[agent] DisplayPasskey {device} passkey={passkey:06d}")
    journal.send(f"[agent] *** USER ACTION REQUIRED: Verify passkey {passkey:06d} matches on both devices ***")
```

**Flow**:
1. BlueZ generates random 6-digit passkey
2. Agent logs the passkey
3. User should verify the passkey matches on both devices
4. User confirms on host device

#### RequestPasskey (Agent-Generated Code)

```python
def RequestPasskey(self, device) -> int:
    # Agent generates a random passkey
    import random
    passkey = random.randint(0, 999999)
    journal.send(f"[agent] RequestPasskey for {device} -> GENERATED passkey={passkey:06d}")
    journal.send(f"[agent] *** USER ACTION REQUIRED: Enter passkey {passkey:06d} on the host device ***")
    return passkey
```

**Flow**:
1. Agent generates random 6-digit passkey
2. Agent returns passkey to BlueZ
3. User must enter the passkey on the host device

#### RequestConfirmation (Auto-Accept)

```python
def RequestConfirmation(self, device, passkey: int) -> None:
    # BlueZ asks us to confirm a passkey
    journal.send(f"[agent] RequestConfirmation {device} passkey={passkey:06d} -> AUTO-ACCEPT")
    journal.send(f"[agent] *** Passkey {passkey:06d} was auto-confirmed ***")
    # No exception = "yes"
```

**Flow**:
1. BlueZ generates passkey and asks for confirmation
2. Agent automatically accepts without user intervention
3. Pairing completes automatically

## Agent Behavior

### Previous Issue (Fixed)

**Problem**: The agent's `RequestPasskey` method returned hardcoded `0` (displayed as "000000"):

```python
def RequestPasskey(self, device) -> int:
    journal.send(f"[agent] RequestPasskey for {device} -> using 000000")
    return 0  # WRONG: Always returns 000000
```

This caused confusion when:
- The PC briefly showed a different passkey (from DisplayPasskey or RequestConfirmation)
- But the agent claimed to send "000000"
- Pairing might succeed or fail depending on timing

**Solution**: Generate a proper random passkey:

```python
def RequestPasskey(self, device) -> int:
    import random
    passkey = random.randint(0, 999999)
    journal.send(f"[agent] RequestPasskey for {device} -> GENERATED passkey={passkey:06d}")
    return passkey  # CORRECT: Returns random passkey
```

### Logging Improvements

All agent methods now log clearly:

- **Passkey values** are displayed with 6-digit zero-padding: `passkey=012345`
- **User action required** messages indicate when manual intervention is needed
- **Auto-accept** messages indicate automatic approval

## Diagnostic Tools

### 1. Pairing Diagnostics Script

```bash
sudo ./scripts/diag_pairing.sh
```

**Features**:
- Checks adapter status (powered, discoverable, pairable)
- Verifies agent and backend services are running
- Lists paired devices with connection status
- Shows recent pairing events from agent logs
- Analyzes agent pairing method implementations
- Provides recommendations for fixing issues

### 2. Interactive Pairing Test

```bash
sudo ./scripts/test_pairing.sh [uinput|ble]
```

**Features**:
- Starts required services
- Configures adapter for pairing
- Monitors agent events in real-time
- Highlights passkey displays
- Tests keyboard input after pairing
- Saves full log for later analysis

### 3. General Troubleshooting

```bash
./scripts/diag_troubleshoot.sh
```

**Features**:
- Comprehensive system diagnostics
- Service status checks
- Configuration validation
- Recent pairing events
- Bluetooth helper availability

### 4. BLE-Specific Diagnostics

```bash
sudo /usr/local/bin/ipr_ble_diagnostics.sh
```

**Features**:
- BLE adapter checks
- HID UUID exposure verification
- BLE daemon status
- Recent BLE daemon logs

### 5. Status Overview

```bash
./scripts/diag_status.sh
```

**Features**:
- Current backend configuration
- Service status summary
- Paired devices list
- Adapter information

## Common Issues

### Issue 1: Agent Returns 000000 But PC Shows Different Code

**Symptom**: Agent logs show "using 000000" but PC briefly displays a different 6-digit code.

**Cause**: This was a bug in the agent implementation (fixed).

**Solution**: 
1. Reinstall the agent with the fixed code:
   ```bash
   sudo ./scripts/ble_install_helper.sh
   ```
2. Restart the agent service:
   ```bash
   sudo systemctl restart bt_hid_agent.service
   ```

### Issue 2: Pairing Fails - "Authentication Failed"

**Symptom**: Pairing fails with authentication error.

**Cause**: Agent service not running or not registered.

**Solution**:
1. Check agent status:
   ```bash
   sudo systemctl status bt_hid_agent.service
   ```
2. Check agent logs:
   ```bash
   sudo journalctl -u bt_hid_agent.service -n 50
   ```
3. Ensure agent is running:
   ```bash
   sudo systemctl restart bt_hid_agent.service
   ```

### Issue 3: Pairing Succeeds But Connection Drops

**Symptom**: Device pairs successfully but connection is lost immediately.

**Cause**: Service authorization failing (AuthorizeService not auto-accepting).

**Solution**:
1. Check agent logs for "AuthorizeService" events:
   ```bash
   sudo journalctl -u bt_hid_agent.service | grep -i authorize
   ```
2. Ensure agent accepts HID service authorization:
   ```bash
   # Should see: "[agent] AuthorizeService ... -> ACCEPT"
   ```

### Issue 4: No Passkey Displayed in Logs

**Symptom**: Pairing initiated but no passkey appears in agent logs.

**Cause**: Agent not receiving pairing requests (agent not registered or wrong capability).

**Solution**:
1. Check if agent is registered:
   ```bash
   sudo journalctl -u bt_hid_agent.service | grep -i "registered as default"
   ```
2. Verify agent capability is "KeyboardOnly":
   ```bash
   grep "RegisterAgent.*KeyboardOnly" /usr/local/bin/bt_hid_agent.py
   ```

### Issue 5: Adapter Not Discoverable

**Symptom**: Host device cannot find "ipr-keyboard" during scan.

**Cause**: Adapter not set to discoverable mode.

**Solution**:
1. Enable discoverable mode:
   ```bash
   sudo bluetoothctl discoverable on
   sudo bluetoothctl pairable on
   ```
2. Check adapter status:
   ```bash
   sudo bluetoothctl show | grep -E "Discoverable|Pairable"
   ```

## Backend-Specific Notes

### UInput Backend

**Service**: `bt_hid_uinput.service`

**Pairing Notes**:
- Uses classic Bluetooth HID profile
- Creates virtual keyboard via uinput
- Typically uses DisplayPasskey or RequestConfirmation
- Pairing is more compatible with older devices

**Common Issues**:
- Some hosts may not support uinput-based HID
- May require "Just Works" pairing on some systems

### BLE Backend

**Service**: `bt_hid_ble.service`

**Pairing Notes**:
- Uses Bluetooth Low Energy GATT HID service (UUID 0x1812)
- Advertises as BLE keyboard (Appearance: 0x03C1)
- Requires BlueZ with GATT support (may need `--experimental`)
- Typically uses DisplayPasskey or RequestConfirmation

**Common Issues**:
- Requires bluetoothd with `--experimental` flag on some systems
- Some hosts may not support BLE HID over GATT
- May require adapter with BLE support (Bluetooth 4.0+)

**BLE-Specific Diagnostics**:
```bash
# Check HID UUID exposure
sudo bluetoothctl show | grep -i 00001812

# Check BLE daemon logs
sudo journalctl -u bt_hid_ble.service -n 50

# Run BLE diagnostics
sudo /usr/local/bin/ipr_ble_diagnostics.sh
```

## Monitoring Pairing in Real-Time

To monitor pairing events as they happen:

```bash
# Terminal 1: Monitor agent events
sudo journalctl -u bt_hid_agent.service -f

# Terminal 2: Monitor backend events (uinput or ble)
sudo journalctl -u bt_hid_uinput.service -f
# or
sudo journalctl -u bt_hid_ble.service -f

# Terminal 3: Initiate pairing from host device
```

Look for these log patterns:

```
# Pairing initiated
[agent] RequestPasskey for /org/bluez/hci0/dev_XX_XX_XX_XX_XX_XX -> GENERATED passkey=123456
[agent] *** USER ACTION REQUIRED: Enter passkey 123456 on the host device ***

# Or BlueZ-generated passkey
[agent] DisplayPasskey /org/bluez/hci0/dev_XX_XX_XX_XX_XX_XX passkey=654321
[agent] *** USER ACTION REQUIRED: Verify passkey 654321 matches on both devices ***

# Or auto-confirmation
[agent] RequestConfirmation /org/bluez/hci0/dev_XX_XX_XX_XX_XX_XX passkey=789012 -> AUTO-ACCEPT
[agent] *** Passkey 789012 was auto-confirmed ***

# Service authorization (critical for HID)
[agent] AuthorizeService device=/org/bluez/hci0/dev_XX_XX_XX_XX_XX_XX uuid=00001124-0000-1000-8000-00805f9b34fb -> ACCEPT
```

## Testing Changes

After fixing the agent or making configuration changes:

1. **Reinstall agent** (if code changed):
   ```bash
   sudo ./scripts/ble_install_helper.sh
   ```

2. **Restart services**:
   ```bash
   sudo systemctl restart bt_hid_agent.service
   sudo systemctl restart bt_hid_uinput.service  # or bt_hid_ble.service
   ```

3. **Run diagnostics**:
   ```bash
   sudo ./scripts/diag_pairing.sh
   ```

4. **Test pairing**:
   ```bash
   sudo ./scripts/test_pairing.sh
   ```

5. **Verify in logs**:
   ```bash
   sudo journalctl -u bt_hid_agent.service -n 50
   ```

## References

- [BlueZ Agent API](https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/agent-api.txt)
- [BlueZ D-Bus API](https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/adapter-api.txt)
- [Bluetooth HID Profile](https://www.bluetooth.com/specifications/specs/hid-profile-1-1/)
- [SERVICES.md](SERVICES.md) - Service documentation
- [README.md](README.md) - Project overview

---

**Last Updated**: 2025-12-10
**Agent Version**: Fixed in ble_install_helper.sh with random passkey generation
