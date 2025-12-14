#!/usr/bin/env python3
"""
ipr_ble_hid_analyzer.py

Debug tool for BLE HID:
  - Watches PropertiesChanged for GATT characteristics
  - Logs HID report Value changes and connection-related indicators

Usage:
  sudo /usr/local/bin/ipr_ble_hid_analyzer.py

Prerequisites:
  - Must be run as root
  - BLE HID daemon must be running

category: Diagnostics
purpose: Monitor GATT characteristics and HID reports for debugging
"""

import dbus
import dbus.mainloop.glib
from gi.repository import GLib
from systemd import journal

BLUEZ = "org.bluez"
PROP_IFACE = "org.freedesktop.DBus.Properties"
OM_IFACE = "org.freedesktop.DBus.ObjectManager"
CHRC_IFACE = "org.bluez.GattCharacteristic1"


def on_properties_changed(interface, changed, invalidated, path=None):
    if "Value" in changed:
        value = bytes(changed["Value"])
        journal.send(f"[HID REPORT] path={path} hex={value.hex(' ')}")
    if "Connected" in changed:
        journal.send(f"[BLE] Connected={changed['Connected']}")


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    manager = bus.get_object(BLUEZ, "/")
    om = dbus.Interface(manager, OM_IFACE)
    objects = om.GetManagedObjects()

    journal.send("ipr_ble_hid_analyzer: monitoring GATT characteristic changes...")

    for path, ifaces in objects.items():
        if CHRC_IFACE in ifaces:
            bus.add_signal_receiver(
                on_properties_changed,
                bus_name=BLUEZ,
                signal_name="PropertiesChanged",
                path=path,
                dbus_interface=PROP_IFACE,
                path_keyword="path",
            )

    loop = GLib.MainLoop()
    loop.run()


if __name__ == "__main__":
    main()
