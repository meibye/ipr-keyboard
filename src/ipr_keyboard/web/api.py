"""Flask API blueprint for the dashboard.

Implements all /api/ endpoints as defined in docs/ui/api-contract.md.
"""

from __future__ import annotations

import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request, session, stream_with_context

from ..config.manager import ConfigManager
from ..logging.logger import get_logger, set_log_level
from .. import transmission
from .. import keydelay
from .. import metrics
from ..usb.detector import expand_folders, list_files, pen_presence
from .auth import UserStore

logger = get_logger()

FOLDER_OPTIONS = [
    {
        "path": "/mnt/irispen/*/Scan text and save",
        "label_en": "Scan to Text & Save",
        "label_da": "Scan til tekst og gem",
    },
    {
        "path": "/mnt/irispen/*/picture",
        "label_en": "Photo OCR",
        "label_da": "Foto OCR",
    },
]

bp_api = Blueprint("api", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(cmd: list[str], timeout: int = 5) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=timeout)
    except Exception as exc:
        return f"ERROR: {exc}"


def _service_active(name: str) -> bool:
    try:
        rc = subprocess.call(
            ["systemctl", "is-active", "--quiet", name],
            timeout=5,
        )
        return rc == 0
    except Exception:
        return False


def _build_bluetooth_state() -> dict[str, Any]:
    ble_active = _service_active("bt_hid_ble.service")
    adapter_out = _run(["bluetoothctl", "show"])
    powered = "Powered: yes" in adapter_out

    connected_device = None
    if ble_active and powered:
        try:
            devices_out = subprocess.check_output(
                ["bluetoothctl", "devices", "Connected"],
                text=True,
                stderr=subprocess.STDOUT,
                timeout=5,
            )
            for line in devices_out.splitlines():
                parts = line.split(None, 2)
                if len(parts) >= 3:
                    connected_device = parts[2].strip()
                    break
        except Exception:
            pass

    if ble_active and powered and connected_device:
        state = "connected"
        label = "Connected"
        explanation = f"Paired with {connected_device}"
    elif ble_active:
        state = "waiting"
        label = "Waiting"
        explanation = "Waiting for paired PC"
    else:
        state = "error"
        label = "Error"
        explanation = "Bluetooth service not running"

    return {
        "state": state,
        "label": label,
        "explanation": explanation,
        "host_name": connected_device,
    }


def _build_pen_state() -> dict[str, Any]:
    """Pen state from what is physically there, not from the Bluetooth agent.

    ready    plugged in and its files are mounted (the app can read scans)
    busy     plugged in, mount not up yet (irispen-mount.service starting)
    missing  not plugged in — or the USB port itself is disabled
    """
    presence = pen_presence()
    if presence == "disabled":
        return {"state": "error", "label": "USB port off",
                "explanation": "The device's USB port was switched off after connection errors — restart the device, then check the pen's cable",
                "device_name": "IR Pen Scanner"}
    if presence == "ready":
        state, label, explanation = "ready", "Ready", "Scanner connected"
    elif presence == "busy":
        state, label, explanation = "busy", "Connecting", "Scanner found, mounting its files…"
    elif presence == "stale":
        # stale FUSE mount after an unplug; irispen-mount.service clears it
        state, label, explanation = "missing", "Not detected", "Scanner unplugged"
    else:
        state, label, explanation = "missing", "Not detected", "Attach the pen / scanner"
    return {"state": state, "label": label, "explanation": explanation, "device_name": "IR Pen Scanner"}


def _build_transmission_state() -> dict[str, Any]:
    return transmission.get()


def _build_system_state(bt: dict[str, Any]) -> dict[str, Any]:
    ble_active = _service_active("bt_hid_ble.service")
    agent_active = _service_active("bt_hid_agent_unified.service")
    if ble_active and agent_active:
        state, label, explanation = "healthy", "Healthy", "No current warnings"
    else:
        state, label, explanation = "warning", "Warning", "One or more services are not running"
    return {"state": state, "label": label, "explanation": explanation}


def _build_health_data() -> dict[str, Any]:
    result: dict[str, Any] = {}
    try:
        mem = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                mem[parts[0].rstrip(":")] = int(parts[1])
        total = mem.get("MemTotal", 0)
        available = mem.get("MemAvailable", 0)
        if total:
            result["memory_percent"] = round((total - available) * 100 / total)
            result["memory_used_mb"] = round((total - available) / 1024)
            result["memory_total_mb"] = round(total / 1024)
    except Exception:
        pass
    try:
        load1 = float(Path("/proc/loadavg").read_text().split()[0])
        result["cpu_load_1"] = load1
    except Exception:
        pass
    try:
        out = subprocess.check_output(["df", "-h", "/"], text=True, timeout=3)
        lines = out.strip().splitlines()
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 5:
                result["disk_used"] = parts[2]
                result["disk_total"] = parts[1]
                result["disk_percent"] = int(parts[4].rstrip("%"))
    except Exception:
        pass
    try:
        secs = float(Path("/proc/uptime").read_text().split()[0])
        days, rem = divmod(int(secs), 86400)
        hours, rem = divmod(rem, 3600)
        mins = rem // 60
        if days:
            result["uptime"] = f"{days}d {hours}h {mins}m"
        elif hours:
            result["uptime"] = f"{hours}h {mins}m"
        else:
            result["uptime"] = f"{mins}m"
    except Exception:
        pass
    return result


def _build_overall_state(bt: dict, pen: dict, tx: dict, sys: dict) -> dict[str, Any]:
    states = [bt["state"], pen["state"], tx["state"], sys["state"]]
    if any(s == "error" for s in states) or tx["state"] == "failed":
        return {"state": "error", "label": "Error", "explanation": "A problem needs attention"}
    if any(s in ("warning", "retrying") for s in states) or sys["state"] == "warning":
        return {"state": "warning", "label": "Warning", "explanation": "Something needs attention"}
    if bt["state"] == "connected" and pen["state"] == "ready":
        return {"state": "ready", "label": "Ready", "explanation": "Ready for use"}
    return {"state": "warning", "label": "Warning", "explanation": "Not fully ready"}


def _parse_journalctl_events(lines: list[str], category_filter: str | None, severity_filter: str | None, limit: int) -> list[dict]:
    events: list[dict] = []
    for i, line in enumerate(reversed(lines)):
        if len(events) >= limit:
            break
        line = line.strip()
        if not line:
            continue

        # Determine category from unit name hints
        lline = line.lower()
        if "bt_hid_ble" in lline or "bluetooth" in lline or "bluetoothctl" in lline:
            category = "bluetooth"
        elif "pen" in lline or "irispen" in lline or "scanner" in lline:
            category = "pen"
        elif "transmission" in lline or "transfer" in lline or "send" in lline:
            category = "transmission"
        elif "systemd" in lline or "kernel" in lline or "reboot" in lline:
            category = "system"
        else:
            category = "system"

        if category_filter and category != category_filter:
            continue

        # Severity from keywords
        if any(k in lline for k in ("error", "failed", "failure", "critical")):
            severity = "error"
        elif any(k in lline for k in ("warn", "warning", "retry", "retrying")):
            severity = "warning"
        else:
            severity = "info"

        if severity_filter and severity != severity_filter:
            continue

        # Friendly summary
        if "connected" in lline and "bluetooth" in category:
            summary = "Bluetooth connected"
            details = "The device connected via Bluetooth."
        elif "disconnected" in lline and "bluetooth" in category:
            summary = "Bluetooth disconnected"
            details = "The Bluetooth connection was lost."
        elif "started" in lline:
            summary = "Service started"
            details = line
        elif "stopped" in lline:
            summary = "Service stopped"
            details = line
        else:
            summary = line[:80] if len(line) > 80 else line
            details = line

        events.append({
            "id": f"evt_{i}",
            "timestamp": _now(),
            "category": category,
            "severity": severity,
            "summary": summary,
            "details": details,
        })

    return events


# ---------------------------------------------------------------------------
# Status endpoints
# ---------------------------------------------------------------------------

@bp_api.get("/status")
def api_status():
    try:
        bt = _build_bluetooth_state()
        pen = _build_pen_state()
        tx = _build_transmission_state()
        sys = _build_system_state(bt)
        overall = _build_overall_state(bt, pen, tx, sys)

        events = _fetch_recent_events(limit=1)
        last_event = events[0] if events else None

        return jsonify({
            "timestamp": _now(),
            "overall": overall,
            "bluetooth": bt,
            "pen": pen,
            "transmission": tx,
            "system": sys,
            "last_event": last_event,
            "recent_activities": transmission.get_history(),
        })
    except Exception:
        logger.exception("Error in /api/status")
        return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


@bp_api.get("/status/bluetooth")
def api_status_bluetooth():
    try:
        bt = _build_bluetooth_state()
        bt["timestamp"] = _now()
        return jsonify(bt)
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


@bp_api.get("/status/pen")
def api_status_pen():
    try:
        pen = _build_pen_state()
        pen["timestamp"] = _now()
        return jsonify(pen)
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


@bp_api.get("/status/transmission")
def api_status_transmission():
    try:
        tx = _build_transmission_state()
        tx["timestamp"] = _now()
        return jsonify(tx)
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


@bp_api.get("/status/system")
def api_status_system():
    try:
        sys = _build_system_state({})
        sys["timestamp"] = _now()
        return jsonify(sys)
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


@bp_api.get("/status/health")
def api_status_health():
    try:
        data = _build_health_data()
        data["timestamp"] = _now()
        return jsonify(data)
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


# ---------------------------------------------------------------------------
# Device endpoint  (/api/device) — mode, hotspot, network, incidents
# ---------------------------------------------------------------------------

_MODE_FILE = Path("/var/lib/ipr-keyboard/mode")
_INCIDENTS_FILE = Path("/var/lib/ipr-keyboard/incidents.log")
_HOTSPOT_SECRET = Path("/etc/ipr-hotspot.secret")
_HOTSPOT_CTL = "/usr/local/bin/ipr_hotspot_ctl.sh"


def _device_mode() -> str:
    try:
        return "development" if _MODE_FILE.read_text().strip() == "development" else "production"
    except OSError:
        return "production"


def _hotspot_active() -> bool:
    out = _run(["nmcli", "-t", "-f", "NAME", "con", "show", "--active"])
    return "ipr-hotspot" in out.splitlines()


def _home_wifi_active() -> bool:
    out = _run(["nmcli", "-t", "-f", "NAME,TYPE", "con", "show", "--active"])
    for line in out.splitlines():
        name, _, ctype = line.partition(":")
        if name != "ipr-hotspot" and ("wireless" in ctype or "ethernet" in ctype):
            return True
    return False


def _hotspot_ssid() -> str:
    try:
        for line in _HOTSPOT_SECRET.read_text().splitlines():
            if line.startswith("SSID="):
                return line[5:].strip()
    except OSError:
        pass
    return ""


def _incidents() -> tuple[int, str]:
    try:
        lines = [ln for ln in _INCIDENTS_FILE.read_text().splitlines() if ln.strip()]
        return len(lines), (lines[-1] if lines else "")
    except OSError:
        return 0, ""


def _build_device_data() -> dict[str, Any]:
    mode = _device_mode()
    hotspot = _hotspot_active()
    home = _home_wifi_active()
    count, last = _incidents()
    if hotspot:
        reach = "Reachable only via the hotspot (10.42.0.1) while it is on"
    elif mode == "development":
        reach = "SSH and dashboard open on the home network"
    else:
        reach = "No ports open on the home network; use the hotspot for maintenance"
    return {
        "mode": mode,
        "hotspot_active": hotspot,
        "hotspot_ssid": _hotspot_ssid(),
        "home_network": home,
        "ip": _get_current_ip(),
        "hostname": _run(["hostname"]).strip(),
        "reachability": reach,
        "incidents_count": count,
        "last_incident": last,
        "device_time": _device_local_time(),
    }


@bp_api.get("/device")
def api_device():
    try:
        data = _build_device_data()
        data["timestamp"] = _now()
        return jsonify(data)
    except Exception:
        logger.exception("API error")
        return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


@bp_api.post("/actions/hotspot")
def api_action_hotspot():
    """Start or stop the management hotspot (admin).  Same helper the magnet uses."""
    denied = _require_admin()
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    enabled = bool(data.get("enabled", True))
    if enabled and not data.get("confirm"):
        return jsonify({"error": {"code": "confirmation_required",
                                  "message": "Set confirm=true: while the hotspot is on, the device leaves the home network."}}), 400
    try:
        result = subprocess.run(
            ["sudo", "-n", _HOTSPOT_CTL, "start" if enabled else "stop"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            msg = ("Hotspot started. Connect to it and open https://10.42.0.1/login."
                   if enabled else "Hotspot stopped. The device rejoins the home network in a few seconds.")
            return jsonify({"ok": True, "message": msg})
        err = (result.stderr or result.stdout or "").strip()
        return jsonify({"ok": False, "message": err or f"ipr_hotspot_ctl.sh exit {result.returncode}"}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "message": "Timed out waiting for the hotspot."}), 500
    except Exception:
        logger.exception("API error")
        return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


# ---------------------------------------------------------------------------
# Event endpoints
# ---------------------------------------------------------------------------

def _fetch_recent_events(limit: int = 50, category: str | None = None, severity: str | None = None) -> list[dict]:
    try:
        cmd = ["journalctl", "-n", str(limit * 4), "-o", "short", "--no-pager"]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=10)
        lines = out.splitlines()
        return _parse_journalctl_events(lines, category, severity, limit)
    except Exception:
        return []


@bp_api.get("/events")
def api_events():
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        category = request.args.get("category") or None
        severity = request.args.get("severity") or None
        events = _fetch_recent_events(limit=limit, category=category, severity=severity)
        return jsonify({"items": events})
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


@bp_api.get("/events/latest")
def api_events_latest():
    try:
        events = _fetch_recent_events(limit=1)
        if events:
            return jsonify(events[0])
        return jsonify({
            "id": "evt_0",
            "timestamp": _now(),
            "category": "system",
            "severity": "info",
            "summary": "No recent events",
            "details": "",
        })
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


# ---------------------------------------------------------------------------
# Log endpoints
# ---------------------------------------------------------------------------

LOG_UNITS = [
    "ipr_keyboard.service",
    "ipr-provision.service",
    "ipr-firewall.service",
    "irispen-mount.service",
    "ipr-led-boot.service",
    "bt_hid_ble.service",
    "bt_hid_agent_unified.service",
    "bluetooth.service",
    "NetworkManager.service",
    "kernel",
]


def _device_local_time() -> str:
    """The device's wall clock, local zone, for correlating with journal lines."""
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


@bp_api.get("/logs/raw")
def api_logs_raw():
    """Tail of the journal, oldest first (newest at the bottom, like `tail`).

    ?unit=<name> may repeat (see LOG_UNITS; "kernel" = -k); ?limit=N (<=1000);
    ?contains=text filters lines.  The response carries the device's local
    time so the reader can relate the timestamps to "now" on the device.
    """
    try:
        limit = min(int(request.args.get("limit", 200)), 1000)
        contains = request.args.get("contains") or None
        units = [u for u in request.args.getlist("unit") if u in LOG_UNITS]
        cmd = ["journalctl", "-n", str(limit), "-o", "short", "--no-pager"]
        for u in units:
            cmd += ["-k"] if u == "kernel" else ["-u", u]
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=10)
        except Exception:
            out = ""
        items = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            if contains and contains.lower() not in line.lower():
                continue
            items.append({"line": line})
        return jsonify({"items": items, "units": units or ["(all)"], "available_units": LOG_UNITS,
                        "device_time": _device_local_time()})
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------

@bp_api.get("/config")
def api_config_get():
    try:
        cfg = ConfigManager.instance().get()
        log_level = cfg.LogLevel if getattr(cfg, "Logging", True) else "OFF"
        return jsonify({
            "device_name": "IPR Pen Bridge",
            "ui_title": "IPR Pen Bridge",
            "bluetooth": {
                "auto_reconnect": True,
                "pairing_timeout_seconds": cfg.PairingTimeoutSeconds,
            },
            "pen": {
                "auto_detect": True,
                "read_timeout_seconds": cfg.ReadTimeoutSeconds,
                "folders": list(cfg.IrisPenFolders or []),
                "folder_options": FOLDER_OPTIONS,
            },
            "timing": {
                "poll_interval_seconds": cfg.PollIntervalSeconds,
                "status_interval_seconds": cfg.StatusIntervalSeconds,
                # The typing speed is the largest single cost of a send, so it
                # is a setting rather than something only the perf harness can
                # reach.  "in_force" is what the daemon is actually using,
                # which differs from the saved value until the next send.
                "typing_delay_ms": int(getattr(cfg, "TypingDelayMs", 20)),
                "typing_delay_in_force_ms": keydelay.read(),
                "typing_chars_per_second": round(
                    keydelay.chars_per_second(getattr(cfg, "TypingDelayMs", 20)), 1
                ),
                "typing_delay_options": [
                    {
                        "ms": ms,
                        "name": keydelay.name_for(ms),
                        "label": keydelay.label_for(ms),
                        "chars_per_second": round(keydelay.chars_per_second(ms), 1),
                    }
                    for ms, _, _ in keydelay.CHOICES
                ],
            },
            "diagnostics": {
                "log_level": log_level,
                "metrics_enabled": bool(getattr(cfg, "MetricsEnabled", False)),
            },
        })
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


@bp_api.post("/config")
def api_config_post():
    try:
        data = request.get_json(force=True) or {}
        cfg_mgr = ConfigManager.instance()
        update_kwargs: dict[str, Any] = {}
        if "diagnostics" in data and "log_level" in data["diagnostics"]:
            new_level = data["diagnostics"]["log_level"]
            update_kwargs["Logging"] = new_level != "OFF"
            if new_level in ("DEBUG", "INFO", "WARNING", "ERROR"):
                update_kwargs["LogLevel"] = new_level
                set_log_level(new_level)
        if "pen" in data and "folders" in data["pen"]:
            allowed = {o["path"] for o in FOLDER_OPTIONS}
            validated = [p for p in data["pen"]["folders"] if p in allowed]
            update_kwargs["IrisPenFolders"] = validated
        if "bluetooth" in data:
            bt = data["bluetooth"]
            if "pairing_timeout_seconds" in bt:
                v = int(bt["pairing_timeout_seconds"])
                if 10 <= v <= 600:
                    update_kwargs["PairingTimeoutSeconds"] = v
        if "pen" in data and "read_timeout_seconds" in data["pen"]:
            v = int(data["pen"]["read_timeout_seconds"])
            if 1 <= v <= 300:
                update_kwargs["ReadTimeoutSeconds"] = v
        if "timing" in data:
            t = data["timing"]
            if "poll_interval_seconds" in t:
                v = float(t["poll_interval_seconds"])
                if 0.1 <= v <= 60:
                    update_kwargs["PollIntervalSeconds"] = v
            if "status_interval_seconds" in t:
                v = int(t["status_interval_seconds"])
                if 1 <= v <= 60:
                    update_kwargs["StatusIntervalSeconds"] = v
            if "typing_delay_ms" in t:
                v = int(t["typing_delay_ms"])
                if not (keydelay.MIN_MS <= v <= keydelay.MAX_MS):
                    return jsonify({"error": {"code": "validation_error",
                                              "message": f"timing.typing_delay_ms must be {keydelay.MIN_MS}-{keydelay.MAX_MS}."}}), 400
                update_kwargs["TypingDelayMs"] = v
                # Put it in force now rather than waiting for the main loop:
                # the trial on the Debug screen changes it between sends.
                keydelay.apply(v)
        if "diagnostics" in data and "metrics_enabled" in data["diagnostics"]:
            v = data["diagnostics"]["metrics_enabled"]
            if not isinstance(v, bool):
                return jsonify({"error": {"code": "validation_error",
                                          "message": "diagnostics.metrics_enabled must be a boolean."}}), 400
            update_kwargs["MetricsEnabled"] = v
            # Apply at once for the web process; the main loop picks it up on
            # its next iteration from the saved config.
            metrics.set_enabled(v)
        if update_kwargs:
            cfg_mgr.update(**update_kwargs)
        return jsonify({"ok": True, "message": "Configuration updated."})
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


# ---------------------------------------------------------------------------
# Performance metrics  (/api/metrics)
# ---------------------------------------------------------------------------

@bp_api.get("/metrics")
def api_metrics():
    """Performance KPIs recorded by ipr_keyboard.metrics.

    Always answers, even when recording is off, so the dashboard and the perf
    harness can tell "disabled" apart from "no data yet".  Computing the
    statistics happens here, on request, never on the recording path.
    """
    try:
        # Keep the web process's view of the switch in step with the saved
        # config: the main loop applies it each iteration, the web process only
        # when asked.
        metrics.set_enabled(bool(getattr(ConfigManager.instance().get(), "MetricsEnabled", False)))
        return jsonify(metrics.snapshot())
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


@bp_api.post("/metrics/reset")
def api_metrics_reset():
    """Discard recorded samples.  The perf harness calls this between runs."""
    try:
        metrics.reset()
        return jsonify({"ok": True, "message": "Metrics cleared."})
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


# ---------------------------------------------------------------------------
# Network endpoints
# ---------------------------------------------------------------------------

def _get_current_ip() -> str:
    """The device's IPv4 address(es).

    The default-route trick only works with a route to the internet; on the
    hotspot alone (10.42.0.1, no uplink) it yields nothing, so fall back to
    listing every global-scope IPv4 address.
    """
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    finally:
        try:
            if s is not None:
                s.close()
        except Exception:
            pass
    try:
        out = subprocess.check_output(
            ["ip", "-4", "-o", "addr", "show", "scope", "global"], text=True, timeout=3
        )
        addrs = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[2] == "inet":
                addrs.append(parts[3].split("/")[0])
        return ", ".join(addrs)
    except Exception:
        return ""


def _get_network_interface() -> str:
    try:
        out = subprocess.check_output(
            ["ip", "route", "get", "8.8.8.8"], text=True, timeout=3
        )
        parts = out.split()
        if "dev" in parts:
            return parts[parts.index("dev") + 1]
    except Exception:
        pass
    return "wlan0"


_NET_APPLY_HELPER = "/usr/local/bin/ipr_net_apply.sh"


def _apply_network(mode: str, ip: str, netmask: str, gateway: str) -> str:
    """Apply dhcp/static settings to the home network profile via nmcli.

    Goes through the root helper (sudoers).  The devices run NetworkManager;
    the earlier implementation wrote /etc/dhcpcd.conf, which nothing read there.
    Returns the helper's last log line; raises PermissionError / RuntimeError.
    """
    if mode == "static":
        if not ip:
            raise ValueError("Static mode needs an IP address.")
        args = ["static", ip, netmask or "255.255.255.0", gateway or ""]
    else:
        args = ["dhcp"]
    result = subprocess.run(
        ["sudo", "-n", _NET_APPLY_HELPER, *args],
        text=True,
        capture_output=True,
        timeout=40,
    )
    stderr = (result.stderr or "").strip()
    if result.returncode != 0:
        if "sudo:" in stderr or "password" in stderr:
            raise PermissionError(stderr or "sudo not permitted for ipr_net_apply.sh")
        raise RuntimeError(stderr or f"ipr_net_apply.sh failed (rc={result.returncode})")
    lines = [ln for ln in (result.stdout or "").splitlines() if ln.strip()]
    return lines[-1] if lines else "applied"


@bp_api.get("/network")
def api_network_get():
    try:
        cfg = ConfigManager.instance().get()
        return jsonify({
            "current_ip": _get_current_ip(),
            "interface": _get_network_interface(),
            "mode": cfg.NetworkMode,
            "static_ip": cfg.StaticIP,
            "static_netmask": cfg.StaticNetmask,
            "static_gateway": cfg.StaticGateway,
            "port": cfg.LogPort,
        })
    except Exception:
        logger.exception("API error")
        return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


@bp_api.post("/network")
def api_network_post():
    denied = _require_admin()
    if denied:
        return denied
    try:
        data = request.get_json(force=True) or {}
        cfg_mgr = ConfigManager.instance()
        update_kwargs: dict[str, Any] = {}

        if "port" in data:
            v = int(data["port"])
            if 1024 <= v <= 65535:
                update_kwargs["LogPort"] = v

        mode = data.get("mode", "").lower()
        if mode in ("dhcp", "static"):
            update_kwargs["NetworkMode"] = mode

        if "static_ip" in data:
            update_kwargs["StaticIP"] = str(data["static_ip"])
        if "static_netmask" in data:
            update_kwargs["StaticNetmask"] = str(data["static_netmask"])
        if "static_gateway" in data:
            update_kwargs["StaticGateway"] = str(data["static_gateway"])

        # Only values that actually differ from the stored config count as a
        # change: the settings page posts every network field on each save,
        # and re-writing dhcpcd.conf (and telling the user about it) for an
        # unchanged mode was noise.
        before = cfg_mgr.get()
        update_kwargs = {k: v for k, v in update_kwargs.items() if getattr(before, k, None) != v}
        if update_kwargs:
            cfg_mgr.update(**update_kwargs)

        # Apply to the NetworkManager home profile if mode or static fields changed.
        # Re-activation is immediate: if the address changes, the browser must
        # reconnect at the new one.
        if any(k in update_kwargs for k in ("NetworkMode", "StaticIP", "StaticNetmask", "StaticGateway")):
            cfg = cfg_mgr.get()
            try:
                _apply_network(cfg.NetworkMode, cfg.StaticIP, cfg.StaticNetmask, cfg.StaticGateway)
                dhcp_msg = ("Network settings applied. If the address changed, reconnect at the new one."
                            if cfg.NetworkMode == "static" else "Network settings applied (DHCP).")
            except PermissionError:
                dhcp_msg = "Settings saved, but the device could not apply them (sudo not permitted for ipr_net_apply.sh)."
            except Exception as exc:
                dhcp_msg = f"Settings saved, but applying them failed: {exc}"
        else:
            dhcp_msg = "Network settings saved."

        return jsonify({"ok": True, "message": dhcp_msg})
    except Exception:
        logger.exception("API error")
        return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


# ---------------------------------------------------------------------------
# Action endpoints
# ---------------------------------------------------------------------------

@bp_api.post("/actions/pairing")
def api_action_pairing():
    try:
        data = request.get_json(force=True) or {}
        enabled = data.get("enabled", True)
        if enabled:
            _run(["bluetoothctl", "pairable", "on"])
            _run(["bluetoothctl", "discoverable", "on"])
            _run(["bluetoothctl", "agent", "on"])
            _run(["bluetoothctl", "default-agent"])
            return jsonify({"ok": True, "message": "Pairing mode enabled."})
        else:
            _run(["bluetoothctl", "pairable", "off"])
            _run(["bluetoothctl", "discoverable", "off"])
            return jsonify({"ok": True, "message": "Pairing mode disabled."})
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


@bp_api.post("/actions/rescan-pen")
def api_action_rescan_pen():
    return jsonify({"ok": True, "message": "Pen rescan started."})


@bp_api.post("/actions/reconnect-bluetooth")
def api_action_reconnect_bluetooth():
    """Restart the BLE HID daemon through the root helper.

    A bare `systemctl restart` from the service gets "Interactive
    authentication required" from polkit (no session) — that was the
    "Failed to restart bt_hid_ble.service" line in the journal.  Note the
    restart drops the current link; the PC reconnects when it sees the new
    advertisement, which on Windows can need a nudge (Connect / BT off-on).
    """
    try:
        ok, msg = _helper_service("restart", "bt_hid_ble")
        if ok:
            return jsonify({"ok": True, "message": "Bluetooth daemon restarted. The PC reconnects when it sees the device again — on Windows press Connect if it does not."})
        return jsonify({"ok": False, "message": msg}), 500
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


def _helper_service(action: str, unit: str) -> tuple[bool, str]:
    """systemctl <action> <unit> via ipr_hotspot_ctl.sh (sudoers); (ok, message)."""
    try:
        result = subprocess.run(
            ["sudo", "-n", _HOTSPOT_CTL, "service", action, unit],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False, f"Timed out waiting for systemctl {action} {unit}."
    if result.returncode == 0:
        return True, ""
    err = (result.stderr or result.stdout or "").strip().splitlines()
    return False, (err[-1] if err else f"systemctl {action} {unit} failed (exit {result.returncode}).")


@bp_api.post("/actions/apply-network")
def api_action_apply_network():
    """Re-apply the stored network settings to the home profile (nmcli)."""
    denied = _require_admin()
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    if not data.get("confirm"):
        return jsonify({"error": {"code": "confirmation_required", "message": "Set confirm=true to proceed. The connection will drop briefly if the IP address changes."}}), 400
    try:
        cfg = ConfigManager.instance().get()
        _apply_network(cfg.NetworkMode, cfg.StaticIP, cfg.StaticNetmask, cfg.StaticGateway)
        return jsonify({"ok": True, "message": "Network settings applied. If the IP address changed, reconnect at the new address."})
    except PermissionError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "message": "Timed out waiting for NetworkManager."}), 500
    except Exception as exc:
        logger.exception("API error")
        return jsonify({"ok": False, "message": f"Applying network settings failed: {exc}"}), 500


@bp_api.post("/actions/reboot")
def api_action_reboot():
    data = request.get_json(force=True) or {}
    if not data.get("confirm"):
        return jsonify({"error": {"code": "confirmation_required", "message": "Set confirm=true to proceed."}}), 400
    try:
        subprocess.Popen(["sudo", "reboot"])
        return jsonify({"ok": True, "message": "Reboot initiated."})
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


@bp_api.post("/actions/shutdown")
def api_action_shutdown():
    data = request.get_json(force=True) or {}
    if not data.get("confirm"):
        return jsonify({"error": {"code": "confirmation_required", "message": "Set confirm=true to proceed."}}), 400
    try:
        subprocess.Popen(["sudo", "shutdown", "-h", "now"])
        return jsonify({"ok": True, "message": "Shutdown initiated."})
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


# ---------------------------------------------------------------------------
# Version endpoint
# ---------------------------------------------------------------------------

@bp_api.get("/version")
def api_version():
    try:
        from .. import __version__ as pkg_ver
        from ..main import VERSION as main_ver
        from ..config import manager as cfg_mod
        from ..bluetooth import keyboard as bt_mod
        from ..usb import detector as det_mod, reader as rdr_mod, deleter as del_mod
        from ..web import server as srv_mod
        return jsonify({
            "package": pkg_ver,
            "python": sys.version,
            "modules": {
                "main":         main_ver,
                "config":       cfg_mod.VERSION,
                "bluetooth":    bt_mod.VERSION,
                "usb.detector": det_mod.VERSION,
                "usb.reader":   rdr_mod.VERSION,
                "usb.deleter":  del_mod.VERSION,
                "web.server":   srv_mod.VERSION,
            },
        })
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


# ---------------------------------------------------------------------------
# SSE stream endpoint
# ---------------------------------------------------------------------------

@bp_api.get("/stream")
def api_stream():
    def generate():
        import time
        while True:
            try:
                _t0 = time.time()
                bt = _build_bluetooth_state()
                pen = _build_pen_state()
                tx = _build_transmission_state()
                sys = _build_system_state(bt)
                overall = _build_overall_state(bt, pen, tx, sys)
                # How much the dashboard costs the device per update; no-op when off.
                metrics.record("sse_build_ms", (time.time() - _t0) * 1000.0)
                payload = json.dumps({
                    "type": "status_update",
                    "data": {
                        "timestamp": _now(),
                        "overall": overall,
                        "bluetooth": bt,
                        "pen": pen,
                        "transmission": tx,
                        "system": sys,
                        "recent_activities": transmission.get_history(),
                    },
                })
                yield f"data: {payload}\n\n"
            except Exception:
                yield "data: {}\n\n"
            # A send of a few hundred characters runs for tens of seconds and
            # the card shows a live character count: at the normal status
            # interval it would step twice and look stuck.  Tick faster only
            # while a send is on screen, so an idle dashboard still costs the
            # device just one build per interval.
            interval = ConfigManager.instance().get().StatusIntervalSeconds
            if transmission.get().get("state") == "sending":
                interval = min(interval, 1.0)
            time.sleep(interval)

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Debug endpoints  (/api/debug/*)
# ---------------------------------------------------------------------------

_SERVICES = [
    {
        "name": "systemd-udevd",
        "label": "Device Manager",
        "description": "Handles hardware device plug/unplug events",
    },
    {
        "name": "dbus",
        "label": "Message Bus",
        "description": "System D-Bus message broker",
    },
    {
        "name": "bluetooth",
        "label": "Bluetooth Core",
        "description": "BlueZ Bluetooth stack",
    },
    {
        "name": "bt_hid_agent_unified",
        "label": "Pen Detector",
        "description": "Pairing and device agent for the Iris pen scanner",
    },
    {
        "name": "bt_hid_ble",
        "label": "BLE Keyboard",
        "description": "BLE HID keyboard daemon (writes to FIFO)",
    },
    {
        "name": "ipr_keyboard",
        "label": "Keyboard Service",
        "description": "Main keyboard bridge application",
    },
]

_SERVICE_NAMES = {s["name"] for s in _SERVICES}
_ALLOWED_ACTIONS = {"start", "stop", "restart"}
# Units the root helper agrees to control; dbus and udevd are inspect-only.
_HELPER_CONTROLLABLE = {"bluetooth", "bt_hid_agent_unified", "bt_hid_ble"}

_BT_SEND_HELPER = "/usr/local/bin/bt_kb_send"
_BT_SEND_FILE_HELPER = "/usr/local/bin/bt_kb_send_file"

_PEN_FILES_CONTENT_CAP = 8192  # bytes


def _service_enabled(name: str) -> bool:
    try:
        rc = subprocess.call(
            ["systemctl", "is-enabled", "--quiet", name],
            timeout=5,
        )
        return rc == 0
    except Exception:
        return False


@bp_api.get("/debug/services")
def api_debug_services():
    try:
        services = []
        for svc in _SERVICES:
            services.append({
                "name": svc["name"],
                "label": svc["label"],
                "description": svc["description"],
                "active": _service_active(svc["name"]),
                "enabled": _service_enabled(svc["name"]),
            })
        return jsonify({"services": services})
    except Exception:
        logger.exception("API error")
        return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


@bp_api.post("/debug/services/<name>/<action>")
def api_debug_service_action(name: str, action: str):
    if name not in _SERVICE_NAMES:
        return jsonify({"error": {"code": "bad_request", "message": f"Unknown service: {name}"}}), 400
    if action not in _ALLOWED_ACTIONS:
        return jsonify({"error": {"code": "bad_request", "message": f"Unknown action: {action}. Allowed: {sorted(_ALLOWED_ACTIONS)}"}}), 400
    if name not in _HELPER_CONTROLLABLE:
        return jsonify({"ok": False, "message": f"{name} can only be inspected here, not controlled (system service)."}), 400
    try:
        ok, msg = _helper_service(action, name)
        if ok:
            return jsonify({"ok": True, "message": f"Service {name} {action} succeeded."})
        return jsonify({"ok": False, "message": msg})
    except Exception as exc:
        logger.exception("Service action error")
        return jsonify({"ok": False, "message": str(exc)}), 500


@bp_api.post("/debug/send-text")
def api_debug_send_text():
    try:
        data = request.get_json(force=True) or {}
        text = data.get("text", "")
        if not text:
            return jsonify({"error": {"code": "bad_request", "message": "text is required and must not be empty."}}), 400
        nowait = bool(data.get("nowait", False))
        cmd = [_BT_SEND_HELPER]
        if nowait:
            cmd.append("--nowait")
        cmd.append(text)
        transmission.set_sending("debug/send-text")
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=20)
            transmission.set_success()
            return jsonify({"ok": True, "message": "Text sent."})
        except FileNotFoundError:
            transmission.set_failed("bt_kb_send helper not found")
            return jsonify({"ok": False, "message": f"Send helper not found: {_BT_SEND_HELPER}"}), 500
        except subprocess.CalledProcessError as exc:
            reason = (exc.stderr or "").strip() or f"exit {exc.returncode}"
            transmission.set_failed(reason)
            return jsonify({"ok": False, "message": f"Send failed: {reason}"}), 500
        except subprocess.TimeoutExpired:
            transmission.set_failed("Send timed out")
            return jsonify({"ok": False, "message": "Send timed out."}), 500
    except Exception:
        logger.exception("API error")
        return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


# The trial sends this once per candidate speed.  Known text, so the user can
# check it character for character on the PC -- the only test that matters,
# since the failure mode of too low a delay is dropped or transposed
# characters rather than an error.  Each line names its own speed, so a
# mangled block can be traced back to the setting that produced it.
TYPING_TRIAL_LINES = (
    "01 The quick brown fox jumps over the lazy dog.",
    "02 Pack my box with five dozen liquor jugs.",
    "03 How vexingly quick daft zebras jump!",
    "04 Digits: 0 1 2 3 4 5 6 7 8 9 and 1234567890.",
    "05 Punctuation: , . ; : ? ! ' \" ( ) - / & % + = @ #",
    "06 Danske bogstaver: æøå ÆØÅ - blev de alle skrevet?",
    "07 Mixed CASE and lower, UPPER and MiXeD together.",
    "08 Repeated: aaa bbb ccc ddd eee fff ggg hhh iii jjj.",
    "09 Spacing:  two  spaces  between  these  words.",
    "10 Last line - if you can read this, nothing was lost.",
)
#: One send per speed.  Ten lines rather than one sentence: a single line
#: is too short to time honestly at the faster steps, and dropped
#: characters are far easier to spot against numbered lines.
TYPING_TRIAL_TEXT = chr(10).join(TYPING_TRIAL_LINES)
TYPING_TRIAL_MAX_DELAYS = 6


@bp_api.post("/debug/typing-trial")
def api_debug_typing_trial():
    """Type the same text at each candidate speed and measure what happened.

    docs/operations/performance.md says to try the ladder and keep the lowest
    value that is still perfect, which until now meant editing a file on the
    device and restarting the BLE daemon -- losing the pairing each time.  The
    daemon re-reads the speed per send, so the whole ladder can run here in
    one go while the PC stays connected.

    The saved setting is restored afterwards: a trial measures, it does not
    decide.  The user picks the winner in Settings.
    """
    try:
        data = request.get_json(force=True) or {}
        delays = data.get("delays") or [ms for ms, _, _ in keydelay.CHOICES]
        try:
            delays = [int(d) for d in delays][:TYPING_TRIAL_MAX_DELAYS]
        except (TypeError, ValueError):
            return jsonify({"error": {"code": "bad_request",
                                      "message": "delays must be a list of whole milliseconds."}}), 400
        bad = [d for d in delays if not (keydelay.MIN_MS <= d <= keydelay.MAX_MS)]
        if bad:
            return jsonify({"error": {"code": "validation_error",
                                      "message": f"delays must each be {keydelay.MIN_MS}-{keydelay.MAX_MS} ms; got {bad}."}}), 400
        if not delays:
            return jsonify({"error": {"code": "bad_request", "message": "No delays to try."}}), 400

        if keydelay.read() is None:
            return jsonify({"ok": False, "message":
                            "The Bluetooth daemon is not accepting a typing speed at runtime. "
                            "Install the current bt_hid_ble daemon and restart it, then try again."}), 409

        body = str(data.get("text") or TYPING_TRIAL_TEXT)
        saved = int(getattr(ConfigManager.instance().get(), "TypingDelayMs", 20))
        results = []
        try:
            for ms in delays:
                keydelay.apply(ms)
                banner = f"===== {keydelay.name_for(ms)} ({ms} ms) ====="
                text = chr(10) * 2 + banner + chr(10) + body + chr(10) * 2
                results.append(_run_typing_trial(ms, text))
        finally:
            keydelay.apply(saved)  # a trial must not change the setting

        done = [r for r in results if r.get("ms_per_char")]
        best = min(done, key=lambda r: r["ms_per_char"]) if done else None
        return jsonify({
            "ok": True,
            "restored_delay_ms": saved,
            "results": results,
            "fastest_ms": best["delay_ms"] if best else None,
            "message": "Now read the text on the PC. Keep the lowest speed that came "
                       "through perfectly, then choose it in Settings.",
        })
    except Exception:
        logger.exception("API error")
        return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


def _run_typing_trial(ms: int, text: str) -> dict[str, Any]:
    """One send, measured from the first character out to the last."""
    from .. import bt_progress

    chars = len(text)
    first_seen: dict[str, float] = {}

    def _saw(progress) -> None:
        if progress.typing and "at" not in first_seen:
            first_seen["at"] = time.monotonic()
        transmission.set_progress(progress.sent, progress.total)

    transmission.set_sending("debug/typing-trial", chars=chars)
    queued_at = time.monotonic()
    try:
        subprocess.run([_BT_SEND_HELPER, text], check=True,
                       capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        transmission.set_failed(str(exc))
        return {"delay_ms": ms, "name": keydelay.name_for(ms),
                "chars": chars, "error": str(exc)}

    final = bt_progress.wait_until_idle(on_progress=_saw)
    finished = time.monotonic()
    transmission.set_success()
    if not final.known:
        return {"delay_ms": ms, "name": keydelay.name_for(ms), "chars": chars,
                "error": "The text was sent, but the daemon reported no progress, "
                         "so it could not be timed."}
    started = first_seen.get("at", queued_at)
    type_ms = (finished - started) * 1000.0
    # A trial IS a measurement, so it belongs in the KPI store: otherwise the
    # Performance panel stayed empty through a run that measured nothing else.
    try:
        metrics.record_typing(
            queue_wait_s=max(0.0, started - queued_at),
            type_s=max(0.0, finished - started),
            chars=final.total or chars,
        )
    except Exception:
        logger.exception("Could not record the trial's typing metrics")
    return {
        "delay_ms": ms,
        "name": keydelay.name_for(ms),
        "label": keydelay.label_for(ms),
        "chars": chars,
        "expected_chars_per_second": round(keydelay.chars_per_second(ms), 1),
        "queue_wait_ms": round((started - queued_at) * 1000.0, 1),
        "type_ms": round(type_ms, 1),
        "ms_per_char": round(type_ms / chars, 2) if chars else None,
        "chars_per_second": round(1000.0 * chars / type_ms, 1) if type_ms > 0 else None,
        "sent": final.sent,
        "complete": final.sent >= chars,
    }


@bp_api.post("/debug/send-file")
def api_debug_send_file():
    try:
        file_obj = request.files.get("file")
        if file_obj is None:
            return jsonify({"error": {"code": "bad_request", "message": "Multipart 'file' field is required."}}), 400

        suffix = os.path.splitext(file_obj.filename or "")[1] or ".txt"
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="ipr_debug_")
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                file_obj.save(f)

            cmd = [_BT_SEND_FILE_HELPER, "--file", tmp_path, "--newline-mode", "cr"]
            transmission.set_sending("debug/send-file")
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
                transmission.set_success()
                return jsonify({"ok": True, "message": "File sent."})
            except FileNotFoundError:
                transmission.set_failed("bt_kb_send_file helper not found")
                return jsonify({"ok": False, "message": f"Send helper not found: {_BT_SEND_FILE_HELPER}"}), 500
            except subprocess.CalledProcessError as exc:
                reason = (exc.stderr or "").strip() or f"exit {exc.returncode}"
                transmission.set_failed(reason)
                return jsonify({"ok": False, "message": f"Send failed: {reason}"}), 500
            except subprocess.TimeoutExpired:
                transmission.set_failed("Send timed out")
                return jsonify({"ok": False, "message": "Send timed out."}), 500
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception:
        logger.exception("API error")
        return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


@bp_api.get("/debug/pen-files")
def api_debug_pen_files():
    try:
        cfg = ConfigManager.instance().get()
        files_result = []
        for folder in expand_folders(cfg.IrisPenFolders):
            folder_str = str(folder)
            for p in list_files(folder):
                try:
                    stat = p.stat()
                    raw = p.read_bytes()
                    content = raw[:_PEN_FILES_CONTENT_CAP].decode("utf-8", errors="replace")
                    truncated = len(raw) > _PEN_FILES_CONTENT_CAP
                    files_result.append({
                        "name": p.name,
                        "path": str(p),
                        "folder": folder_str,
                        "size_bytes": stat.st_size,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "content": content,
                        "truncated": truncated,
                    })
                except OSError:
                    pass
        folders = list(cfg.IrisPenFolders or [])
        return jsonify({"folders": folders, "files": files_result})
    except Exception:
        logger.exception("API error")
        return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


# ---------------------------------------------------------------------------
# Auth endpoints  (/api/auth/*)
# ---------------------------------------------------------------------------

def _err(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def _require_admin():
    if not session.get("is_admin"):
        return _err("forbidden", "Admin access required.", 403)
    return None


@bp_api.post("/auth/login")
def api_auth_login():
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip().lower()
    password = str(body.get("password", ""))
    if not username or not password:
        return _err("bad_request", "Username and password are required.", 400)
    if UserStore.instance().verify(username, password):
        session.clear()
        session.permanent = True
        session["username"] = username
        session["is_admin"] = UserStore.instance().user_info(username)["is_admin"]
        return jsonify({"ok": True, "username": username})
    return _err("invalid_credentials", "Invalid username or password.", 401)


@bp_api.post("/auth/logout")
def api_auth_logout():
    session.clear()
    return jsonify({"ok": True})


@bp_api.get("/auth/me")
def api_auth_me():
    username = session.get("username")
    if not username:
        return _err("unauthenticated", "Not logged in.", 401)
    return jsonify({"username": username, "is_admin": bool(session.get("is_admin"))})


@bp_api.get("/auth/users")
def api_auth_users():
    denied = _require_admin()
    if denied:
        return denied
    return jsonify({"users": UserStore.instance().list_users()})


@bp_api.post("/auth/users")
def api_auth_users_create():
    denied = _require_admin()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip().lower()
    password = str(body.get("password", ""))
    is_admin = bool(body.get("is_admin", False))
    try:
        UserStore.instance().add_user(username, password, is_admin)
    except ValueError as exc:
        return _err("bad_request", str(exc), 400)
    return jsonify({"ok": True})


@bp_api.put("/auth/users/<username>")
def api_auth_users_update(username: str):
    caller = session.get("username")
    caller_is_admin = bool(session.get("is_admin"))
    if caller != username and not caller_is_admin:
        return _err("forbidden", "Admin access required.", 403)
    body = request.get_json(silent=True) or {}

    if body.get("password"):
        try:
            UserStore.instance().change_password(username, str(body["password"]))
        except KeyError:
            return _err("not_found", f"User '{username}' not found.", 404)
        except ValueError as exc:
            return _err("bad_request", str(exc), 400)

    if "is_admin" in body:
        if not caller_is_admin:
            return _err("forbidden", "Admin access required to change admin status.", 403)
        if caller == username and not bool(body["is_admin"]):
            return _err("bad_request", "You cannot remove your own admin status.", 400)
        try:
            UserStore.instance().set_admin(username, bool(body["is_admin"]))
        except (KeyError, ValueError) as exc:
            return _err("bad_request", str(exc), 400)

    return jsonify({"ok": True})


@bp_api.delete("/auth/users/<username>")
def api_auth_users_delete(username: str):
    denied = _require_admin()
    if denied:
        return denied
    if session.get("username") == username:
        return _err("bad_request", "You cannot delete your own account.", 400)
    try:
        UserStore.instance().delete_user(username)
    except KeyError:
        return _err("not_found", f"User '{username}' not found.", 404)
    except ValueError as exc:
        return _err("bad_request", str(exc), 400)
    return jsonify({"ok": True})
