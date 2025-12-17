#!/usr/bin/env bash
#
# svc_install_bt_hid_agent_unified.sh
#
# Installs the bt_hid_agent_unified service and script.
# This service provides Bluetooth pairing and authorization.
#
# Usage:
#   sudo ./scripts/service/svc_install_bt_hid_agent_unified.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#
# category: Service
# purpose: Install UNIFIED Bluetooth HID agent service for pairing
# sudo: yes
#

set -eo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

AGENT_PATH="/usr/local/bin/bt_hid_agent_unified.py"
HELPER_SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER_SRC_PATH="${HELPER_SRC_DIR}/lib/bt_agent_unified_env.sh"
HELPER_DST_DIR="/usr/local/lib/ipr-keyboard"
HELPER_DST_PATH="${HELPER_DST_DIR}/bt_agent_unified_env.sh"

echo "=== [svc_install_bt_hid_agent_unified] Installing bt_hid_agent_unified service ==="


################################################################################################################
# How to run it for “Windows should not ask for passkeys”
# A) BLE HID over GATT (the one that actually meets the requirement reliably)
#
# Run the agent like this:
#       sudo python3 bt_agent_unified.py --mode nowinpasskey --capability NoInputNoOutput
#
# And in your BLE HID GATT implementation, ensure your Security/Permissions do not require MITM. 
# Concretely:
#       - IO capability: NoInputNoOutput
#       - Bonding: OK
#       - MITM: off
#       - LE Secure Connections: fine, but if you require MITM, you’ll force numeric comparison/passkey flows.
# If your BLE HID code currently sets flags like “MITM required” (often via BlueZ/gatt permission/security levels), remove that requirement.
#
# Windows steps (important):
#       - Remove the device from Windows “Bluetooth & devices” (forget it).
#       - On the Pi: remove old bonds (see “clean bonds” section below).
# Pair again from Windows. You should get a simple Pair without a code.
#
# B) Classic HID fallback (best-effort “no passkey”)
#       sudo python3 bt_agent_unified.py --mode nowinpasskey --capability NoInputNoOutput
#
# This may still trigger a Windows passkey/number prompt depending on how Windows decides to pair with that classic HID device. If it does, you have two choices:
#       - accept that Classic HID won’t meet “never ask passkey”
#       - stick to BLE HID for Windows
################################################################################################################

########################################
# Create Bluetooth agent script
########################################
echo "=== [svc_install_bt_hid_agent_unified] Writing $AGENT_PATH ==="
cat > "$AGENT_PATH" << 'EOF'
#!/usr/bin/env python3
"""
bt_hid_agent_unified.py

Unified BlueZ Agent that supports both “no passkey” and “fixed PIN” (when legacy happens)

Use one agent and select a mode:
        -mode nowinpasskey = prefer flows that do not involve passkey entry (JustWorks / auto-confirm)
        -mode fixedpin = provide a legacy PIN (only if Windows chooses legacy PIN pairing)
"""

import argparse
import signal
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

BLUEZ = "org.bluez"
AGENT_IFACE = "org.bluez.Agent1"
AGENT_MGR = "org.bluez.AgentManager1"
OM_IFACE = "org.freedesktop.DBus.ObjectManager"
PROP_IFACE = "org.freedesktop.DBus.Properties"

class Rejected(dbus.DBusException):
    _dbus_error_name = "org.bluez.Error.Rejected"

class Canceled(dbus.DBusException):
    _dbus_error_name = "org.bluez.Error.Canceled"

def dev_short(path: str) -> str:
    return path.split("/")[-1]

class Agent(dbus.service.Object):
    """
    Modes:
      - nowinpasskey: avoid RequestPasskey; auto-confirm RequestConfirmation; authorize automatically
      - fixedpin: respond to RequestPinCode with fixed PIN (legacy pairing only)
    """
    def __init__(self, bus, path, mode, fixed_pin=None, verbose=True):
        super().__init__(bus, path)
        self.mode = mode
        self.fixed_pin = fixed_pin
        self.verbose = verbose

    def log(self, msg):
        if self.verbose:
            print(msg, flush=True)

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        self.log("[agent] Release()")

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Cancel(self):
        self.log("[agent] Cancel()")
        raise Canceled("Canceled")

    # Legacy PIN (old pairing model)
    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        d = dev_short(device)
        if self.mode == "fixedpin" and self.fixed_pin is not None:
            self.log(f"[agent] RequestPinCode({d}) -> {self.fixed_pin}")
            return str(self.fixed_pin)
        self.log(f"[agent] RequestPinCode({d}) -> rejecting (mode={self.mode})")
        raise Rejected("No PIN")

    # SSP Passkey Entry (what we want Windows to NOT do)
    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        d = dev_short(device)
        if self.mode == "nowinpasskey":
            self.log(f"[agent] RequestPasskey({d}) -> rejecting to avoid passkey-entry")
            raise Rejected("Avoid passkey-entry")
        self.log(f"[agent] RequestPasskey({d}) -> rejecting (no passkey configured)")
        raise Rejected("No passkey")

    # Numeric comparison
    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        d = dev_short(device)
        self.log(f"[agent] RequestConfirmation({d}) number={int(passkey):06d} -> accepting")
        return

    # Some stacks call these:
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

    @dbus.service.method(AGENT_IFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        d = dev_short(device)
        self.log(f"[agent] DisplayPasskey({d}) passkey={int(passkey):06d} entered={int(entered)}")

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        d = dev_short(device)
        self.log(f"[agent] DisplayPinCode({d}) pin={pincode}")

def find_adapter(bus, prefer="hci0"):
    om = dbus.Interface(bus.get_object(BLUEZ, "/"), OM_IFACE)
    objs = om.GetManagedObjects()
    adapters = [p for p, ifs in objs.items() if "org.bluez.Adapter1" in ifs]
    if not adapters:
        raise RuntimeError("No Bluetooth adapter found")
    for a in adapters:
        if a.endswith("/" + prefer):
            return a
    return adapters[0]

def set_adapter_ready(bus, adapter_path: str):
    props = dbus.Interface(bus.get_object(BLUEZ, adapter_path), PROP_IFACE)
    props.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(True))
    props.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(True))
    props.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(True))

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

    Agent(
        bus=bus,
        path=args.agent_path,
        mode=args.mode,
        fixed_pin=args.fixed_pin if args.mode == "fixedpin" else None,
        verbose=not args.quiet,
    )

    mgr = dbus.Interface(bus.get_object(BLUEZ, "/org/bluez"), AGENT_MGR)
    mgr.RegisterAgent(args.agent_path, args.capability)
    mgr.RequestDefaultAgent(args.agent_path)

    print(f"[agent] mode={args.mode} capability={args.capability} adapter={adapter}", flush=True)

    loop = GLib.MainLoop()

    def stop(*_):
        try:
            mgr.UnregisterAgent(args.agent_path)
        except Exception:
            pass
        loop.quit()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    loop.run()

if __name__ == "__main__":
    main()
EOF

chmod +x "$AGENT_PATH"

########################################
# Install shared helper (used by other scripts)
########################################
echo "=== [svc_install_bt_hid_agent_unified] Installing shared helper to $HELPER_DST_PATH ==="
install -d -m 0755 "$HELPER_DST_DIR"
install -m 0755 "$HELPER_SRC_PATH" "$HELPER_DST_PATH"

########################################
# Create systemd service unit
########################################
echo "=== [svc_install_bt_hid_agent_unified] Writing bt_hid_agent_unified.service ==="
cat > /etc/systemd/system/bt_hid_agent_unified.service << 'EOF'
# /etc/systemd/system/bt_hid_agent_unified.service
[Unit]
Description=IPR Bluetooth Agent (Unified BlueZ Agent1)
After=bluetooth.target
Requires=bluetooth.target

[Service]
Type=simple
EnvironmentFile=-/etc/default/bt_hid_agent_unified
ExecStart=/usr/bin/python3 /usr/local/bin/bt_hid_agent_unified.py \
  --mode ${BT_AGENT_MODE} \
  --capability ${BT_AGENT_CAPABILITY} \
  --agent-path ${BT_AGENT_PATH} \
  --adapter ${BT_AGENT_ADAPTER} \
  ${BT_AGENT_EXTRA_ARGS}
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

########################################
# Ensure default environment config exists
########################################
echo "=== [svc_install_bt_hid_agent_unified] Ensuring /etc/default/bt_hid_agent_unified exists ==="
if [[ ! -f /etc/default/bt_hid_agent_unified ]]; then
  install -d -m 0755 /etc/default
  cat > /etc/default/bt_hid_agent_unified <<'EOF'
# Unified BlueZ agent config (ipr-keyboard)
BT_AGENT_MODE=nowinpasskey
BT_AGENT_CAPABILITY=NoInputNoOutput
BT_AGENT_PATH=/ipr/agent
BT_AGENT_ADAPTER=hci0
BT_AGENT_EXTRA_ARGS=
EOF
  chmod 0644 /etc/default/bt_hid_agent_unified
fi

########################################
# Disable legacy agent (if present) and start unified agent
########################################
systemctl disable --now bt_hid_agent.service 2>/dev/null || true
systemctl enable bt_hid_agent_unified.service
systemctl restart bt_hid_agent_unified.service

echo "=== [svc_install_bt_hid_agent_unified] Installation complete ==="
