#!/usr/bin/env python3
import argparse
import os
import sys

import dbus
import dbus.mainloop.glib
import dbus.service
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

    props.Set(ADAPTER_IFACE, "Powered", dbus.Boolean(True))
    props.Set(ADAPTER_IFACE, "Pairable", dbus.Boolean(True))
    props.Set(ADAPTER_IFACE, "Discoverable", dbus.Boolean(True))

    # STABILITY FIX: Set Class to Keyboard (0x002540)
    try:
        props.Set(ADAPTER_IFACE, "Class", dbus.UInt32(0x002540))
        if verbose:
            print(
                f"[agent] Adapter Class set to 0x002540 (Keyboard) for {adapter_path}",
                flush=True,
            )
    except Exception as e:
        if verbose:
            print(f"[agent] Warning: Could not set Class: {e}", flush=True)

    try:
        props.Set(ADAPTER_IFACE, "PairableTimeout", dbus.UInt32(0))
        props.Set(ADAPTER_IFACE, "DiscoverableTimeout", dbus.UInt32(0))
    except Exception:
        pass

    alias = env_clean("BT_DEVICE_NAME", "IPR Keyboard")
    if alias:
        try:
            props.Set(ADAPTER_IFACE, "Alias", dbus.String(alias))
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
            print(
                f"[agent] Trust set failed for {dev_short(device_path)}: {e}",
                flush=True,
            )


class Agent(dbus.service.Object):
    def __init__(self, bus, path="/ipr/agent", verbose=True):
        super().__init__(bus, path)
        self.bus = bus
        self.path = path
        self.verbose = verbose

    def log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        self.log(
            f"[agent] RequestConfirmation({dev_short(device)}) passkey={int(passkey):06d} -> Auto-Accepting"
        )
        trust_device(self.bus, device, verbose=self.verbose)
        return

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        self.log(f"[agent] RequestAuthorization({dev_short(device)}) -> Auto-Accepting")
        trust_device(self.bus, device, verbose=self.verbose)
        return

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        self.log(
            f"[agent] AuthorizeService({dev_short(device)}) uuid={uuid} -> Accepting"
        )
        trust_device(self.bus, device, verbose=self.verbose)
        return

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Cancel(self):
        self.log("[agent] Cancelled by host")
        return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="hci0")
    args = ap.parse_args()

    env_dbg = env_clean("BT_AGENT_DEBUG", "0")
    verbose = env_dbg == "1"

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter = find_adapter(bus, args.adapter)
    set_adapter_ready(bus, adapter, verbose=verbose)

    agent = Agent(bus=bus, path="/ipr/agent", verbose=verbose)
    mgr = dbus.Interface(bus.get_object(BLUEZ, "/org/bluez"), AGENT_MGR_IFACE)

    try:
        mgr.UnregisterAgent("/ipr/agent")
    except Exception:
        pass

    mgr.RegisterAgent("/ipr/agent", "NoInputNoOutput")
    mgr.RequestDefaultAgent("/ipr/agent")

    if verbose:
        print(f"[agent] Registered. adapter={adapter} debug=ON", flush=True)
    GLib.MainLoop().run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
