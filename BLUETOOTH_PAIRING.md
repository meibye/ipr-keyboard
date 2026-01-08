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

The ipr-keyboard system uses a BlueZ agent to handle Bluetooth pairing requests automatically. The agent is implemented in `bt_hid_agent_unified.py` and runs as the `bt_hid_agent_unified.service` systemd service.

### Pairing Flow

1. **Discovery**: Host device (PC/phone) scans for Bluetooth devices
2. **Connection Request**: Host initiates connection to "IPR Keyboard"
3. **Pairing Request**: BlueZ invokes agent methods to handle authentication
4. **Service Authorization**: Agent approves HID profile connection
5. **Connection Established**: Devices are paired and ready for use

## Pairing Methods

BlueZ supports several pairing methods. The agent capability determines which methods are used:

### Agent Capabilities

The ipr-keyboard agent is registered with **"NoInputNoOutput"** capability, which implements **"Just Works"** pairing:

- **No passkey display or entry required** - Pairing happens automatically
- **RequestConfirmation**: Agent automatically accepts BlueZ-generated passkey
- **AuthorizeService**: Agent automatically authorizes HID service connection
- **Optimal for HID keyboards** - No user interaction needed, especially with Windows 11

### Method Details

#### RequestConfirmation (Auto-Accept - "Just Works" Pairing)

```python
def RequestConfirmation(self, device, passkey: int) -> None:
    # BlueZ asks us to confirm a passkey - we auto-accept for "Just Works"
    self.log(f"[agent] RequestConfirmation({d}) passkey={int(passkey):06d} -> accepting + trusting")
    trust_device(self.bus, device, verbose=self.verbose)
    return  # No exception = "yes"
```

**Flow**:
1. BlueZ generates passkey and asks for confirmation
2. Agent automatically accepts without user intervention
3. Agent also marks device as "Trusted" for seamless reconnection
4. Pairing completes automatically - **no user action required**

This is the **recommended approach for BLE HID keyboards** with Windows 11 as it provides a seamless pairing experience without requiring the user to enter or verify passkeys.

#### AuthorizeService (Auto-Accept)

```python
def AuthorizeService(self, device, uuid):
    d = dev_short(device)
    self.log(f"[agent] AuthorizeService({d}) uuid={uuid} -> accepting")
    trust_device(self.bus, device, verbose=self.verbose)
    return  # No exception = authorized
```

**Flow**:
1. Host requests authorization to use HID service (UUID 00001124-...)
2. Agent automatically accepts the service authorization
3. Device is marked as "Trusted"
4. HID connection is established

This is **critical** for HID profile to work - if this fails, device pairs but cannot send keyboard input.

## Agent Behavior

### Current Implementation ("Just Works" Pairing)

The ipr-keyboard agent uses **NoInputNoOutput** capability for seamless "Just Works" pairing:

**Key Features:**
- **No passkey display**: Agent doesn't have a display to show passkeys
- **No passkey entry**: Agent doesn't have input capability for entering passkeys  
- **Automatic acceptance**: All pairing requests are auto-accepted via RequestConfirmation
- **Service authorization**: HID service access is automatically approved
- **Device trusting**: Paired devices are marked as "Trusted" for auto-reconnect

**Why "Just Works" for HID Keyboards?**

This is the recommended approach for BLE HID keyboards because:
1. **Windows 11 compatibility**: Works reliably with Windows 11 Bluetooth stack
2. **Seamless UX**: No user interaction required - just pair and use
3. **Secure enough**: Physical proximity required, BLE encryption enabled
4. **No UI needed**: Perfect for headless Raspberry Pi keyboard emulator
5. **Avoids confusion**: No passkeys to enter or verify

### Service Unit Configuration

The agent service (`bt_hid_agent_unified.service`) is configured with:

```bash
ExecStart=/usr/bin/python3 -u /usr/local/bin/bt_hid_agent_unified.py \
  --mode nowinpasskey \
  --capability NoInputNoOutput \
  --adapter ${BT_HCI:-hci0}
```

### BLE-Only Mode

The service also configures the adapter for BLE-only operation:

```bash
ExecStartPre=/bin/sh -c '/usr/bin/btmgmt -i "${BT_HCI:-hci0}" le on'
ExecStartPre=/bin/sh -c '/usr/bin/btmgmt -i "${BT_HCI:-hci0}" bredr off'
```

This ensures:
- Windows doesn't see two devices (BR/EDR classic + BLE)
- Only one "IPR Keyboard" appears in Bluetooth settings
- BLE HID over GATT is used (optimal for modern systems)

### Logging

All agent methods log their activity to the systemd journal:

```
# Pairing initiated with "Just Works"
[agent] RequestConfirmation(dev_XX_XX_XX_XX_XX_XX) passkey=123456 -> accepting + trusting
[agent] Trusted set for dev_XX_XX_XX_XX_XX_XX

# Service authorization (critical for HID)
[agent] AuthorizeService(dev_XX_XX_XX_XX_XX_XX) uuid=00001124-0000-1000-8000-00805f9b34fb -> accepting
```

**Note**: The passkey shown in RequestConfirmation is generated by BlueZ but is NOT displayed to the user in "Just Works" mode. The agent simply logs it for debugging purposes and auto-accepts.

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
- Shows "Just Works" auto-acceptance
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

### Issue 1: Pairing Fails - "Authentication Failed"

**Symptom**: Pairing fails with authentication error.

**Cause**: Agent service not running or not registered.

**Solution**:
1. Check agent status:
   ```bash
   sudo systemctl status bt_hid_agent_unified.service
   ```
2. Check agent logs:
   ```bash
   sudo journalctl -u bt_hid_agent_unified.service -n 50
   ```
3. Ensure agent is running:
   ```bash
   sudo systemctl restart bt_hid_agent_unified.service
   ```

### Issue 2: Pairing Succeeds But Connection Drops

**Symptom**: Device pairs successfully but connection is lost immediately.

**Cause**: Service authorization failing (AuthorizeService not auto-accepting).

**Solution**:
1. Check agent logs for "AuthorizeService" events:
   ```bash
   sudo journalctl -u bt_hid_agent_unified.service | grep -i authorize
   ```
2. Ensure agent accepts HID service authorization:
   ```bash
   # Should see: "[agent] AuthorizeService ... -> accepting"
   ```

### Issue 3: No Agent Activity in Logs

**Symptom**: Pairing initiated but no agent logs appear.

**Cause**: Agent not receiving pairing requests (agent not registered or wrong capability).

**Solution**:
1. Check if agent is registered:
   ```bash
   sudo journalctl -u bt_hid_agent_unified.service | grep -i "registered"
   ```
2. Verify agent capability is "NoInputNoOutput":
   ```bash
   systemctl cat bt_hid_agent_unified.service | grep capability
   # Should show: --capability NoInputNoOutput
   ```

### Issue 4: Adapter Not Discoverable

**Symptom**: Host device cannot find "IPR Keyboard" during scan.

**Cause**: Adapter not set to discoverable mode or BLE advertising not active.

**Solution**:
1. Check BLE daemon status:
   ```bash
   sudo systemctl status bt_hid_ble.service
   ```
2. Verify advertising is active:
   ```bash
   sudo journalctl -u bt_hid_ble.service | grep -i "advertisement registered"
   ```
3. Check adapter status:
   ```bash
   sudo bluetoothctl show | grep -E "Powered|Discoverable"
   ```

### Issue 5: Windows Shows Two Devices

**Symptom**: Windows Bluetooth settings shows two "IPR Keyboard" devices (one classic, one BLE).

**Cause**: Controller mode is set to "dual" instead of "le" (BLE-only).

**Solution**:
1. Check controller mode in agent service:
   ```bash
   sudo journalctl -u bt_hid_agent_unified.service -n 5 | grep "le on"
   ```
2. Ensure /opt/ipr_common.env has correct setting:
   ```bash
   grep BT_CONTROLLER_MODE /opt/ipr_common.env
   # Should show: BT_CONTROLLER_MODE="le"
   ```
3. Restart agent to apply:
   ```bash
   sudo systemctl restart bt_hid_agent_unified.service
   ```

## Backend-Specific Notes

### UInput Backend

**Service**: `bt_hid_uinput.service`

**Pairing Notes**:
- Uses classic Bluetooth HID profile
- Creates virtual keyboard via uinput
- Uses "Just Works" pairing with NoInputNoOutput capability
- Pairing is compatible with older devices
- May work better with some non-Windows hosts

**Common Issues**:
- Some hosts may not support uinput-based HID
- Classic Bluetooth may conflict with BLE mode if controller not configured correctly

### BLE Backend (Recommended for Windows 11)

**Service**: `bt_hid_ble.service`

**Pairing Notes**:
- Uses Bluetooth Low Energy GATT HID service (UUID 0x1812)
- Advertises as BLE keyboard (Appearance: 0x03C1)
- Requires BlueZ with GATT support (may need `--experimental`)
- Uses "Just Works" pairing with NoInputNoOutput capability
- **Optimal for Windows 11** - most reliable pairing experience

**Common Issues**:
- Requires bluetoothd with `--experimental` flag on some systems (handled automatically)
- Some hosts may not support BLE HID over GATT (rare with modern systems)
- May require adapter with BLE support (Bluetooth 4.0+, standard on Raspberry Pi 3/4/Zero 2 W)

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
sudo journalctl -u bt_hid_agent_unified.service -f

# Terminal 2: Monitor BLE backend events
sudo journalctl -u bt_hid_ble.service -f

# Terminal 3: Initiate pairing from host device (Windows 11 PC)
```

Look for these log patterns:

```
# Agent registered and ready
[agent] Registered. mode=nowinpasskey capability=NoInputNoOutput adapter=/org/bluez/hci0 verbose=False

# Pairing initiated with "Just Works"
[agent] RequestConfirmation(dev_XX_XX_XX_XX_XX_XX) passkey=123456 -> accepting + trusting
[agent] Trusted set for dev_XX_XX_XX_XX_XX_XX

# Service authorization (critical for HID)
[agent] AuthorizeService(dev_XX_XX_XX_XX_XX_XX) uuid=00001124-0000-1000-8000-00805f9b34fb -> accepting

# BLE daemon confirms connection
[ble] InputReport StartNotify (Windows subscribed)
```

**Note**: With "Just Works" pairing, you won't see passkey prompts or user action messages. The entire pairing process happens automatically.

## Testing Changes

After making configuration changes or updating services:

1. **Restart agent** (always needed after config changes):
   ```bash
   sudo systemctl restart bt_hid_agent_unified.service
   ```

2. **Restart BLE daemon** (if using BLE backend):
   ```bash
   sudo systemctl restart bt_hid_ble.service
   ```

3. **Run diagnostics**:
   ```bash
   sudo ./scripts/diag_pairing.sh
   ```

4. **Test pairing from Windows 11**:
   - Open Settings → Bluetooth & devices
   - Click "Add device" → Bluetooth
   - Select "IPR Keyboard" from list
   - Wait for automatic pairing (no passkey required)
   - Device should connect immediately

5. **Verify in logs**:
   ```bash
   sudo journalctl -u bt_hid_agent_unified.service -n 50
   sudo journalctl -u bt_hid_ble.service -n 50
   ```

6. **Test keyboard input**:
   ```bash
   echo "Hello from Raspberry Pi" | bt_kb_send "$(cat -)"
   ```
   Text should appear on paired Windows 11 PC.

## References

- [BlueZ Agent API](https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/agent-api.txt)
- [BlueZ D-Bus API](https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/adapter-api.txt)
- [Bluetooth HID Profile](https://www.bluetooth.com/specifications/specs/hid-profile-1-1/)
- [Bluetooth Core Spec - Security (Just Works)](https://www.bluetooth.com/specifications/specs/core-specification/)
- [SERVICES.md](SERVICES.md) - Service documentation
- [README.md](README.md) - Project overview

---

**Last Updated**: 2026-01-07  
**Agent Version**: bt_hid_agent_unified.py with NoInputNoOutput capability ("Just Works" pairing)  
**Recommended for**: Windows 11, macOS, modern Linux, iOS, Android
