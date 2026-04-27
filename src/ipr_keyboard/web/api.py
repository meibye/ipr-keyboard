"""Flask API blueprint for the dashboard.

Implements all /api/ endpoints as defined in docs/ui/api-contract.md.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request, session, stream_with_context

from ..config.manager import ConfigManager
from ..logging.logger import get_logger, set_log_level
from .. import transmission
from ..usb.detector import list_files
from .auth import UserStore

logger = get_logger()

FOLDER_OPTIONS = [
    {
        "path": "/mnt/irispen/Intern delt lagerplads/Scan text and save",
        "label_en": "Scan to Text & Save",
        "label_da": "Scan til tekst og gem",
    },
    {
        "path": "/mnt/irispen/Intern delt lagerplads/picture",
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
    agent_active = _service_active("bt_hid_agent_unified.service")
    if agent_active:
        state, label, explanation = "ready", "Ready", "Scanner found"
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

@bp_api.get("/logs/raw")
def api_logs_raw():
    try:
        limit = min(int(request.args.get("limit", 100)), 1000)
        contains = request.args.get("contains") or None
        cmd = ["journalctl", "-n", str(limit), "-o", "short", "--no-pager"]
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
            items.append({"timestamp": _now(), "line": line})
        return jsonify({"items": items})
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
                "pairing_timeout_seconds": 120,
            },
            "pen": {
                "auto_detect": True,
                "read_timeout_seconds": 10,
                "folder": cfg.IrisPenFolder,
                "folder_options": FOLDER_OPTIONS,
            },
            "diagnostics": {
                "log_level": log_level,
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
        if "pen" in data and "folder" in data["pen"]:
            requested = data["pen"]["folder"]
            allowed = [o["path"] for o in FOLDER_OPTIONS]
            if requested in allowed:
                update_kwargs["IrisPenFolder"] = requested
        if update_kwargs:
            cfg_mgr.update(**update_kwargs)
        return jsonify({"ok": True, "message": "Configuration updated."})
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


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
    try:
        subprocess.Popen(["systemctl", "restart", "bt_hid_ble.service"])
        return jsonify({"ok": True, "message": "Bluetooth reconnect started."})
    except Exception:
        logger.exception("API error"); return jsonify({"error": {"code": "internal_error", "message": "An internal error occurred."}}), 500


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
                bt = _build_bluetooth_state()
                pen = _build_pen_state()
                tx = _build_transmission_state()
                sys = _build_system_state(bt)
                overall = _build_overall_state(bt, pen, tx, sys)
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
            time.sleep(5)

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
    try:
        result = subprocess.run(
            ["sudo", "systemctl", action, name],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return jsonify({"ok": True, "message": f"Service {name} {action} succeeded."})
        stderr = (result.stderr or "").strip()
        return jsonify({"ok": False, "message": stderr or f"Service {name} {action} failed (exit {result.returncode})."})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "message": f"Timed out waiting for systemctl {action} {name}."}), 500
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
        folder = Path(cfg.IrisPenFolder)
        files_result = []
        for p in list_files(folder):
            try:
                stat = p.stat()
                raw = p.read_bytes()
                content = raw[:_PEN_FILES_CONTENT_CAP].decode("utf-8", errors="replace")
                truncated = len(raw) > _PEN_FILES_CONTENT_CAP
                files_result.append({
                    "name": p.name,
                    "path": str(p),
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "content": content,
                    "truncated": truncated,
                })
            except OSError:
                pass
        return jsonify({"folder": str(folder), "files": files_result})
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
    is_admin = bool(session.get("is_admin"))
    if caller != username and not is_admin:
        return _err("forbidden", "Admin access required to change another user's password.", 403)
    body = request.get_json(silent=True) or {}
    password = str(body.get("password", ""))
    try:
        UserStore.instance().change_password(username, password)
    except KeyError:
        return _err("not_found", f"User '{username}' not found.", 404)
    except ValueError as exc:
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
