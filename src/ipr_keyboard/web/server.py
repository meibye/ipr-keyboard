"""Flask web server application factory.

Creates and configures the Flask application with all blueprints.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, List

from flask import Flask, jsonify

from ..config.manager import ConfigManager
from ..config.web import bp_config
from ..logging.logger import get_logger
from ..logging.web import bp_logs

logger = get_logger()

VERSION = '2026-04-12 19:40:34'

def log_version_info():
    logger.info(f"==== ipr_keyboard.web.server VERSION: {VERSION} ====")


def _run_cmd(cmd: List[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    except Exception as exc:
        return f"ERROR: {exc}"


def _service_status(name: str) -> str:
    try:
        # is-active --quiet returns 0 only when active
        rc = subprocess.call(["systemctl", "is-active", "--quiet", name])
        if rc == 0:
            return "active"
        # Check if enabled even if not active
        rc = subprocess.call(["systemctl", "is-enabled", "--quiet", name])
        if rc == 0:
            return "enabled-not-active"
        return "inactive"
    except Exception:
        return "unknown"


def create_app() -> Flask:
    app = Flask(__name__)

    # Register blueprints
    app.register_blueprint(bp_config)
    app.register_blueprint(bp_logs)

    from .api import bp_api
    app.register_blueprint(bp_api)

    from flask import render_template

    @app.route("/")
    def index():
        """Root: Serve the image-first dashboard SPA."""
        return render_template("dashboard.html")

    @app.get("/health")
    def health():
        """Simple health-check endpoint."""
        return jsonify({"status": "ok"})

    @app.route("/status")
    def status():
        env = {
            "IPR_USER": os.environ.get("IPR_USER", ""),
            "IPR_PROJECT_ROOT": os.environ.get("IPR_PROJECT_ROOT", ""),
        }
        project_root = Path(env["IPR_PROJECT_ROOT"] or ".")
        config_file = project_root / "ipr-keyboard" / "config.json"
        log_file = project_root / "ipr-keyboard" / "logs" / "ipr_keyboard.log"
        services = {
            "bt_hid_ble.service": _service_status("bt_hid_ble.service"),
            "bt_hid_agent_unified.service": _service_status("bt_hid_agent_unified.service"),
        }
        adapter_info = _run_cmd(["bluetoothctl", "show"])
        devices: list[dict[str, Any]] = []
        try:
            devices_out = subprocess.check_output(
                ["bluetoothctl", "devices"], text=True
            )
            for line in devices_out.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    mac = parts[1]
                    info_out = _run_cmd(["bluetoothctl", "info", mac])
                    devices.append({"mac": mac, "info": info_out})
        except Exception as exc:
            devices.append({"error": f"failed to query devices: {exc}"})
        return render_template(
            "status.html",
            env=env,
            config={"file": str(config_file), "exists": config_file.exists()},
            log={"file": str(log_file), "exists": log_file.exists()},
            services=services,
            bluetooth={"adapter": adapter_info, "devices": devices},
        )

    @app.route("/logs/")
    def logs():
        # Supported units from svc_tail_all_logs.sh
        units = [
            "ipr_keyboard.service",
            "ipr-provision.service",
            "bt_hid_ble.service",
            "bt_hid_agent_unified.service",
            "bluetooth.service",
            "dbus.service",
            "systemd-udevd.service",
        ]
        import flask
        selected_units = flask.request.args.getlist("unit")
        if not selected_units:
            selected_units = ["ipr_keyboard.service"]
        # Build journalctl command
        cmd = ["journalctl", "-n", "1000", "-o", "short"]
        for u in selected_units:
            cmd += ["-u", u]
        try:
            log_content = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
        except Exception as exc:
            log_content = f"Could not read logs: {exc}"
        return render_template("logs_select.html", log_content=log_content, units=units, selected_units=selected_units)

    @app.route("/pairing/", methods=["GET", "POST"])
    def pairing():
        result = error = None
        # Start pairing on POST
        if flask.request.method == "POST":
            try:
                out = _run_cmd(["bluetoothctl", "pairable", "on"])
                out += _run_cmd(["bluetoothctl", "discoverable", "on"])
                out += _run_cmd(["bluetoothctl", "agent", "on"])
                out += _run_cmd(["bluetoothctl", "default-agent"])
                result = "Pairing mode enabled. Device is now discoverable."
            except Exception as exc:
                error = f"Failed to start pairing: {exc}"
        # List paired devices
        devices: list[dict[str, str]] = []
        try:
            devices_out = subprocess.check_output(["bluetoothctl", "devices"], text=True)
            for line in devices_out.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    mac = parts[1]
                    info_out = _run_cmd(["bluetoothctl", "info", mac])
                    devices.append({"mac": mac, "info": info_out})
        except Exception as exc:
            devices.append({"error": f"failed to query devices: {exc}"})
        return render_template("pairing.html", result=result, error=error, devices=devices)

    @app.route("/config/", methods=["GET", "POST"])
    def config():
        result = error = None
        config_mgr = ConfigManager.instance()
        config_obj = config_mgr.get()
        config_dict = config_obj.to_dict()
        if flask.request.method == "POST":
            if "restart" in flask.request.form:
                try:
                    subprocess.Popen(["sudo", "reboot"])
                    result = "Restarting machine..."
                except Exception as exc:
                    error = f"Failed to restart: {exc}"
            elif "shutdown" in flask.request.form:
                try:
                    subprocess.Popen(["sudo", "shutdown", "-h", "now"])
                    result = "Shutting down machine..."
                except Exception as exc:
                    error = f"Failed to shutdown: {exc}"
            else:
                update_kwargs = {}
                for key, value in flask.request.form.items():
                    if key in config_dict:
                        # Type conversion
                        field_type = type(getattr(config_obj, key))
                        if field_type is bool:
                            update_kwargs[key] = value == "on"
                        elif field_type is int:
                            try:
                                update_kwargs[key] = int(value)
                            except Exception:
                                update_kwargs[key] = config_dict[key]
                        else:
                            update_kwargs[key] = value
                try:
                    config_mgr.update(**update_kwargs)
                    result = "Configuration updated."
                except Exception as exc:
                    error = f"Failed to update config: {exc}"
                config_obj = config_mgr.get()
                config_dict = config_obj.to_dict()
        return render_template("config.html", config=config_dict, result=result, error=error)

    logger.info("Web server created")
    return app
