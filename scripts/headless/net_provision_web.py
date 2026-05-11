#!/usr/bin/env python3
"""
IPR Keyboard Management Web Interface

Serves the management UI at http://10.42.0.1/ while the permanent hotspot is
active.  Allows scanning for Wi-Fi networks and saving credentials for cases
where the Pi should also connect to a home network via wlan0.

Authentication: HTTP Basic Auth using the hotspot password from
/etc/ipr-hotspot.secret.  The same password is used to join the hotspot SSID,
so no extra credential is required.

Installation:
    sudo cp scripts/headless/net_provision_web.py /usr/local/sbin/ipr-provision-web.py
    sudo chmod +x /usr/local/sbin/ipr-provision-web.py

Service:
    Managed by ipr-provision.service (launched by ipr-provision.sh)

category: Headless
purpose: Permanent management web interface over hotspot
sudo: yes (runs as root to bind port 80)
"""

import subprocess
import time
from functools import wraps
from pathlib import Path

from flask import Flask, redirect, render_template_string, request

SECRET_FILE = Path("/etc/ipr-hotspot.secret")
HOTSPOT_CON = "ipr-hotspot"
_AUTH_USER = "ipr"
_AUTH_PASS: str = ""  # loaded at startup from secret file

# Rate limiting: {ip: [attempt_count, window_start_epoch]}
_rate: dict[str, list] = {}
_RATE_MAX = 5
_RATE_WINDOW = 60  # seconds

app = Flask(__name__)


def _load_secret() -> str:
    """Return the PASS value from /etc/ipr-hotspot.secret."""
    if not SECRET_FILE.exists():
        return ""
    for line in SECRET_FILE.read_text().splitlines():
        if line.startswith("PASS="):
            return line[5:].strip()
    return ""


def _require_auth(f):
    """Decorator: HTTP Basic Auth using the hotspot password."""
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
    """Return True if the request is allowed, False if rate-limited."""
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
.row{display:grid;grid-template-columns:1fr 1fr;gap:.8rem}
.box{padding:1rem;border:1px solid #ddd;border-radius:10px;margin:1rem 0;background:#fafafa}
code{background:#e8e8e8;padding:.3rem .5rem;border-radius:6px}
.small{color:#555;font-size:.95rem}
.err{color:#c0392b;background:#fadbd8;border-color:#e74c3c}
.ok{color:#27ae60;background:#d5f4e6;border-color:#2ecc71}
label{display:block;margin-bottom:.3rem;font-weight:600;color:#2c3e50}
.header-box{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;border:none}
.header-box h1,.header-box p{color:white}
</style>
</head>
<body>
<div class="container">
<div class="box header-box">
<h1>IPR Keyboard</h1>
<p class="small">You are connected directly to your IPR Keyboard device.
No router needed — use this page to configure Wi-Fi or check device status.</p>
</div>
<div class="box">
<p class="small">Management address: <code>http://10.42.0.1/</code></p>
</div>
{% if msg %}<div class="box {% if ok %}ok{% else %}err{% endif %}">{{ msg }}</div>{% endif %}
<div class="box">
<h3 style="margin-top:0">Connect to a Wi-Fi Network</h3>
<p class="small">Optional — only needed if the Pi should also reach the internet via Wi-Fi.</p>
<form method="post" action="/connect">
<label>SSID</label>
<select name="ssid" required>{% for s in ssids %}<option value="{{ s }}">{{ s }}</option>{% endfor %}</select>
<div class="row">
<div><label>Password</label><input name="psk" type="password" placeholder="Wi-Fi password"></div>
<div><label>Security</label><select name="security"><option value="auto">Auto</option><option value="open">Open</option></select></div>
</div>
<button type="submit">Save &amp; Connect</button>
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
    """Return the SSID currently broadcast by the hotspot, or empty string."""
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


def wifi_scan_ssids() -> list[str]:
    subprocess.run(["nmcli", "radio", "wifi", "on"], check=False)
    subprocess.run(["nmcli", "dev", "wifi", "rescan"], check=False)
    time.sleep(2)  # rescan is async; wait for results

    own_ssid = _hotspot_ssid()
    try:
        out = sh(["nmcli", "-t", "-f", "SSID", "dev", "wifi", "list"])
        ssids = []
        for line in out.splitlines():
            s = line.strip()
            if s and s not in ssids and s != own_ssid:
                ssids.append(s)
        return ssids or ["(no networks found — try rescan)"]
    except subprocess.CalledProcessError:
        return ["(scan failed — try rescan)"]


@app.get("/")
@_require_auth
def index():
    ssids = wifi_scan_ssids()
    return render_template_string(PAGE_TEMPLATE, ssids=ssids, msg=None, ok=False)


@app.post("/rescan")
@_require_auth
def rescan():
    ssids = wifi_scan_ssids()
    return render_template_string(
        PAGE_TEMPLATE, ssids=ssids, msg="✓ Networks rescanned.", ok=True
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
        ssids = wifi_scan_ssids()
        return render_template_string(
            PAGE_TEMPLATE, ssids=ssids, msg="❌ No SSID selected.", ok=False
        )

    try:
        if sec == "open" or (sec == "auto" and not psk):
            sh(["nmcli", "dev", "wifi", "connect", ssid])
        else:
            sh(["nmcli", "dev", "wifi", "connect", ssid, "password", psk])
        return redirect("/success")
    except subprocess.CalledProcessError as e:
        import html as _html
        ssids = wifi_scan_ssids()
        msg = f"❌ Connection failed:\n{_html.escape(e.output[-800:])}"
        return render_template_string(PAGE_TEMPLATE, ssids=ssids, msg=msg, ok=False)


@app.get("/success")
def success():
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>IPR Keyboard — Connected</title>
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
  <h2>✓ Credentials Saved</h2>
  <p>Connecting — this may take a moment.</p>
  <p>The hotspot stays active. Return to <code>http://10.42.0.1/</code> any time.</p>
  <p style="margin-top:2rem;font-size:.9rem;color:#7f8c8d">
    Once on your network, the Pi is also reachable via SSH:<br>
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
    print("[ipr-provision-web] Starting management web interface...")
    print("[ipr-provision-web] Access at http://10.42.0.1/ when hotspot is active")
    app.run(host="0.0.0.0", port=80)
