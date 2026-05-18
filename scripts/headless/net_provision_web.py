#!/usr/bin/env python3
"""
IPR Keyboard Management Web Interface

Serves the management UI at https://10.42.0.1/ while the permanent hotspot is
active.  Pages:
  /         Home — device status, hotspot credentials, SSH address
  /wifi     Wi-Fi setup — scan networks, save credentials
  /reboot   POST — reboot the Pi
  /shutdown POST — shut down the Pi

Authentication: HTTP Basic Auth using the hotspot password from
/etc/ipr-hotspot.secret.  The same password is used to join the hotspot SSID,
so no extra credential is required.

HTTPS: A self-signed certificate is generated once at /etc/ipr-provision-ssl/
and reused on subsequent starts.  Browsers will warn on first visit; tap
"Advanced -> Proceed" to continue.

Wi-Fi connect: credentials are saved as a NetworkManager profile with
autoconnect enabled but NOT immediately activated.  The hotspot (wlan0) stays
up; the Pi connects to the saved network on next boot.

Scan cache: Wi-Fi scanning runs in a background thread so page loads are
instant.  A scan is triggered at startup and again when the user clicks Rescan.

Installation:
    sudo cp scripts/headless/net_provision_web.py /usr/local/sbin/ipr-provision-web.py
    sudo chmod +x /usr/local/sbin/ipr-provision-web.py

Service:
    Managed by ipr-provision.service (launched by ipr-provision.sh)

category: Headless
purpose: Permanent management web interface over hotspot
sudo: yes (runs as root to bind port 443)
"""

import ssl
import subprocess
import threading
import time
from functools import wraps
from pathlib import Path

from flask import Flask, redirect, render_template_string, request

SECRET_FILE = Path("/etc/ipr-hotspot.secret")
HOTSPOT_CON = "ipr-hotspot"
SSL_DIR = Path("/etc/ipr-provision-ssl")
CERT_FILE = SSL_DIR / "cert.pem"
KEY_FILE = SSL_DIR / "key.pem"
_AUTH_USER = "ipr"
_AUTH_PASS: str = ""  # loaded at startup from secret file

# Rate limiting: {ip: [attempt_count, window_start_epoch]}
_rate: dict[str, list] = {}
_RATE_MAX = 5
_RATE_WINDOW = 60  # seconds

# Scan cache: background thread writes here; request handlers read without blocking
_scan_cache: list[str] = ["(scanning — please wait)"]
_scan_lock = threading.Lock()
_scan_in_progress = False

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Auth + TLS
# ---------------------------------------------------------------------------

def _load_secret() -> str:
    if not SECRET_FILE.exists():
        return ""
    for line in SECRET_FILE.read_text().splitlines():
        if line.startswith("PASS="):
            return line[5:].strip()
    return ""


def _ensure_ssl_cert() -> ssl.SSLContext:
    """Generate a persistent self-signed cert if absent, return SSLContext."""
    SSL_DIR.mkdir(mode=0o700, exist_ok=True)
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        print("[ipr-provision-web] Generating self-signed TLS certificate...")
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048",
                "-keyout", str(KEY_FILE), "-out", str(CERT_FILE),
                "-days", "3650", "-nodes",
                "-subj", "/CN=IPR Keyboard",
                "-addext", "subjectAltName=IP:10.42.0.1",
            ],
            check=True,
            capture_output=True,
        )
        KEY_FILE.chmod(0o600)
        CERT_FILE.chmod(0o644)
        print(f"[ipr-provision-web] Certificate written to {CERT_FILE}")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(CERT_FILE), str(KEY_FILE))
    return ctx


def _require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != _AUTH_USER or auth.password != _AUTH_PASS:
            return (
                "Unauthorized",
                401,
                {"WWW-Authenticate": 'Basic realm="IPR Keyboard"'},
            )
        return f(*args, **kwargs)
    return decorated


def _check_rate_limit(ip: str) -> bool:
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
# Device info helpers
# ---------------------------------------------------------------------------

def _read_hotspot_secret() -> tuple[str, str]:
    """Return (SSID, PASS) from /etc/ipr-hotspot.secret."""
    ssid = pass_ = ""
    if SECRET_FILE.exists():
        for line in SECRET_FILE.read_text().splitlines():
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
    """Return the first non-hotspot IP if connected to a home network, else ''."""
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True).strip()
        for ip in out.split():
            if ip and not ip.startswith("10.42."):
                return ip
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Page shell (nav + wrapper)
# ---------------------------------------------------------------------------

_SHELL = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>IPR Keyboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     margin:0;background:#f0f2f5;min-height:100vh}
nav{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
    padding:.8rem 1.2rem;display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}
nav a{color:rgba(255,255,255,.85);text-decoration:none;padding:.45rem .9rem;
      border-radius:20px;font-size:.95rem;transition:background .15s}
nav a:hover,nav a.active{background:rgba(255,255,255,.25);color:white}
nav .brand{color:white;font-weight:700;font-size:1.05rem;margin-right:auto}
nav form{margin:0}
nav button{background:rgba(255,255,255,.15);color:white;
           border:1px solid rgba(255,255,255,.4);
           padding:.45rem .9rem;border-radius:20px;font-size:.95rem;cursor:pointer}
nav button:hover{background:rgba(255,255,255,.3)}
.page{max-width:780px;margin:1.5rem auto;padding:0 1rem}
.card{background:white;border-radius:12px;padding:1.5rem;
      box-shadow:0 2px 8px rgba(0,0,0,.08);margin-bottom:1.2rem}
.card h2{margin:0 0 1rem;font-size:1.1rem;color:#2c3e50}
.row{display:flex;justify-content:space-between;align-items:baseline;
     padding:.5rem 0;border-bottom:1px solid #f0f0f0}
.row:last-child{border-bottom:none}
.row .lbl{color:#666;font-size:.9rem}
.row .val{font-weight:600;color:#2c3e50;text-align:right;word-break:break-all}
code{background:#eef;padding:.2rem .4rem;border-radius:4px;font-size:.88rem}
input,select{font-size:1rem;padding:.75rem;width:100%;border-radius:8px;
             border:1px solid #ddd;margin:.5rem 0}
.btn{font-size:1rem;padding:.8rem 1.2rem;border-radius:8px;border:none;
     cursor:pointer;font-weight:600;width:100%;margin:.5rem 0;display:block}
.btn-primary{background:#3498db;color:white}.btn-primary:hover{background:#2980b9}
.btn-secondary{background:#95a5a6;color:white}.btn-secondary:hover{background:#7f8c8d}
.btn-sm{display:inline-block;width:auto;padding:.75rem 1rem;margin:0}
.pw-row{display:grid;grid-template-columns:1fr auto;gap:.6rem;align-items:center;
        margin:.5rem 0}
.pw-row input{margin:0}
label{display:block;margin:.8rem 0 .2rem;font-weight:600;color:#444;font-size:.9rem}
.msg{padding:.9rem 1.1rem;border-radius:8px;margin-bottom:1rem;font-size:.95rem}
.msg.ok{background:#d5f4e6;color:#1e7e46;border:1px solid #a3e4bf}
.msg.err{background:#fadbd8;color:#922b21;border:1px solid #f1a8a0}
.badge{display:inline-block;background:#eee;border-radius:12px;
       padding:.2rem .7rem;font-size:.85rem;color:#555}
.badge.green{background:#d5f4e6;color:#1e7e46}
</style>
</head>
<body>
<nav>
  <span class="brand">IPR Keyboard</span>
  <a href="/" {% if page=='home' %}class="active"{% endif %}>Home</a>
  <a href="/wifi" {% if page=='wifi' %}class="active"{% endif %}>Wi-Fi Setup</a>
  <form method="post" action="/reboot"
        onsubmit="return confirm('Reboot the device now?')">
    <button type="submit">Reboot</button>
  </form>
  <form method="post" action="/shutdown"
        onsubmit="return confirm('Shut down the device now?')">
    <button type="submit">Shutdown</button>
  </form>
</nav>
<div class="page">
{% if msg %}<div class="msg {% if ok %}ok{% else %}err{% endif %}">{{ msg }}</div>{% endif %}
{{ body | safe }}
</div>
</body>
</html>"""


def _render(page: str, body: str, msg: str = "", ok: bool = False) -> str:
    return render_template_string(_SHELL, page=page, body=body, msg=msg, ok=ok)


# ---------------------------------------------------------------------------
# Wi-Fi scan helpers
# ---------------------------------------------------------------------------

def sh(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()


def _hotspot_ssid() -> str:
    try:
        out = sh(["nmcli", "-t", "-f", "GENERAL.CONNECTION", "dev", "show", "wlan0"])
        con_name = ""
        for line in out.splitlines():
            if line.startswith("GENERAL.CONNECTION:"):
                con_name = line.split(":", 1)[1].strip()
                break
        if not con_name or con_name == "--":
            return ""
        return sh(
            ["nmcli", "-t", "-f", "802-11-wireless.ssid", "con", "show", con_name]
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
        out = sh(["nmcli", "-t", "-f", "SSID", "dev", "wifi", "list"])
        ssids = []
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
    """Save credentials as a NetworkManager profile without activating it."""
    con_name = f"ipr-wifi-{ssid}"
    subprocess.run(
        ["nmcli", "con", "delete", con_name],
        check=False, capture_output=True,
    )
    if sec == "open" or (sec == "auto" and not psk):
        sh([
            "nmcli", "con", "add", "type", "wifi",
            "con-name", con_name,
            "ssid", ssid,
            "connection.autoconnect", "yes",
            "connection.autoconnect-priority", "10",
        ])
    else:
        sh([
            "nmcli", "con", "add", "type", "wifi",
            "con-name", con_name,
            "ssid", ssid,
            "wifi-sec.key-mgmt", "wpa-psk",
            "wifi-sec.psk", psk,
            "connection.autoconnect", "yes",
            "connection.autoconnect-priority", "10",
        ])


# ---------------------------------------------------------------------------
# Page body builders
# ---------------------------------------------------------------------------

def _home_body() -> str:
    hotspot_ssid, hotspot_pass = _read_hotspot_secret()
    hostname = _device_hostname()
    user = _ssh_user()
    home_ip = _home_network_ip()
    net_row = (
        f'<div class="row"><span class="lbl">Home network IP</span>'
        f'<span class="val">{home_ip} <span class="badge green">connected</span></span></div>'
        if home_ip else
        '<div class="row"><span class="lbl">Home network</span>'
        '<span class="val"><span class="badge">not connected</span></span></div>'
    )
    return f"""
<div class="card">
  <h2>Device Status</h2>
  <div class="row">
    <span class="lbl">Hostname</span>
    <span class="val">{hostname}</span>
  </div>
  <div class="row">
    <span class="lbl">SSH (mDNS)</span>
    <span class="val"><code>ssh {user}@{hostname}.local</code></span>
  </div>
  {net_row}
</div>
<div class="card">
  <h2>Management Hotspot</h2>
  <div class="row">
    <span class="lbl">SSID</span>
    <span class="val">{hotspot_ssid or "(not generated)"}</span>
  </div>
  <div class="row">
    <span class="lbl">Password</span>
    <span class="val"><code>{hotspot_pass or "(unknown)"}</code></span>
  </div>
  <div class="row">
    <span class="lbl">Web UI</span>
    <span class="val"><code>https://10.42.0.1/</code></span>
  </div>
  <div class="row">
    <span class="lbl">Login</span>
    <span class="val"><code>ipr</code> / hotspot password above</span>
  </div>
</div>"""


def _wifi_body(ssids: list[str]) -> str:
    options = "".join(f'<option value="{s}">{s}</option>' for s in ssids)
    return f"""
<div class="card">
  <h2>Connect to a Wi-Fi Network</h2>
  <p style="color:#666;font-size:.9rem;margin-top:0">
    Optional &mdash; saves credentials so the Pi can also reach the internet.
    The hotspot stays active; the Pi connects to this network after reboot.
  </p>
  <form method="post" action="/connect">
    <label>Network</label>
    <select name="ssid" required>{options}</select>
    <label>Security</label>
    <select name="security">
      <option value="auto">Auto (WPA2)</option>
      <option value="open">Open</option>
    </select>
    <label>Password</label>
    <div class="pw-row">
      <input id="psk" name="psk" type="password"
             placeholder="Wi-Fi password" autocomplete="new-password">
      <button type="button" class="btn btn-secondary btn-sm"
        onclick="var f=document.getElementById('psk');
                 f.type=f.type==='password'?'text':'password'">Show</button>
    </div>
    <button type="submit" class="btn btn-primary"
            style="margin-top:1rem">Save &amp; Connect on Reboot</button>
  </form>
</div>
<div class="card">
  <form method="post" action="/rescan">
    <button type="submit" class="btn btn-secondary">Rescan Networks</button>
  </form>
</div>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
@_require_auth
def index():
    msg_key = request.args.get("msg", "")
    ssid_saved = request.args.get("ssid", "")
    msg, ok = "", False
    if msg_key == "saved" and ssid_saved:
        import html as _html
        msg = (
            f"Wi-Fi credentials saved for <strong>{_html.escape(ssid_saved)}</strong>. "
            "The Pi will connect to this network after reboot. "
            "The hotspot remains active."
        )
        ok = True
    return _render("home", _home_body(), msg=msg, ok=ok)


@app.get("/wifi")
@_require_auth
def wifi_page():
    with _scan_lock:
        ssids = list(_scan_cache)
    return _render("wifi", _wifi_body(ssids))


@app.post("/rescan")
@_require_auth
def rescan():
    _trigger_scan_background()
    with _scan_lock:
        ssids = list(_scan_cache)
    return _render(
        "wifi",
        _wifi_body(ssids),
        msg="Scanning in background &mdash; reload in a few seconds to see updated networks.",
        ok=True,
    )


@app.post("/connect")
@_require_auth
def connect():
    ip = request.remote_addr or "unknown"
    if not _check_rate_limit(ip):
        return "Too many attempts — wait 60 seconds and try again.", 429

    ssid = (request.form.get("ssid") or "").strip()
    psk = request.form.get("psk") or ""
    sec = request.form.get("security") or "auto"

    if not ssid or ssid.startswith("("):
        with _scan_lock:
            ssids = list(_scan_cache)
        return _render("wifi", _wifi_body(ssids), msg="No SSID selected.", ok=False)

    try:
        _save_wifi_profile(ssid, psk, sec)
        import urllib.parse
        return redirect(f"/?msg=saved&ssid={urllib.parse.quote(ssid)}")
    except subprocess.CalledProcessError as e:
        import html as _html
        with _scan_lock:
            ssids = list(_scan_cache)
        msg = f"Could not save credentials: {_html.escape(e.output[-800:])}"
        return _render("wifi", _wifi_body(ssids), msg=msg, ok=False)


@app.post("/reboot")
@_require_auth
def reboot():
    subprocess.Popen(["reboot"])
    body = """
<div class="card" style="text-align:center;padding:3rem">
  <h2 style="color:#e67e22">Rebooting&hellip;</h2>
  <p style="color:#666">The device is restarting. Reconnect to the hotspot
  in about 30 seconds, then return to <code>https://10.42.0.1/</code></p>
</div>"""
    return _render("home", body, msg="Reboot initiated.", ok=True)


@app.post("/shutdown")
@_require_auth
def shutdown():
    subprocess.Popen(["shutdown", "-h", "now"])
    body = """
<div class="card" style="text-align:center;padding:3rem">
  <h2 style="color:#e74c3c">Shutting down&hellip;</h2>
  <p style="color:#666">The device is shutting down. It is safe to remove
  power after the activity LED stops blinking.</p>
</div>"""
    return _render("home", body, msg="Shutdown initiated.", ok=True)


if __name__ == "__main__":
    _AUTH_PASS = _load_secret()
    if not _AUTH_PASS:
        print(
            "[ipr-provision-web] WARNING: /etc/ipr-hotspot.secret not found or empty — "
            "authentication disabled. Run ipr-provision.sh first."
        )
    ssl_ctx = _ensure_ssl_cert()
    _trigger_scan_background()
    print("[ipr-provision-web] Starting management web interface...")
    print("[ipr-provision-web] Access at https://10.42.0.1/ when hotspot is active")
    app.run(host="0.0.0.0", port=443, ssl_context=ssl_ctx)
