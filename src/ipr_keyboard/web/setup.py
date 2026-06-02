"""
Setup / provisioning Blueprint  (/setup/)

Provides a simple management interface accessible via the Wi-Fi hotspot.
Authentication uses a form-based session login (username "ipr", password from
/etc/ipr-hotspot.secret).  Login is at /setup/login; /setup/ca.crt is public.

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
    session,
    url_for,
)

bp_setup = Blueprint("setup", __name__, url_prefix="/setup")

_SECRET_FILE = Path("/etc/ipr-hotspot.secret")
_CA_CERT_FILE = Path("/etc/ipr-ssl/ca.crt")
_SERVER_CERT_FILE = Path("/etc/ipr-ssl/server.crt")
_CERT_RENEW_SCRIPT = Path("/usr/local/sbin/ipr-cert-renew.sh")
_SETUP_USER = "ipr"
_SESSION_KEY = "setup_ok"

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
# Auth helpers
# ---------------------------------------------------------------------------

def _load_hotspot_password() -> str:
    try:
        if not _SECRET_FILE.exists():
            return ""
        for line in _SECRET_FILE.read_text().splitlines():
            if line.startswith("PASS="):
                return line[5:].strip()
    except OSError:
        pass
    return ""


def require_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get(_SESSION_KEY):
            return redirect(url_for("setup.login_page", next=request.path))
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
    try:
        if _SECRET_FILE.exists():
            for line in _SECRET_FILE.read_text().splitlines():
                if line.startswith("SSID="):
                    ssid = line[5:].strip()
                elif line.startswith("PASS="):
                    pass_ = line[5:].strip()
    except OSError:
        pass
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


def _cert_expiry() -> str:
    """Return the server cert expiry date as a plain string, or '' if unreadable."""
    try:
        out = subprocess.check_output(
            ["openssl", "x509", "-in", str(_SERVER_CERT_FILE), "-noout", "-enddate"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        return out.split("=", 1)[-1].strip() if "=" in out else out
    except Exception:
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

@bp_setup.get("/login")
def login_page():
    if session.get(_SESSION_KEY):
        return redirect(url_for("setup.home"))
    return render_template("setup/login.html", error=None)


@bp_setup.post("/login")
def login_submit():
    ip = request.remote_addr or "unknown"
    if not _check_rate(ip):
        return render_template(
            "setup/login.html",
            error="Too many attempts — wait 60 seconds and try again.",
        ), 429
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    expected = _load_hotspot_password()
    if username == _SETUP_USER and expected and password == expected:
        session[_SESSION_KEY] = True
        next_url = request.args.get("next", "")
        if next_url and next_url.startswith("/setup/") and ".." not in next_url:
            return redirect(next_url)
        return redirect(url_for("setup.home"))
    return render_template("setup/login.html", error="Invalid username or password."), 401


@bp_setup.route("/logout")
def logout():
    session.pop(_SESSION_KEY, None)
    return redirect(url_for("setup.login_page"))


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
@require_login
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
@require_login
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
@require_login
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
@require_login
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
@require_login
def connect():
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
@require_login
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
@require_login
def system():
    msg = request.args.get("msg", "")
    ok = request.args.get("ok", "0") == "1"
    return render_template(
        "setup/system.html",
        page="system",
        msg=msg, ok=ok,
        cert_expiry=_cert_expiry(),
        cert_renew_available=_CERT_RENEW_SCRIPT.exists(),
    )


@bp_setup.post("/renew-cert")
@require_login
def renew_cert():
    if not _CERT_RENEW_SCRIPT.exists():
        return render_template(
            "setup/system.html",
            page="system",
            msg="Certificate renewal script not installed. Run install_provision_service.sh first.",
            ok=False,
            cert_expiry=_cert_expiry(),
            cert_renew_available=False,
        )
    try:
        subprocess.check_output(
            ["sudo", str(_CERT_RENEW_SCRIPT), "--force"],
            text=True, stderr=subprocess.STDOUT, timeout=60,
        )
        # Service restart happens inside the renew script; give it a moment then
        # schedule a second restart in case the first one races with this response.
        subprocess.Popen(
            ["sudo", "bash", "-c", "sleep 4 && systemctl restart ipr_keyboard.service"],
        )
        return render_template(
            "setup/system.html",
            page="system",
            msg=(
                "Certificate renewed. The service is restarting — "
                "this page will reload in 10 seconds."
            ),
            ok=True,
            cert_expiry=_cert_expiry(),
            cert_renew_available=True,
            auto_reload=10,
        )
    except subprocess.TimeoutExpired:
        return render_template(
            "setup/system.html",
            page="system",
            msg="Certificate renewal timed out. Check the journal for details.",
            ok=False,
            cert_expiry=_cert_expiry(),
            cert_renew_available=True,
        )
    except subprocess.CalledProcessError as e:
        return render_template(
            "setup/system.html",
            page="system",
            msg=f"Certificate renewal failed: {e.output.strip()[-400:] if e.output else str(e)}",
            ok=False,
            cert_expiry=_cert_expiry(),
            cert_renew_available=True,
        )


@bp_setup.post("/reboot")
@require_login
def reboot():
    subprocess.Popen(["sudo", "reboot"])
    return render_template(
        "setup/system.html",
        page="system",
        msg="Reboot initiated. Reconnect to the hotspot in about 30 seconds.",
        ok=True,
        cert_expiry=_cert_expiry(),
        cert_renew_available=_CERT_RENEW_SCRIPT.exists(),
    )


@bp_setup.post("/shutdown")
@require_login
def shutdown():
    subprocess.Popen(["sudo", "shutdown", "-h", "now"])
    return render_template(
        "setup/system.html",
        page="system",
        msg="Shutdown initiated. Remove power after the LED stops blinking.",
        ok=True,
        cert_expiry=_cert_expiry(),
        cert_renew_available=_CERT_RENEW_SCRIPT.exists(),
    )
