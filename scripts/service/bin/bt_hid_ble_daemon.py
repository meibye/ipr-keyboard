#!/usr/bin/env python3
import os
import threading
import time
from collections import deque

import dbus
import dbus.mainloop.glib
import dbus.service
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
    return v


def env_bool(name: str, default: str = "0") -> bool:
    return env_str(name, default).strip() == "1"


BLE_DEBUG = env_bool("BT_BLE_DEBUG", "0")


def log_info(msg: str, always: bool = False):
    if BLE_DEBUG or always:
        journal.send(msg, PRIORITY=getattr(journal, "LOG_INFO", 6))


def log_err(msg: str):
    journal.send(msg, PRIORITY=getattr(journal, "LOG_ERR", 3))


# BlueZ Constants
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

MOD_LSHIFT = 0x02
LETTER_USAGES = {chr(ord("a") + i): 0x04 + i for i in range(26)}
DIGIT_USAGES = {
    str(i): 0x1E + (0 if i == 1 else i - 1 if i > 0 else 9) for i in range(10)
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
    "å": (0x2F, 0),
    "Å": (0x2F, MOD_LSHIFT),
    "æ": (0x33, 0),
    "Æ": (0x33, MOD_LSHIFT),
    "ø": (0x34, 0),
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


def build_kbd_report(mods: int, keycode: int) -> bytes:
    return bytes([mods & 0xFF, 0x00, keycode & 0xFF, 0, 0, 0, 0, 0])


HID_REPORT_MAP = bytes(
    [
        0x05,
        0x01,
        0x09,
        0x06,
        0xA1,
        0x01,
        0x05,
        0x07,
        0x19,
        0xE0,
        0x29,
        0xE7,
        0x15,
        0x00,
        0x25,
        0x01,
        0x75,
        0x01,
        0x95,
        0x08,
        0x81,
        0x02,
        0x95,
        0x01,
        0x75,
        0x08,
        0x81,
        0x01,
        0x95,
        0x06,
        0x75,
        0x08,
        0x15,
        0x00,
        0x25,
        0x65,
        0x19,
        0x00,
        0x29,
        0x65,
        0x81,
        0x00,
        0xC0,
    ]
)


class Application(dbus.service.Object):
    def __init__(self, bus):
        self.path = "/org/bluez/ipr/app"
        self.services = []
        super().__init__(bus, self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(DBUS_OM_IFACE, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        res = {}
        for s in self.services:
            res[s.get_path()] = s.get_properties()
            for c in s.characteristics:
                res[c.get_path()] = c.get_properties()
                for d in c.descriptors:
                    res[d.get_path()] = d.get_properties()
        return res


class Service(dbus.service.Object):
    def __init__(self, bus, index, uuid, primary=True):
        self.path = f"/org/bluez/ipr/service{index}"
        self.bus, self.uuid, self.primary, self.characteristics = bus, uuid, primary, []
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
            }
        }


class Characteristic(dbus.service.Object):
    def __init__(self, bus, index, uuid, flags, service):
        self.path = service.path + f"/char{index}"
        self.bus, self.uuid, self.flags, self.service, self.descriptors = (
            bus,
            uuid,
            flags,
            service,
            [],
        )
        self._value, self.notifying = bytearray(), False
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
                "Value": dbus.Array(self._value, signature="y"),
            }
        }

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        return dbus.Array(self._value, signature="y")

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


class Descriptor(dbus.service.Object):
    def __init__(self, bus, index, uuid, flags, characteristic):
        self.path = characteristic.path + f"/desc{index}"
        self.bus, self.uuid, self.flags, self.characteristic, self._value = (
            bus,
            uuid,
            flags,
            characteristic,
            bytearray(),
        )
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

    @dbus.service.method(GATT_DESC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        return dbus.Array(self._value, signature="y")


class PnpIdCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(bus, index, UUID_PNP_ID, ["read"], service)
        # STABILITY FIX: Use Google Vendor ID (0x00E0)
        self._value = bytearray([0x01, 0xE0, 0x00, 0x01, 0x00, 0x01, 0x00])


class InputReportCharacteristic(Characteristic):
    def __init__(self, bus, index, service, notify_event: threading.Event):
        super().__init__(bus, index, UUID_REPORT, ["read", "notify"], service)
        self.notify_event = notify_event
        self.add_descriptor(Descriptor(bus, 0, UUID_REPORT_REFERENCE, ["read"], self))
        self.descriptors[0]._value = bytearray([0x00, 0x01])

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="")
    def StartNotify(self, options):
        self.notifying = True
        self.notify_event.set()
        log_info("[ble] StartNotify: Windows subscribed", always=True)

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="", out_signature="")
    def StopNotify(self):
        self.notifying = False
        self.notify_event.clear()
        log_info("[ble] StopNotify: Windows unsubscribed", always=True)

    def notify_report(self, report_bytes: bytes):
        if not self.notifying:
            return False
        self._value = bytearray(report_bytes)
        self.PropertiesChanged(
            GATT_CHRC_IFACE, {"Value": dbus.Array(self._value, signature="y")}, []
        )
        return True


class HidService(Service):
    def __init__(self, bus, index, notify_event):
        super().__init__(bus, index, UUID_HID_SERVICE)
        self.add_characteristic(
            Characteristic(bus, 0, UUID_HID_INFORMATION, ["read"], self)
        )
        self.characteristics[0]._value = bytearray([0x11, 0x01, 0x00, 0x02])
        self.add_characteristic(Characteristic(bus, 1, UUID_REPORT_MAP, ["read"], self))
        self.characteristics[1]._value = bytearray(HID_REPORT_MAP)
        self.add_characteristic(
            Characteristic(
                bus, 2, UUID_PROTOCOL_MODE, ["read", "write-without-response"], self
            )
        )
        self.characteristics[2]._value = bytearray([0x01])
        self.input_report = InputReportCharacteristic(bus, 3, self, notify_event)
        self.add_characteristic(self.input_report)


class DeviceInfoService(Service):
    def __init__(self, bus, index):
        super().__init__(bus, index, UUID_DIS_SERVICE)
        self.add_characteristic(PnpIdCharacteristic(bus, 0, self))
        self.add_characteristic(
            Characteristic(bus, 1, UUID_MANUFACTURER, ["read"], self)
        )
        self.characteristics[1]._value = bytearray(
            env_str("BT_MANUFACTURER", "IPR").encode()
        )


class Advertisement(dbus.service.Object):
    def __init__(self, bus, index, service_uuids, local_name):
        self.path = f"/org/bluez/ipr/advertisement{index}"
        self.bus, self.service_uuids, self.local_name = bus, service_uuids, local_name
        super().__init__(bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        return {
            ADVERTISEMENT_IFACE: {
                "Type": "peripheral",
                "ServiceUUIDs": dbus.Array(self.service_uuids, signature="s"),
                "LocalName": self.local_name,
                "Appearance": dbus.UInt16(0x03C1),  # FIX: Keyboard Icon
                "Flags": dbus.Array([dbus.Byte(0x02), dbus.Byte(0x04)], signature="y"),
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        return self.get_properties()[ADVERTISEMENT_IFACE]

    @dbus.service.method(ADVERTISEMENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        os._exit(0)


def fifo_worker(input_report: InputReportCharacteristic, notify_event: threading.Event):
    if not os.path.exists(FIFO_PATH):
        os.mkfifo(FIFO_PATH)
    os.chmod(FIFO_PATH, 0o666)
    q = deque()
    while True:
        try:
            with open(FIFO_PATH, "r") as f:
                for line in f:
                    text = line.rstrip("\n")
                    for ch in text:
                        q.append(ch)
                    while q and notify_event.is_set():
                        ch = q.popleft()
                        code, mods = map_char(ch)
                        if code:
                            input_report.notify_report(build_kbd_report(mods, code))
                            time.sleep(0.01)
                            input_report.notify_report(build_kbd_report(0, 0))
                            time.sleep(0.01)
        except Exception:
            time.sleep(1)


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter_path = "/org/bluez/" + env_str("BT_HCI", "hci0")

    gatt_mgr = dbus.Interface(bus.get_object(BLUEZ, adapter_path), GATT_MANAGER_IFACE)
    adv_mgr = dbus.Interface(bus.get_object(BLUEZ, adapter_path), LE_ADV_MGR_IFACE)

    notify_event = threading.Event()
    app = Application(bus)
    hid = HidService(bus, 1, notify_event)
    dis = DeviceInfoService(bus, 2)
    app.add_service(hid)
    app.add_service(dis)

    adv = Advertisement(
        bus, 0, [UUID_HID_SERVICE], env_str("BT_DEVICE_NAME", "IPR Keyboard")
    )

    gatt_mgr.RegisterApplication(
        app.get_path(),
        {},
        reply_handler=lambda: log_info("[ble] GATT OK"),
        error_handler=lambda e: log_err(f"GATT Err: {e}"),
    )
    adv_mgr.RegisterAdvertisement(
        adv.get_path(),
        {},
        reply_handler=lambda: log_info("[ble] ADV OK"),
        error_handler=lambda e: log_err(f"ADV Err: {e}"),
    )

    threading.Thread(
        target=fifo_worker, args=(hid.input_report, notify_event), daemon=True
    ).start()
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
