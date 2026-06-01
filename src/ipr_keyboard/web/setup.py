"""
Setup / provisioning Blueprint  (/setup/)

Provides a simple management interface accessible via the Wi-Fi hotspot.
Authentication uses HTTP Basic Auth with the hotspot password from
/etc/ipr-hotspot.secret.  All routes except /setup/ca.crt require auth.

This blueprint supersedes scripts/headless/net_provision_web.py.
"""

from __future__ import annotations

import subprocess
import threading
import time
import urllib.parse
from functools import wraps
from pathlib import Path

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

bp_setup = Blueprint("setup", __name__, url_prefix="/setup")

_SECRET_FILE = Path("/etc/ipr-hotspot.secret")
_CA_CERT_FILE = Path("/etc/ipr-ssl/ca.crt")
_BASIC_AUTH_USER = "ipr"

_LOG_UNITS = [
    "ipr_keyboard.service",
    "ipr-provision.service",
    "bt_hid_ble.service",
    "bt_hid_agent_unified.service",
    "bluetooth.service",
]

# ---------------------------------------------------------------------------
# Rate limiting  {ip: [attempt_count, window_start_epoch]}
# ---------------------------------------------------------------------------

_rate: dict[str, list] = {}
_RATE_MAX = 5
_RATE_WINDOW = 60


def _check_rate(ip: str) -> bool:
    now = time.time()
    entry = _rate.get(ip)
    if entry is None or now - entry[1] > _RATE_WINDOW:
        _rate[ip] = [1, now]
        return True
    if entry[0] >= _RATE_MAX:
        return False
    entry[0] += 1
    return True


# ---------------------------------------------------------------------------
# HTTP Basic Auth
# ---------------------------------------------------------------------------

def _load_hotspot_password() -> str:
    if not _SECRET_FILE.exists():
        return ""
    for line in _SECRET_FILE.read_text().splitlines():
        if line.startswith("PASS="):
            return line[5:].strip()
    return ""


def require_basic_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        ip = request.remote_addr or "unknown"
        if not _check_rate(ip):
            return "Too many attempts — wait 60 seconds and try again.", 429
        auth = request.authorization
        password = _load_hotspot_password()
        if not auth or auth.username != _BASIC_AUTH_USER or auth.password != password:
            return (
                "Unauthorized",
                401,
                {"WWW-Authenticate": 'Basic realm="IPR Keyboard"'},
            )
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# System helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(
            cmd, text=True, stderr=subprocess.STDOUT,
        ).strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip() if e.output else f"(exit {e.returncode})"
    except Exception as e:
        return f"(error: {e})"


def _read_hotspot_secret() -> tuple[str, str]:
    ssid = pass_ = ""
    if _SECRET_FILE.exists():
        for line in _SECRET_FILE.read_text().splitlines():
            if line.startswith("SSID="):
                ssid = line[5:].strip()
            elif line.startswith("PASS="):
                pass_ = line[5:].strip()
    return ssid, pass_


def _device_hostname() -> str:
    try:
        return subprocess.check_output(["hostname"], text=True).strip()
    except Exception:
        return "unknown"


def _ssh_user() -> str:
    env_file = Path("/opt/ipr_common.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("APP_USER="):
                return line[9:].strip()
    return "meibye"


def _home_network_ip() -> str:
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True).strip()
        for ip in out.split():
            if ip and not ip.startswith("10.42."):
                return ip
    except Exception:
        pass
    return ""


def _service_status(name: str) -> str:
    try:
        rc = subprocess.call(
            ["systemctl", "is-active", "--quiet", name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return "active" if rc == 0 else "inactive"
    except Exception:
        return "unknown"


def _bt_info() -> dict:
    adapter_out = _run(["bluetoothctl", "show"])
    powered = any(
        "yes" in line.split(":", 1)[-1].strip().lower()
        for line in adapter_out.splitlines()
        if "Powered:" in line
    )
    devices = []
    try:
        devs_out = subprocess.check_output(
            ["bluetoothctl", "devices"], text=True, stderr=subprocess.DEVNULL,
        )
        for line in devs_out.splitlines():
            parts = line.split(None, 2)
            if len(parts) >= 2:
                mac = parts[1]
                info = _run(["bluetoothctl", "info", mac])
                connected = any(
                    "yes" in l.split(":", 1)[-1].lower()
                    for l in info.splitlines()
                    if "Connected:" in l
                )
                name = parts[2] if len(parts) == 3 else mac
                devices.append({"mac": mac, "name": name, "connected": connected})
    except Exception:
        pass
    return {"powered": powered, "devices": devices}


# ---------------------------------------------------------------------------
# Wi-Fi scan helpers
# ---------------------------------------------------------------------------

_scan_cache: list[str] = ["(scanning — please wait)"]
_scan_lock = threading.Lock()
_scan_in_progress = False


def _sh(cmd: list[str]) -> str:
    return subprocess.check_output(
        cmd, stderr=subprocess.STDOUT, text=True,
    ).strip()


def _hotspot_ssid() -> str:
    try:
        out = _sh(["nmcli", "-t", "-f", "GENERAL.CONNECTION", "dev", "show", "wlan0"])
        con_name = ""
        for line in out.splitlines():
            if line.startswith("GENERAL.CONNECTION:"):
                con_name = line.split(":", 1)[1].strip()
                break
        if not con_name or con_name == "--":
            return ""
        return _sh(
            ["nmcli", "-t", "-f", "802-11-wireless.ssid", "con", "show", con_name],
        ).split(":", 1)[-1].strip()
    except subprocess.CalledProcessError:
        return ""


def _do_scan() -> None:
    global _scan_cache, _scan_in_progress
    subprocess.run(["nmcli", "radio", "wifi", "on"], check=False)
    subprocess.run(["nmcli", "dev", "wifi", "rescan"], check=False)
    time.sleep(3)
    own_ssid = _hotspot_ssid()
    try:
        out = _sh(["nmcli", "-t", "-f", "SSID", "dev", "wifi", "list"])
        ssids: list[str] = []
        for line in out.splitlines():
            s = line.strip()
            if s and s not in ssids and s != own_ssid:
                ssids.append(s)
        result = ssids or ["(no networks found — try rescan)"]
    except subprocess.CalledProcessError:
        result = ["(scan failed — try rescan)"]
    with _scan_lock:
        _scan_cache = result
        _scan_in_progress = False


def _trigger_scan_background() -> None:
    global _scan_in_progress
    with _scan_lock:
        if _scan_in_progress:
            return
        _scan_in_progress = True
    threading.Thread(target=_do_scan, daemon=True).start()


def _save_wifi_profile(ssid: str, psk: str, sec: str) -> None:
    con_name = f"ipr-wifi-{ssid}"
    subprocess.run(
        ["nmcli", "con", "delete", con_name],
        check=False, capture_output=True,
    )
    if sec == "open" or (sec == "auto" and not psk):
        _sh([
            "nmcli", "con", "add", "type", "wifi",
            "con-name", con_name, "ssid", ssid,
            "connection.autoconnect", "yes",
            "connection.autoconnect-priority", "10",
        ])
    else:
        _sh([
            "nmcli", "con", "add", "type", "wifi",
            "con-name", con_name, "ssid", ssid,
            "wifi-sec.key-mgmt", "wpa-psk",
            "wifi-sec.psk", psk,
            "connection.autoconnect", "yes",
            "connection.autoconnect-priority", "10",
        ])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp_setup.get("/ca.crt")
def download_ca_cert():
    """Serve the CA certificate for download — no auth required."""
    if not _CA_CERT_FILE.exists():
        return "CA certificate not found. Run gen_ipr_ssl_cert.sh first.", 404
    return send_file(
        str(_CA_CERT_FILE),
        mimetype="application/x-pem-file",
        as_attachment=True,
        download_name="ipr-keyboard-ca.crt",
    )


@bp_setup.get("/")
@require_basic_auth
def home():
    hotspot_ssid, hotspot_pass = _read_hotspot_secret()
    msg, ok = "", False
    msg_key = request.args.get("msg", "")
    ssid_saved = request.args.get("ssid", "")
    if msg_key == "saved" and ssid_saved:
        msg = (
            f"Wi-Fi credentials saved for <strong>{ssid_saved}</strong>. "
            "The Pi will connect after reboot. The hotspot remains active."
        )
        ok = True
    return render_template(
        "setup/home.html",
        page="home",
        msg=msg, ok=ok,
        hostname=_device_hostname(),
        ssh_user=_ssh_user(),
        home_ip=_home_network_ip(),
        hotspot_ssid=hotspot_ssid,
        hotspot_pass=hotspot_pass,
    )


@bp_setup.get("/status")
@require_basic_auth
def status():
    services = [
        {"label": "IPR Keyboard",   "status": _service_status("ipr_keyboard.service")},
        {"label": "BT HID BLE",     "status": _service_status("bt_hid_ble.service")},
        {"label": "BT HID Agent",   "status": _service_status("bt_hid_agent_unified.service")},
        {"label": "Hotspot / Setup","status": _service_status("ipr-provision.service")},
    ]
    bt = _bt_info()
    return render_template(
        "setup/status.html",
        page="status",
        msg="", ok=False,
        services=services,
        bt_powered=bt["powered"],
        bt_devices=bt["devices"],
    )


@bp_setup.get("/wifi")
@require_basic_auth
def wifi():
    _trigger_scan_background()
    with _scan_lock:
        ssids = list(_scan_cache)
    return render_template(
        "setup/wifi.html",
        page="wifi",
        msg="", ok=False,
        ssids=ssids,
    )


@bp_setup.post("/rescan")
@require_basic_auth
def rescan():
    _trigger_scan_background()
    with _scan_lock:
        ssids = list(_scan_cache)
    return render_template(
        "setup/wifi.html",
        page="wifi",
        ssids=ssids,
        msg="Scanning in background — reload in a few seconds to see updated networks.",
        ok=True,
    )


@bp_setup.post("/connect")
@require_basic_auth
def connect():
    ip = request.remote_addr or "unknown"
    if not _check_rate(ip):
        return "Too many attempts — wait 60 seconds and try again.", 429

    ssid = (request.form.get("ssid") or "").strip()
    psk = request.form.get("psk") or ""
    sec = request.form.get("security") or "auto"

    if not ssid or ssid.startswith("("):
        with _scan_lock:
            ssids = list(_scan_cache)
        return render_template(
            "setup/wifi.html", page="wifi",
            ssids=ssids, msg="No SSID selected.", ok=False,
        )

    try:
        _save_wifi_profile(ssid, psk, sec)
        return redirect(
            url_for("setup.home") + f"?msg=saved&ssid={urllib.parse.quote(ssid)}"
        )
    except subprocess.CalledProcessError as e:
        with _scan_lock:
            ssids = list(_scan_cache)
        msg = f"Could not save credentials: {e.output[-800:] if e.output else ''}"
        return render_template(
            "setup/wifi.html", page="wifi",
            ssids=ssids, msg=msg, ok=False,
        )


@bp_setup.get("/logs")
@require_basic_auth
def logs():
    selected = request.args.getlist("unit") or ["ipr_keyboard.service"]
    cmd = ["journalctl", "-n", "200", "-o", "short", "--no-pager"]
    for u in selected:
        cmd += ["-u", u]
    try:
        log_content = subprocess.check_output(
            cmd, text=True, stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        log_content = e.output or "(no output)"
    except Exception as e:
        log_content = f"Error reading logs: {e}"
    return render_template(
        "setup/logs.html",
        page="logs",
        msg="", ok=False,
        all_units=_LOG_UNITS,
        selected_units=selected,
        log_content=log_content,
    )


@bp_setup.get("/system")
@require_basic_auth
def system():
    msg = request.args.get("msg", "")
    return render_template(
        "setup/system.html",
        page="system",
        msg=msg, ok=False,
    )


@bp_setup.post("/reboot")
@require_basic_auth
def reboot():
    subprocess.Popen(["sudo", "reboot"])
    return render_template(
        "setup/system.html",
        page="system",
        msg="Reboot initiated. Reconnect to the hotspot in about 30 seconds.",
        ok=True,
    )


@bp_setup.post("/shutdown")
@require_basic_auth
def shutdown():
    subprocess.Popen(["sudo", "shutdown", "-h", "now"])
    return render_template(
        "setup/system.html",
        page="system",
        msg="Shutdown initiated. Remove power after the LED stops blinking.",
        ok=True,
    )
