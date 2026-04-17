"""Dashboard API Blueprint.

Provides /api/ prefix routes for the image-first web dashboard as defined
in docs/ui/api-contract.md.

State is gathered from systemctl service checks and bluetoothctl, then
translated into stable, user-facing UI state labels as defined in
docs/ui/user-states.md.
"""

from __future__ import annotations

import datetime
import json
import subprocess
import threading
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Blueprint, Response, jsonify, request, stream_with_context

from ..config.manager import ConfigManager
from ..logging.logger import get_logger

logger = get_logger()

bp_api = Blueprint("api", __name__, url_prefix="/api")

# In-memory event store — circular buffer, 200 events max
_EVENTS_LOCK = threading.Lock()
_EVENTS: deque = deque(maxlen=200)
_EVENT_COUNTER = 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _add_event(category: str, severity: str, summary: str, details: str = "") -> dict:
    global _EVENT_COUNTER
    with _EVENTS_LOCK:
        _EVENT_COUNTER += 1
        event: Dict[str, Any] = {
            "id": f"evt_{_EVENT_COUNTER:04d}",
            "timestamp": _now_iso(),
            "category": category,
            "severity": severity,
            "summary": summary,
            "details": details,
        }
        _EVENTS.append(event)
    return event


def _run_cmd(cmd: List[str], timeout: int = 5) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=timeout)
    except Exception as exc:
        return f"ERROR: {exc}"


def _service_active(name: str) -> bool:
    try:
        rc = subprocess.call(
            ["systemctl", "is-active", "--quiet", name],
            timeout=3,
        )
        return rc == 0
    except Exception:
        return False


def _build_bluetooth_state() -> Dict[str, Any]:
    """Map raw Bluetooth state to UI state."""
    host_name: Optional[str] = None
    state = "waiting"
    explanation = "Waiting for paired PC"

    try:
        devices_out = subprocess.check_output(
            ["bluetoothctl", "devices"], text=True, timeout=5
        )
        for line in devices_out.splitlines():
            parts = line.split(None, 2)
            if len(parts) < 2:
                continue
            mac = parts[1]
            try:
                info = subprocess.check_output(
                    ["bluetoothctl", "info", mac], text=True, timeout=5
                )
                if "Connected: yes" in info:
                    state = "connected"
                    for info_line in info.splitlines():
                        if info_line.strip().startswith("Name:"):
                            host_name = info_line.split(":", 1)[1].strip()
                            break
                    explanation = (
                        f"Paired with {host_name}" if host_name else "Device connected"
                    )
                    break
            except Exception:
                pass
    except Exception:
        pass

    result: Dict[str, Any] = {
        "state": state,
        "label": "Connected" if state == "connected" else "Waiting",
        "explanation": explanation,
    }
    if host_name:
        result["host_name"] = host_name
    return result


def _build_pen_state() -> Dict[str, Any]:
    """Map raw pen / scanner state to UI state."""
    config_mgr = ConfigManager.instance()
    cfg = config_mgr.get()
    pen_folder = Path(cfg.IrisPenFolder)

    if not pen_folder.exists():
        return {
            "state": "missing",
            "label": "Not detected",
            "explanation": "Attach the pen / scanner",
        }

    try:
        files = list(pen_folder.iterdir())
        if files:
            return {
                "state": "ready",
                "label": "Ready",
                "explanation": "Scanner found",
            }
    except Exception:
        pass

    return {
        "state": "missing",
        "label": "Not detected",
        "explanation": "Attach the pen / scanner",
    }


def _build_system_state() -> Dict[str, Any]:
    """Map service health to system UI state."""
    ble_active = _service_active("bt_hid_ble.service")
    agent_active = _service_active("bt_hid_agent_unified.service")

    if ble_active and agent_active:
        return {"state": "healthy", "label": "Healthy", "explanation": "All services running"}
    if ble_active or agent_active:
        return {"state": "warning", "label": "Warning", "explanation": "Some services not running"}
    return {"state": "warning", "label": "Waiting", "explanation": "Services starting up"}


def _build_overall_state(
    bluetooth: Dict[str, Any],
    pen: Dict[str, Any],
    transmission: Dict[str, Any],
    system: Dict[str, Any],
) -> Dict[str, Any]:
    """Calculate overall device state from subsystem states."""
    states = [bluetooth["state"], pen["state"], transmission["state"], system["state"]]
    error_states = {"error", "failed"}
    warning_states = {"warning", "retrying", "reconnecting"}
    busy_states = {"sending", "preparing", "reading", "detecting", "pairing"}

    if any(s in error_states for s in states):
        return {"state": "error", "label": "Error", "explanation": "Check events for details"}
    if any(s in warning_states for s in states):
        return {"state": "warning", "label": "Warning", "explanation": "Something needs attention"}
    if any(s in busy_states for s in states):
        return {"state": "busy", "label": "Busy", "explanation": "Device is working"}
    if bluetooth["state"] == "connected":
        return {"state": "ready", "label": "Ready", "explanation": "Ready for use"}
    return {"state": "warning", "label": "Waiting", "explanation": "Waiting for connections"}


# ---------------------------------------------------------------------------
# Status endpoints
# ---------------------------------------------------------------------------

@bp_api.get("/status")
def api_status():
    """Complete dashboard state for the Home screen."""
    timestamp = _now_iso()
    bluetooth = _build_bluetooth_state()
    pen = _build_pen_state()
    transmission: Dict[str, Any] = {
        "state": "idle",
        "label": "Idle",
        "explanation": "No active send",
    }
    system = _build_system_state()
    overall = _build_overall_state(bluetooth, pen, transmission, system)

    with _EVENTS_LOCK:
        last_event = _EVENTS[-1] if _EVENTS else None

    return jsonify({
        "timestamp": timestamp,
        "overall": overall,
        "bluetooth": bluetooth,
        "pen": pen,
        "transmission": transmission,
        "system": system,
        "last_event": last_event,
    })


@bp_api.get("/status/bluetooth")
def api_status_bluetooth():
    return jsonify({"timestamp": _now_iso(), **_build_bluetooth_state()})


@bp_api.get("/status/pen")
def api_status_pen():
    return jsonify({"timestamp": _now_iso(), **_build_pen_state()})


@bp_api.get("/status/transmission")
def api_status_transmission():
    return jsonify({
        "timestamp": _now_iso(),
        "state": "idle",
        "label": "Idle",
        "explanation": "No active send",
        "progress_percent": 0,
        "items_sent": 0,
        "retry_count": 0,
        "last_success_at": None,
    })


@bp_api.get("/status/system")
def api_status_system():
    return jsonify({"timestamp": _now_iso(), **_build_system_state()})


# ---------------------------------------------------------------------------
# Event endpoints
# ---------------------------------------------------------------------------

@bp_api.get("/events")
def api_events():
    limit = min(int(request.args.get("limit", 50)), 200)
    category = request.args.get("category")
    severity = request.args.get("severity")
    since = request.args.get("since")

    with _EVENTS_LOCK:
        items = list(_EVENTS)

    if category:
        items = [e for e in items if e.get("category") == category]
    if severity:
        items = [e for e in items if e.get("severity") == severity]
    if since:
        items = [e for e in items if e.get("timestamp", "") >= since]

    return jsonify({"items": items[-limit:]})


@bp_api.get("/events/latest")
def api_events_latest():
    with _EVENTS_LOCK:
        if _EVENTS:
            return jsonify(_EVENTS[-1])
    return jsonify(None)


# ---------------------------------------------------------------------------
# Log endpoints
# ---------------------------------------------------------------------------

@bp_api.get("/logs/raw")
def api_logs_raw():
    limit = min(int(request.args.get("limit", 100)), 1000)
    contains = request.args.get("contains")

    cmd = ["journalctl", "-n", str(limit), "-o", "short", "-u", "ipr_keyboard.service"]
    try:
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=10)
    except Exception as exc:
        logger.warning("api_logs_raw: journalctl failed: %s", exc)
        output = ""

    lines = output.splitlines()
    if contains:
        lower = contains.lower()
        lines = [ln for ln in lines if lower in ln.lower()]

    return jsonify({"items": [{"timestamp": _now_iso(), "line": ln} for ln in lines]})


# ---------------------------------------------------------------------------
# Configuration endpoints
# ---------------------------------------------------------------------------

@bp_api.get("/config")
def api_config_get():
    config_mgr = ConfigManager.instance()
    cfg = config_mgr.get()
    return jsonify({
        "device_name": "IPR Pen Bridge",
        "ui_title": "IPR Pen Bridge",
        "iris_pen_folder": cfg.IrisPenFolder,
        "delete_files": cfg.DeleteFiles,
        "bluetooth": {
            "auto_reconnect": True,
            "pairing_timeout_seconds": 120,
        },
        "pen": {
            "auto_detect": True,
            "read_timeout_seconds": 10,
        },
        "diagnostics": {
            "log_level": "INFO" if cfg.Logging else "OFF",
        },
    })


@bp_api.post("/config")
def api_config_post():
    data = request.get_json(silent=True) or {}
    config_mgr = ConfigManager.instance()

    update_kwargs: Dict[str, Any] = {}
    if "iris_pen_folder" in data:
        update_kwargs["IrisPenFolder"] = data["iris_pen_folder"]
    if "delete_files" in data:
        update_kwargs["DeleteFiles"] = bool(data["delete_files"])
    if isinstance(data.get("diagnostics"), dict):
        level = data["diagnostics"].get("log_level")
        if level is not None:
            update_kwargs["Logging"] = level != "OFF"

    try:
        config_mgr.update(**update_kwargs)
        _add_event("config", "info", "Configuration updated", "Settings were saved.")
        return jsonify({"ok": True, "message": "Configuration updated."})
    except Exception as exc:
        logger.warning("api_config_post: update failed: %s", exc)
        return jsonify({"error": {"code": "update_failed", "message": "Configuration update failed."}}), 500


# ---------------------------------------------------------------------------
# Action endpoints
# ---------------------------------------------------------------------------

@bp_api.post("/actions/pairing")
def api_action_pairing():
    data = request.get_json(silent=True) or {}
    enabled = data.get("enabled", True)
    try:
        if enabled:
            subprocess.Popen(["bluetoothctl", "pairable", "on"])
            subprocess.Popen(["bluetoothctl", "discoverable", "on"])
            _add_event("bluetooth", "info", "Pairing mode enabled", "Device is now discoverable.")
            return jsonify({"ok": True, "message": "Pairing mode enabled."})
        else:
            subprocess.Popen(["bluetoothctl", "pairable", "off"])
            subprocess.Popen(["bluetoothctl", "discoverable", "off"])
            _add_event("bluetooth", "info", "Pairing mode disabled")
            return jsonify({"ok": True, "message": "Pairing mode disabled."})
    except Exception as exc:
        logger.warning("api_action_pairing: failed: %s", exc)
        return jsonify({"error": {"code": "action_failed", "message": "Pairing action failed."}}), 500


@bp_api.post("/actions/rescan-pen")
def api_action_rescan_pen():
    _add_event("pen", "info", "Pen rescan started", "Looking for pen / scanner device.")
    return jsonify({"ok": True, "message": "Pen rescan started."})


@bp_api.post("/actions/reconnect-bluetooth")
def api_action_reconnect():
    try:
        subprocess.Popen(["systemctl", "restart", "bt_hid_ble.service"])
        _add_event("bluetooth", "info", "Bluetooth reconnect started")
        return jsonify({"ok": True, "message": "Bluetooth reconnect started."})
    except Exception as exc:
        logger.warning("api_action_reconnect: failed: %s", exc)
        return jsonify({"error": {"code": "action_failed", "message": "Reconnect action failed."}}), 500


@bp_api.post("/actions/reboot")
def api_action_reboot():
    data = request.get_json(silent=True) or {}
    if not data.get("confirm"):
        return jsonify({
            "error": {"code": "confirmation_required", "message": "Set confirm=true to reboot."}
        }), 400
    try:
        _add_event("system", "warning", "Reboot initiated", "Device is rebooting.")
        subprocess.Popen(["sudo", "reboot"])
        return jsonify({"ok": True, "message": "Reboot initiated."})
    except Exception as exc:
        logger.warning("api_action_reboot: failed: %s", exc)
        return jsonify({"error": {"code": "action_failed", "message": "Reboot action failed."}}), 500


@bp_api.post("/actions/shutdown")
def api_action_shutdown():
    data = request.get_json(silent=True) or {}
    if not data.get("confirm"):
        return jsonify({
            "error": {"code": "confirmation_required", "message": "Set confirm=true to shut down."}
        }), 400
    try:
        _add_event("system", "warning", "Shutdown initiated", "Device is shutting down.")
        subprocess.Popen(["sudo", "shutdown", "-h", "now"])
        return jsonify({"ok": True, "message": "Shutdown initiated."})
    except Exception as exc:
        logger.warning("api_action_shutdown: failed: %s", exc)
        return jsonify({"error": {"code": "action_failed", "message": "Shutdown action failed."}}), 500


# ---------------------------------------------------------------------------
# Realtime endpoint
# ---------------------------------------------------------------------------

@bp_api.get("/stream")
def api_stream():
    """Server-Sent Events for live dashboard updates."""
    import time

    def event_stream():
        last_count = 0
        while True:
            time.sleep(3)
            with _EVENTS_LOCK:
                current_count = len(_EVENTS)
                if current_count > last_count:
                    new_events = list(_EVENTS)[last_count:]
                    last_count = current_count
                else:
                    new_events = []

            for event in new_events:
                payload = json.dumps({"type": "event_added", "data": event})
                yield f"data: {payload}\n\n"

            # Periodic heartbeat ping
            yield f"data: {json.dumps({'type': 'ping'})}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
