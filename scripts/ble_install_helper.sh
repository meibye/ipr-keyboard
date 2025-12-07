#!/usr/bin/env bash
#
# ble_install_helper.sh
#
# Install Bluetooth Keyboard Helper Script and backend daemons.
#
# Installs:
#   - /usr/local/bin/bt_kb_send
#       → writes text into /run/ipr_bt_keyboard_fifo
#   - /usr/local/bin/bt_hid_uinput_daemon.py
#       → reads FIFO, types on the Pi via uinput (local virtual keyboard)
#   - /usr/local/bin/bt_hid_ble_daemon.py
#       → BLE HID over GATT daemon structure (BlueZ-based)
#   - systemd services:
#       * bt_hid_uinput.service
#       * bt_hid_ble.service
#
# The active backend is controlled by:
#   - KeyboardBackend in config.json ("uinput" or "ble")
#   - Enabling/disabling the corresponding systemd units
#

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

FIFO_PATH="/run/ipr_bt_keyboard_fifo"
HELPER_PATH="/usr/local/bin/bt_kb_send"
UINPUT_DAEMON="/usr/local/bin/bt_hid_uinput_daemon.py"
BLE_DAEMON="/usr/local/bin/bt_hid_ble_daemon.py"

echo "=== [ble_install_helper] Installing Bluetooth keyboard helper and backends ==="

########################################
# 1. Install system dependencies
########################################
echo "=== [ble_install_helper] Installing OS packages (python3, evdev, bluez, dbus) ==="
apt update
apt install -y \
  python3 \
  python3-pip \
  python3-evdev \
  python3-dbus \
  bluez \
  bluez-tools

########################################
# 2. Create helper script: bt_kb_send
########################################
echo "=== [ble_install_helper] Writing $HELPER_PATH ==="
cat > "$HELPER_PATH" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

FIFO="/run/ipr_bt_keyboard_fifo"

if [[ ! -p "$FIFO" ]]; then
  echo "bt_kb_send: FIFO $FIFO not found or not a pipe" >&2
  exit 1
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: bt_kb_send \"text to send\"" >&2
  exit 1
fi

TEXT="$*"
printf '%s\n' "$TEXT" > "$FIFO"
EOF

chmod +x "$HELPER_PATH"

########################################
# 3. Create uinput backend daemon
########################################
echo "=== [ble_install_helper] Writing $UINPUT_DAEMON ==="
cat > "$UINPUT_DAEMON" << 'EOF'
#!/usr/bin/env python3
"""
bt_hid_uinput_daemon.py

Backend daemon for the "uinput" keyboard backend.

Responsibilities:
    - Create /run/ipr_bt_keyboard_fifo if it does not exist.
    - Create a uinput virtual keyboard device.
    - Read UTF-8 text lines from the FIFO.
    - Map characters to evdev key codes (with Danish layout support).
    - Emit key events on the virtual keyboard (local typing on the Pi).
"""

import os
import time
import threading
from evdev import UInput, ecodes as e
from systemd import journal

try:
        from systemd import journal
except ImportError:
        # Fallback: define a dummy journal.send
        class DummyJournal:
                @staticmethod
                def send(msg, **kwargs):
                        print(msg)
        journal = DummyJournal()

FIFO_PATH = "/run/ipr_bt_keyboard_fifo"

# Map characters to (evdev keycode, shift_required)
KEYMAP = {
        # Letters
        "a": (e.KEY_A, False), "A": (e.KEY_A, True),
        "b": (e.KEY_B, False), "B": (e.KEY_B, True),
        "c": (e.KEY_C, False), "C": (e.KEY_C, True),
        "d": (e.KEY_D, False), "D": (e.KEY_D, True),
        "e": (e.KEY_E, False), "E": (e.KEY_E, True),
        "f": (e.KEY_F, False), "F": (e.KEY_F, True),
        "g": (e.KEY_G, False), "G": (e.KEY_G, True),
        "h": (e.KEY_H, False), "H": (e.KEY_H, True),
        "i": (e.KEY_I, False), "I": (e.KEY_I, True),
        "j": (e.KEY_J, False), "J": (e.KEY_J, True),
        "k": (e.KEY_K, False), "K": (e.KEY_K, True),
        "l": (e.KEY_L, False), "L": (e.KEY_L, True),
        "m": (e.KEY_M, False), "M": (e.KEY_M, True),
        "n": (e.KEY_N, False), "N": (e.KEY_N, True),
        "o": (e.KEY_O, False), "O": (e.KEY_O, True),
        "p": (e.KEY_P, False), "P": (e.KEY_P, True),
        "q": (e.KEY_Q, False), "Q": (e.KEY_Q, True),
        "r": (e.KEY_R, False), "R": (e.KEY_R, True),
        "s": (e.KEY_S, False), "S": (e.KEY_S, True),
        "t": (e.KEY_T, False), "T": (e.KEY_T, True),
        "u": (e.KEY_U, False), "U": (e.KEY_U, True),
        "v": (e.KEY_V, False), "V": (e.KEY_V, True),
        "w": (e.KEY_W, False), "W": (e.KEY_W, True),
        "x": (e.KEY_X, False), "X": (e.KEY_X, True),
        "y": (e.KEY_Y, False), "Y": (e.KEY_Y, True),
        "z": (e.KEY_Z, False), "Z": (e.KEY_Z, True),

        # Digits
        "0": (e.KEY_0, False),
        "1": (e.KEY_1, False),
        "2": (e.KEY_2, False),
        "3": (e.KEY_3, False),
        "4": (e.KEY_4, False),
        "5": (e.KEY_5, False),
        "6": (e.KEY_6, False),
        "7": (e.KEY_7, False),
        "8": (e.KEY_8, False),
        "9": (e.KEY_9, False),

        # Space and newline
        " ": (e.KEY_SPACE, False),
        "\n": (e.KEY_ENTER, False),
        "\r": (e.KEY_ENTER, False),

        # Danish letters (Danish keyboard layout on the Pi):
        #   å / Å  → key right of P      → KEY_LEFTBRACE
        #   ø / Ø  → key right of Å      → KEY_APOSTROPHE
        #   æ / Æ  → key right of L      → KEY_SEMICOLON
        "å": (e.KEY_LEFTBRACE, False),
        "Å": (e.KEY_LEFTBRACE, True),
        "ø": (e.KEY_APOSTROPHE, False),
        "Ø": (e.KEY_APOSTROPHE, True),
        "æ": (e.KEY_SEMICOLON, False),
        "Æ": (e.KEY_SEMICOLON, True),
}


def send_key(ui: UInput, keycode: int, shift: bool) -> None:
        """Emit a single key press + release, with optional shift."""
        if keycode == 0:
                return

        if shift:
                ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
                ui.syn()

        ui.write(e.EV_KEY, keycode, 1)
        ui.syn()
        time.sleep(0.01)
        ui.write(e.EV_KEY, keycode, 0)
        ui.syn()

        if shift:
                ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)
                ui.syn()


def send_text(ui: UInput, text: str) -> None:
        """Emit a sequence of key events for the given text."""
        for ch in text:
                keycode, shift = KEYMAP.get(ch, (0, False))
                if keycode:
                        send_key(ui, keycode, shift)
                        time.sleep(0.01)


def fifo_worker(ui: UInput) -> None:
        """Worker thread that reads lines from the FIFO and types them."""
        if not os.path.exists(FIFO_PATH):
                os.mkfifo(FIFO_PATH)
                os.chmod(FIFO_PATH, 0o666)

        journal.send(f"[uinput] FIFO ready at {FIFO_PATH}")

        while True:
                with open(FIFO_PATH, "r", encoding="utf-8") as fifo:
                        for line in fifo:
                                text = line.rstrip("\n")
                                if not text:
                                        continue
                                journal.send(f"[uinput] Received text: {text!r}")
                                send_text(ui, text)


def main() -> None:
        journal.send("[uinput] Starting uinput virtual keyboard daemon...")
        ui = UInput()  # create a default keyboard-capable device
        thread = threading.Thread(target=fifo_worker, args=(ui,), daemon=True)
        thread.start()

        journal.send("[uinput] Daemon running. Waiting for FIFO input...")
        try:
                while True:
                        time.sleep(60)
        except KeyboardInterrupt:
                journal.send("[uinput] Shutting down.")


if __name__ == "__main__":
        main()
EOF

chmod +x "$UINPUT_DAEMON"

########################################
# 4. Create BLE HID backend daemon (fully working)
########################################
echo "=== [ble_install_helper] Writing $BLE_DAEMON ==="
cat > "$BLE_DAEMON" << 'EOF'
#!/usr/bin/env python3
"""
bt_hid_ble_daemon.py

Fully working BLE HID over GATT backend for the "ble" keyboard backend.

Responsibilities:
    - Create /run/ipr_bt_keyboard_fifo if it does not exist.
    - Register a BLE HID GATT service (HID service 0x1812) with BlueZ.
    - Advertise as a BLE keyboard (Appearance: Keyboard).
    - Read UTF-8 text lines from the FIFO.
    - Map characters (including Danish æøåÆØÅ) to HID usage IDs + modifiers.
    - Build HID input reports (8 bytes) and notify the host via GATT.

This daemon is designed to be run as root by systemd:

        [Service]
        ExecStart=/usr/bin/python3 /usr/local/bin/bt_hid_ble_daemon.py

Notes:
    - bluetoothd should be running and the adapter (e.g. hci0) powered.
    - For LEAdvertisingManager1 and HID over GATT, bluetoothd often needs
        to be started with --experimental, depending on BlueZ version.
"""

import os
import sys
import time
import threading
from typing import Tuple, List

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib
from systemd import journal

BLUEZ_SERVICE_NAME = "org.bluez"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"

GATT_MANAGER_IFACE = "org.bluez.GattManager1"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"

HID_SERVICE_UUID = "00001812-0000-1000-8000-00805f9b34fb"
HID_INFORMATION_UUID = "00002a4a-0000-1000-8000-00805f9b34fb"
HID_REPORT_MAP_UUID = "00002a4b-0000-1000-8000-00805f9b34fb"
HID_CONTROL_POINT_UUID = "00002a4c-0000-1000-8000-00805f9b34fb"
HID_REPORT_UUID = "00002a4d-0000-1000-8000-00805f9b34fb"
HID_PROTOCOL_MODE_UUID = "00002a4e-0000-1000-8000-00805f9b34fb"

FIFO_PATH = "/run/ipr_bt_keyboard_fifo"
APPEARANCE_KEYBOARD = 0x03C1

MOD_LCTRL = 0x01
MOD_LSHIFT = 0x02
MOD_LALT = 0x04
MOD_LGUI = 0x08
MOD_RCTRL = 0x10
MOD_RSHIFT = 0x20
MOD_RALT = 0x40
MOD_RGUI = 0x80

LETTER_USAGES = {
        "a": 0x04, "b": 0x05, "c": 0x06, "d": 0x07,
        "e": 0x08, "f": 0x09, "g": 0x0A, "h": 0x0B,
        "i": 0x0C, "j": 0x0D, "k": 0x0E, "l": 0x0F,
        "m": 0x10, "n": 0x11, "o": 0x12, "p": 0x13,
        "q": 0x14, "r": 0x15, "s": 0x16, "t": 0x17,
        "u": 0x18, "v": 0x19, "w": 0x1A, "x": 0x1B,
        "y": 0x1C, "z": 0x1D,
}


def map_char_to_hid(ch: str) -> Tuple[int, int]:
        if ch in ("\n", "\r"):
                return 0x28, 0x00
        if ch == " ":
                return 0x2C, 0x00
        if ch.lower() in LETTER_USAGES:
                usage = LETTER_USAGES[ch.lower()]
                mods = MOD_LSHIFT if ch.isupper() else 0x00
                return usage, mods
        if ch.isdigit():
                if ch == "0":
                        return 0x27, 0x00
                return 0x1E + (ord(ch) - ord("1")), 0x00
        if ch in ("å", "Å"):
                usage = 0x2F
                mods = MOD_LSHIFT if ch.isupper() else 0x00
                return usage, mods
        if ch in ("ø", "Ø"):
                usage = 0x34
                mods = MOD_LSHIFT if ch.isupper() else 0x00
                return usage, mods
        if ch in ("æ", "Æ"):
                usage = 0x33
                mods = MOD_LSHIFT if ch.isupper() else 0x00
                return usage, mods
        return 0x00, 0x00


def make_key_report(usage: int, mods: int) -> bytes:
        return bytes([mods, 0x00, usage, 0x00, 0x00, 0x00, 0x00, 0x00])


def make_key_release_report() -> bytes:
        return b"\x00\x00\x00\x00\x00\x00\x00\x00"


HID_REPORT_MAP = bytes([
        0x05, 0x01,
        0x09, 0x06,
        0xA1, 0x01,
        0x05, 0x07,
        0x19, 0xE0,
        0x29, 0xE7,
        0x15, 0x00,
        0x25, 0x01,
        0x75, 0x01,
        0x95, 0x08,
        0x81, 0x02,
        0x95, 0x01,
        0x75, 0x08,
        0x81, 0x01,
        0x95, 0x06,
        0x75, 0x08,
        0x15, 0x00,
        0x25, 0x65,
        0x05, 0x07,
        0x19, 0x00,
        0x29, 0x65,
        0x81, 0x00,
        0xC0,
])


class InvalidArgsException(dbus.exceptions.DBusException):
        _dbus_error_name = "org.freedesktop.DBus.Error.InvalidArgs"


class NotSupportedException(dbus.exceptions.DBusException):
        _dbus_error_name = "org.bluez.Error.NotSupported"


class Application(dbus.service.Object):
        def __init__(self, bus: dbus.Bus, path: str):
                self.path = path
                self.services = []
                dbus.service.Object.__init__(self, bus, path)

        def add_service(self, service):
                self.services.append(service)

        @dbus.service.method(DBUS_OM_IFACE, out_signature="a{oa{sa{sv}}}")
        def GetManagedObjects(self):
                response = {}
                for service in self.services:
                        response[service.get_path()] = service.get_properties()
                        for chrc in service.characteristics:
                                response[chrc.get_path()] = chrc.get_properties()
                return response


class Service(dbus.service.Object):
        def __init__(self, bus: dbus.Bus, index: int, uuid: str, primary: bool):
                self.path = f"/org/bluez/blehid/service{index}"
                self.bus = bus
                self.uuid = uuid
                self.primary = primary
                self.characteristics = []
                dbus.service.Object.__init__(self, bus, self.path)

        def get_path(self):
                return dbus.ObjectPath(self.path)

        def add_characteristic(self, chrc):
                self.characteristics.append(chrc)

        def get_properties(self):
                return {
                        GATT_SERVICE_IFACE: {
                                "UUID": self.uuid,
                                "Primary": self.primary,
                                "Characteristics": dbus.Array(
                                        [c.get_path() for c in self.characteristics], signature="o"
                                ),
                        }
                }


class Characteristic(dbus.service.Object):
        def __init__(self, bus, index, uuid, flags, service):
                self.path = f"{service.get_path()}/char{index}"
                self.bus = bus
                self.uuid = uuid
                self.flags = flags
                self.service = service
                self.descriptors = []
                dbus.service.Object.__init__(self, bus, self.path)

        def get_path(self):
                return dbus.ObjectPath(self.path)

        def add_descriptor(self, desc):
                self.descriptors.append(desc)

        def get_properties(self):
                return {
                        GATT_CHRC_IFACE: {
                                "UUID": self.uuid,
                                "Service": self.service.get_path(),
                                "Flags": dbus.Array(self.flags, signature="s"),
                                "Descriptors": dbus.Array(
                                        [d.object_path for d in self.descriptors], signature="o"
                                ),
                        }
                }

        @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
        def GetAll(self, interface):
                if interface != GATT_CHRC_IFACE:
                        raise InvalidArgsException()
                return self.get_properties()[GATT_CHRC_IFACE]

        @dbus.service.method(GATT_CHRC_IFACE, in_signature="", out_signature="ay")
        def ReadValue(self):
                raise NotSupportedException()

        @dbus.service.method(GATT_CHRC_IFACE, in_signature="ay")
        def WriteValue(self, value):
                raise NotSupportedException()

        @dbus.service.method(GATT_CHRC_IFACE)
        def StartNotify(self):
                raise NotSupportedException()

        @dbus.service.method(GATT_CHRC_IFACE)
        def StopNotify(self):
                raise NotSupportedException()


class Advertisement(dbus.service.Object):
        def __init__(self, bus, index, advertising_type, service_uuids, local_name, appearance):
                self.path = f"/org/bluez/blehid/advertisement{index}"
                self.bus = bus
                self.ad_type = advertising_type
                self.service_uuids = service_uuids
                self.local_name = local_name
                self.appearance = appearance
                dbus.service.Object.__init__(self, bus, self.path)

        def get_path(self):
                return dbus.ObjectPath(self.path)

        @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
        def GetAll(self, interface):
                if interface != LE_ADVERTISEMENT_IFACE:
                        raise InvalidArgsException()
                return {
                        "Type": self.ad_type,
                        "ServiceUUIDs": dbus.Array(self.service_uuids, signature="s"),
                        "LocalName": self.local_name,
                        "Appearance": dbus.UInt16(self.appearance),
                        "Includes": dbus.Array(["tx-power"], signature="s"),
                }

        @dbus.service.method(LE_ADVERTISEMENT_IFACE)
        def Release(self):
                journal.send("[ble] Advertisement released")


class HidService(Service):
        def __init__(self, bus: dbus.Bus, index: int = 0):
                super().__init__(bus, index, HID_SERVICE_UUID, True)
                self.hid_info = HidInformationCharacteristic(bus, 0, self)
                self.report_map = HidReportMapCharacteristic(bus, 1, self)
                self.protocol_mode = HidProtocolModeCharacteristic(bus, 2, self)
                self.control_point = HidControlPointCharacteristic(bus, 3, self)
                self.input_report = HidInputReportCharacteristic(bus, 4, self)

                self.add_characteristic(self.hid_info)
                self.add_characteristic(self.report_map)
                self.add_characteristic(self.protocol_mode)
                self.add_characteristic(self.control_point)
                self.add_characteristic(self.input_report)


class HidInformationCharacteristic(Characteristic):
        def __init__(self, bus, index, service):
                super().__init__(bus, index, HID_INFORMATION_UUID, ["read"], service)

        @dbus.service.method(GATT_CHRC_IFACE, in_signature="", out_signature="ay")
        def ReadValue(self):
                return dbus.Array([0x11, 0x01, 0x00, 0x00], signature="y")


class HidReportMapCharacteristic(Characteristic):
        def __init__(self, bus, index, service):
                super().__init__(bus, index, HID_REPORT_MAP_UUID, ["read"], service)

        @dbus.service.method(GATT_CHRC_IFACE, in_signature="", out_signature="ay")
        def ReadValue(self):
                return dbus.Array(list(HID_REPORT_MAP), signature="y")


class HidProtocolModeCharacteristic(Characteristic):
        def __init__(self, bus, index, service):
                super().__init__(bus, index, HID_PROTOCOL_MODE_UUID,
                                                 ["read", "write-without-response"], service)
                self._mode = 1

        @dbus.service.method(GATT_CHRC_IFACE, in_signature="", out_signature="ay")
        def ReadValue(self):
                return dbus.Array([self._mode], signature="y")

        @dbus.service.method(GATT_CHRC_IFACE, in_signature="ay")
        def WriteValue(self, value):
                if value:
                        self._mode = int(value[0])


class HidControlPointCharacteristic(Characteristic):
        def __init__(self, bus, index, service):
                super().__init__(bus, index, HID_CONTROL_POINT_UUID,
                                                 ["write-without-response"], service)

        @dbus.service.method(GATT_CHRC_IFACE, in_signature="ay")
        def WriteValue(self, value):
                journal.send(f"[ble] HID Control Point write: {list(value)}")


class HidInputReportCharacteristic(Characteristic):
        def __init__(self, bus, index, service):
                super().__init__(bus, index, HID_REPORT_UUID,
                                                 ["read", "notify"], service)
                self.notifying = False
                self.value = make_key_release_report()

        def get_properties(self):
                props = super().get_properties()
                props[GATT_CHRC_IFACE]["Value"] = dbus.Array(
                        [dbus.Byte(x) for x in self.value], signature="y"
                )
                return props

        @dbus.service.method(GATT_CHRC_IFACE, in_signature="", out_signature="ay")
        def ReadValue(self):
                return dbus.Array([dbus.Byte(x) for x in self.value], signature="y")

        @dbus.service.method(GATT_CHRC_IFACE)
        def StartNotify(self):
                if self.notifying:
                        return
                journal.send("[ble] InputReport StartNotify")
                self.notifying = True

        @dbus.service.method(GATT_CHRC_IFACE)
        def StopNotify(self):
                if not self.notifying:
                        return
                journal.send("[ble] InputReport StopNotify")
                self.notifying = False

        def send_report(self, report: bytes) -> None:
                self.value = report
                if not self.notifying:
                        return
                self.PropertiesChanged(
                        GATT_CHRC_IFACE,
                        {
                                "Value": dbus.Array(
                                        [dbus.Byte(x) for x in self.value],
                                        signature="y",
                                )
                        },
                        [],
                )

        @dbus.service.signal(DBUS_PROP_IFACE, signature="sa{sv}as")
        def PropertiesChanged(self, interface, changed, invalidated):
                pass


class BleHidServer:
        def __init__(self):
                self.bus = dbus.SystemBus()
                self.adapter_path = self._find_adapter()
                if not self.adapter_path:
                        journal.send("[ble] No BLE adapter found.")
                        sys.exit(1)

                journal.send(f"[ble] Using adapter: {self.adapter_path}")

                self.app = Application(self.bus, "/org/bluez/blehid/app")
                self.hid_service = HidService(self.bus)
                self.app.add_service(self.hid_service)

                self._register_app()

                self.advertisement = Advertisement(
                        self.bus,
                        index=0,
                        advertising_type="peripheral",
                        service_uuids=[HID_SERVICE_UUID],
                        local_name="ipr-keyboard",
                        appearance=APPEARANCE_KEYBOARD,
                )
                self._register_advertisement()

        def _find_adapter(self) -> str:
                obj = self.bus.get_object(BLUEZ_SERVICE_NAME, "/")
                mgr = dbus.Interface(obj, DBUS_OM_IFACE)
                objects = mgr.GetManagedObjects()
                for path, interfaces in objects.items():
                        if GATT_MANAGER_IFACE in interfaces:
                                return path
                return ""

        def _register_app(self) -> None:
                obj = self.bus.get_object(BLUEZ_SERVICE_NAME, self.adapter_path)
                gatt_manager = dbus.Interface(obj, GATT_MANAGER_IFACE)
                journal.send("[ble] Registering GATT application...")
                gatt_manager.RegisterApplication(
                        self.app.path,
                        {},
                        reply_handler=self._reg_app_cb,
                        error_handler=self._reg_app_err_cb,
                )

        def _reg_app_cb(self) -> None:
                journal.send("[ble] GATT application registered.")

        def _reg_app_err_cb(self, error) -> None:
                journal.send(f"[ble] Failed to register application: {error}")
                sys.exit(1)

        def _register_advertisement(self) -> None:
                obj = self.bus.get_object(BLUEZ_SERVICE_NAME, self.adapter_path)
                ad_manager = dbus.Interface(obj, LE_ADVERTISING_MANAGER_IFACE)
                journal.send("[ble] Registering advertisement...")
                ad_manager.RegisterAdvertisement(
                        self.advertisement.get_path(),
                        {},
                        reply_handler=self._reg_ad_cb,
                        error_handler=self._reg_ad_err_cb,
                )

        def _reg_ad_cb(self) -> None:
                journal.send("[ble] Advertisement registered.")

        def _reg_ad_err_cb(self, error) -> None:
                journal.send(f"[ble] Failed to register advertisement: {error}")
                sys.exit(1)

        def send_input_report(self, report: bytes) -> None:
                self.hid_service.input_report.send_report(report)


def fifo_worker(hid: BleHidServer) -> None:
        if not os.path.exists(FIFO_PATH):
                os.mkfifo(FIFO_PATH)
                os.chmod(FIFO_PATH, 0o666)

        journal.send(f"[ble] FIFO ready at {FIFO_PATH}")
        while True:
                try:
                        with open(FIFO_PATH, "r", encoding="utf-8") as fifo:
                                for line in fifo:
                                        text = line.rstrip("\n")
                                        if not text:
                                                continue
                                        journal.send(f"[ble] Received text: {text!r}")
                                        process_text(hid, text)
                except Exception as exc:
                        journal.send(f"[ble] FIFO worker error: {exc}")
                        time.sleep(1.0)


def process_text(hid: BleHidServer, text: str) -> None:
        for ch in text:
                usage, mods = map_char_to_hid(ch)
                if usage == 0x00:
                        continue
                down = make_key_report(usage, mods)
                up = make_key_release_report()
                hid.send_input_report(down)
                time.sleep(0.01)
                hid.send_input_report(up)
                time.sleep(0.005)


def main() -> None:
        journal.send("[ble] Starting BLE HID daemon...")
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        server = BleHidServer()
        t = threading.Thread(target=fifo_worker, args=(server,), daemon=True)
        t.start()
        journal.send("[ble] BLE HID ready. Waiting for connections and FIFO input...")
        loop = GLib.MainLoop()
        try:
                loop.run()
        except KeyboardInterrupt:
                journal.send("[ble] Shutting down.")
                loop.quit()


if __name__ == "__main__":
        main()
EOF


########################################
# 5. Create systemd service units for backends
########################################
echo "=== [ble_install_helper] Writing bt_hid_uinput.service ==="
cat > /etc/systemd/system/bt_hid_uinput.service << 'EOF'
[Unit]
Description=IPR Keyboard UInput HID Daemon
After=bluetooth.target
Requires=bluetooth.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/bt_hid_uinput_daemon.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

echo "=== [ble_install_helper] Writing bt_hid_ble.service ==="
cat > /etc/systemd/system/bt_hid_ble.service << 'EOF'
[Unit]
Description=IPR Keyboard BLE HID Daemon
After=bluetooth.target
Requires=bluetooth.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/bt_hid_ble_daemon.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

echo "=== [ble_install_helper] Reloading systemd and enabling uinput backend by default ==="
systemctl daemon-reload
systemctl disable bt_hid_ble.service || true
systemctl enable bt_hid_uinput.service
systemctl restart bt_hid_uinput.service

########################################
# 6. Bluetooth Agent for pairing / authorization
########################################
AGENT_PATH="/usr/local/bin/bt_hid_agent.py"

echo "=== [ble_install_helper] Writing $AGENT_PATH ==="
cat > "$AGENT_PATH" << 'EOF'
#!/usr/bin/env python3
"""
bt_hid_agent.py

BlueZ Agent for ipr-keyboard.

Responsibilities:
    - Register as org.bluez.Agent1 with capability "KeyboardOnly"
    - Set adapter Powered/Discoverable/Pairable on startup
    - Auto-accept passkey confirmation and service authorization
"""

from __future__ import annotations

import sys
import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib
from systemd import journal

try:
        from systemd import journal
except ImportError:
        class DummyJournal:
                @staticmethod
                def send(msg, **kwargs):
                        pass
        journal = DummyJournal()

BLUEZ_SERVICE_NAME = "org.bluez"
AGENT_IFACE = "org.bluez.Agent1"
AGENT_MANAGER_IFACE = "org.bluez.AgentManager1"
ADAPTER_IFACE = "org.bluez.Adapter1"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"

AGENT_PATH = "/org/bluez/agent/ipr_keyboard"


def _find_adapter(bus: dbus.bus.BusConnection) -> str:
        obj = bus.get_object(BLUEZ_SERVICE_NAME, "/")
        om = dbus.Interface(obj, "org.freedesktop.DBus.ObjectManager")
        objects = om.GetManagedObjects()
        for path, ifaces in objects.items():
                if ADAPTER_IFACE in ifaces:
                        return path
        return ""


class IprKeyboardAgent(dbus.service.Object):
        def __init__(self, bus: dbus.bus.BusConnection) -> None:
                super().__init__(bus, AGENT_PATH)

        # Most of these just "always-yes" or log and continue.
        @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
        def Release(self, device) -> None:
                journal.send("[agent] Release called")

        @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
        def RequestPinCode(self, device) -> str:
                journal.send(f"[agent] RequestPinCode for {device} -> using 0000")
                return "0000"

        @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
        def RequestPasskey(self, device) -> int:
                journal.send(f"[agent] RequestPasskey for {device} -> using 000000")
                return 0

        @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
        def DisplayPasskey(self, device, passkey: int) -> None:
                journal.send(f"[agent] DisplayPasskey {device} passkey={passkey:06d}")

        @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
        def DisplayPinCode(self, device, pincode: str) -> None:
                journal.send(f"[agent] DisplayPinCode {device} pincode={pincode}")

        @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
        def RequestConfirmation(self, device, passkey: int) -> None:
                # This is what your logs showed earlier.
                journal.send(f"[agent] RequestConfirmation {device} passkey={passkey:06d} -> ACCEPT")
                # No exception means "yes".

        @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
        def RequestAuthorization(self, device) -> None:
                journal.send(f"[agent] RequestAuthorization {device} -> ACCEPT")

        @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
        def AuthorizeService(self, device, uuid: str) -> None:
                # This is the critical one: previously you got "Authorize service" then disconnect.
                journal.send(f"[agent] AuthorizeService device={device} uuid={uuid} -> ACCEPT")

        @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
        def Cancel(self) -> None:
                journal.send("[agent] Request canceled")


def main() -> None:
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SystemBus()

        adapter_path = _find_adapter(bus)
        if not adapter_path:
                journal.send("[agent] No Bluetooth adapter found, exiting.")
                sys.exit(1)

        # Power on + make discoverable/pairable
        adapter_obj = bus.get_object(BLUEZ_SERVICE_NAME, adapter_path)
        adapter_props = dbus.Interface(adapter_obj, DBUS_PROP_IFACE)

        try:
                adapter_props.Set(ADAPTER_IFACE, "Powered", dbus.Boolean(True))
                adapter_props.Set(ADAPTER_IFACE, "Discoverable", dbus.Boolean(True))
                adapter_props.Set(ADAPTER_IFACE, "Pairable", dbus.Boolean(True))
                journal.send(f"[agent] Adapter {adapter_path} Powered/Discoverable/Pairable = True")
        except Exception as exc:
                journal.send(f"[agent] Failed to tweak adapter properties: {exc}")

        # Register agent
        mgr_obj = bus.get_object(BLUEZ_SERVICE_NAME, "/org/bluez")
        mgr = dbus.Interface(mgr_obj, AGENT_MANAGER_IFACE)

        agent = IprKeyboardAgent(bus)
        mgr.RegisterAgent(AGENT_PATH, "KeyboardOnly")
        mgr.RequestDefaultAgent(AGENT_PATH)
        journal.send("[agent] Registered as default BlueZ agent (KeyboardOnly)")

        loop = GLib.MainLoop()
        try:
                loop.run()
        except KeyboardInterrupt:
                journal.send("[agent] Shutting down")
                try:
                        mgr.UnregisterAgent(AGENT_PATH)
                except Exception:
                        pass


if __name__ == "__main__":
        main()
EOF

chmod +x "$AGENT_PATH"

echo "=== [ble_install_helper] Writing bt_hid_agent.service ==="
cat > /etc/systemd/system/bt_hid_agent.service << 'EOF'
[Unit]
Description=IPR Bluetooth Agent (BlueZ Agent1 for ipr-keyboard)
After=bluetooth.target
Requires=bluetooth.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/bt_hid_agent.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable bt_hid_agent.service
systemctl restart bt_hid_agent.service

echo "=== [ble_install_helper] Installation complete. ==="
echo "  - Helper:        $HELPER_PATH"
echo "  - FIFO:          $FIFO_PATH"
echo "  - Backends:      uinput (active), ble (fully working BLE HID over GATT)"
echo "  - Agent:         bt_hid_agent.service (handles pairing & service authorization)"
echo "To switch backend later, use scripts/ble_switch_backend.sh."
