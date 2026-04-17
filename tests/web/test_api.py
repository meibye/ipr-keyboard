"""Tests for /api/ endpoints defined in docs/ui/api-contract.md."""

import subprocess


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_subprocess_idle(monkeypatch):
    """Patch subprocess so services appear inactive and bluetoothctl returns defaults."""

    def mock_call(cmd, **kwargs):
        return 1  # not active

    def mock_check_output(cmd, **kwargs):
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
        if "journalctl" in cmd_str:
            return "Apr 17 14:20:00 pi bt_hid_ble[123]: started\nApr 17 14:21:00 pi bt_hid_ble[123]: connected"
        if "bluetoothctl" in cmd_str:
            return "Powered: no\n"
        return ""

    monkeypatch.setattr(subprocess, "call", mock_call)
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)


# ---------------------------------------------------------------------------
# Status endpoints
# ---------------------------------------------------------------------------

def test_api_status_returns_json(flask_client, temp_config, monkeypatch):
    """GET /api/status returns 200 with expected top-level fields."""
    _mock_subprocess_idle(monkeypatch)

    res = flask_client.get("/api/status")

    assert res.status_code == 200
    data = res.get_json()
    assert "timestamp" in data
    assert "overall" in data
    assert "bluetooth" in data
    assert "pen" in data
    assert "transmission" in data
    assert "system" in data


def test_api_status_bluetooth(flask_client, temp_config, monkeypatch):
    """GET /api/status/bluetooth returns 200 with state field."""
    _mock_subprocess_idle(monkeypatch)

    res = flask_client.get("/api/status/bluetooth")

    assert res.status_code == 200
    data = res.get_json()
    assert "state" in data
    assert "label" in data


def test_api_status_pen(flask_client, temp_config, monkeypatch):
    """GET /api/status/pen returns state field."""
    _mock_subprocess_idle(monkeypatch)

    res = flask_client.get("/api/status/pen")

    assert res.status_code == 200
    data = res.get_json()
    assert "state" in data


def test_api_status_transmission(flask_client, temp_config, monkeypatch):
    """GET /api/status/transmission returns state field."""
    _mock_subprocess_idle(monkeypatch)

    res = flask_client.get("/api/status/transmission")

    assert res.status_code == 200
    data = res.get_json()
    assert "state" in data


def test_api_status_system(flask_client, temp_config, monkeypatch):
    """GET /api/status/system returns state field."""
    _mock_subprocess_idle(monkeypatch)

    res = flask_client.get("/api/status/system")

    assert res.status_code == 200
    data = res.get_json()
    assert "state" in data


# ---------------------------------------------------------------------------
# Event endpoints
# ---------------------------------------------------------------------------

def test_api_events_returns_list(flask_client, temp_config, monkeypatch):
    """GET /api/events returns {items: [...]}."""
    _mock_subprocess_idle(monkeypatch)

    res = flask_client.get("/api/events")

    assert res.status_code == 200
    data = res.get_json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_api_events_latest(flask_client, temp_config, monkeypatch):
    """GET /api/events/latest returns a single event object."""
    _mock_subprocess_idle(monkeypatch)

    res = flask_client.get("/api/events/latest")

    assert res.status_code == 200
    data = res.get_json()
    assert "timestamp" in data
    assert "summary" in data


def test_api_events_category_filter(flask_client, temp_config, monkeypatch):
    """GET /api/events?category=bluetooth returns filtered items."""
    _mock_subprocess_idle(monkeypatch)

    res = flask_client.get("/api/events?category=bluetooth&limit=10")

    assert res.status_code == 200
    data = res.get_json()
    assert "items" in data
    for item in data["items"]:
        assert item["category"] == "bluetooth"


# ---------------------------------------------------------------------------
# Log endpoints
# ---------------------------------------------------------------------------

def test_api_logs_raw(flask_client, temp_config, monkeypatch):
    """GET /api/logs/raw returns {items: [...]}."""
    _mock_subprocess_idle(monkeypatch)

    res = flask_client.get("/api/logs/raw")

    assert res.status_code == 200
    data = res.get_json()
    assert "items" in data
    assert isinstance(data["items"], list)


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------

def test_api_config_get(flask_client, temp_config, monkeypatch):
    """GET /api/config returns expected shape."""
    res = flask_client.get("/api/config")

    assert res.status_code == 200
    data = res.get_json()
    assert "device_name" in data
    assert "bluetooth" in data
    assert "pen" in data
    assert "diagnostics" in data


def test_api_config_post(flask_client, temp_config, monkeypatch):
    """POST /api/config updates config and returns ok."""
    payload = {
        "diagnostics": {"log_level": "DEBUG"},
    }

    res = flask_client.post(
        "/api/config",
        json=payload,
        content_type="application/json",
    )

    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert "message" in data


# ---------------------------------------------------------------------------
# Action endpoints — safety checks
# ---------------------------------------------------------------------------

def test_api_reboot_requires_confirm(flask_client, temp_config):
    """POST /api/actions/reboot without confirm returns 400."""
    res = flask_client.post("/api/actions/reboot", json={}, content_type="application/json")

    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data


def test_api_shutdown_requires_confirm(flask_client, temp_config):
    """POST /api/actions/shutdown without confirm returns 400."""
    res = flask_client.post("/api/actions/shutdown", json={}, content_type="application/json")

    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data


def test_api_reboot_with_confirm(flask_client, temp_config, monkeypatch):
    """POST /api/actions/reboot with confirm=true triggers reboot and returns ok."""
    popen_calls = []

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            popen_calls.append(cmd)

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    res = flask_client.post(
        "/api/actions/reboot",
        json={"confirm": True},
        content_type="application/json",
    )

    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert any("reboot" in str(c) for c in popen_calls)


def test_api_shutdown_with_confirm(flask_client, temp_config, monkeypatch):
    """POST /api/actions/shutdown with confirm=true triggers shutdown and returns ok."""
    popen_calls = []

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            popen_calls.append(cmd)

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    res = flask_client.post(
        "/api/actions/shutdown",
        json={"confirm": True},
        content_type="application/json",
    )

    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert any("shutdown" in str(c) for c in popen_calls)


def test_api_pairing_action(flask_client, temp_config, monkeypatch):
    """POST /api/actions/pairing returns ok."""

    def mock_check_output(cmd, **kwargs):
        return ""

    monkeypatch.setattr(subprocess, "check_output", mock_check_output)

    res = flask_client.post(
        "/api/actions/pairing",
        json={"enabled": True, "timeout_seconds": 120},
        content_type="application/json",
    )

    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True


def test_api_reconnect_bluetooth(flask_client, temp_config, monkeypatch):
    """POST /api/actions/reconnect-bluetooth returns ok."""
    popen_calls = []

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            popen_calls.append(cmd)

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    res = flask_client.post("/api/actions/reconnect-bluetooth", json={})

    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True


def test_api_rescan_pen(flask_client, temp_config):
    """POST /api/actions/rescan-pen returns ok."""
    res = flask_client.post("/api/actions/rescan-pen", json={})

    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
