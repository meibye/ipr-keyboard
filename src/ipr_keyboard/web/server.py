"""Flask web server application factory.

Creates and configures the Flask application with all blueprints.
"""
from __future__ import annotations

from flask import Flask, jsonify

from ..logging.logger import get_logger
from ..config.web import bp_config
from ..logging.web import bp_logs

logger = get_logger()


def create_app() -> Flask:
        import os
        import subprocess
        import json
        from pathlib import Path
        from flask import Response
        from ..config.manager import ConfigManager

        @app.get("/status")
        def status():
            """System status endpoint.
            Returns JSON with Bluetooth backend, service status, Bluetooth pairing, USB mount, web API, and logging info.
            """
            cfg = ConfigManager.instance().get()
            config_file = Path(os.environ.get("IPR_PROJECT_ROOT", ".")) / "ipr-keyboard" / "config.json"
            log_file = Path(os.environ.get("IPR_PROJECT_ROOT", ".")) / "ipr-keyboard" / "logs" / "ipr_keyboard.log"
            # Backend
            backend = getattr(cfg, "KeyboardBackend", None) or "default"
            # Service status
            services = {}
            for svc in ["bt_hid_daemon.service", "bt_hid_ble.service", "bt_hid_uinput.service"]:
                try:
                    res = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, check=False)
                    services[svc] = res.stdout.strip()
                except Exception:
                    services[svc] = "unknown"
            # Bluetooth pairing info
            bt_info = []
            try:
                out = subprocess.run(["bluetoothctl", "paired-devices"], capture_output=True, text=True, check=False)
                bt_info = out.stdout.strip().splitlines()
            except Exception:
                bt_info = ["bluetoothctl not available"]
            # USB mount
            mount_path = getattr(cfg, "IrisPenFolder", "/mnt/irispen")
            try:
                mounts = subprocess.run(["mount"], capture_output=True, text=True, check=False).stdout
                mounted = any(mount_path in line for line in mounts.splitlines())
            except Exception:
                mounted = False
            # Web API port
            port = getattr(cfg, "LogPort", 8080)
            # Web API listening
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                listening = s.connect_ex(("127.0.0.1", int(port))) == 0
                s.close()
            except Exception:
                listening = False
            # Log file
            log_exists = log_file.exists()
            log_tail = []
            if log_exists:
                try:
                    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                        log_tail = f.readlines()[-3:]
                except Exception:
                    log_tail = ["(error reading log)"]
            return jsonify({
                "backend": backend,
                "services": services,
                "bluetooth_paired_devices": bt_info,
                "usb_mount": {"path": mount_path, "mounted": mounted},
                "web_api": {"port": port, "listening": listening},
                "log_file": {"exists": log_exists, "tail": log_tail},
                "config_file": str(config_file),
            })
    """Create and configure the Flask application.
    
    Registers all blueprints (config and logs) and sets up health check endpoint.
    
    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    app.register_blueprint(bp_config)
    app.register_blueprint(bp_logs)

    @app.get("/health")
    def health():
        """Health check endpoint.
        
        Returns:
            JSON response with status "ok".
        """
        return jsonify({"status": "ok"})

    logger.info("Web server created")
    return app
