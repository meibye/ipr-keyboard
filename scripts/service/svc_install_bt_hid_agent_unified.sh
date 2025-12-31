#!/usr/bin/env bash
#
# svc_install_bt_hid_agent_unified.sh
#
# Installs the unified BlueZ agent service used for pairing.
#
# IMPORTANT:
#   Windows will often show TWO devices if the adapter is made classic-discoverable
#   (BR/EDR inquiry scan) while you also advertise a BLE peripheral.
#
#   Default behavior here is BLE-only pairing UX:
#     - Powered = True
#     - Pairable = True
#     - Discoverable (classic) = False
#
#   To explicitly enable classic discoverability (only if you need it):
#     set BT_ENABLE_CLASSIC_DISCOVERABLE="1" in /opt/ipr_common.env
#
# Usage:
#   sudo ./scripts/service/svc_install_bt_hid_agent_unified.sh
#
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

SERVICE_NAME="bt_hid_agent_unified"
AGENT_BIN="/usr/local/bin/bt_hid_agent_unified.py"
ENV_FILE="/opt/ipr_common.env"

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

def dev_short(path: str) -> str:
    if not path:
        return "<?>"
    return path.split("/")[-1]

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

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        d = dev_short(device)
        if self.mode == "fixedpin":
            self.log(f"[agent] RequestPinCode for {d} -> fixed pin {self.fixed_pin}")
            return self.fixed_pin
        self.log(f"[agent] RequestPinCode for {d} -> returning 0000")
        return "0000"

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        d = dev_short(device)
        # Windows may reject passkey flows for certain BLE HID configs;
        # keep it deterministic and simple.
        if self.mode == "fixedpin":
            pk = int(self.fixed_pin)
            self.log(f"[agent] RequestPasskey for {d} -> fixed passkey {pk}")
            return dbus.UInt32(pk)
        self.log(f"[agent] RequestPasskey for {d} -> returning 0")
        return dbus.UInt32(0)

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def DisplayPasskey(self, device, passkey):
        d = dev_short(device)
        self.log(f"[agent] DisplayPasskey({d}) passkey={int(passkey):06d}")

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        d = dev_short(device)
        self.log(f"[agent] DisplayPinCode({d}) pin={pincode}")

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        d = dev_short(device)
        # For NoInputNoOutput capability, auto-accept.
        self.log(f"[agent] RequestConfirmation({d}) passkey={int(passkey):06d} -> accepting")
        return

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        d = dev_short(device)
        self.log(f"[agent] RequestAuthorization({d}) -> accepting")
        return

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        d = dev_short(device)
        self.log(f"[agent] AuthorizeService({d}) uuid={uuid} -> accepting")
        return

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Cancel(self):
        self.log("[agent] Cancel()")
        return

def find_adapter(bus, prefer="hci0") -> str:
    om = dbus.Interface(bus.get_object(BLUEZ, "/"), "org.freedesktop.DBus.ObjectManager")
    objects = om.GetManagedObjects()
    # Prefer explicit hci name
    for path, ifaces in objects.items():
        if "org.bluez.Adapter1" in ifaces and path.endswith(prefer):
            return path
    # Else first adapter
    for path, ifaces in objects.items():
        if "org.bluez.Adapter1" in ifaces:
            return path
    raise RuntimeError("No BlueZ adapter found")

def set_adapter_ready(bus, adapter_path: str):
    props = dbus.Interface(bus.get_object(BLUEZ, adapter_path), PROP_IFACE)
    props.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(True))
    props.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(True))

    # IMPORTANT:
    #  - If we also set Adapter1.Discoverable=True (classic/BR-EDR inquiry scan),
    #    Windows often shows *two* devices: one BR/EDR entry and one BLE advertising entry.
    #  - We default to BLE-only pairing UX, so we keep classic discoverability OFF.
    #
    # If you explicitly want classic discoverability for the uinput/BR-EDR backend,
    # set BT_ENABLE_CLASSIC_DISCOVERABLE=1 in /opt/ipr_common.env.
    enable_classic = os.environ.get("BT_ENABLE_CLASSIC_DISCOVERABLE", "0").strip()
    # strip inline comment if present (people sometimes write: 1  # comment)
    if " #" in enable_classic:
        enable_classic = enable_classic.split(" #", 1)[0].strip()
    if enable_classic == "1":
        props.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(True))
    else:
        try:
            props.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(False))
        except Exception:
            # Some adapters/drivers don't allow setting this explicitly; ignore.
            pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["nowinpasskey", "fixedpin"], default="nowinpasskey")
    ap.add_argument("--fixed-pin", default="0000")
    ap.add_argument("--capability", default="NoInputNoOutput",
                    help="Use NoInputNoOutput for 'no passkey' goal")
    ap.add_argument("--agent-path", default="/ipr/agent")
    ap.add_argument("--adapter", default="hci0")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter = find_adapter(bus, args.adapter)
    set_adapter_ready(bus, adapter)

    agent = Agent(
        bus=bus,
        path=args.agent_path,
        mode=args.mode,
        fixed_pin=args.fixed_pin if args.mode == "fixedpin" else None,
        verbose=not args.quiet,
    )

    mgr = dbus.Interface(bus.get_object(BLUEZ, "/org/bluez"), AGENT_MGR_IFACE)

    try:
        mgr.UnregisterAgent(args.agent_path)
    except Exception:
        pass

    mgr.RegisterAgent(args.agent_path, args.capability)
    mgr.RequestDefaultAgent(args.agent_path)

    print(f"[agent] Registered. mode={args.mode} capability={args.capability} adapter={adapter}", flush=True)
    GLib.MainLoop().run()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
PYEOF

chmod +x "$AGENT_BIN"

echo "=== [svc_install_bt_hid_agent_unified] Writing service unit ==="
cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=IPR Keyboard Unified BlueZ Agent
After=bluetooth.target
Requires=bluetooth.target

[Service]
Type=simple
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${AGENT_BIN} --mode nowinpasskey --capability NoInputNoOutput --adapter hci0
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"

echo "=== [svc_install_bt_hid_agent_unified] Done ==="
echo "Start with:"
echo "  sudo systemctl restart ${SERVICE_NAME}.service"
