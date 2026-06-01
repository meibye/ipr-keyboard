#!/usr/bin/env python3
"""
svc_status_monitor.py

Interactive TUI for ipr-keyboard service/daemon status and control.
Covers systemd units, internal application threads, and runtime component checks.

Usage:
  sudo ./scripts/service/svc_status_monitor.py

Prerequisites:
  - Must be run as root
  - python3, curses, systemctl, journalctl must be available

category: Service
purpose: Interactive TUI for monitoring and controlling services

Requires: python3, curses, systemctl, journalctl
"""

import curses
import json
import os
import re
import socket
import subprocess
import threading
import time

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# ---------------------------------------------------------------------------
# Systemd service definitions  (unit name, short description)
# ---------------------------------------------------------------------------

SERVICES = [
    # ---- core application stack ----
    ("ipr_keyboard.service",         "Main app: USB→BT bridge, web API, config"),
    ("bt_hid_ble.service",           "BLE HID GATT keyboard daemon"),
    ("bt_hid_agent_unified.service", "Bluetooth pairing agent"),
    # ---- headless / network ----
    ("ipr-provision.service",        "Wi-Fi hotspot setup (oneshot)"),
    ("ipr-cert-renew.timer",         "TLS cert auto-renewal timer (daily)"),
    ("NetworkManager.service",       "Network Manager (hotspot/Wi-Fi via nmcli)"),
    # ---- bluetooth stack ----
    ("bluetooth.service",            "BlueZ Bluetooth stack daemon"),
    ("dbus.service",                 "D-Bus system message bus"),
    ("systemd-udevd.service",        "Device event manager (udev)"),
]

# ---------------------------------------------------------------------------
# Application component checks
# These cover internal threads and sub-processes that run inside the systemd
# services above.  Status is derived by probing ports or querying system state
# rather than systemctl.
# ---------------------------------------------------------------------------

def _config_path() -> str:
    """Locate config.json relative to this script or in the default dev tree."""
    candidates = [
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))),
            "config.json",
        ),
        os.path.expanduser("~/dev/ipr-keyboard/config.json"),
        "/home/pi/dev/ipr-keyboard/config.json",
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return ""


def _get_web_port() -> int:
    """Read web server port from config.json (default 8080)."""
    p = _config_path()
    if p:
        try:
            with open(p) as f:
                data = json.load(f)
                return int(data.get("LogPort", data.get("port", 8080)))
        except Exception:
            pass
    return 8080


def _check_tcp(host: str, port: int, timeout: float = 1.0) -> str:
    """Return 'listening' if the TCP port accepts a connection, else 'not reachable'."""
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return "listening"
    except OSError:
        return "not reachable"


def _svc_active(unit: str) -> bool:
    try:
        return subprocess.call(
            ["systemctl", "is-active", "--quiet", unit],
            timeout=3, stderr=subprocess.DEVNULL,
        ) == 0
    except Exception:
        return False


def _check_web_dashboard() -> str:
    """Probe the Flask web server TCP port."""
    return _check_tcp("127.0.0.1", _get_web_port())


def _check_bt_forwarder() -> str:
    """BT forwarder runs as a thread inside ipr_keyboard.service."""
    return "running" if _svc_active("ipr_keyboard.service") else "stopped"


def _check_hotspot() -> str:
    """Query nmcli for the ipr-hotspot connection state."""
    try:
        out = subprocess.check_output(
            ["nmcli", "-t", "-f", "GENERAL.STATE", "con", "show", "ipr-hotspot"],
            text=True, stderr=subprocess.DEVNULL, timeout=3,
        ).strip()
        return "active" if "activated" in out.lower() else "inactive"
    except FileNotFoundError:
        return "nmcli missing"
    except subprocess.CalledProcessError:
        return "not configured"
    except Exception:
        return "unknown"


def _check_setup_https() -> str:
    """Probe the /setup/ HTTPS endpoint served by ipr_keyboard.service on port 443."""
    if not _svc_active("ipr_keyboard.service"):
        return "service down"
    return _check_tcp("127.0.0.1", 443)


def _check_cert_renewal() -> str:
    """Report days remaining on the server TLS certificate."""
    cert = "/etc/ipr-ssl/server.crt"
    if not os.path.isfile(cert):
        return "cert missing"
    try:
        import ssl as _ssl
        ctx = _ssl.create_default_context()
        # Use openssl to get the expiry without needing a live connection
        import datetime
        out = subprocess.check_output(
            ["openssl", "x509", "-in", cert, "-noout", "-enddate"],
            text=True, stderr=subprocess.DEVNULL, timeout=3,
        ).strip()
        # notAfter=Jul  3 18:04:37 2027 GMT
        date_str = out.split("=", 1)[-1].strip()
        expiry = datetime.datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
        days = (expiry - datetime.datetime.utcnow()).days
        if days < 0:
            return "EXPIRED"
        if days <= 30:
            return f"expires in {days}d !"
        return f"ok ({days}d left)"
    except Exception:
        return "unknown"


# (label, description, check_fn) — check_fn() returns a status string
APP_COMPONENTS = [
    ("Web Dashboard",   "Flask web UI + REST API (ipr_keyboard.svc)",  _check_web_dashboard),
    ("BT Forwarder",    "USB→BLE keyboard forwarding loop",             _check_bt_forwarder),
    ("Hotspot",         "Wi-Fi provisioning hotspot (nmcli)",           _check_hotspot),
    ("Setup HTTPS",     "Provisioning UI at /setup/ (port 443)",        _check_setup_https),
    ("TLS Cert",        "Server cert validity (auto-renews at 30 days)", _check_cert_renewal),
]

# ---------------------------------------------------------------------------
# Service status helpers
# ---------------------------------------------------------------------------

def get_service_status(svc: str) -> str:
    """Return the systemctl is-active status string for a unit."""
    try:
        return subprocess.check_output(
            ["systemctl", "is-active", svc],
            text=True, stderr=subprocess.DEVNULL, timeout=5,
        ).strip()
    except subprocess.CalledProcessError as exc:
        # is-active exits non-zero for inactive/failed but still prints the state
        text = (exc.output or "").strip()
        if text:
            return text
        # Distinguish "not installed" from genuinely inactive
        unit_dirs = [
            "/etc/systemd/system",
            "/lib/systemd/system",
            "/usr/lib/systemd/system",
        ]
        if not any(os.path.isfile(os.path.join(d, svc)) for d in unit_dirs):
            return "not installed"
        return "inactive"
    except Exception:
        return "unknown"


def status_color(status: str) -> int:
    """Map a status string to a curses colour-pair index (1–4)."""
    s = status.lower()
    if s in ("active", "running", "listening") or s.startswith("ok ("):
        return 2  # green
    if s in ("failed", "dead", "not reachable", "stopped", "service down",
             "expired", "cert missing"):
        return 1  # red
    if s in ("activating", "inactive", "not configured") or "expires in" in s:
        return 3  # yellow
    # not installed, nmcli missing, unknown, error, checking… …
    return 4  # cyan/dim


# ---------------------------------------------------------------------------
# Background polling threads
# ---------------------------------------------------------------------------

class _ServicePoller(threading.Thread):
    def __init__(self, services):
        super().__init__(daemon=True)
        self.services = services
        self.status = {s[0]: "checking…" for s in services}
        self.running = True

    def run(self):
        while self.running:
            for unit, _ in self.services:
                self.status[unit] = get_service_status(unit)
            time.sleep(2)

    def stop(self):
        self.running = False


class _AppPoller(threading.Thread):
    """Polls application component checks at a slower rate (network probes)."""
    def __init__(self, components):
        super().__init__(daemon=True)
        self.components = components
        self.status = {c[0]: "checking…" for c in components}
        self.running = True

    def run(self):
        while self.running:
            for label, _, check_fn in self.components:
                try:
                    self.status[label] = check_fn()
                except Exception:
                    self.status[label] = "error"
            time.sleep(5)

    def stop(self):
        self.running = False


# ---------------------------------------------------------------------------
# Bluetooth device helpers (unchanged)
# ---------------------------------------------------------------------------

def get_bt_devices():
    return []


def device_status_color(connected, paired):
    if connected:
        return 2
    if paired:
        return 3
    return 1


# ---------------------------------------------------------------------------
# Config / diagnostic helpers (unchanged)
# ---------------------------------------------------------------------------

def get_config_info():
    p = _config_path()
    if not p:
        return {"error": "config.json not found"}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception as exc:
        return {"error": str(exc)}


def get_diag_info():
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("diag_status.sh", "diag_troubleshoot.sh"):
        path = os.path.join(script_dir, name)
        if os.path.isfile(path):
            try:
                raw = subprocess.check_output(
                    [path], text=True, timeout=10,
                    env={**os.environ, "TERM": "dumb", "NO_COLOR": "1"},
                ).strip()
                return _ANSI_ESCAPE.sub("", raw)
            except Exception:
                pass
    return "Diagnostics unavailable"


# ---------------------------------------------------------------------------
# Helper: safe addstr (clamps to terminal bounds)
# ---------------------------------------------------------------------------

def _addstr(stdscr, row, col, text, attr=curses.A_NORMAL):
    max_row, max_col = stdscr.getmaxyx()
    if row < 0 or row >= max_row - 1:
        return
    if col >= max_col:
        return
    available = max_col - col - 1
    if available <= 0:
        return
    try:
        stdscr.addstr(row, col, text[:available], attr)
    except curses.error:
        pass


# ---------------------------------------------------------------------------
# Detail views (Enter key on a row)
# ---------------------------------------------------------------------------

def _show_journal(stdscr, svc, has_colors):
    """Scrollable journal viewer with toggleable line wrapping (w key)."""
    import textwrap

    try:
        raw = subprocess.check_output(
            ["journalctl", "-u", svc, "-n", "300", "--no-pager"], text=True,
            stderr=subprocess.DEVNULL,
        )
        raw_lines = raw.splitlines()
    except subprocess.CalledProcessError as exc:
        raw_lines = (exc.output or "").splitlines() or [f"Error: {exc}"]
    except Exception as exc:
        raw_lines = [f"Error: {exc}"]

    wrap_enabled = True

    def build_display(width: int) -> list[str]:
        if not wrap_enabled:
            return list(raw_lines)
        lines: list[str] = []
        for raw_line in raw_lines:
            if not raw_line:
                lines.append("")
            else:
                lines.extend(textwrap.wrap(raw_line, width=width) or [""])
        return lines

    max_rows, max_cols = stdscr.getmaxyx()
    content_rows = max_rows - 3
    display = build_display(max(max_cols - 4, 10))
    total = len(display)
    offset = max(0, total - content_rows)  # start at bottom

    stdscr.nodelay(False)
    while True:
        max_rows, max_cols = stdscr.getmaxyx()
        content_width = max(max_cols - 4, 10)
        content_rows = max_rows - 3

        stdscr.clear()
        _addstr(stdscr, 0, 2, f"Journal: {svc}", curses.A_BOLD)

        visible = display[offset: offset + content_rows]
        for idx, line in enumerate(visible):
            _addstr(stdscr, 2 + idx, 2, line)

        # Status bar
        pct = int(100 * (offset + content_rows) / total) if total else 100
        pct = min(pct, 100)
        wrap_label = "wrap:ON" if wrap_enabled else "wrap:OFF"
        status = (
            f"Lines {offset + 1}–{min(offset + content_rows, total)}/{total}"
            f"  ({pct}%)  ↑↓ PgUp/PgDn  w:{wrap_label}  q/Esc return"
        )
        _addstr(stdscr, max_rows - 1, 2, status, curses.A_DIM)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), 27, curses.KEY_BACKSPACE):
            break
        elif key == curses.KEY_UP:
            offset = max(offset - 1, 0)
        elif key == curses.KEY_DOWN:
            offset = min(offset + 1, max(0, total - content_rows))
        elif key == curses.KEY_PPAGE:
            offset = max(offset - content_rows, 0)
        elif key == curses.KEY_NPAGE:
            offset = min(offset + content_rows, max(0, total - content_rows))
        elif key == curses.KEY_HOME:
            offset = 0
        elif key == curses.KEY_END:
            offset = max(0, total - content_rows)
        elif key in (ord("w"), ord("W")):
            # Toggle wrap; preserve approximate scroll position by percent
            pct_pos = offset / total if total else 0
            wrap_enabled = not wrap_enabled
            display = build_display(content_width)
            total = len(display)
            offset = max(0, min(int(pct_pos * total), total - content_rows))


def _show_service_detail(stdscr, svc, has_colors):
    _addstr(stdscr, 0, 2, f"Service: {svc}", curses.A_BOLD)
    _addstr(stdscr, 2, 2,
            "Actions: [S]tart  s[T]op  [R]estart  [J]ournal  [E]nable  [D]isable",
            curses.A_DIM)
    _addstr(stdscr, curses.LINES - 1, 2, "Press key for action or any other key to return…")
    stdscr.refresh()
    action = stdscr.getch()
    if action in (ord("s"), ord("S")):
        subprocess.run(["sudo", "systemctl", "start", svc])
    elif action in (ord("t"), ord("T")):
        subprocess.run(["sudo", "systemctl", "stop", svc])
    elif action in (ord("r"), ord("R")):
        subprocess.run(["sudo", "systemctl", "restart", svc])
    elif action in (ord("e"), ord("E")):
        subprocess.run(["systemctl", "enable", svc])
    elif action in (ord("d"), ord("D")):
        subprocess.run(["systemctl", "disable", svc])
    elif action in (ord("j"), ord("J")):
        stdscr.clear()
        _show_journal(stdscr, svc, has_colors)


def _show_app_detail(stdscr, label, desc, status):
    _addstr(stdscr, 0, 2, f"Component: {label}", curses.A_BOLD)
    _addstr(stdscr, 1, 2, desc, curses.A_DIM)
    _addstr(stdscr, 3, 2, f"Status: {status}")

    row = 5
    if label == "Web Dashboard":
        port = _get_web_port()
        _addstr(stdscr, row, 2, f"URL: https://<device-ip>:{port}/")
        row += 1
        _addstr(stdscr, row, 2, f"Setup: https://10.42.0.1/setup/")
    elif label == "Hotspot":
        secret = "/etc/ipr-hotspot.secret"
        if os.path.isfile(secret):
            try:
                lines = open(secret).read().splitlines()
                for i, line in enumerate(lines[:6]):
                    _addstr(stdscr, row + i, 2, line)
                row += len(lines[:6]) + 1
            except Exception as exc:
                _addstr(stdscr, row, 2, f"Could not read secret: {exc}")
        else:
            _addstr(stdscr, row, 2, "Secret file not found: " + secret)
        row += 1
        _addstr(stdscr, row, 2, "Setup UI: https://10.42.0.1/setup/")
    elif label == "Setup HTTPS":
        _addstr(stdscr, row, 2, "URL: https://10.42.0.1/setup/")
        row += 1
        _addstr(stdscr, row, 2, "Managed by: ipr_keyboard.service (Flask /setup/ Blueprint)")
    elif label == "TLS Cert":
        _addstr(stdscr, row, 2, "Cert: /etc/ipr-ssl/server.crt")
        row += 1
        _addstr(stdscr, row, 2, "Auto-renewal: ipr-cert-renew.timer (daily, renews at ≤30 days)")
        row += 1
        _addstr(stdscr, row, 2, "Manual: https://10.42.0.1/setup/system → Renew Certificate")
    elif label == "BT Forwarder":
        _addstr(stdscr, row, 2, "Thread inside ipr_keyboard.service.")
        row += 1
        _addstr(stdscr, row, 2, "Control via the ipr_keyboard.service entry above.")

    _addstr(stdscr, curses.LINES - 1, 2, "Press any key to return…")
    stdscr.refresh()
    stdscr.getch()


# ---------------------------------------------------------------------------
# Config / diagnostics scrollable view
# ---------------------------------------------------------------------------

def _show_config_diag(stdscr):
    """Scrollable config + diagnostics viewer."""
    import textwrap

    cfg = get_config_info()
    cfg_lines = ["── Config ──"] + [f"  {k}: {v}" for k, v in cfg.items()]
    diag_raw = get_diag_info()
    diag_lines = ["", "── Diagnostics ──"] + diag_raw.splitlines()
    all_lines = cfg_lines + diag_lines

    stdscr.nodelay(False)
    offset = 0

    while True:
        max_rows, max_cols = stdscr.getmaxyx()
        content_width = max(max_cols - 4, 10)
        content_rows = max_rows - 2  # title row + status bar

        # Wrap lines to terminal width
        display: list[str] = []
        for line in all_lines:
            if not line:
                display.append("")
            elif line.startswith("──"):
                display.append(line)
            else:
                display.extend(textwrap.wrap(line, width=content_width) or [""])
        total = len(display)
        offset = max(0, min(offset, total - content_rows))

        stdscr.clear()
        _addstr(stdscr, 0, 2, "Config / Diagnostics", curses.A_BOLD)

        for idx, line in enumerate(display[offset: offset + content_rows]):
            bold = line.startswith("──")
            attr = curses.A_BOLD if bold else curses.A_DIM
            _addstr(stdscr, 1 + idx, 2, line, attr)

        pct = int(100 * (offset + content_rows) / total) if total else 100
        status = (
            f"Lines {offset + 1}–{min(offset + content_rows, total)}/{total}"
            f"  ({min(pct, 100)}%)  ↑↓ PgUp/PgDn  q/Esc return"
        )
        _addstr(stdscr, max_rows - 1, 2, status, curses.A_DIM)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord("q"), ord("Q"), ord("c"), ord("C"), 27, curses.KEY_BACKSPACE):
            break
        elif key == curses.KEY_UP:
            offset = max(offset - 1, 0)
        elif key == curses.KEY_DOWN:
            offset = min(offset + 1, max(0, total - content_rows))
        elif key == curses.KEY_PPAGE:
            offset = max(offset - content_rows, 0)
        elif key == curses.KEY_NPAGE:
            offset = min(offset + content_rows, max(0, total - content_rows))
        elif key == curses.KEY_HOME:
            offset = 0
        elif key == curses.KEY_END:
            offset = max(0, total - content_rows)


# ---------------------------------------------------------------------------
# Main TUI
# ---------------------------------------------------------------------------

def main(stdscr, delay):
    has_colors = False
    if curses.has_colors():
        try:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_RED, -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_CYAN, -1)
            has_colors = True
        except Exception:
            pass

    svc_poller = _ServicePoller(SERVICES)
    app_poller = _AppPoller(APP_COMPONENTS)
    svc_poller.start()
    app_poller.start()

    # sel_type: "service" | "app"
    sel_type = "service"
    sel_idx = 0

    def clamp():
        nonlocal sel_idx
        limit = len(SERVICES) if sel_type == "service" else len(APP_COMPONENTS)
        sel_idx = max(0, min(sel_idx, limit - 1))

    while True:
        stdscr.clear()
        row = 0

        _addstr(stdscr, row, 2, "IPR Service Monitor", curses.A_BOLD)
        row += 1
        _addstr(stdscr, row, 2,
                "Navigate: ↑↓  Tab: switch section  Enter: details  r: refresh  q: quit",
                curses.A_DIM)
        row += 1
        _addstr(stdscr, row, 2, f"Poll delay: {delay}s  (+/-)", curses.A_DIM)
        row += 2

        # ---- Systemd Services ----
        _addstr(stdscr, row, 2, "── Systemd Services " + "─" * 58, curses.A_BOLD)
        row += 1
        _addstr(stdscr, row, 4, f"{'Status':<14}", curses.A_BOLD | curses.A_UNDERLINE)
        _addstr(stdscr, row, 18, f"{'Unit':<30}", curses.A_BOLD | curses.A_UNDERLINE)
        _addstr(stdscr, row, 49, "Description", curses.A_BOLD | curses.A_UNDERLINE)
        row += 1

        for i, (unit, desc) in enumerate(SERVICES):
            status = svc_poller.status.get(unit, "checking…")
            color = status_color(status)
            attr = curses.A_NORMAL
            if has_colors:
                attr |= curses.color_pair(color)
            if sel_type == "service" and sel_idx == i:
                attr |= curses.A_REVERSE
            _addstr(stdscr, row, 4,  f"{status:<14}", attr)
            _addstr(stdscr, row, 18, f"{unit:<30}", attr)
            _addstr(stdscr, row, 49, desc, attr)
            row += 1

        row += 1

        # ---- Application Components ----
        _addstr(stdscr, row, 2, "── Application Components " + "─" * 52, curses.A_BOLD)
        row += 1
        _addstr(stdscr, row, 4, f"{'Status':<14}", curses.A_BOLD | curses.A_UNDERLINE)
        _addstr(stdscr, row, 18, f"{'Component':<30}", curses.A_BOLD | curses.A_UNDERLINE)
        _addstr(stdscr, row, 49, "Description", curses.A_BOLD | curses.A_UNDERLINE)
        row += 1

        for i, (label, desc, _) in enumerate(APP_COMPONENTS):
            status = app_poller.status.get(label, "checking…")
            color = status_color(status)
            attr = curses.A_NORMAL
            if has_colors:
                attr |= curses.color_pair(color)
            if sel_type == "app" and sel_idx == i:
                attr |= curses.A_REVERSE
            _addstr(stdscr, row, 4,  f"{status:<14}", attr)
            _addstr(stdscr, row, 18, f"{label:<30}", attr)
            _addstr(stdscr, row, 49, desc, attr)
            row += 1

        row += 1

        # ---- Bluetooth Devices ----
        _addstr(stdscr, row, 2, "── Bluetooth Devices " + "─" * 57, curses.A_BOLD)
        row += 1
        devices = get_bt_devices()
        if devices:
            for dev in devices:
                label = (f"{dev[1]} ({dev[0]}) "
                         f"[{'Connected' if dev[2] else 'Disconnected'}"
                         f"{'/Paired' if dev[3] else '/Unpaired'}]")
                color = device_status_color(dev[2], dev[3])
                attr = curses.color_pair(color) if has_colors else curses.A_NORMAL
                _addstr(stdscr, row, 4, label, attr)
                row += 1
        else:
            _addstr(stdscr, row, 4, "No devices", curses.A_DIM)
            row += 1

        row += 1

        # ---- Config summary ----
        if row < curses.LINES - 5:
            _addstr(stdscr, row, 2, "── Config " + "─" * 68, curses.A_BOLD)
            row += 1
            cfg = get_config_info()
            for k, v in list(cfg.items())[:4]:
                if row >= curses.LINES - 3:
                    break
                _addstr(stdscr, row, 4, f"{k}: {v}", curses.A_DIM)
                row += 1

        if row < curses.LINES - 2:
            _addstr(stdscr, row, 2,
                    "Press [c] for full config/diagnostics", curses.A_DIM)

        stdscr.refresh()

        # ---- Input handling ----
        c = stdscr.getch()

        if c in (ord("q"), ord("Q")):
            break

        elif c in (ord("r"), ord("R")):
            for unit, _ in SERVICES:
                svc_poller.status[unit] = get_service_status(unit)
            for label, _, fn in APP_COMPONENTS:
                try:
                    app_poller.status[label] = fn()
                except Exception:
                    app_poller.status[label] = "error"

        elif c == ord("\t"):  # Tab: switch between sections
            sel_type = "app" if sel_type == "service" else "service"
            sel_idx = 0

        elif c == curses.KEY_UP:
            sel_idx = max(sel_idx - 1, 0)

        elif c == curses.KEY_DOWN:
            limit = len(SERVICES) if sel_type == "service" else len(APP_COMPONENTS)
            sel_idx = min(sel_idx + 1, limit - 1)

        elif c == ord("+"):
            delay = min(delay + 1, 30)

        elif c == ord("-"):
            delay = max(delay - 1, 1)

        elif c in (curses.KEY_ENTER, 10, 13):
            stdscr.clear()
            if sel_type == "service":
                svc, _ = SERVICES[sel_idx]
                _show_service_detail(stdscr, svc, has_colors)
            elif sel_type == "app":
                label, desc, _ = APP_COMPONENTS[sel_idx]
                status = app_poller.status.get(label, "unknown")
                _show_app_detail(stdscr, label, desc, status)

        elif c == ord("c"):
            _show_config_diag(stdscr)

    svc_poller.stop()
    app_poller.stop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_delay = 5

if __name__ == "__main__":
    curses.wrapper(main, _delay)
