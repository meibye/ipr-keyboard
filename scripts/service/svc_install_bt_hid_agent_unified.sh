#!/usr/bin/env bash
#
# svc_install_bt_hid_agent_unified.sh
#
# VERSION: 2026/01/04 20:40:48
# 
# Installs:
#   - Unified BlueZ Agent service for pairing (bt_hid_agent_unified.service)
#   - BLE HID daemon (bt_hid_ble_daemon.py) for HID over GATT keyboard
#
# Features:
#   - Supports --agent-debug and --ble-debug parameters to enable verbose logging
#   - Updates /opt/ipr_common.env with BT_AGENT_DEBUG and BT_BLE_DEBUG accordingly
#   - Ensures correct discoverability for Windows BLE HID pairing
#
# Debugging:
#   BT_AGENT_DEBUG="1"   -> verbose agent logs (otherwise quiet)
#   BT_BLE_DEBUG="1"     -> verbose BLE daemon logs (otherwise concise)
#
# IMPORTANT (Windows visibility):
#   Windows may not list a BLE HID peripheral unless Adapter1.Discoverable is ON.
#   In dual-mode, this can cause Windows to show TWO devices (BR/EDR + BLE).
#   - If BT_CONTROLLER_MODE=le: Discoverable is set ON (safe; no BR/EDR identity)
#   - Else: Discoverable follows BT_ENABLE_CLASSIC_DISCOVERABLE (default off)
#
# Usage:
#   sudo ./scripts/service/svc_install_bt_hid_agent_unified.sh [--agent-debug] [--ble-debug]
#
# category: Service
# purpose: Install unified BlueZ agent and BLE HID daemon
# parameters: --agent-debug,--ble-debug
# sudo: yes

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

AGENT_SERVICE_NAME="bt_hid_agent_unified"
BLE_SERVICE_NAME="bt_hid_ble"
AGENT_BIN="/usr/local/bin/bt_hid_agent_unified.py"
BLE_BIN="/usr/local/bin/bt_hid_ble_daemon.py"

ENV_FILE="/opt/ipr_common.env"
AGENT_UNIT="/etc/systemd/system/${AGENT_SERVICE_NAME}.service"
BLE_UNIT="/etc/systemd/system/${BLE_SERVICE_NAME}.service"

BT_OVERRIDE_DIR="/etc/systemd/system/bluetooth.service.d"
BT_OVERRIDE_FILE="${BT_OVERRIDE_DIR}/override.conf"
BT_MAIN_CONF="/etc/bluetooth/main.conf"

# Parse parameters
AGENT_DEBUG=0
BLE_DEBUG=0
for arg in "$@"; do
  case "$arg" in
    --agent-debug) AGENT_DEBUG=1 ;;
    --ble-debug)   BLE_DEBUG=1 ;;
  esac
done

mkdir -p "$(dirname "$ENV_FILE")"

# Ensure ENV_FILE exists and has sane defaults for stable Windows BLE HID
if [[ ! -f "$ENV_FILE" ]]; then
  cat > "$ENV_FILE" <<EOF
# Common env for IPR BT keyboard services
# Debug
BT_AGENT_DEBUG="0"
BT_BLE_DEBUG="0"

# Prefer LE-only to avoid Windows showing two devices (Classic + BLE)
BT_CONTROLLER_MODE="le"
BT_ENABLE_CLASSIC_DISCOVERABLE="0"

# Adapter to use
BT_HCI="hci0"

# Advertising/local name
BT_DEVICE_NAME="IPR Keyboard (Dev)"

# Device Information Service values
BT_MANUFACTURER="IPR"
BT_MODEL="IPR Keyboard"

# PnP ID (USB VID/PID/VER). Linux Foundation defaults are fine for testing.
BT_USB_VID="0x1234"
BT_USB_PID="0x5678"
BT_USB_VER="0x0100"
EOF
fi

# Update debug flags in ENV_FILE
if grep -q '^BT_AGENT_DEBUG=' "$ENV_FILE"; then
  sed -i 's/^BT_AGENT_DEBUG=.*/BT_AGENT_DEBUG="'$AGENT_DEBUG'"/' "$ENV_FILE"
else
  echo 'BT_AGENT_DEBUG="'$AGENT_DEBUG'"' >> "$ENV_FILE"
fi

if grep -q '^BT_BLE_DEBUG=' "$ENV_FILE"; then
  sed -i 's/^BT_BLE_DEBUG=.*/BT_BLE_DEBUG="'$BLE_DEBUG'"/' "$ENV_FILE"
else
  echo 'BT_BLE_DEBUG="'$BLE_DEBUG'"' >> "$ENV_FILE"
fi

# ------------------------------------------------------------------------------
# Bluetooth daemon plugin minimization (stability / remove "unknown display")
# Keep only what BLE HID over GATT needs:
#   - hog (HID over GATT)
#   - gap (advertising / GAP)
#   - scanparam (LE scan parameters)
#   - battery (optional; harmless, used by some hosts)
#
# Disable:
#   - a2dp,avrcp,bap (audio/media)
#   - network (PAN)
#   - input (classic HID)
#   - midi
#   - neard,health,deviceinfo,sap
#   - gamepad plugins (sixaxis, wiimote)
#   - autopair (can fight your custom agent)
#
#    OLD: sap,avrcp,a2dp,network,input,health,midi,battery,bap,neard,wiimote,sixaxis,autopair,deviceinfo,hostname
# ------------------------------------------------------------------------------
mkdir -p "$BT_OVERRIDE_DIR"

# Ensure Experimental=true in main.conf (some BlueZ builds require it for LE GATT/advertising)
if [[ -f "$BT_MAIN_CONF" ]] && ! grep -q '^Experimental=true' "$BT_MAIN_CONF"; then
  if grep -q '^\[General\]' "$BT_MAIN_CONF"; then
    sed -i '/^\[General\]/a Experimental=true' "$BT_MAIN_CONF"
  else
    printf '\n[General]\nExperimental=true\n' >> "$BT_MAIN_CONF"
  fi
fi

echo "=== [svc_install_bt_hid_agent_unified] Writing $BT_OVERRIDE_FILE ==="
cat > "$BT_OVERRIDE_FILE" <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/libexec/bluetooth/bluetoothd --experimental --noplugin=sap,avrcp,a2dp,network,input,midi,neard,wiimote,sixaxis,autopair,hostname,bap
ConfigurationDirectoryMode=0755
EOF

# ------------------------------------------------------------------------------
# Write Unified Agent
# - Forces adapter into stable state: Powered/Pairable/Discoverable, timeouts=0
# - Sets Alias from BT_DEVICE_NAME (helps Windows caching)
# - Trusts the device on RequestAuthorization/RequestConfirmation
# ------------------------------------------------------------------------------
echo "=== [svc_install_bt_hid_agent_unified] Writing $AGENT_BIN ==="
cat > "$AGENT_BIN" << 'PYEOF'
#!/usr/bin/env python3
import os
import sys
import argparse
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

BLUEZ = "org.bluez"
AGENT_MGR_IFACE = "org.bluez.AgentManager1"
AGENT_IFACE = "org.bluez.Agent1"
PROP_IFACE = "org.freedesktop.DBus.Properties"
OM_IFACE = "org.freedesktop.DBus.ObjectManager"

ADAPTER_IFACE = "org.bluez.Adapter1"
DEVICE_IFACE = "org.bluez.Device1"

def env_clean(name: str, default: str = "") -> str:
    v = os.environ.get(name, default)
    if v is None:
        return default
    v = str(v).strip()
    if " #" in v:
        v = v.split(" #", 1)[0].strip()
    if "\t#" in v:
        v = v.split("\t#", 1)[0].strip()
    return v

def dev_short(path: str) -> str:
    return path.split("/")[-1] if path else "<?>"

def find_adapter(bus, prefer="hci0") -> str:
    om = dbus.Interface(bus.get_object(BLUEZ, "/"), OM_IFACE)
    objects = om.GetManagedObjects()

    for path, ifaces in objects.items():
        if ADAPTER_IFACE in ifaces and path.endswith(prefer):
            return path

    for path, ifaces in objects.items():
        if ADAPTER_IFACE in ifaces:
            return path

    raise RuntimeError("No BlueZ adapter found")

def set_adapter_ready(bus, adapter_path: str, verbose: bool = False):
    props = dbus.Interface(bus.get_object(BLUEZ, adapter_path), PROP_IFACE)

    # Always ensure powered/pairable
    props.Set(ADAPTER_IFACE, "Powered", dbus.Boolean(True))
    props.Set(ADAPTER_IFACE, "Pairable", dbus.Boolean(True))

    # Timeouts = 0 => keep it pairable/discoverable until you stop services
    try:
        props.Set(ADAPTER_IFACE, "PairableTimeout", dbus.UInt32(0))
    except Exception:
        pass
    try:
        props.Set(ADAPTER_IFACE, "DiscoverableTimeout", dbus.UInt32(0))
    except Exception:
        pass

    # Set Alias to reduce Windows cache weirdness
    alias = env_clean("BT_DEVICE_NAME", "")
    if alias:
        try:
            props.Set(ADAPTER_IFACE, "Alias", dbus.String(alias))
        except Exception:
            pass

    controller_mode = env_clean("BT_CONTROLLER_MODE", "le").lower()  # le/dual/bredr
    enable_classic = env_clean("BT_ENABLE_CLASSIC_DISCOVERABLE", "0")

    if verbose:
        print(f"[agent] BT_CONTROLLER_MODE={controller_mode} BT_ENABLE_CLASSIC_DISCOVERABLE={enable_classic}", flush=True)

    # For LE HID + Windows: make adapter discoverable.
    # In LE-only mode this should not create a BR/EDR “second device”.
    if controller_mode == "le":
        try:
            props.Set(ADAPTER_IFACE, "Discoverable", dbus.Boolean(True))
        except Exception:
            pass
    else:
        # Dual/BREDR: default OFF unless explicitly enabled.
        if enable_classic == "1":
            try:
                props.Set(ADAPTER_IFACE, "Discoverable", dbus.Boolean(True))
            except Exception:
                pass
        else:
            try:
                props.Set(ADAPTER_IFACE, "Discoverable", dbus.Boolean(False))
            except Exception:
                pass

def trust_device(bus, device_path: str, verbose: bool = False):
    try:
        props = dbus.Interface(bus.get_object(BLUEZ, device_path), PROP_IFACE)
        props.Set(DEVICE_IFACE, "Trusted", dbus.Boolean(True))
        if verbose:
            print(f"[agent] Trusted set for {dev_short(device_path)}", flush=True)
    except Exception as e:
        if verbose:
            print(f"[agent] Trust set failed for {dev_short(device_path)}: {e}", flush=True)

class Agent(dbus.service.Object):
    def __init__(self, bus, path="/ipr/agent", mode="nowinpasskey", fixed_pin="0000", verbose=True):
        super().__init__(bus, path)
        self.bus = bus
        self.path = path
        self.mode = mode
        self.fixed_pin = fixed_pin
        self.verbose = verbose

    def log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)

    # @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
    # def RequestPinCode(self, device):
    #     d = dev_short(device)
    #     if self.mode == "fixedpin":
    #         self.log(f"[agent] RequestPinCode for {d} -> fixed pin {self.fixed_pin}")
    #         return self.fixed_pin
    #     self.log(f"[agent] RequestPinCode for {d} -> returning 0000")
    #     return "0000"

    # @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
    # def RequestPasskey(self, device):
    #     d = dev_short(device)
    #     if self.mode == "fixedpin":
    #         pk = int(self.fixed_pin)
    #         self.log(f"[agent] RequestPasskey for {d} -> fixed passkey {pk}")
    #         return dbus.UInt32(pk)
    #     # For your "no win passkey" mode, keep it deterministic.
    #     self.log(f"[agent] RequestPasskey for {d} -> returning 0")
    #     return dbus.UInt32(0)

    # @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    # def DisplayPasskey(self, device, passkey):
    #     d = dev_short(device)
    #     self.log(f"[agent] DisplayPasskey({d}) passkey={int(passkey):06d}")

    # @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    # def DisplayPinCode(self, device, pincode):
    #     d = dev_short(device)
    #     self.log(f"[agent] DisplayPinCode({d}) pin={pincode}")

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        d = dev_short(device)
        self.log(f"[agent] RequestConfirmation({d}) passkey={int(passkey):06d} -> accepting + trusting")
        trust_device(self.bus, device, verbose=self.verbose)
        return

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        d = dev_short(device)
        self.log(f"[agent] RequestAuthorization({d}) -> accepting + trusting")
        trust_device(self.bus, device, verbose=self.verbose)
        return

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        d = dev_short(device)
        self.log(f"[agent] AuthorizeService({d}) uuid={uuid} -> accepting")
        # Trust here too (some stacks call this instead)
        trust_device(self.bus, device, verbose=self.verbose)
        return

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Cancel(self):
        self.log("[agent] Cancel()")
        return

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["nowinpasskey", "fixedpin"], default="nowinpasskey")
    ap.add_argument("--fixed-pin", default="0000")
    ap.add_argument("--capability", default="NoInputNoOutput")
    ap.add_argument("--agent-path", default="/ipr/agent")
    ap.add_argument("--adapter", default="hci0")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    env_dbg = env_clean("BT_AGENT_DEBUG", "0")
    verbose = (not args.quiet) or (env_dbg == "1")

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter = find_adapter(bus, args.adapter)
    set_adapter_ready(bus, adapter, verbose=verbose)

    agent = Agent(
        bus=bus,
        path=args.agent_path,
        mode=args.mode,
        fixed_pin=args.fixed_pin,
        verbose=verbose,
    )

    mgr = dbus.Interface(bus.get_object(BLUEZ, "/org/bluez"), AGENT_MGR_IFACE)

    try:
        mgr.UnregisterAgent(args.agent_path)
    except Exception:
        pass

    mgr.RegisterAgent(args.agent_path, args.capability)
    mgr.RequestDefaultAgent(args.agent_path)

    print(f"[agent] Registered. mode={args.mode} capability={args.capability} adapter={adapter} verbose={verbose}", flush=True)
    GLib.MainLoop().run()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
PYEOF
chmod +x "$AGENT_BIN"

# ------------------------------------------------------------------------------
# Write BLE HID daemon
# - Buffers FIFO text until StartNotify happens (Windows subscribed)
# - Avoid log spam for every dropped key while unsubscribed
# ------------------------------------------------------------------------------
echo "=== [svc_install_bt_hid_agent_unified] Writing $BLE_BIN ==="
cat > "$BLE_BIN" << 'PYEOF'
#!/usr/bin/env python3
"""
bt_hid_ble_daemon.py - BLE HID over GATT keyboard daemon.

Key fixes for your current symptoms:
  - Buffer FIFO input until Windows subscribes to Input Report notifications
    (StartNotify). This stops: "InputReport not notifying yet; dropping report".
  - PropertiesChanged is emitted as a SIGNAL (required for notifications).
"""

import os
import sys
import time
import threading
from collections import deque

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

try:
    from systemd import journal
except ImportError:
    class DummyJournal:
        LOG_INFO = 6
        LOG_ERR = 3
        @staticmethod
        def send(msg, **kwargs):
            print(msg, flush=True)
    journal = DummyJournal()

def env_str(name: str, default: str = "") -> str:
    v = os.environ.get(name, default)
    if v is None:
        return default
    v = str(v).strip()
    if " #" in v:
        v = v.split(" #", 1)[0].rstrip()
    if "\t#" in v:
        v = v.split("\t#", 1)[0].rstrip()
    return v

def env_bool(name: str, default: str = "0") -> bool:
    return env_str(name, default).strip() == "1"

BLE_DEBUG = env_bool("BT_BLE_DEBUG", "0")

def log_info(msg: str, always: bool = False):
    if BLE_DEBUG or always:
        journal.send(msg, PRIORITY=getattr(journal, "LOG_INFO", 6))

def log_err(msg: str):
    journal.send(msg, PRIORITY=getattr(journal, "LOG_ERR", 3))

BLUEZ = "org.bluez"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"

GATT_MANAGER_IFACE = "org.bluez.GattManager1"
LE_ADV_MGR_IFACE = "org.bluez.LEAdvertisingManager1"

GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
GATT_DESC_IFACE = "org.bluez.GattDescriptor1"
ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"

FIFO_PATH = "/run/ipr_bt_keyboard_fifo"
NOTIFY_FLAG_PATH = "/run/ipr_bt_keyboard_notifying"

# UUIDs
UUID_HID_SERVICE = "1812"
UUID_HID_INFORMATION = "2a4a"
UUID_REPORT_MAP = "2a4b"
UUID_HID_CONTROL_POINT = "2a4c"
UUID_REPORT = "2a4d"
UUID_PROTOCOL_MODE = "2a4e"
UUID_REPORT_REFERENCE = "2908"

UUID_DIS_SERVICE = "180a"
UUID_PNP_ID = "2a50"
UUID_MANUFACTURER = "2a29"
UUID_MODEL_NUMBER = "2a24"

# HID modifier bits
MOD_LSHIFT = 0x02

LETTER_USAGES = {chr(ord('a') + i): 0x04 + i for i in range(26)}
DIGIT_USAGES = {
    "1": 0x1E, "2": 0x1F, "3": 0x20, "4": 0x21, "5": 0x22,
    "6": 0x23, "7": 0x24, "8": 0x25, "9": 0x26, "0": 0x27,
}
PUNCT = {
    " ": (0x2C, 0),
    "\n": (0x28, 0),
    "\r": (0x28, 0),
    "\t": (0x2B, 0),
    "-": (0x2D, 0),
    "_": (0x2D, MOD_LSHIFT),
}
SPECIAL_DK = {
    "å": (0x2F, 0), "Å": (0x2F, MOD_LSHIFT),
    "æ": (0x33, 0), "Æ": (0x33, MOD_LSHIFT),
    "ø": (0x34, 0), "Ø": (0x34, MOD_LSHIFT),
}

def map_char(ch: str):
    if ch in PUNCT:
        return PUNCT[ch]
    if ch in DIGIT_USAGES:
        return (DIGIT_USAGES[ch], 0)
    if ch in SPECIAL_DK:
        return SPECIAL_DK[ch]
    if ch in LETTER_USAGES:
        return (LETTER_USAGES[ch], 0)
    if ch.lower() in LETTER_USAGES and ch.isupper():
        return (LETTER_USAGES[ch.lower()], MOD_LSHIFT)
    return (0, 0)

def build_kbd_report(mods: int, keycode: int) -> bytes:
    return bytes([mods & 0xFF, 0x00, keycode & 0xFF, 0, 0, 0, 0, 0])

HID_REPORT_MAP = bytes([
    0x05, 0x01, 0x09, 0x06, 0xA1, 0x01,
    0x05, 0x07, 0x19, 0xE0, 0x29, 0xE7,
    0x15, 0x00, 0x25, 0x01, 0x75, 0x01,
    0x95, 0x08, 0x81, 0x02,
    0x95, 0x01, 0x75, 0x08, 0x81, 0x01,
    0x95, 0x06, 0x75, 0x08, 0x15, 0x00,
    0x25, 0x65, 0x19, 0x00, 0x29, 0x65,
    0x81, 0x00,
    0xC0
])

class Application(dbus.service.Object):
    def __init__(self, bus):
        self.path = "/org/bluez/ipr/app"
        self.services = []
        super().__init__(bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(DBUS_OM_IFACE, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        response = {}
        for s in self.services:
            response[s.get_path()] = s.get_properties()
            for c in s.characteristics:
                response[c.get_path()] = c.get_properties()
                for d in c.descriptors:
                    response[d.get_path()] = d.get_properties()
        return response

class Service(dbus.service.Object):
    def __init__(self, bus, index, uuid, primary=True):
        self.path = f"/org/bluez/ipr/service{index}"
        self.bus = bus
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []
        super().__init__(bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_characteristic(self, chrc):
        self.characteristics.append(chrc)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                "UUID": self.uuid,
                "Primary": dbus.Boolean(self.primary),
                "Characteristics": dbus.Array([c.get_path() for c in self.characteristics], signature="o"),
            }
        }

class Characteristic(dbus.service.Object):
    def __init__(self, bus, index, uuid, flags, service):
        self.path = service.path + f"/char{index}"
        self.bus = bus
        self.uuid = uuid
        self.flags = flags
        self.service = service
        self.descriptors = []
        self._value = bytearray()
        self.notifying = False
        super().__init__(bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_descriptor(self, desc):
        self.descriptors.append(desc)

    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                "Service": self.service.get_path(),
                "UUID": self.uuid,
                "Flags": dbus.Array(self.flags, signature="s"),
                "Descriptors": dbus.Array([d.get_path() for d in self.descriptors], signature="o"),
                "Value": dbus.Array(self._value, signature="y"),
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_CHRC_IFACE:
            raise dbus.exceptions.DBusException("org.freedesktop.DBus.Error.InvalidArgs", "Invalid interface")
        return self.get_properties()[GATT_CHRC_IFACE]

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        value = bytes(self._value)
        offset = int(options.get("offset", 0)) if isinstance(options, dict) else 0
        if offset > len(value):
            raise dbus.exceptions.DBusException(
                "org.bluez.Error.InvalidOffset", "Invalid offset"
            )
        return dbus.Array(value[offset:], signature="y")

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}", out_signature="")
    def WriteValue(self, value, options):
        self._value = bytearray(value)

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="")
    def StartNotify(self, options):
        self.notifying = True

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="", out_signature="")
    def StopNotify(self):
        self.notifying = False

    @dbus.service.signal(DBUS_PROP_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    def _emit_properties_changed(self, changed_dict):
        self.PropertiesChanged(GATT_CHRC_IFACE, changed_dict, [])

class Descriptor(dbus.service.Object):
    def __init__(self, bus, index, uuid, flags, characteristic):
        self.path = characteristic.path + f"/desc{index}"
        self.bus = bus
        self.uuid = uuid
        self.flags = flags
        self.characteristic = characteristic
        self._value = bytearray()
        super().__init__(bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        return {
            GATT_DESC_IFACE: {
                "Characteristic": self.characteristic.get_path(),
                "UUID": self.uuid,
                "Flags": dbus.Array(self.flags, signature="s"),
                "Value": dbus.Array(self._value, signature="y"),
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_DESC_IFACE:
            raise dbus.exceptions.DBusException("org.freedesktop.DBus.Error.InvalidArgs", "Invalid interface")
        return self.get_properties()[GATT_DESC_IFACE]

    @dbus.service.method(GATT_DESC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        return dbus.Array(self._value, signature="y")

class ReportReferenceDescriptor(Descriptor):
    def __init__(self, bus, index, characteristic, report_id: int, report_type: int):
        super().__init__(bus, index, UUID_REPORT_REFERENCE, ["read"], characteristic)
        self._value = bytearray([report_id & 0xFF, report_type & 0xFF])

class HidInformationCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_HID_INFORMATION, ["read"], service)
        self._value = bytearray([0x11, 0x01, 0x00, 0x02])  # HID 1.11, country=0, flags=0x02

class ReportMapCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_REPORT_MAP, ["read"], service)
        self._value = bytearray(HID_REPORT_MAP)

class ProtocolModeCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_PROTOCOL_MODE, ["read", "write-without-response"], service)
        self._value = bytearray([0x01])  # Report Protocol

class HidControlPointCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_HID_CONTROL_POINT, ["write-without-response"], service)
        self._value = bytearray([0x00])

class InputReportCharacteristic(Characteristic):
    def __init__(self, bus, index, service, notify_event: threading.Event):
        super().__init__(bus, index, UUID_REPORT, ["read", "notify"], service)
        self._value = bytearray(build_kbd_report(0, 0))
        self.notify_event = notify_event
        self.add_descriptor(ReportReferenceDescriptor(bus, 0, self, report_id=0, report_type=1))

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="")
    def StartNotify(self, options):
        self.notifying = True
        self.notify_event.set()
        try:
            with open(NOTIFY_FLAG_PATH, "w", encoding="utf-8") as f:
                f.write("1\n")
        except Exception:
            pass
        log_info("[ble] InputReport StartNotify (Windows subscribed)", always=True)


    @dbus.service.method(GATT_CHRC_IFACE, in_signature="", out_signature="")
    def StopNotify(self):
        self.notifying = False
        self.notify_event.clear()
        try:
            os.unlink(NOTIFY_FLAG_PATH)
        except FileNotFoundError:
            pass
        except Exception:
            pass
        log_info("[ble] InputReport StopNotify (Windows unsubscribed)", always=True)


    def notify_report(self, report_bytes: bytes):
        if not self.notifying:
            return False
        self._value = bytearray(report_bytes)
        self._emit_properties_changed({"Value": dbus.Array(self._value, signature="y")})
        return True

class HidService(Service):
    def __init__(self, bus, index, notify_event: threading.Event):
        super().__init__(bus, index, UUID_HID_SERVICE, primary=True)
        self.hid_info = HidInformationCharacteristic(bus, 0, self)
        self.report_map = ReportMapCharacteristic(bus, 1, self)
        self.protocol_mode = ProtocolModeCharacteristic(bus, 2, self)
        self.control_point = HidControlPointCharacteristic(bus, 3, self)
        self.input_report = InputReportCharacteristic(bus, 4, self, notify_event)

        self.add_characteristic(self.hid_info)
        self.add_characteristic(self.report_map)
        self.add_characteristic(self.protocol_mode)
        self.add_characteristic(self.control_point)
        self.add_characteristic(self.input_report)

class ReadOnlyStringCharacteristic(Characteristic):
    def __init__(self, bus, index, uuid, value_str, service):
        super().__init__(bus, index, uuid, ["read"], service)
        self._value = bytearray(value_str.encode("utf-8"))

class PnpIdCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_PNP_ID, ["read"], service)
        vid = int(env_str("BT_USB_VID", "0x1D6B"), 0)
        pid = int(env_str("BT_USB_PID", "0x0246"), 0)
        ver = int(env_str("BT_USB_VER", "0x0100"), 0)
        self._value = bytearray([
            0x02,
            vid & 0xFF, (vid >> 8) & 0xFF,
            pid & 0xFF, (pid >> 8) & 0xFF,
            ver & 0xFF, (ver >> 8) & 0xFF,
        ])
        if BLE_DEBUG:
            log_info(f"[ble] PnpIdCharacteristic bytes: {list(self._value)}")

class DeviceInfoService(Service):
    def __init__(self, bus, index):
        super().__init__(bus, index, UUID_DIS_SERVICE, primary=True)
        self.pnp = PnpIdCharacteristic(bus, 0, self)
        self.mfg = ReadOnlyStringCharacteristic(bus, 1, UUID_MANUFACTURER, env_str("BT_MANUFACTURER", "IPR"), self)
        self.model = ReadOnlyStringCharacteristic(bus, 2, UUID_MODEL_NUMBER, env_str("BT_MODEL", "IPR Keyboard"), self)
        self.add_characteristic(self.pnp)
        self.add_characteristic(self.mfg)
        self.add_characteristic(self.model)

class Advertisement(dbus.service.Object):
    def __init__(self, bus, index, adv_type, service_uuids, local_name, appearance):
        self.path = f"/org/bluez/ipr/advertisement{index}"
        self.bus = bus
        self.ad_type = adv_type
        self.service_uuids = service_uuids
        self.local_name = local_name
        self.appearance = appearance
        super().__init__(bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        return {
            ADVERTISEMENT_IFACE: {
                "Type": self.ad_type,
                "ServiceUUIDs": dbus.Array(self.service_uuids, signature="s"),
                "Flags": dbus.Array([dbus.Byte(0x02), dbus.Byte(0x04)], signature="y"),  # general + BR/EDR not supported
                "LocalName": self.local_name,
                "Appearance": dbus.UInt16(self.appearance),
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != ADVERTISEMENT_IFACE:
            raise dbus.exceptions.DBusException("org.freedesktop.DBus.Error.InvalidArgs", "Invalid interface")
        return self.get_properties()[ADVERTISEMENT_IFACE]

    @dbus.service.method(ADVERTISEMENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        log_info("[ble] Advertisement released -> exiting for restart", always=True)
        os._exit(0)


def ensure_fifo():
    if not os.path.exists(FIFO_PATH):
        os.mkfifo(FIFO_PATH)
        os.chmod(FIFO_PATH, 0o666)

def pick_adapter_path(bus, prefer="hci0") -> str:
    om = dbus.Interface(bus.get_object(BLUEZ, "/"), DBUS_OM_IFACE)
    objects = om.GetManagedObjects()
    for path, ifaces in objects.items():
        if "org.bluez.Adapter1" in ifaces and path.endswith(prefer):
            return path
    for path, ifaces in objects.items():
        if "org.bluez.Adapter1" in ifaces:
            return path
    raise RuntimeError("No Bluetooth adapter found (org.bluez.Adapter1)")

def on_err(tag: str):
    def _h(e):
        log_err(f"[ble][ERROR] {tag}: {e}")
    return _h

def on_ok(msg: str):
    def _h(*args, **kwargs):
        log_info(msg, always=True)
    return _h

def fifo_worker(input_report: InputReportCharacteristic, notify_event: threading.Event):
    ensure_fifo()
    log_info(f"[ble] FIFO ready at {FIFO_PATH}", always=True)

    # Queue characters received before StartNotify.
    q = deque()
    q_max = 2048
    last_drop_log = 0.0

    def enqueue_text(s: str):
        nonlocal last_drop_log
        for ch in s:
            if len(q) >= q_max:
                # Drop oldest to keep "latest" data
                q.popleft()
                now = time.time()
                if now - last_drop_log > 2.0:
                    log_info("[ble] FIFO queue full; dropping oldest buffered chars (waiting for StartNotify)", always=True)
                    last_drop_log = now
            q.append(ch)

    def flush_queue():
        # Drain queue respecting notify state.
        while q and notify_event.is_set():
            ch = q.popleft()
            keycode, mods = map_char(ch)
            if keycode == 0:
                continue
            ok = input_report.notify_report(build_kbd_report(mods, keycode))
            if ok:
                time.sleep(0.008)
                input_report.notify_report(build_kbd_report(0, 0))
                time.sleep(0.008)
            else:
                # Lost notify mid-flight: put char back and stop.
                q.appendleft(ch)
                break

    while True:
        try:
            with open(FIFO_PATH, "r", encoding="utf-8") as fifo:
                for line in fifo:
                    text = line.rstrip("\n")
                    if not text:
                        continue
                    log_info(f"[ble] FIFO received: {text!r}", always=True)

                    enqueue_text(text)

                    # Wait briefly for subscription; if not, keep buffering.
                    if not notify_event.is_set():
                        notify_event.wait(timeout=1.5)

                    if notify_event.is_set():
                        flush_queue()
                    else:
                        # Don’t spam per-key logs; one line per message is enough.
                        log_info("[ble] Waiting for InputReport StartNotify; buffered text (not dropped).", always=True)

        except Exception as ex:
            log_err(f"[ble][ERROR] FIFO worker exception: {ex}")
            time.sleep(1.0)

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter_path = pick_adapter_path(bus, prefer=env_str("BT_HCI", "hci0"))

    gatt_mgr = dbus.Interface(bus.get_object(BLUEZ, adapter_path), GATT_MANAGER_IFACE)
    adv_mgr = dbus.Interface(bus.get_object(BLUEZ, adapter_path), LE_ADV_MGR_IFACE)

    notify_event = threading.Event()

    app = Application(bus)
    hid_service = HidService(bus, 1, notify_event)
    dis_service = DeviceInfoService(bus, 2)

    app.add_service(hid_service)
    app.add_service(dis_service)

    adv = Advertisement(
        bus=bus,
        index=0,
        adv_type="peripheral",
        service_uuids=[UUID_HID_SERVICE],
        local_name=env_str("BT_DEVICE_NAME", "IPR Keyboard"),
        appearance=0x03C1,  # Keyboard
    )

    log_info("[ble] Starting BLE HID daemon...", always=True)
    log_info(f"[ble] Advertising LocalName='{env_str('BT_DEVICE_NAME', 'IPR Keyboard')}'", always=True)
    log_info(f"[ble] Debug BT_BLE_DEBUG={'1' if BLE_DEBUG else '0'}", always=True)

    log_info("[ble] Registering GATT application...", always=True)
    gatt_mgr.RegisterApplication(
        app.get_path(), {},
        reply_handler=on_ok("[ble] GATT application registered"),
        error_handler=on_err("RegisterApplication"),
    )

    log_info("[ble] Registering advertisement...", always=True)
    adv_mgr.RegisterAdvertisement(
        adv.get_path(), {},
        reply_handler=on_ok("[ble] Advertisement registered"),
        error_handler=on_err("RegisterAdvertisement"),
    )

    t = threading.Thread(target=fifo_worker, args=(hid_service.input_report, notify_event), daemon=True)
    t.start()

    log_info("[ble] BLE HID ready. Waiting for Windows connection + StartNotify...", always=True)
    GLib.MainLoop().run()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
PYEOF
chmod +x "$BLE_BIN"

# ------------------------------------------------------------------------------
# systemd units
# - Restart=always: BLE can get "released" or transient failures
# - PartOf=bluetooth.service: keep them aligned with bluetooth restarts
# ------------------------------------------------------------------------------
echo "=== [svc_install_bt_hid_agent_unified] Writing service unit: $AGENT_UNIT ==="
cat > "$AGENT_UNIT" << EOF
[Unit]
Description=IPR Keyboard Unified BlueZ Agent
After=bluetooth.service
Requires=bluetooth.service
BindsTo=bluetooth.service

[Service]
Type=simple
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${AGENT_SERVICE_NAME}
EnvironmentFile=-${ENV_FILE}
ExecStartPre=/usr/bin/btmgmt -i ${BT_HCI:-hci0} le on
ExecStartPre=/usr/bin/btmgmt -i ${BT_HCI:-hci0} bredr off
ExecStartPre=/usr/bin/btmgmt -i ${BT_HCI:-hci0} advertising on
ExecStart=/usr/bin/python3 -u ${AGENT_BIN} --mode nowinpasskey --capability NoInputNoOutput --adapter \${BT_HCI:-hci0}
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target bluetooth.service
EOF

echo "=== [svc_install_bt_hid_agent_unified] Writing service unit: $BLE_UNIT ==="
cat > "$BLE_UNIT" << EOF
[Unit]
Description=IPR Keyboard BLE HID Daemon
After=bt_hid_agent_unified.service bluetooth.service
Requires=bt_hid_agent_unified.service bluetooth.service
BindsTo=bluetooth.service

[Service]
Type=simple
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${BLE_SERVICE_NAME}
EnvironmentFile=-${ENV_FILE}
ExecStart=/usr/bin/python3 -u ${BLE_BIN}
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target bluetooth.service
EOF

systemctl daemon-reload
systemctl enable "${AGENT_SERVICE_NAME}.service" >/dev/null 2>&1 || true
systemctl enable "${BLE_SERVICE_NAME}.service" >/dev/null 2>&1 || true

echo "=== [svc_install_bt_hid_agent_unified] Done ==="
echo ""
echo "Next steps (important):"
echo "  1) Restart bluetooth to apply plugin drop-in:"
echo "     sudo systemctl restart bluetooth"
echo "  2) Restart services:"
echo "     sudo systemctl restart ${AGENT_SERVICE_NAME}.service"
echo "     sudo systemctl restart ${BLE_SERVICE_NAME}.service"
echo ""
echo "Verify:"
echo "  sudo systemctl status bluetooth ${AGENT_SERVICE_NAME}.service ${BLE_SERVICE_NAME}.service -n 30"
echo "  sudo journalctl -u ${AGENT_SERVICE_NAME}.service -n 120 --no-pager"
echo "  sudo journalctl -u ${BLE_SERVICE_NAME}.service -n 200 --no-pager"
echo ""
echo "If you want debug logs, set in ${ENV_FILE}:"
echo "  BT_AGENT_DEBUG=\"1\""
echo "  BT_BLE_DEBUG=\"1\""
