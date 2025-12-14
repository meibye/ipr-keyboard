"""
Pairing wizard routes for ipr-keyboard web interface.

These routes provide a web-based interface for BLE pairing and backend management.
Auto-generated and installed by ble_setup_extras.sh
"""

from flask import Blueprint, render_template
import subprocess

pairing_bp = Blueprint('pairing', __name__, url_prefix='/pairing')


@pairing_bp.route("")
def pairing_page():
    """Display the pairing wizard interface."""
    return render_template("pairing_wizard.html")


@pairing_bp.route("/activate-ble")
def pairing_activate():
    """Switch backend selector to BLE and activate backend manager."""
    subprocess.call(["sudo", "sh", "-c", "echo ble > /etc/ipr-keyboard/backend"])
    subprocess.call(["sudo", "systemctl", "start", "ipr_backend_manager.service"])
    return "BLE backend activated via ipr_backend_manager."


@pairing_bp.route("/start")
def pairing_start():
    """Execute Bluetooth pairing mode commands."""
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
