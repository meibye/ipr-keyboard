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

    @app.get("/health")
    def health():
        """Simple health-check endpoint."""
        return jsonify({"status": "ok"})

    @app.get("/status")
    def status():
        """System status endpoint.

        Returns JSON with:
          - environment (IPR_USER, IPR_PROJECT_ROOT)
          - config file info and chosen KeyboardBackend
          - log file presence
          - systemd status for bt_hid_* services
          - Bluetooth adapter + paired device info
        """
        env = {
            "IPR_USER": os.environ.get("IPR_USER", ""),
            "IPR_PROJECT_ROOT": os.environ.get("IPR_PROJECT_ROOT", ""),
        }

        project_root = Path(env["IPR_PROJECT_ROOT"] or ".")
        config_file = project_root / "ipr-keyboard" / "config.json"
        log_file = project_root / "ipr-keyboard" / "logs" / "ipr_keyboard.log"

        cfg = ConfigManager.instance().get()
        backend = getattr(cfg, "KeyboardBackend", None)

        services = {
            "bt_hid_uinput.service": _service_status("bt_hid_uinput.service"),
            "bt_hid_ble.service": _service_status("bt_hid_ble.service"),
            "bt_hid_agent.service": _service_status("bt_hid_agent.service"),
        }

        # Bluetooth adapter info
        adapter_info = _run_cmd(["bluetoothctl", "show"])

        # Paired devices and their info
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

        return jsonify(
            {
                "env": env,
                "config": {
                    "file": str(config_file),
                    "exists": config_file.exists(),
                    "keyboard_backend": backend,
                },
                "log": {
                    "file": str(log_file),
                    "exists": log_file.exists(),
                },
                "services": services,
                "bluetooth": {
                    "adapter": adapter_info,
                    "devices": devices,
                },
            }
        )

    logger.info("Web server created")
    return app
