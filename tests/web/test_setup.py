"""Tests for the /setup/ blueprint (provisioning interface)."""
import subprocess

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def anon_client(temp_config, monkeypatch, tmp_path):
    """Unauthenticated Flask test client — no session injected."""
    from ipr_keyboard.config.manager import ConfigManager
    from ipr_keyboard.web.server import create_app
    from ipr_keyboard.web import auth as auth_module

    users_file = tmp_path / "users.json"
    monkeypatch.setattr(auth_module, "users_path", lambda: users_file)
    auth_module.UserStore._instance = None

    ConfigManager.instance()
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client

    auth_module.UserStore._instance = None


@pytest.fixture
def setup_client(temp_config, monkeypatch, tmp_path):
    """Flask test client with setup session authenticated (setup_ok=True)."""
    from ipr_keyboard.config.manager import ConfigManager
    from ipr_keyboard.web.server import create_app
    from ipr_keyboard.web import auth as auth_module

    users_file = tmp_path / "users.json"
    monkeypatch.setattr(auth_module, "users_path", lambda: users_file)
    auth_module.UserStore._instance = None

    ConfigManager.instance()
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["setup_ok"] = True
        yield client

    auth_module.UserStore._instance = None


def _mock_subprocess(monkeypatch):
    """Patch subprocess calls used by setup blueprint helpers."""

    def mock_call(cmd, **kwargs):
        return 1  # not active

    def mock_check_output(cmd, **kwargs):
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
        if "bluetoothctl" in cmd_str:
            return "Powered: no\n"
        if "journalctl" in cmd_str:
            return "Jun 10 12:00:00 ipr ipr_keyboard[1]: started"
        if "openssl" in cmd_str:
            return "notAfter=Dec 31 23:59:59 2026 GMT"
        if "hostname" in cmd_str:
            return "ipr-keyboard"
        return ""

    monkeypatch.setattr(subprocess, "call", mock_call)
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)


# ---------------------------------------------------------------------------
# Auth & login
# ---------------------------------------------------------------------------


def test_setup_login_get_returns_200(anon_client):
    """GET /setup/login renders the login page without auth."""
    res = anon_client.get("/setup/login")
    assert res.status_code == 200


def test_setup_login_post_valid_creds(anon_client, monkeypatch):
    """POST /setup/login with correct credentials sets setup_ok and redirects."""
    import ipr_keyboard.web.setup as setup_mod

    monkeypatch.setattr(setup_mod, "_load_hotspot_password", lambda: "s3cret")

    res = anon_client.post(
        "/setup/login",
        data={"username": "ipr", "password": "s3cret"},
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert "/setup/" in res.headers["Location"]


def test_setup_login_post_invalid_creds(anon_client, monkeypatch):
    """POST /setup/login with wrong password returns 401."""
    import ipr_keyboard.web.setup as setup_mod

    monkeypatch.setattr(setup_mod, "_load_hotspot_password", lambda: "s3cret")

    res = anon_client.post(
        "/setup/login",
        data={"username": "ipr", "password": "wrong"},
    )
    assert res.status_code == 401


def test_setup_logout_clears_session(setup_client):
    """GET /setup/logout clears setup_ok and redirects to /setup/login."""
    res = setup_client.get("/setup/logout", follow_redirects=False)
    assert res.status_code == 302
    assert "login" in res.headers["Location"]


def test_setup_protected_route_redirects_without_auth(anon_client):
    """GET /setup/ without a valid session redirects to /setup/login."""
    res = anon_client.get("/setup/", follow_redirects=False)
    assert res.status_code == 302
    assert "login" in res.headers["Location"]


def test_setup_accessible_via_dashboard_admin_session(temp_config, monkeypatch, tmp_path):
    """GET /setup/ with a main-dashboard admin session returns 200 (no hotspot login)."""
    import ipr_keyboard.web.setup as setup_mod
    from ipr_keyboard.config.manager import ConfigManager
    from ipr_keyboard.web.server import create_app
    from ipr_keyboard.web import auth as auth_module

    users_file = tmp_path / "users.json"
    monkeypatch.setattr(auth_module, "users_path", lambda: users_file)
    auth_module.UserStore._instance = None
    ConfigManager.instance()

    app = create_app()
    app.config["TESTING"] = True

    monkeypatch.setattr(setup_mod, "_read_hotspot_secret", lambda: ("TestSSID", "pass"))
    monkeypatch.setattr(setup_mod, "_bt_info", lambda: {"powered": False, "devices": []})

    def mock_check_output(cmd, **kwargs):
        return ""

    monkeypatch.setattr(__import__("subprocess"), "check_output", mock_check_output)

    with app.test_client() as client:
        with client.session_transaction() as sess:
            # Main-dashboard session: username set, is_admin True, no setup_ok
            sess["username"] = "admin"
            sess["is_admin"] = True

        res = client.get("/setup/", follow_redirects=False)

    assert res.status_code == 200
    auth_module.UserStore._instance = None


# ---------------------------------------------------------------------------
# Public routes (no auth required)
# ---------------------------------------------------------------------------


def test_setup_lang_valid(anon_client):
    """GET /setup/lang/da sets language cookie and redirects."""
    res = anon_client.get("/setup/lang/da", follow_redirects=False)
    assert res.status_code == 302


def test_setup_lang_invalid_still_redirects(anon_client):
    """GET /setup/lang/<unsupported> ignores code and still redirects (no error)."""
    res = anon_client.get("/setup/lang/zz", follow_redirects=False)
    assert res.status_code == 302


def test_setup_ca_cert_missing_returns_404(anon_client):
    """GET /setup/ca.crt returns 404 when the CA file is absent."""
    res = anon_client.get("/setup/ca.crt")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Authenticated routes (setup_ok required)
# ---------------------------------------------------------------------------


def test_setup_home_renders(setup_client, monkeypatch):
    """GET /setup/ with valid setup session returns 200."""
    import ipr_keyboard.web.setup as setup_mod

    _mock_subprocess(monkeypatch)
    monkeypatch.setattr(setup_mod, "_read_hotspot_secret", lambda: ("TestSSID", "pass"))

    res = setup_client.get("/setup/")
    assert res.status_code == 200


def test_setup_status_renders(setup_client, monkeypatch):
    """GET /setup/status returns 200 with service and Bluetooth data."""
    import ipr_keyboard.web.setup as setup_mod

    _mock_subprocess(monkeypatch)
    monkeypatch.setattr(
        setup_mod, "_bt_info", lambda: {"powered": False, "devices": []}
    )

    res = setup_client.get("/setup/status")
    assert res.status_code == 200


def test_setup_wifi_renders(setup_client, monkeypatch):
    """GET /setup/wifi triggers background scan and returns 200."""
    import ipr_keyboard.web.setup as setup_mod

    monkeypatch.setattr(setup_mod, "_trigger_scan_background", lambda: None)

    res = setup_client.get("/setup/wifi")
    assert res.status_code == 200


def test_setup_rescan_post(setup_client, monkeypatch):
    """POST /setup/rescan triggers background Wi-Fi scan and returns 200."""
    import ipr_keyboard.web.setup as setup_mod

    monkeypatch.setattr(setup_mod, "_trigger_scan_background", lambda: None)

    res = setup_client.post("/setup/rescan")
    assert res.status_code == 200


def test_setup_connect_saves_profile(setup_client, monkeypatch):
    """POST /setup/connect with a valid SSID saves the Wi-Fi profile and redirects."""
    import ipr_keyboard.web.setup as setup_mod

    saved = []
    monkeypatch.setattr(
        setup_mod, "_save_wifi_profile", lambda s, p, sec: saved.append(s)
    )

    res = setup_client.post(
        "/setup/connect",
        data={"ssid": "HomeNetwork", "psk": "password", "security": "auto"},
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert saved == ["HomeNetwork"]


def test_setup_connect_no_ssid_shows_error(setup_client):
    """POST /setup/connect without an SSID renders wifi page with error (200)."""
    res = setup_client.post(
        "/setup/connect",
        data={"ssid": "", "psk": "", "security": "auto"},
    )
    assert res.status_code == 200


def test_setup_logs_renders(setup_client, monkeypatch):
    """GET /setup/logs returns 200 with log content."""
    _mock_subprocess(monkeypatch)

    res = setup_client.get("/setup/logs")
    assert res.status_code == 200


def test_setup_system_renders(setup_client, monkeypatch):
    """GET /setup/system returns 200 with cert expiry info."""
    _mock_subprocess(monkeypatch)

    res = setup_client.get("/setup/system")
    assert res.status_code == 200


def test_setup_renew_cert_no_script(setup_client):
    """POST /setup/renew-cert when the renewal script is absent returns 200."""
    # _CERT_RENEW_SCRIPT won't exist in test env; route handles this gracefully
    res = setup_client.post("/setup/renew-cert")
    assert res.status_code == 200


def test_setup_reboot_post(setup_client, monkeypatch):
    """POST /setup/reboot calls reboot subprocess and returns 200."""
    _mock_subprocess(monkeypatch)
    popen_calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: popen_calls.append(cmd))

    res = setup_client.post("/setup/reboot")

    assert res.status_code == 200
    assert any("reboot" in " ".join(c) for c in popen_calls)


def test_setup_shutdown_post(setup_client, monkeypatch):
    """POST /setup/shutdown calls shutdown subprocess and returns 200."""
    _mock_subprocess(monkeypatch)
    popen_calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: popen_calls.append(cmd))

    res = setup_client.post("/setup/shutdown")

    assert res.status_code == 200
    assert any("shutdown" in " ".join(c) for c in popen_calls)
