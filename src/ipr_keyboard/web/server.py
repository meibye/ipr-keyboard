"""Flask web server application factory.

Creates and configures the Flask application with all blueprints.
"""

from __future__ import annotations

import os
import secrets
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Any, List
from urllib.parse import urlparse

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from ..config.web import bp_config
from ..logging.logger import get_logger
from ..logging.web import bp_logs
from ..utils.helpers import project_root
from .auth import UserStore

logger = get_logger()

VERSION = "2026-04-12 19:40:34"


def log_version_info():
    logger.info(f"==== ipr_keyboard.web.server VERSION: {VERSION} ====")


def _run_cmd(cmd: List[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    except Exception as exc:
        return f"ERROR: {exc}"


def _resolve_secret_key() -> str:
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    key_file = project_root() / "secret_key.txt"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    new_key = secrets.token_hex(32)
    key_file.write_text(new_key, encoding="utf-8")
    try:
        key_file.chmod(0o600)
    except Exception:
        pass
    logger.info("Generated new secret key at %s", key_file)
    return new_key


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


_PUBLIC_PATHS = {"/health", "/login", "/logout", "/api/auth/login", "/setup"}


def create_app() -> Flask:
    app = Flask(__name__)

    app.config["SECRET_KEY"] = _resolve_secret_key()

    # Stylesheets and icons are served from a fixed URL, so a browser that has
    # cached an older copy keeps using it after an update -- the dashboard then
    # renders with the wrong layout until it is reloaded by hand.  Stamp every
    # static URL with the file's modification time so a changed file is a new
    # URL and the question never arises.
    @app.template_global()
    def asset_url(filename: str) -> str:  # used as asset_url('ipr.css')
        url = url_for("static", filename=filename)
        try:
            stamp = int((Path(app.static_folder) / filename).stat().st_mtime)
        except (OSError, TypeError):
            return url
        return f"{url}?v={stamp}"

    app.config["SESSION_COOKIE_SECURE"] = True
    app.permanent_session_lifetime = timedelta(days=7)
    UserStore.instance()  # bootstrap default admin user on first run

    # Register blueprints
    app.register_blueprint(bp_config)
    app.register_blueprint(bp_logs)

    from .api import bp_api

    app.register_blueprint(bp_api)

    from .setup import bp_setup

    app.register_blueprint(bp_setup)

    @app.before_request
    def _require_login():
        path = request.path
        if path.startswith("/static/"):
            return
        if any(path == p or path.startswith(p + "/") for p in _PUBLIC_PATHS):
            return
        if not session.get("username"):
            if path.startswith("/api/"):
                return jsonify(
                    {"error": {"code": "unauthenticated", "message": "Login required."}}
                ), 401
            # Clients on the management hotspot (10.42.0.x) should use the
            # setup login, not the main dashboard login.
            if (request.remote_addr or "").startswith("10.42.0."):
                return redirect(url_for("setup.login_page"))
            return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            if UserStore.instance().verify(username, password):
                session.clear()
                session.permanent = True
                session["username"] = username
                session["is_admin"] = UserStore.instance().user_info(username)[
                    "is_admin"
                ]
                next_url = request.args.get("next", "")
                if urlparse(next_url).netloc:
                    next_url = ""
                return redirect(next_url or url_for("index"))
            error = "Invalid username or password."
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    def index():
        return render_template("dashboard.html", is_admin=bool(session.get("is_admin")))

    @app.after_request
    def _no_store_html(response):
        """Never let a browser keep an HTML page.

        The pages carry their own JavaScript, and a cached page talking to an
        updated API misreports rather than failing: an old dashboard read a
        field the new API had stopped sending, decided every row of the speed
        trial was "incomplete", and sent us chasing a bug that was not there.
        Static assets are versioned and still cached; only the documents are
        not.
        """
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response

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
            "bt_hid_agent_unified.service": _service_status(
                "bt_hid_agent_unified.service"
            ),
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

    @app.route("/pairing/", methods=["GET", "POST"])
    def pairing():
        result = error = None
        # Start pairing on POST
        if request.method == "POST":
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
            "pairing.html", result=result, error=error, devices=devices
        )

    logger.info("Web server created")
    return app
