"""Fixtures for end-to-end tests over real HTTP.

Three modes, chosen automatically:

1. **Local (default).**  No ``IPR_*`` variables set — the real Flask app is
   started in-process on an ephemeral 127.0.0.1 port and the tests run against
   it.  This exercises the socket / WSGI / redirect / cookie path that the
   Flask test client in ``tests/web/`` cannot reach, with no manual setup.
2. **Device.**  ``IPR_BASE_URL`` (and/or ``IPR_SETUP_URL``) set — tests run
   against that device instead.
3. **Device, strict.**  ``--e2e`` — as above, but a missing variable or a
   failed login is a failure rather than a skip, so a mistyped password cannot
   masquerade as "tests passed".

Environment variables:
  IPR_BASE_URL          Base URL of the device's web server, e.g. http://192.168.1.42:8080
  IPR_SETUP_URL         Base URL when connected to the hotspot, e.g. http://10.42.0.1:8080
                        Falls back to IPR_BASE_URL when absent.
  IPR_PASSWORD          Password for the main dashboard admin user (default: "admin")
  IPR_SETUP_PASSWORD    Password for the setup interface (hotspot secret)

Note that local mode proves the HTTP surface, not the hardware: systemd,
nmcli and journalctl calls fail through to their error paths, so the pages
render but report nothing useful.  Hardware behaviour still needs a device
run (tier 3+ in TESTING_PLAN.md).
"""

import json
import os
import threading
from datetime import datetime, timezone

import pytest
import requests

# Credentials used only by the local fallback server.  Must satisfy the
# 8-character minimum enforced by UserStore.
LOCAL_ADMIN_PASSWORD = "e2e-local-admin"
LOCAL_SETUP_PASSWORD = "e2e-local-setup"


def _fail_or_skip(request, message: str):
    """Fail under --e2e, otherwise skip."""
    if request.config.getoption("--e2e"):
        pytest.fail(message)
    pytest.skip(f"E2E test skipped: {message}")


@pytest.fixture(scope="session")
def local_mode(request) -> bool:
    """True when no device URL is configured and the local server is used."""
    if os.environ.get("IPR_BASE_URL") or os.environ.get("IPR_SETUP_URL"):
        return False
    if request.config.getoption("--e2e"):
        pytest.fail(
            "--e2e requires a device: set IPR_BASE_URL (and IPR_SETUP_PASSWORD "
            "for the setup tests)."
        )
    return True


@pytest.fixture(scope="session")
def _local_server(tmp_path_factory):
    """Serve the real app on 127.0.0.1 with an ephemeral port."""
    from werkzeug.security import generate_password_hash
    from werkzeug.serving import make_server

    from ipr_keyboard.web import auth as auth_module
    from ipr_keyboard.web import setup as setup_module
    from ipr_keyboard.web.server import create_app

    users_file = tmp_path_factory.mktemp("e2e") / "users.json"
    # Seed the admin account before create_app() runs.  An empty store would
    # make UserStore._ensure_default() mint a random password and overwrite
    # admin_initial_password.txt in the project root.
    users_file.write_text(
        json.dumps(
            {
                "version": 1,
                "users": {
                    "admin": {
                        "password_hash": generate_password_hash(LOCAL_ADMIN_PASSWORD),
                        "created_at": datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        "is_admin": True,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    original_users_path = auth_module.users_path
    original_hotspot_password = setup_module._load_hotspot_password
    auth_module.users_path = lambda: users_file
    auth_module.UserStore._instance = None
    # /etc/ipr-hotspot.secret only exists on the device.
    setup_module._load_hotspot_password = lambda: LOCAL_SETUP_PASSWORD

    app = create_app()
    # Served over plain HTTP here, so a Secure-only cookie would never be
    # sent back and every authenticated request would 401.
    app.config["SESSION_COOKIE_SECURE"] = False

    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        auth_module.users_path = original_users_path
        setup_module._load_hotspot_password = original_hotspot_password
        auth_module.UserStore._instance = None


@pytest.fixture(scope="session")
def base_url(request, local_mode) -> str:
    if local_mode:
        return request.getfixturevalue("_local_server")
    url = os.environ.get("IPR_BASE_URL", "").rstrip("/")
    if not url:
        _fail_or_skip(request, "IPR_BASE_URL not set")
    return url


@pytest.fixture(scope="session")
def setup_url(request, local_mode) -> str:
    if local_mode:
        return request.getfixturevalue("_local_server")
    url = (os.environ.get("IPR_SETUP_URL") or os.environ.get("IPR_BASE_URL") or "").rstrip("/")
    if not url:
        _fail_or_skip(request, "IPR_SETUP_URL (or IPR_BASE_URL) not set")
    return url


@pytest.fixture(scope="session")
def dashboard_session(request, base_url, local_mode) -> requests.Session:
    """Authenticated requests.Session for the main dashboard."""
    if local_mode:
        password = LOCAL_ADMIN_PASSWORD
    else:
        password = os.environ.get("IPR_PASSWORD", "admin")
    sess = requests.Session()
    sess.verify = False  # self-signed cert on device
    res = sess.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": password},
        timeout=10,
    )
    if res.status_code != 200:
        _fail_or_skip(
            request, f"dashboard login failed ({res.status_code}) — check IPR_PASSWORD"
        )
    return sess


@pytest.fixture(scope="session")
def setup_session(request, setup_url, local_mode) -> requests.Session:
    """Authenticated requests.Session for the setup interface."""
    if local_mode:
        password = LOCAL_SETUP_PASSWORD
    else:
        password = os.environ.get("IPR_SETUP_PASSWORD", "")
        if not password:
            _fail_or_skip(request, "IPR_SETUP_PASSWORD not set")
    sess = requests.Session()
    sess.verify = False
    res = sess.post(
        f"{setup_url}/setup/login",
        data={"username": "ipr", "password": password},
        allow_redirects=True,
        timeout=10,
    )
    if res.status_code not in (200, 302):
        _fail_or_skip(
            request,
            f"setup login failed ({res.status_code}) — check IPR_SETUP_PASSWORD",
        )
    return sess
