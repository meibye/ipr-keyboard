#!/usr/bin/env bash
#
# ble_setup_extras.sh
#
# Set up all extra RPi-side components for ipr-keyboard:
#   - Backend manager (prevents uinput + BLE running at same time)
#   - /etc/ipr-keyboard/backend selector
#   - BLE diagnostics script
#   - BLE HID analyzer
#   - Pairing wizard HTML template
#   - Pairing routes in src/ipr_keyboard/web/server.py
#
# Run as: sudo ./scripts/ble_setup_extras.sh
#

set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
  echo "Please run this script as root (sudo ./scripts/ble_setup_extras.sh)."
  exit 1
fi

echo "=== [ble_setup_extras] Setting up ipr-keyboard RPi extras ==="

# ---------------------------------------------------------------------------
# Locate project root (assume scripts/ is at $PROJECT_ROOT/scripts)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Script dir:    $SCRIPT_DIR"
echo "Project root:  $PROJECT_ROOT"

# ---------------------------------------------------------------------------
# 1. Backend selector file: /etc/ipr-keyboard/backend
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Configuring backend selector ==="
BACKEND_DIR="/etc/ipr-keyboard"
BACKEND_FILE="$BACKEND_DIR/backend"
CONFIG_FILE="$PROJECT_ROOT/config.json"

mkdir -p "$BACKEND_DIR"

if [[ ! -f "$BACKEND_FILE" ]]; then
  # Try to read backend from config.json if it exists
  BACKEND_VALUE="ble"  # default
  if [[ -f "$CONFIG_FILE" ]] && command -v jq >/dev/null 2>&1; then
    CONFIG_BACKEND=$(jq -r '.KeyboardBackend // "ble"' "$CONFIG_FILE")
    if [[ "$CONFIG_BACKEND" == "uinput" || "$CONFIG_BACKEND" == "ble" ]]; then
      BACKEND_VALUE="$CONFIG_BACKEND"
      echo "  Using backend from config.json: $BACKEND_VALUE"
    fi
  fi
  echo "$BACKEND_VALUE" > "$BACKEND_FILE"
  echo "  Created $BACKEND_FILE with backend '$BACKEND_VALUE'"
else
  echo "  $BACKEND_FILE already exists (content: '$(cat "$BACKEND_FILE")')"
fi

# ---------------------------------------------------------------------------
# 2. Install backend manager service
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Installing backend manager service ==="
"$SCRIPT_DIR/svc_install_ipr_backend_manager.sh"

systemctl enable ipr_backend_manager.service
systemctl start ipr_backend_manager.service
echo "  Enabled and started ipr_backend_manager.service"

# ---------------------------------------------------------------------------
# 3. BLE diagnostics script
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Installing BLE diagnostics script ==="
BLE_DIAG="/usr/local/bin/ipr_ble_diagnostics.sh"

cat > "$BLE_DIAG" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

RED="\033[0;31m"; GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RESET="\033[0m"

say() { echo -e "${YELLOW}== $1 ==${RESET}"; }
ok()  { echo -e "${GREEN}$1${RESET}"; }
err() { echo -e "${RED}$1${RESET}"; }

say "1. Checking Bluetooth adapter"
if ! bluetoothctl show >/dev/null 2>&1; then
    err "No Bluetooth adapter found (bluetoothctl show failed)."
    exit 1
fi
ok "Adapter found"

say "2. Checking HID UUID exposure (0x1812)"
if bluetoothctl show | grep -qi "00001812"; then
    ok "HID service (00001812-0000-1000-8000-00805f9b34fb) exposed"
else
    err "HID service not visible – BLE HID daemon may not be registered"
fi

say "3. Checking BLE HID daemon service"
if systemctl is-active --quiet bt_hid_ble.service; then
    ok "bt_hid_ble.service is active"
else
    err "bt_hid_ble.service is NOT active"
fi

say "4. Checking Agent service"
if systemctl is-active --quiet bt_hid_agent.service; then
    ok "bt_hid_agent.service is active"
else
    err "bt_hid_agent.service is NOT active (pairing likely to fail)"
fi

say "5. Adapter power state (btmgmt info)"
if command -v btmgmt >/dev/null 2>&1; then
    sudo btmgmt info || err "btmgmt info failed"
else
    err "btmgmt not installed; skipping detailed controller info"
fi

say "6. Recent BLE HID daemon logs (bt_hid_ble.service)"
sudo journalctl -u bt_hid_ble.service -n20 --no-pager || echo "No logs yet."

say "7. FIFO existence check"
/bin/ls -l /run/ipr_bt_keyboard_fifo 2>/dev/null && ok "FIFO exists" || err "FIFO missing: /run/ipr_bt_keyboard_fifo"

say "Diagnostics completed."
EOF

chmod +x "$BLE_DIAG"
echo "  Installed $BLE_DIAG"

# ---------------------------------------------------------------------------
# 5. BLE HID analyzer (DBus signal listener for HID reports)
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Installing BLE HID analyzer ==="
BLE_ANALYZER="/usr/local/bin/ipr_ble_hid_analyzer.py"

cat > "$BLE_ANALYZER" << 'EOF'
#!/usr/bin/env python3
"""
ipr_ble_hid_analyzer.py

Debug tool for BLE HID:
  - Watches PropertiesChanged for GATT characteristics
  - Logs HID report Value changes and connection-related indicators
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
EOF

chmod +x "$BLE_ANALYZER"
echo "  Installed $BLE_ANALYZER"

# ---------------------------------------------------------------------------
# 6. Pairing wizard HTML template
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Installing pairing wizard HTML template ==="
TEMPLATES_DIR="$PROJECT_ROOT/src/ipr_keyboard/web/templates"
PAIRING_TEMPLATE="$TEMPLATES_DIR/pairing_wizard.html"

mkdir -p "$TEMPLATES_DIR"

cat > "$PAIRING_TEMPLATE" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>IPR Keyboard – Pairing Wizard</title>
  <style>
    body { background:#111; color:#eee; font-family:sans-serif; margin:0; padding:20px; }
    h1 { margin-top:0; }
    .card { background:#222; padding:15px 18px; border-radius:8px; margin-bottom:18px; border:1px solid #333; }
    button { background:#3b82f6; border:none; padding:8px 14px; color:white; border-radius:6px; cursor:pointer; font-size:0.9rem; }
    button:hover { background:#2563eb; }
    pre { background:#000; padding:8px 10px; border-radius:6px; font-size:0.8rem; max-height:260px; overflow:auto; }
  </style>
</head>
<body>
  <h1>IPR Keyboard – Pairing Wizard</h1>

  <div class="card">
    <h2>Step 1: Activate BLE Backend</h2>
    <p>This will switch the device to use the BLE HID backend and stop the classic HID backend.</p>
    <button onclick="activateBackend()">Activate BLE Backend</button>
    <pre id="backendResult"></pre>
  </div>

  <div class="card">
    <h2>Step 2: Start Pairing Mode</h2>
    <p>Put the Pi into Bluetooth pairing mode, then add the device on your Windows PC.</p>
    <button onclick="startPairing()">Start Pairing Mode</button>
    <pre id="pairingResult"></pre>
  </div>

  <div class="card">
    <h2>Step 3: Inspect Status</h2>
    <button onclick="loadStatus()">Refresh Status</button>
    <pre id="statusBox"></pre>
  </div>

  <script>
    function activateBackend() {
      fetch("/pairing/activate-ble")
        .then(r => r.text())
        .then(t => { document.getElementById("backendResult").textContent = t; })
        .catch(e => { document.getElementById("backendResult").textContent = "Error: " + e; });
    }

    function startPairing() {
      fetch("/pairing/start")
        .then(r => r.text())
        .then(t => { document.getElementById("pairingResult").textContent = t; })
        .catch(e => { document.getElementById("pairingResult").textContent = "Error: " + e; });
    }

    function loadStatus() {
      fetch("/status")
        .then(r => r.json())
        .then(j => {
          document.getElementById("statusBox").textContent = JSON.stringify(j, null, 2);
        })
        .catch(e => { document.getElementById("statusBox").textContent = "Error: " + e; });
    }
  </script>
</body>
</html>
EOF

echo "  Installed $PAIRING_TEMPLATE"

# ---------------------------------------------------------------------------
# 7. Inject pairing routes into server.py (once)
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Injecting pairing routes into server.py (if missing) ==="
SERVER_PY="$PROJECT_ROOT/src/ipr_keyboard/web/server.py"

if [[ ! -f "$SERVER_PY" ]]; then
  echo "ERROR: $SERVER_PY not found; cannot inject pairing routes."
else
  if grep -q "IPR-KEYBOARD PAIRING ROUTES" "$SERVER_PY"; then
    echo "  Pairing routes already present in server.py; skipping injection."
  else
    cat >> "$SERVER_PY" << 'EOF'

# ---------------------------------------------------------------------------
# IPR-KEYBOARD PAIRING ROUTES (auto-injected by ble_setup_extras.sh)
# ---------------------------------------------------------------------------
from flask import render_template
import subprocess

@app.route("/pairing")
def pairing_page():
    return render_template("pairing_wizard.html")

@app.route("/pairing/activate-ble")
def pairing_activate():
    # Switch backend selector to BLE and run backend manager
    subprocess.call(["sudo", "sh", "-c", "echo ble > /etc/ipr-keyboard/backend"])
    subprocess.call(["sudo", "systemctl", "start", "ipr_backend_manager.service"])
    return "BLE backend activated via ipr_backend_manager."

@app.route("/pairing/start")
def pairing_start():
    cmds = [
        "bluetoothctl power on",
        "bluetoothctl discoverable on",
        "bluetoothctl pairable on",
        "bluetoothctl agent KeyboardOnly",
        "bluetoothctl default-agent"
    ]
    out_lines = []
    for c in cmds:
        out_lines.append(f"$ {c}")
        try:
            out = subprocess.check_output(c, shell=True, text=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:
            out = exc.output
        out_lines.append(out)
        out_lines.append("")
    return "Pairing mode commands executed:\n\n" + "\n".join(out_lines)
EOF
    echo "  Pairing routes appended to $SERVER_PY"
  fi
fi

echo "=== [ble_setup_extras] Setup complete ==="
echo "You can now use:"
echo "  - ipr_ble_diagnostics.sh          (BLE health check)"
echo "  - ipr_ble_hid_analyzer.py         (HID report analyzer)"
echo "  - /pairing                        (web pairing wizard)"
echo "  - /etc/ipr-keyboard/backend       (backend selector: 'ble' or 'uinput')"

echo "  - ipr_backend_manager.service     (ensures only one backend is active)"

# ---------------------------------------------------------------------------
# Final check: Ensure bt_hid_agent.service is active
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Checking bt_hid_agent.service status ==="
if systemctl is-active --quiet bt_hid_agent.service; then
  echo "[OK] bt_hid_agent.service is active."
else
  echo "[ERROR] bt_hid_agent.service is NOT active!"
  echo "Run: sudo systemctl start bt_hid_agent.service"
fi
