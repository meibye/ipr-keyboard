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
from .pairing_routes import pairing_bp

logger = get_logger()


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
    app.register_blueprint(pairing_bp)

    from flask import render_template

    @app.route("/")
    def index():
        """Root: Human-readable HTML index of server functionality with links."""
        return render_template("index.html")

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
        project_root = Path(os.environ.get("IPR_PROJECT_ROOT", "."))
        log_file = project_root / "ipr-keyboard" / "logs" / "ipr_keyboard.log"
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                log_content = f.read()[-100_000:]
        except Exception as exc:
            log_content = f"Could not read log: {exc}"
        return render_template("logs.html", log_content=log_content)

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
        config_dict = config_mgr.as_dict()
        if flask.request.method == "POST":
            if "restart" in flask.request.form:
                try:
                    subprocess.Popen(["sudo", "reboot"])
                    result = "Restarting machine..."
                except Exception as exc:
                    error = f"Failed to restart: {exc}"
            else:
                for key in config_dict:
                    if key in flask.request.form:
                        try:
                            config_mgr.set(key, flask.request.form[key])
                            result = f"Updated {key}."
                        except Exception as exc:
                            error = f"Failed to update {key}: {exc}"
                config_dict = config_mgr.as_dict()
        return render_template("config.html", config=config_dict, result=result, error=error)

    logger.info("Web server created")
    return app
