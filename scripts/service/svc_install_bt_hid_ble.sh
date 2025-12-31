#!/usr/bin/env bash
#
# svc_install_bt_hid_ble.sh
#
# Installs the bt_hid_ble service and daemon.
# This service provides a BLE HID over GATT keyboard backend.
#
# Usage:
#   sudo ./scripts/service/svc_install_bt_hid_ble.sh
#
# Prerequisites:
#   - Must be run as root
#
# category: Service
# purpose: Install BLE HID over GATT backend service
# sudo: yes
#
set -euo pipefail

BLE_DAEMON="/usr/local/bin/bt_hid_ble_daemon.py"
SERVICE_UNIT="/etc/systemd/system/bt_hid_ble.service"
ENV_FILE="/opt/ipr_common.env"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

echo "=== [svc_install_bt_hid_ble] Writing $BLE_DAEMON ==="
cat > "$BLE_DAEMON" << 'EOF'
#!/usr/bin/env python3
"""
bt_hid_ble_daemon.py

BLE HID over GATT keyboard daemon.

Fixes included:
  - Registers a VALID HID service (0x1812) with required characteristics so
    BlueZ won't fail with: org.bluez.Error.Failed: No object received
  - Registers an LE advertisement using BT_DEVICE_NAME from /opt/ipr_common.env
    with safe env parsing (strips inline comments).
  - Reads /run/ipr_bt_keyboard_fifo and sends keystrokes as HID input reports.

Notes:
  - This is a minimal, working HID-over-GATT keyboard.
  - Character mapping is intentionally limited (letters, digits, space, enter, tab,
    and Danish å/æ/ø). You can extend later.
"""

import os
import sys
import time
import threading
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
    """
    Read env var and strip accidental inline comments like:
      BT_DEVICE_NAME="IPR Keyboard"  # comment
    because systemd EnvironmentFile can treat that comment as part of the value.
    """
    v = os.environ.get(name, default)
    if v is None:
        return default
    v = str(v).strip()
    if " #" in v:
        v = v.split(" #", 1)[0].rstrip()
    if "\t#" in v:
        v = v.split("\t#", 1)[0].rstrip()
    return v

BLUEZ_SERVICE_NAME = "org.bluez"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"

GATT_MANAGER_IFACE = "org.bluez.GattManager1"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"

GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
GATT_DESC_IFACE = "org.bluez.GattDescriptor1"

ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"

FIFO_PATH = "/run/ipr_bt_keyboard_fifo"

# HID Service/Characteristic UUIDs
UUID_HID_SERVICE        = "1812"
UUID_HID_INFORMATION    = "2a4a"
UUID_REPORT_MAP         = "2a4b"
UUID_HID_CONTROL_POINT  = "2a4c"
UUID_REPORT             = "2a4d"
UUID_PROTOCOL_MODE      = "2a4e"
UUID_REPORT_REFERENCE   = "2908"

# HID constants: modifier bits
MOD_LCTRL  = 0x01
MOD_LSHIFT = 0x02
MOD_LALT   = 0x04
MOD_LGUI   = 0x08
MOD_RCTRL  = 0x10
MOD_RSHIFT = 0x20
MOD_RALT   = 0x40
MOD_RGUI   = 0x80

# Minimal character mapping (extend later)
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
}

# Danish letters assuming Windows host uses Danish layout
# å/æ/ø correspond to physical keys in US positions: [ ; '
SPECIAL_DK = {
    "å": (0x2F, 0),             # [ key
    "Å": (0x2F, MOD_LSHIFT),
    "æ": (0x33, 0),             # ; key
    "Æ": (0x33, MOD_LSHIFT),
    "ø": (0x34, 0),             # ' key
    "Ø": (0x34, MOD_LSHIFT),
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

# --- BlueZ GATT framework (Application/Service/Characteristic/Descriptor) ---

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
    PATH_BASE = "/org/bluez/ipr/service"
    def __init__(self, bus, index, uuid, primary=True):
        self.path = self.PATH_BASE + str(index)
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
        self.path = service.path + "/char" + str(index)
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
            raise dbus.exceptions.DBusException(
                "org.freedesktop.DBus.Error.InvalidArgs", "Invalid interface"
            )
        return self.get_properties()[GATT_CHRC_IFACE]

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        return dbus.Array(self._value, signature="y")

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}", out_signature="")
    def WriteValue(self, value, options):
        # default: store it
        self._value = bytearray(value)

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="")
    def StartNotify(self, options):
        self.notifying = True

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="", out_signature="")
    def StopNotify(self):
        self.notifying = False

    def _emit_properties_changed(self, changed_dict):
        props_iface = dbus.Interface(self, DBUS_PROP_IFACE)
        props_iface.PropertiesChanged(GATT_CHRC_IFACE, changed_dict, [])

class Descriptor(dbus.service.Object):
    def __init__(self, bus, index, uuid, flags, characteristic):
        self.path = characteristic.path + "/desc" + str(index)
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
            raise dbus.exceptions.DBusException(
                "org.freedesktop.DBus.Error.InvalidArgs", "Invalid interface"
            )
        return self.get_properties()[GATT_DESC_IFACE]

    @dbus.service.method(GATT_DESC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        return dbus.Array(self._value, signature="y")

    @dbus.service.method(GATT_DESC_IFACE, in_signature="aya{sv}", out_signature="")
    def WriteValue(self, value, options):
        self._value = bytearray(value)

# --- LE Advertisement ---

class Advertisement(dbus.service.Object):
    PATH_BASE = "/org/bluez/ipr/advertisement"
    def __init__(self, bus, index, advertising_type, service_uuids, local_name, appearance):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.ad_type = advertising_type
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
                "LocalName": self.local_name,
                "Appearance": dbus.UInt16(self.appearance),
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != ADVERTISEMENT_IFACE:
            raise dbus.exceptions.DBusException(
                "org.freedesktop.DBus.Error.InvalidArgs", "Invalid interface"
            )
        return self.get_properties()[ADVERTISEMENT_IFACE]

    @dbus.service.method(ADVERTISEMENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        journal.send("[ble] Advertisement released", PRIORITY=journal.LOG_INFO)

# --- HID implementation ---

# Standard keyboard report (8 bytes): modifiers, reserved, 6 keycodes
def build_kbd_report(mods: int, keycode: int) -> bytes:
    return bytes([mods & 0xFF, 0x00, keycode & 0xFF, 0, 0, 0, 0, 0])

# HID Report Map for a basic keyboard (no Report ID; single input report)
# This is the standard pattern used by many BLE HID keyboard examples.
HID_REPORT_MAP = bytes([
    0x05, 0x01,       # Usage Page (Generic Desktop)
    0x09, 0x06,       # Usage (Keyboard)
    0xA1, 0x01,       # Collection (Application)
    0x05, 0x07,       #   Usage Page (Keyboard/Keypad)
    0x19, 0xE0,       #   Usage Minimum (224)
    0x29, 0xE7,       #   Usage Maximum (231)
    0x15, 0x00,       #   Logical Minimum (0)
    0x25, 0x01,       #   Logical Maximum (1)
    0x75, 0x01,       #   Report Size (1)
    0x95, 0x08,       #   Report Count (8)
    0x81, 0x02,       #   Input (Data,Var,Abs) ; Modifier byte
    0x95, 0x01,       #   Report Count (1)
    0x75, 0x08,       #   Report Size (8)
    0x81, 0x01,       #   Input (Const,Array,Abs) ; Reserved byte
    0x95, 0x06,       #   Report Count (6)
    0x75, 0x08,       #   Report Size (8)
    0x15, 0x00,       #   Logical Minimum (0)
    0x25, 0x65,       #   Logical Maximum (101)
    0x19, 0x00,       #   Usage Minimum (0)
    0x29, 0x65,       #   Usage Maximum (101)
    0x81, 0x00,       #   Input (Data,Array) ; Key arrays (6 bytes)
    0xC0              # End Collection
])

class HidInformationCharacteristic(Characteristic):
    # HID Information (2A4A): bcdHID (0x0111), bCountryCode (0), Flags (0x02 = normally connectable)
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_HID_INFORMATION, ["read"], service)
        self._value = bytearray([0x11, 0x01, 0x00, 0x02])

class ReportMapCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_REPORT_MAP, ["read"], service)
        self._value = bytearray(HID_REPORT_MAP)

class ProtocolModeCharacteristic(Characteristic):
    # 0x01 = Report Protocol
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_PROTOCOL_MODE, ["read", "write-without-response"], service)
        self._value = bytearray([0x01])

class HidControlPointCharacteristic(Characteristic):
    # Accept suspend/exit suspend (0/1) - store only.
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_HID_CONTROL_POINT, ["write-without-response"], service)
        self._value = bytearray([0x00])

class ReportReferenceDescriptor(Descriptor):
    # 0x2908: [Report ID, Report Type]
    # Report Type: 1 = Input Report, 2 = Output Report, 3 = Feature Report
    def __init__(self, bus, index, characteristic, report_id: int, report_type: int):
        super().__init__(bus, index, UUID_REPORT_REFERENCE, ["read"], characteristic)
        self._value = bytearray([report_id & 0xFF, report_type & 0xFF])

class InputReportCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_REPORT, ["read", "notify"], service)
        self._value = bytearray(build_kbd_report(0, 0))
        # Report Reference: ID=1, Type=Input
        self.add_descriptor(ReportReferenceDescriptor(bus, 0, self, report_id=1, report_type=1))

    def notify_report(self, report_bytes: bytes):
        if not self.notifying:
            return
        self._value = bytearray(report_bytes)
        self._emit_properties_changed({"Value": dbus.Array(self._value, signature="y")})

class HidService(Service):
    def __init__(self, bus, index):
        super().__init__(bus, index, UUID_HID_SERVICE, primary=True)

        self.hid_info = HidInformationCharacteristic(bus, 0, self)
        self.report_map = ReportMapCharacteristic(bus, 1, self)
        self.protocol_mode = ProtocolModeCharacteristic(bus, 2, self)
        self.control_point = HidControlPointCharacteristic(bus, 3, self)
        self.input_report = InputReportCharacteristic(bus, 4, self)

        self.add_characteristic(self.hid_info)
        self.add_characteristic(self.report_map)
        self.add_characteristic(self.protocol_mode)
        self.add_characteristic(self.control_point)
        self.add_characteristic(self.input_report)

def ensure_fifo():
    if not os.path.exists(FIFO_PATH):
        os.mkfifo(FIFO_PATH)
        os.chmod(FIFO_PATH, 0o666)

def pick_adapter_path(bus) -> str:
    om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, "/"), DBUS_OM_IFACE)
    objects = om.GetManagedObjects()
    for path, ifaces in objects.items():
        if "org.bluez.Adapter1" in ifaces:
            return path
    raise RuntimeError("No Bluetooth adapter found (org.bluez.Adapter1)")

def on_err(tag: str):
    def _h(e):
        journal.send(f"[ble][ERROR] {tag}: {e}", PRIORITY=getattr(journal, "LOG_ERR", 3))
    return _h

def on_ok(msg: str):
    def _h(*args, **kwargs):
        journal.send(msg, PRIORITY=journal.LOG_INFO)
    return _h

def fifo_worker(input_report: InputReportCharacteristic):
    ensure_fifo()
    journal.send(f"[ble] FIFO ready at {FIFO_PATH}", PRIORITY=journal.LOG_INFO)

    while True:
        try:
            with open(FIFO_PATH, "r", encoding="utf-8") as fifo:
                for line in fifo:
                    text = line.rstrip("\n")
                    if not text:
                        continue
                    journal.send(f"[ble] FIFO received: {text!r}", PRIORITY=journal.LOG_INFO)
                    for ch in text:
                        keycode, mods = map_char(ch)
                        if keycode == 0:
                            continue
                        # key down
                        input_report.notify_report(build_kbd_report(mods, keycode))
                        time.sleep(0.008)
                        # key up
                        input_report.notify_report(build_kbd_report(0, 0))
                        time.sleep(0.008)
        except Exception as ex:
            journal.send(f"[ble][ERROR] FIFO worker exception: {ex}", PRIORITY=getattr(journal, "LOG_ERR", 3))
            time.sleep(1.0)

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter_path = pick_adapter_path(bus)

    gatt_mgr = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path), GATT_MANAGER_IFACE)
    adv_mgr = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter_path), LE_ADVERTISING_MANAGER_IFACE)

    app = Application(bus)
    hid_service = HidService(bus, 0)
    app.add_service(hid_service)

    adv = Advertisement(
        bus=bus,
        index=0,
        advertising_type="peripheral",
        service_uuids=[UUID_HID_SERVICE],
        local_name=env_str("BT_DEVICE_NAME", "IPR Keyboard"),
        appearance=0x03C1,  # Keyboard
    )

    journal.send("[ble] Starting BLE HID daemon...", PRIORITY=journal.LOG_INFO)
    journal.send(f"[ble] Advertising LocalName='{env_str('BT_DEVICE_NAME', 'IPR Keyboard')}'", PRIORITY=journal.LOG_INFO)

    journal.send("[ble] Registering GATT application...", PRIORITY=journal.LOG_INFO)
    gatt_mgr.RegisterApplication(
        app.get_path(), {},
        reply_handler=on_ok("[ble] GATT application registered"),
        error_handler=on_err("RegisterApplication"),
    )

    journal.send("[ble] Registering advertisement...", PRIORITY=journal.LOG_INFO)
    adv_mgr.RegisterAdvertisement(
        adv.get_path(), {},
        reply_handler=on_ok("[ble] Advertisement registered"),
        error_handler=on_err("RegisterAdvertisement"),
    )

    # Start FIFO thread (report notifications only work when client enabled notifications)
    t = threading.Thread(target=fifo_worker, args=(hid_service.input_report,), daemon=True)
    t.start()

    journal.send("[ble] BLE HID ready. Waiting for connections and FIFO input...", PRIORITY=journal.LOG_INFO)
    GLib.MainLoop().run()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
EOF

chmod +x "$BLE_DAEMON"

echo "=== [svc_install_bt_hid_ble] Writing systemd unit: $SERVICE_UNIT ==="
cat > "$SERVICE_UNIT" << EOF
[Unit]
Description=IPR Keyboard BLE HID Daemon
After=bluetooth.target
Requires=bluetooth.target

[Service]
Type=simple
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${BLE_DAEMON}
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable bt_hid_ble.service

echo "=== [svc_install_bt_hid_ble] Installation complete ==="
echo "Now run:"
echo "  sudo systemctl restart bt_hid_ble.service"
echo "Then watch logs:"
echo "  journalctl -u bt_hid_ble.service -n 200 --no-pager"
