#!/usr/bin/env python3
"""
IPR Wi-Fi Provisioning Web Interface

This Flask application provides a web-based interface for configuring Wi-Fi credentials
on a Raspberry Pi via a hotspot connection. When the Pi cannot connect to a known Wi-Fi
network, it creates a hotspot and this web interface allows users to scan for and connect
to available networks.

The interface runs on port 80 at http://10.42.0.1/ when the hotspot is active.

Installation:
    sudo cp scripts/headless/net_provision_web.py /usr/local/sbin/ipr-provision-web.py
    sudo chmod +x /usr/local/sbin/ipr-provision-web.py

Service:
    Managed by ipr-provision-web.service

category: Headless
purpose: Wi-Fi provisioning web interface
sudo: yes (runs as root to bind port 80)
"""

import html
import subprocess

from flask import Flask, redirect, render_template_string, request

app = Flask(__name__)

# HTML template for provisioning interface
PAGE_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>IPR Wi-Fi Provisioning</title>
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
.header-box h1{color:white}
</style>
</head>
<body>
<div class="container">
<div class="box header-box">
<h1>IPR Keyboard Wi-Fi Setup</h1>
<p class="small">Configure your Raspberry Pi Wi-Fi connection</p>
</div>
<div class="box">
<p class="small">Connected to IPR provisioning hotspot<br>Access at <code>http://10.42.0.1/</code></p>
</div>
{% if msg %}<div class="box {% if ok %}ok{% else %}err{% endif %}">{{ msg }}</div>{% endif %}
<div class="box">
<h3 style="margin-top:0">Select Your Network</h3>
<form method="post" action="/connect">
<label>SSID</label>
<select name="ssid" required>{% for s in ssids %}<option value="{{ s }}">{{ s }}</option>{% endfor %}</select>
<div class="row">
<div><label>Password</label><input name="psk" type="password" placeholder="Wi-Fi password"></div>
<div><label>Security</label><select name="security"><option value="auto">Auto</option><option value="open">Open</option></select></div>
</div>
<button type="submit">Save & Connect</button>
</form>
</div>
<div class="box">
<form method="post" action="/rescan"><button type="submit" style="background:#95a5a6">Rescan Networks</button></form>
</div>
</div>
</body>
</html>"""


def sh(cmd: list[str]) -> str:
    """Execute shell command and return output"""
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()


def wifi_scan_ssids() -> list[str]:
    """Scan for available Wi-Fi networks and return list of SSIDs"""
    # Ensure Wi-Fi radio is on
    subprocess.run(["nmcli", "radio", "wifi", "on"], check=False)
    subprocess.run(["nmcli", "dev", "wifi", "rescan"], check=False)

    try:
        out = sh(["nmcli", "-t", "-f", "SSID", "dev", "wifi", "list"])
        ssids = []
        for line in out.splitlines():
            s = line.strip()
            if s and s not in ssids:
                ssids.append(s)
        return ssids or ["(no networks found — try rescan)"]
    except subprocess.CalledProcessError:
        return ["(scan failed — try rescan)"]


@app.get("/")
def index():
    """Main provisioning page"""
    ssids = wifi_scan_ssids()
    return render_template_string(PAGE_TEMPLATE, ssids=ssids, msg=None, ok=False)


@app.post("/rescan")
def rescan():
    """Rescan for networks"""
    ssids = wifi_scan_ssids()
    return render_template_string(
        PAGE_TEMPLATE, ssids=ssids, msg="✓ Networks rescanned.", ok=True
    )


@app.post("/connect")
def connect():
    """Connect to selected Wi-Fi network"""
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
            # Open network
            sh(["nmcli", "dev", "wifi", "connect", ssid])
        else:
            # Secured network
            sh(["nmcli", "dev", "wifi", "connect", ssid, "password", psk])

        # Connection succeeded
        return redirect("/success")
    except subprocess.CalledProcessError as e:
        ssids = wifi_scan_ssids()
        msg = f"❌ Connection failed:\n{html.escape(e.output[-800:])}"
        return render_template_string(PAGE_TEMPLATE, ssids=ssids, msg=msg, ok=False)


@app.get("/success")
def success():
    """Success page after connection"""
    return """
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <title>Wi-Fi Connected</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
          body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            margin: 2rem;
            text-align: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
          }
          .box {
            background: white;
            color: #2c3e50;
            padding: 3rem;
            border-radius: 12px;
            max-width: 500px;
            margin: 4rem auto;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
          }
          h2 { margin-top: 0; color: #27ae60; }
        </style>
      </head>
      <body>
        <div class="box">
          <h2>✓ Wi-Fi Configured Successfully!</h2>
          <p>The Raspberry Pi is attempting to connect to your network.</p>
          <p>You can close this page. The Pi will exit hotspot mode shortly.</p>
          <p style="margin-top: 2rem; font-size: 0.9rem; color: #7f8c8d;">
            Access the Pi via SSH once connected:<br>
            <code>ssh user@hostname.local</code>
          </p>
        </div>
      </body>
    </html>
    """


if __name__ == "__main__":
    print("[ipr-provision-web] Starting Wi-Fi provisioning web interface...")
    print("[ipr-provision-web] Access at http://10.42.0.1/ when hotspot is active")
    app.run(host="0.0.0.0", port=80)
