#!/usr/bin/env python3
"""
IPR Keyboard Management Web Interface

Serves the management UI at https://10.42.0.1/ while the permanent hotspot is
active.  Allows scanning for Wi-Fi networks and saving credentials for cases
where the Pi should also connect to a home network via wlan0.

Authentication: HTTP Basic Auth using the hotspot password from
/etc/ipr-hotspot.secret.  The same password is used to join the hotspot SSID,
so no extra credential is required.

HTTPS: A self-signed certificate is generated once at /etc/ipr-provision-ssl/
and reused on subsequent starts.  Browsers will warn on first visit; tap
"Advanced -> Proceed" to continue.  This avoids the repeated iOS "not safe to
send password" prompt that occurs over plain HTTP.

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


PAGE_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>IPR Keyboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;margin:1.2rem;max-width:780px;background:#f5f5f5}
.container{background:white;border-radius:12px;padding:2rem;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
h1{color:#2c3e50;margin-top:0}
input,select,button{font-size:1rem;padding:.8rem;width:100%;margin:.6rem 0;border-radius:8px;border:1px solid #ddd;box-sizing:border-box}
button{background:#3498db;color:white;border:none;cursor:pointer;font-weight:600}
button:hover{background:#2980b9}
.row{display:grid;grid-template-columns:1fr auto;gap:.8rem;align-items:end}
.box{padding:1rem;border:1px solid #ddd;border-radius:10px;margin:1rem 0;background:#fafafa}
code{background:#e8e8e8;padding:.3rem .5rem;border-radius:6px}
.small{color:#555;font-size:.95rem}
.err{color:#c0392b;background:#fadbd8;border-color:#e74c3c}
.ok{color:#27ae60;background:#d5f4e6;border-color:#2ecc71}
label{display:block;margin-bottom:.3rem;font-weight:600;color:#2c3e50}
.header-box{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;border:none}
.header-box h1,.header-box p{color:white}
.show-btn{width:auto;padding:.8rem 1rem;margin:0;background:#e0e0e0;color:#333;border-color:#ccc}
.show-btn:hover{background:#d0d0d0}
.sec-row{display:grid;grid-template-columns:1fr 1fr;gap:.8rem}
</style>
</head>
<body>
<div class="container">
<div class="box header-box">
<h1>IPR Keyboard</h1>
<p class="small">You are connected directly to your IPR Keyboard device.
No router needed &mdash; use this page to configure Wi-Fi or check device status.</p>
</div>
<div class="box">
<p class="small">Management address: <code>https://10.42.0.1/</code></p>
</div>
{% if msg %}<div class="box {% if ok %}ok{% else %}err{% endif %}">{{ msg }}</div>{% endif %}
<div class="box">
<h3 style="margin-top:0">Connect to a Wi-Fi Network</h3>
<p class="small">Optional &mdash; saves credentials so the Pi can also reach the internet via Wi-Fi.
The hotspot stays active; the Pi connects to this network after reboot.</p>
<form method="post" action="/connect">
<label>SSID</label>
<select name="ssid" required>{% for s in ssids %}<option value="{{ s }}">{{ s }}</option>{% endfor %}</select>
<div class="sec-row">
<div>
  <label>Security</label>
  <select name="security"><option value="auto">Auto (WPA2)</option><option value="open">Open</option></select>
</div>
</div>
<label>Password</label>
<div class="row">
  <input id="psk" name="psk" type="password" placeholder="Wi-Fi password" autocomplete="new-password">
  <button type="button" class="show-btn" onclick="var f=document.getElementById('psk');f.type=f.type==='password'?'text':'password'">Show</button>
</div>
<button type="submit">Save &amp; Connect on Reboot</button>
</form>
</div>
<div class="box">
<form method="post" action="/rescan"><button type="submit" style="background:#95a5a6">Rescan Networks</button></form>
</div>
</div>
</body>
</html>"""


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
    time.sleep(3)  # rescan is async; give it time to populate
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


@app.get("/")
@_require_auth
def index():
    with _scan_lock:
        ssids = list(_scan_cache)
    return render_template_string(PAGE_TEMPLATE, ssids=ssids, msg=None, ok=False)


@app.post("/rescan")
@_require_auth
def rescan():
    _trigger_scan_background()
    with _scan_lock:
        ssids = list(_scan_cache)
    return render_template_string(
        PAGE_TEMPLATE, ssids=ssids,
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
        return render_template_string(
            PAGE_TEMPLATE, ssids=ssids, msg="No SSID selected.", ok=False
        )

    try:
        _save_wifi_profile(ssid, psk, sec)
        return redirect("/success")
    except subprocess.CalledProcessError as e:
        import html as _html
        with _scan_lock:
            ssids = list(_scan_cache)
        msg = f"Could not save credentials: {_html.escape(e.output[-800:])}"
        return render_template_string(PAGE_TEMPLATE, ssids=ssids, msg=msg, ok=False)


@app.get("/success")
def success():
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>IPR Keyboard &mdash; Saved</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
         margin:2rem;text-align:center;
         background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white}
    .box{background:white;color:#2c3e50;padding:3rem;border-radius:12px;
         max-width:500px;margin:4rem auto;box-shadow:0 10px 30px rgba(0,0,0,0.3)}
    h2{margin-top:0;color:#27ae60}
    code{background:#e8e8e8;padding:.2rem .4rem;border-radius:4px;font-size:.9rem}
  </style>
</head>
<body>
<div class="box">
  <h2>Credentials Saved</h2>
  <p>Wi-Fi credentials saved. The Pi will connect to this network after the next reboot.</p>
  <p>The hotspot remains active &mdash; return to <code>https://10.42.0.1/</code> at any time.</p>
  <p style="margin-top:2rem;font-size:.9rem;color:#7f8c8d">
    After reboot, the Pi is also reachable via SSH:<br>
    <code>ssh meibye@ipr-dev-pi4.local</code>
  </p>
</div>
</body>
</html>"""


if __name__ == "__main__":
    _AUTH_PASS = _load_secret()
    if not _AUTH_PASS:
        print(
            "[ipr-provision-web] WARNING: /etc/ipr-hotspot.secret not found or empty — "
            "authentication disabled. Run ipr-provision.sh first."
        )
    ssl_ctx = _ensure_ssl_cert()
    # Kick off initial background scan so results are ready when first user arrives
    _trigger_scan_background()
    print("[ipr-provision-web] Starting management web interface...")
    print("[ipr-provision-web] Access at https://10.42.0.1/ when hotspot is active")
    app.run(host="0.0.0.0", port=443, ssl_context=ssl_ctx)
