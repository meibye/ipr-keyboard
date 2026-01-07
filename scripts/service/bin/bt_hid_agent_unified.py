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
    # In LE-only mode this should not create a BR/EDR "second device".
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
