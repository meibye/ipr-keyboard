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

AGENT_PATH = "/ipr/agent"


class Rejected(dbus.DBusException):
    _dbus_error_name = "org.bluez.Error.Rejected"


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


def find_adapter(bus: dbus.SystemBus, prefer: str = "hci0") -> str:
    om = dbus.Interface(bus.get_object(BLUEZ, "/"), OM_IFACE)
    objects = om.GetManagedObjects()

    for path, ifaces in objects.items():
        if ADAPTER_IFACE in ifaces and path.endswith(prefer):
            return path

    for path, ifaces in objects.items():
        if ADAPTER_IFACE in ifaces:
            return path

    raise RuntimeError("No BlueZ adapter found")


def set_adapter_ready(
    bus: dbus.SystemBus, adapter_path: str, verbose: bool = False
) -> None:
    props = dbus.Interface(bus.get_object(BLUEZ, adapter_path), PROP_IFACE)

    props.Set(ADAPTER_IFACE, "Powered", dbus.Boolean(True))
    props.Set(ADAPTER_IFACE, "Pairable", dbus.Boolean(True))
    props.Set(ADAPTER_IFACE, "Discoverable", dbus.Boolean(True))

    try:
        props.Set(ADAPTER_IFACE, "PairableTimeout", dbus.UInt32(0))
        props.Set(ADAPTER_IFACE, "DiscoverableTimeout", dbus.UInt32(0))
    except Exception:
        pass

    alias = env_clean("BT_DEVICE_NAME", "IPR Keyboard")
    # BLE advertising is limited to 31 bytes. To ensure appearance fits,
    # truncate name if it would exceed ~12 characters (leaving room for
    # flags, UUID, appearance, and overhead).
    if alias and len(alias) > 12:
        alias = alias[:12]
    if alias:
        try:
            props.Set(ADAPTER_IFACE, "Alias", dbus.String(alias))
        except Exception:
            pass

    if verbose:
        print(f"[agent] Adapter ready: {adapter_path}", flush=True)


def trust_device(bus: dbus.SystemBus, device_path: str, verbose: bool = False) -> None:
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
    def __init__(
        self, bus: dbus.SystemBus, path: str = AGENT_PATH, verbose: bool = False
    ):
        super().__init__(bus, path)
        self.bus = bus
        self.path = path
        self.verbose = verbose

    def log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        self.log("[agent] Release()")

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        # Not expected for BLE HOGP + NoInputNoOutput, but implement to avoid UnknownMethod.
        self.log(f"[agent] RequestPinCode({dev_short(device)}) -> '0000'")
        trust_device(self.bus, device, verbose=self.verbose)
        return "0000"

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        # Not expected for BLE HOGP + NoInputNoOutput, but implement to avoid UnknownMethod.
        self.log(f"[agent] RequestPasskey({dev_short(device)}) -> 000000")
        trust_device(self.bus, device, verbose=self.verbose)
        return dbus.UInt32(0)

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        self.log(f"[agent] DisplayPinCode({dev_short(device)}) pin={pincode}")

    @dbus.service.method(AGENT_IFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        self.log(
            f"[agent] DisplayPasskey({dev_short(device)}) passkey={int(passkey):06d} entered={int(entered)}"
        )

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        self.log(
            f"[agent] RequestConfirmation({dev_short(device)}) passkey={int(passkey):06d} -> accept"
        )
        trust_device(self.bus, device, verbose=self.verbose)

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        self.log(f"[agent] RequestAuthorization({dev_short(device)}) -> accept")
        trust_device(self.bus, device, verbose=self.verbose)

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        self.log(f"[agent] AuthorizeService({dev_short(device)}) uuid={uuid} -> accept")
        trust_device(self.bus, device, verbose=self.verbose)

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Cancel(self):
        self.log("[agent] Cancel()")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="hci0")
    args = ap.parse_args()

    verbose = env_clean("BT_AGENT_DEBUG", "0") == "1"

    # Auto-unblock Bluetooth if soft-blocked
    try:
        import subprocess
        rfkill_out = subprocess.check_output(["rfkill", "list", "bluetooth"], encoding="utf-8")
        if "Soft blocked: yes" in rfkill_out:
            subprocess.run(["sudo", "rfkill", "unblock", "bluetooth"], check=False)
            if verbose:
                print("[agent] Auto-unblocked Bluetooth via rfkill.", flush=True)
    except Exception as exc:
        if verbose:
            print(f"[agent] rfkill check failed: {exc}", flush=True)

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter = find_adapter(bus, args.adapter)
    set_adapter_ready(bus, adapter, verbose=verbose)

    agent = Agent(bus=bus, path=AGENT_PATH, verbose=verbose)
    mgr = dbus.Interface(bus.get_object(BLUEZ, "/org/bluez"), AGENT_MGR_IFACE)

    try:
        mgr.UnregisterAgent(AGENT_PATH)
    except Exception:
        pass

    capability = env_clean("BT_AGENT_CAPABILITY", "NoInputNoOutput")
    mgr.RegisterAgent(AGENT_PATH, capability)
    mgr.RequestDefaultAgent(AGENT_PATH)

    if verbose:
        print(
            f"[agent] Registered. adapter={adapter} capability={capability} debug=ON",
            flush=True,
        )

    GLib.MainLoop().run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Rejected:
        sys.exit(1)
