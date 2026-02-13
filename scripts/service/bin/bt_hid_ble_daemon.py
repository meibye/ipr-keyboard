#!/usr/bin/env python3
import argparse
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


def env_hex_int(name: str, default: int) -> int:
    raw = env_str(name, "")
    if not raw:
        return default
    try:
        return int(raw, 0)
    except ValueError:
        return default


BLE_DEBUG = env_bool("BT_BLE_DEBUG", "0")


def log_info(msg: str, always: bool = False) -> None:
    if BLE_DEBUG or always:
        journal.send(msg, PRIORITY=getattr(journal, "LOG_INFO", 6))


def log_err(msg: str) -> None:
    journal.send(msg, PRIORITY=getattr(journal, "LOG_ERR", 3))


# BlueZ constants
BLUEZ = "org.bluez"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"
ADAPTER_IFACE = "org.bluez.Adapter1"
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
UUID_BOOT_KEYBOARD_INPUT_REPORT = "2a22"
UUID_BOOT_KEYBOARD_OUTPUT_REPORT = "2a32"
UUID_REPORT_REFERENCE = "2908"

UUID_DIS_SERVICE = "180a"
UUID_PNP_ID = "2a50"
UUID_MANUFACTURER = "2a29"
UUID_MODEL_NUMBER = "2a24"

UUID_BATTERY_SERVICE = "180f"
UUID_BATTERY_LEVEL = "2a19"

# HID keyboard appearance
APPEARANCE_KEYBOARD = 0x03C1

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


# Report protocol descriptor with input + output report (keyboard LEDs).
HID_REPORT_MAP = bytes(
    [
        0x05,
        0x01,  # Usage Page (Generic Desktop)
        0x09,
        0x06,  # Usage (Keyboard)
        0xA1,
        0x01,  # Collection (Application)
        0x05,
        0x07,  #   Usage Page (Key Codes)
        0x19,
        0xE0,  #   Usage Minimum (224)
        0x29,
        0xE7,  #   Usage Maximum (231)
        0x15,
        0x00,  #   Logical Minimum (0)
        0x25,
        0x01,  #   Logical Maximum (1)
        0x75,
        0x01,  #   Report Size (1)
        0x95,
        0x08,  #   Report Count (8)
        0x81,
        0x02,  #   Input (Data, Variable, Absolute) - Modifier byte
        0x95,
        0x01,  #   Report Count (1)
        0x75,
        0x08,  #   Report Size (8)
        0x81,
        0x01,  #   Input (Constant) - Reserved byte
        0x95,
        0x05,  #   Report Count (5)
        0x75,
        0x01,  #   Report Size (1)
        0x05,
        0x08,  #   Usage Page (LEDs)
        0x19,
        0x01,  #   Usage Minimum (1)
        0x29,
        0x05,  #   Usage Maximum (5)
        0x91,
        0x02,  #   Output (Data, Variable, Absolute) - LED report
        0x95,
        0x01,  #   Report Count (1)
        0x75,
        0x03,  #   Report Size (3)
        0x91,
        0x01,  #   Output (Constant) - LED padding
        0x95,
        0x06,  #   Report Count (6)
        0x75,
        0x08,  #   Report Size (8)
        0x15,
        0x00,  #   Logical Minimum (0)
        0x25,
        0x65,  #   Logical Maximum (101)
        0x05,
        0x07,  #   Usage Page (Key Codes)
        0x19,
        0x00,  #   Usage Minimum (0)
        0x29,
        0x65,  #   Usage Maximum (101)
        0x81,
        0x00,  #   Input (Data, Array) - Key array
        0xC0,  # End Collection
    ]
)


class InvalidArgsException(dbus.DBusException):
    _dbus_error_name = "org.freedesktop.DBus.Error.InvalidArgs"


class NotPermittedException(dbus.DBusException):
    _dbus_error_name = "org.bluez.Error.NotPermitted"


def has_flag(flags, options) -> bool:
    return any(opt in flags for opt in options)


class NotifyState:
    def __init__(self):
        self._lock = threading.Lock()
        self._count = 0
        self.event = threading.Event()

    def acquire(self) -> None:
        with self._lock:
            self._count += 1
            self.event.set()

    def release(self) -> None:
        with self._lock:
            self._count = max(0, self._count - 1)
            if self._count == 0:
                self.event.clear()


class Application(dbus.service.Object):
    def __init__(self, bus):
        self.path = "/org/bluez/ipr/app"
        self.services = []
        super().__init__(bus, self.path)

    def add_service(self, service):
        self.services.append(service)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(DBUS_OM_IFACE, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            for chrc in service.characteristics:
                response[chrc.get_path()] = chrc.get_properties()
                for desc in chrc.descriptors:
                    response[desc.get_path()] = desc.get_properties()
        return response


class Service(dbus.service.Object):
    def __init__(self, bus, index, uuid, primary=True):
        self.path = f"/org/bluez/ipr/service{index}"
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
                "UUID": dbus.String(self.uuid),
                "Primary": dbus.Boolean(self.primary),
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_SERVICE_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[GATT_SERVICE_IFACE]


class Characteristic(dbus.service.Object):
    def __init__(self, bus, index, uuid, flags, service):
        self.path = service.path + f"/char{index}"
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
                "UUID": dbus.String(self.uuid),
                "Flags": dbus.Array(self.flags, signature="s"),
                "Value": dbus.Array(self._value, signature="y"),
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_CHRC_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[GATT_CHRC_IFACE]

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        if not has_flag(
            self.flags,
            ["read", "encrypt-read", "encrypt-authenticated-read", "secure-read"],
        ):
            raise NotPermittedException()
        return dbus.Array(self._value, signature="y")

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}", out_signature="")
    def WriteValue(self, value, options):
        if not has_flag(
            self.flags,
            [
                "write",
                "write-without-response",
                "encrypt-write",
                "encrypt-authenticated-write",
                "secure-write",
            ],
        ):
            raise NotPermittedException()
        self._value = bytearray(value)

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="", out_signature="")
    def StartNotify(self):
        if not has_flag(
            self.flags,
            ["notify", "indicate", "encrypt-notify", "encrypt-indicate"],
        ):
            raise NotPermittedException()
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
                "UUID": dbus.String(self.uuid),
                "Flags": dbus.Array(self.flags, signature="s"),
                "Value": dbus.Array(self._value, signature="y"),
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_DESC_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[GATT_DESC_IFACE]

    @dbus.service.method(GATT_DESC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        return dbus.Array(self._value, signature="y")


class StaticValueCharacteristic(Characteristic):
    def __init__(self, bus, index, uuid, flags, service, value: bytes):
        super().__init__(bus, index, uuid, flags, service)
        self._value = bytearray(value)


class ProtocolModeCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(
            bus,
            index,
            UUID_PROTOCOL_MODE,
            ["read", "write-without-response"],
            service,
        )
        # 0x00 = Boot Protocol, 0x01 = Report Protocol
        self.mode = 0x01
        self._value = bytearray([self.mode])

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}", out_signature="")
    def WriteValue(self, value, options):
        if len(value) != 1:
            raise InvalidArgsException()
        mode = int(value[0])
        if mode not in (0x00, 0x01):
            raise InvalidArgsException()
        self.mode = mode
        self._value = bytearray([mode])
        log_info(f"[ble] Protocol mode set: {mode}", always=True)


class HidControlPointCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(
            bus, index, UUID_HID_CONTROL_POINT, ["write-without-response"], service
        )
        self.suspended = False

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}", out_signature="")
    def WriteValue(self, value, options):
        if len(value) != 1:
            raise InvalidArgsException()
        # 0x00 = Suspend, 0x01 = Exit Suspend
        self.suspended = int(value[0]) == 0x00
        state = "suspend" if self.suspended else "resume"
        log_info(f"[ble] HID control point: {state}", always=True)


class InputReportCharacteristic(Characteristic):
    def __init__(self, bus, index, service, notify_state: NotifyState, report_id: int):
        super().__init__(
            bus,
            index,
            UUID_REPORT,
            ["read", "notify", "encrypt-read", "encrypt-notify"],
            service,
        )
        self.notify_state = notify_state
        self._value = bytearray(build_kbd_report(0, 0))
        self.add_descriptor(Descriptor(bus, 0, UUID_REPORT_REFERENCE, ["read"], self))
        self.descriptors[0]._value = bytearray([report_id & 0xFF, 0x01])

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="", out_signature="")
    def StartNotify(self):
        self.notifying = True
        self.notify_state.acquire()
        log_info("[ble] Input report notify enabled", always=True)

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="", out_signature="")
    def StopNotify(self):
        self.notifying = False
        self.notify_state.release()
        log_info("[ble] Input report notify disabled", always=True)

    def notify_report(self, report_bytes: bytes) -> bool:
        if not self.notifying:
            return False
        self._value = bytearray(report_bytes)
        self.PropertiesChanged(
            GATT_CHRC_IFACE,
            {"Value": dbus.Array(self._value, signature="y")},
            [],
        )
        return True


class OutputReportCharacteristic(Characteristic):
    def __init__(self, bus, index, service, report_id: int):
        super().__init__(
            bus,
            index,
            UUID_REPORT,
            [
                "read",
                "write",
                "write-without-response",
                "encrypt-read",
                "encrypt-write",
            ],
            service,
        )
        self.led_mask = 0
        self._value = bytearray([0x00])
        self.add_descriptor(Descriptor(bus, 0, UUID_REPORT_REFERENCE, ["read"], self))
        self.descriptors[0]._value = bytearray([report_id & 0xFF, 0x02])

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}", out_signature="")
    def WriteValue(self, value, options):
        if len(value) < 1:
            raise InvalidArgsException()
        self.led_mask = int(value[0]) & 0x1F
        self._value = bytearray([self.led_mask])
        log_info(f"[ble] LED output report: 0x{self.led_mask:02X}")


class BootKeyboardInputCharacteristic(Characteristic):
    def __init__(self, bus, index, service, notify_state: NotifyState):
        super().__init__(
            bus,
            index,
            UUID_BOOT_KEYBOARD_INPUT_REPORT,
            ["read", "notify", "encrypt-read", "encrypt-notify"],
            service,
        )
        self.notify_state = notify_state
        self._value = bytearray(build_kbd_report(0, 0))

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="", out_signature="")
    def StartNotify(self):
        self.notifying = True
        self.notify_state.acquire()
        log_info("[ble] Boot input notify enabled", always=True)

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="", out_signature="")
    def StopNotify(self):
        self.notifying = False
        self.notify_state.release()
        log_info("[ble] Boot input notify disabled", always=True)

    def notify_report(self, report_bytes: bytes) -> bool:
        if not self.notifying:
            return False
        self._value = bytearray(report_bytes)
        self.PropertiesChanged(
            GATT_CHRC_IFACE,
            {"Value": dbus.Array(self._value, signature="y")},
            [],
        )
        return True


class BootKeyboardOutputCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(
            bus,
            index,
            UUID_BOOT_KEYBOARD_OUTPUT_REPORT,
            [
                "read",
                "write",
                "write-without-response",
                "encrypt-read",
                "encrypt-write",
            ],
            service,
        )
        self._value = bytearray([0x00])

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}", out_signature="")
    def WriteValue(self, value, options):
        if len(value) < 1:
            raise InvalidArgsException()
        self._value = bytearray([int(value[0]) & 0x1F])


class HidService(Service):
    def __init__(self, bus, index, notify_state: NotifyState):
        super().__init__(bus, index, UUID_HID_SERVICE)

        hid_info = StaticValueCharacteristic(
            bus,
            0,
            UUID_HID_INFORMATION,
            ["read"],
            self,
            bytes(
                [0x11, 0x01, 0x00, 0x03]
            ),  # HID v1.11, country=0, remote wake + normally connectable
        )
        self.add_characteristic(hid_info)

        report_map = StaticValueCharacteristic(
            bus,
            1,
            UUID_REPORT_MAP,
            ["read", "encrypt-read"],
            self,
            HID_REPORT_MAP,
        )
        self.add_characteristic(report_map)

        self.control_point = HidControlPointCharacteristic(bus, 2, self)
        self.add_characteristic(self.control_point)

        self.protocol_mode = ProtocolModeCharacteristic(bus, 3, self)
        self.add_characteristic(self.protocol_mode)

        self.input_report = InputReportCharacteristic(
            bus, 4, self, notify_state, report_id=1
        )
        self.add_characteristic(self.input_report)

        self.output_report = OutputReportCharacteristic(bus, 5, self, report_id=1)
        self.add_characteristic(self.output_report)

        self.boot_input = BootKeyboardInputCharacteristic(bus, 6, self, notify_state)
        self.add_characteristic(self.boot_input)

        self.boot_output = BootKeyboardOutputCharacteristic(bus, 7, self)
        self.add_characteristic(self.boot_output)

    def notify_key_report(self, report: bytes) -> bool:
        # Report mode host should use Input Report characteristic.
        if self.protocol_mode.mode == 0x00:
            return self.boot_input.notify_report(
                report
            ) or self.input_report.notify_report(report)
        return self.input_report.notify_report(report) or self.boot_input.notify_report(
            report
        )


class DeviceInfoService(Service):
    def __init__(self, bus, index):
        super().__init__(bus, index, UUID_DIS_SERVICE)

        manufacturer = env_str("BT_MANUFACTURER", "IPR")
        model = env_str("BT_MODEL", "IPR Keyboard")

        vid = env_hex_int("BT_USB_VID", 0x1209) & 0xFFFF
        pid = env_hex_int("BT_USB_PID", 0x0001) & 0xFFFF
        ver = env_hex_int("BT_USB_VER", 0x0100) & 0xFFFF

        pnp = bytes(
            [
                0x02,  # USB Vendor ID source
                vid & 0xFF,
                (vid >> 8) & 0xFF,
                pid & 0xFF,
                (pid >> 8) & 0xFF,
                ver & 0xFF,
                (ver >> 8) & 0xFF,
            ]
        )

        self.add_characteristic(
            StaticValueCharacteristic(bus, 0, UUID_PNP_ID, ["read"], self, pnp)
        )
        self.add_characteristic(
            StaticValueCharacteristic(
                bus, 1, UUID_MANUFACTURER, ["read"], self, manufacturer.encode("utf-8")
            )
        )
        self.add_characteristic(
            StaticValueCharacteristic(
                bus, 2, UUID_MODEL_NUMBER, ["read"], self, model.encode("utf-8")
            )
        )


class BatteryLevelCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        super().__init__(
            bus,
            index,
            UUID_BATTERY_LEVEL,
            ["read", "notify", "encrypt-read", "encrypt-notify"],
            service,
        )
        self._value = bytearray([100])

    def notify_level(self):
        if not self.notifying:
            return
        self.PropertiesChanged(
            GATT_CHRC_IFACE,
            {"Value": dbus.Array(self._value, signature="y")},
            [],
        )


class BatteryService(Service):
    def __init__(self, bus, index):
        super().__init__(bus, index, UUID_BATTERY_SERVICE)
        self.level = BatteryLevelCharacteristic(bus, 0, self)
        self.add_characteristic(self.level)


class Advertisement(dbus.service.Object):
    def __init__(self, bus, index, service_uuids, local_name):
        self.path = f"/org/bluez/ipr/advertisement{index}"
        self.service_uuids = service_uuids
        self.local_name = local_name
        super().__init__(bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def get_properties(self):
        return {
            ADVERTISEMENT_IFACE: {
                "Type": dbus.String("peripheral"),
                "ServiceUUIDs": dbus.Array(self.service_uuids, signature="s"),
                "LocalName": dbus.String(self.local_name),
                "Appearance": dbus.UInt16(APPEARANCE_KEYBOARD),
            }
        }

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != ADVERTISEMENT_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[ADVERTISEMENT_IFACE]

    @dbus.service.method(ADVERTISEMENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        log_info("[ble] Advertisement released", always=True)


def find_adapter_path(bus: dbus.SystemBus, preferred_hci: str) -> str:
    preferred_suffix = "/" + preferred_hci
    om = dbus.Interface(bus.get_object(BLUEZ, "/"), DBUS_OM_IFACE)
    objects = om.GetManagedObjects()

    for path, ifaces in objects.items():
        if ADAPTER_IFACE in ifaces and path.endswith(preferred_suffix):
            return path

    for path, ifaces in objects.items():
        if ADAPTER_IFACE in ifaces:
            return path

    raise RuntimeError("No Bluetooth adapter found in BlueZ")


def set_adapter_ready(bus: dbus.SystemBus, adapter_path: str) -> None:
    props = dbus.Interface(bus.get_object(BLUEZ, adapter_path), DBUS_PROP_IFACE)

    try:
        props.Set(ADAPTER_IFACE, "Powered", dbus.Boolean(True))
        props.Set(ADAPTER_IFACE, "Pairable", dbus.Boolean(True))
        props.Set(ADAPTER_IFACE, "Discoverable", dbus.Boolean(True))

        props.Set(ADAPTER_IFACE, "PairableTimeout", dbus.UInt32(0))
        props.Set(ADAPTER_IFACE, "DiscoverableTimeout", dbus.UInt32(0))

        alias = env_str("BT_DEVICE_NAME", "IPR Keyboard")
        if alias:
            props.Set(ADAPTER_IFACE, "Alias", dbus.String(alias))
    except dbus.DBusException as exc:
        # Adapter state is usually already configured by bt_hid_agent_unified.
        log_info(f"[ble] Adapter setup warning: {exc}")


def ensure_fifo_exists() -> None:
    if not os.path.exists(FIFO_PATH):
        os.mkfifo(FIFO_PATH)
    os.chmod(FIFO_PATH, 0o666)


def send_next_character(
    queue: deque, hid: HidService, notify_state: NotifyState
) -> bool:
    if not queue:
        return False

    if not notify_state.event.is_set():
        return False

    ch = queue[0]
    keycode, mods = map_char(ch)

    # Drop unsupported characters rather than stalling the queue indefinitely.
    if keycode == 0:
        queue.popleft()
        return True

    press = build_kbd_report(mods, keycode)
    release = build_kbd_report(0, 0)

    if not hid.notify_key_report(press):
        return False

    time.sleep(0.012)
    hid.notify_key_report(release)
    time.sleep(0.008)

    queue.popleft()
    return True


def drain_queue(queue: deque, hid: HidService, notify_state: NotifyState) -> None:
    while queue:
        if not send_next_character(queue, hid, notify_state):
            break


def fifo_worker(hid: HidService, notify_state: NotifyState):
    ensure_fifo_exists()
    queue = deque()

    while True:
        try:
            # First drain pending keys so reconnect does not lose queued text.
            while queue:
                if notify_state.event.is_set():
                    drain_queue(queue, hid, notify_state)
                else:
                    time.sleep(0.05)

            with open(FIFO_PATH, "r", encoding="utf-8", errors="ignore") as fifo:
                for line in fifo:
                    text = line.rstrip("\n")
                    for ch in text:
                        queue.append(ch)
                    if notify_state.event.is_set():
                        drain_queue(queue, hid, notify_state)
        except Exception as exc:
            log_err(f"[ble] FIFO worker error: {exc}")
            time.sleep(1)


def _retryable_dbus_error(exc: dbus.DBusException) -> bool:
    name = exc.get_dbus_name() or ""
    msg = str(exc)
    tokens = ("NotReady", "InProgress", "Failed", "NoReply", "TimedOut")
    return any(token in name or token in msg for token in tokens)


def register_ble_stack_async(main_loop, bus, adapter_path, app, adv) -> None:
    gatt_mgr = dbus.Interface(bus.get_object(BLUEZ, adapter_path), GATT_MANAGER_IFACE)
    adv_mgr = dbus.Interface(bus.get_object(BLUEZ, adapter_path), LE_ADV_MGR_IFACE)

    state = {
        "attempt": 0,
        "max_attempts": 60,
    }

    def fail_and_exit(reason: str) -> bool:
        log_err(f"[ble] Registration failed: {reason}")
        main_loop.quit()
        os._exit(1)

    def schedule_retry(source: str, exc: dbus.DBusException) -> bool:
        state["attempt"] += 1
        attempt = state["attempt"]

        if not _retryable_dbus_error(exc):
            return fail_and_exit(f"{source} non-retryable error: {exc}")

        if attempt >= state["max_attempts"]:
            return fail_and_exit(
                f"{source} exceeded retry budget ({state['max_attempts']}): {exc}"
            )

        log_info(
            f"[ble] {source} retry {attempt}/{state['max_attempts']} after error: {exc}",
            always=True,
        )
        GLib.timeout_add_seconds(1, do_register_gatt)
        return False

    def on_adv_ok() -> None:
        log_info(f"[ble] Registered GATT+ADV on {adapter_path}", always=True)

    def on_adv_err(exc: dbus.DBusException) -> None:
        schedule_retry("RegisterAdvertisement", exc)

    def on_gatt_ok() -> None:
        log_info("[ble] GATT application registered", always=True)
        adv_mgr.RegisterAdvertisement(
            adv.get_path(),
            {},
            reply_handler=on_adv_ok,
            error_handler=on_adv_err,
        )

    def on_gatt_err(exc: dbus.DBusException) -> None:
        schedule_retry("RegisterApplication", exc)

    def do_register_gatt() -> bool:
        gatt_mgr.RegisterApplication(
            app.get_path(),
            {},
            reply_handler=on_gatt_ok,
            error_handler=on_gatt_err,
        )
        return False

    # Start once the GLib loop is running so BlueZ can call GetManagedObjects
    # immediately and receive a timely response.
    GLib.idle_add(do_register_gatt)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", default=env_str("BT_HCI", "hci0"))
    args = parser.parse_args()

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter_path = find_adapter_path(bus, args.adapter)
    set_adapter_ready(bus, adapter_path)

    notify_state = NotifyState()

    app = Application(bus)
    hid = HidService(bus, 0, notify_state)
    dis = DeviceInfoService(bus, 1)
    battery = BatteryService(bus, 2)

    app.add_service(hid)
    app.add_service(dis)
    app.add_service(battery)

    adv = Advertisement(
        bus,
        0,
        [UUID_HID_SERVICE],
        env_str("BT_DEVICE_NAME", "IPR Keyboard"),
    )

    threading.Thread(target=fifo_worker, args=(hid, notify_state), daemon=True).start()

    main_loop = GLib.MainLoop()
    register_ble_stack_async(main_loop, bus, adapter_path, app, adv)
    main_loop.run()


if __name__ == "__main__":
    main()
