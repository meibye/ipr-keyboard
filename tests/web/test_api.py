"""Tests for the /api/ dashboard Blueprint.

Covers all endpoints defined in docs/ui/api-contract.md.
"""

import subprocess


# ---------------------------------------------------------------------------
# /api/status* endpoints
# ---------------------------------------------------------------------------

def test_api_status_structure(flask_client, temp_config, monkeypatch):
    """GET /api/status returns all required top-level fields."""
    def mock_call(cmd, **kwargs):
        return 1

    def mock_check_output(cmd, text=True, stderr=None, **kwargs):
        if "bluetoothctl" in cmd:
            return ""
        return ""

    monkeypatch.setattr(subprocess, "call", mock_call)
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)

    r = flask_client.get("/api/status")
    assert r.status_code == 200
    d = r.get_json()
    for key in ("timestamp", "overall", "bluetooth", "pen", "transmission", "system"):
        assert key in d, f"Missing key: {key}"


def test_api_status_bluetooth_connected(flask_client, temp_config, monkeypatch):
    """GET /api/status detects a connected Bluetooth device."""
    call_count = [0]

    def mock_call(cmd, **kwargs):
        return 1

    def mock_check_output(cmd, text=True, stderr=None, **kwargs):
        if "bluetoothctl" in cmd:
            if "devices" in cmd:
                return "Device AA:BB:CC:DD:EE:FF Office-PC"
            if "info" in cmd:
                return "Connected: yes\nName: Office-PC"
        return ""

    monkeypatch.setattr(subprocess, "call", mock_call)
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)

    r = flask_client.get("/api/status")
    assert r.status_code == 200
    d = r.get_json()
    assert d["bluetooth"]["state"] == "connected"
    assert d["bluetooth"]["host_name"] == "Office-PC"


def test_api_status_bluetooth_waiting(flask_client, temp_config, monkeypatch):
    """GET /api/status shows waiting when no device is connected."""
    def mock_check_output(cmd, text=True, stderr=None, **kwargs):
        if "bluetoothctl" in cmd:
            return ""
        return ""

    def mock_call(cmd, **kwargs):
        return 1

    monkeypatch.setattr(subprocess, "call", mock_call)
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)

    r = flask_client.get("/api/status")
    d = r.get_json()
    assert d["bluetooth"]["state"] == "waiting"


def test_api_status_bluetooth(flask_client, temp_config, monkeypatch):
    """GET /api/status/bluetooth returns Bluetooth sub-state."""
    monkeypatch.setattr(subprocess, "call", lambda cmd, **kw: 1)
    monkeypatch.setattr(subprocess, "check_output", lambda cmd, **kw: "")

    r = flask_client.get("/api/status/bluetooth")
    assert r.status_code == 200
    d = r.get_json()
    assert "state" in d
    assert "label" in d
    assert "timestamp" in d


def test_api_status_pen_missing(flask_client, temp_config, tmp_path, monkeypatch):
    """GET /api/status/pen returns missing when pen folder does not exist."""
    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: tmp_path / "config.json",
    )
    from ipr_keyboard.utils.helpers import save_json
    save_json(tmp_path / "config.json", {
        "IrisPenFolder": str(tmp_path / "nonexistent_pen"),
    })
    from ipr_keyboard.config.manager import ConfigManager
    ConfigManager._instance = None

    r = flask_client.get("/api/status/pen")
    assert r.status_code == 200
    d = r.get_json()
    assert d["state"] == "missing"


def test_api_status_pen_ready(flask_client, temp_config, tmp_path, monkeypatch):
    """GET /api/status/pen returns ready when pen folder has files."""
    pen_dir = tmp_path / "pen"
    pen_dir.mkdir()
    (pen_dir / "scan.txt").write_text("hello")

    from ipr_keyboard.utils.helpers import save_json
    save_json(tmp_path / "config.json", {"IrisPenFolder": str(pen_dir)})
    from ipr_keyboard.config.manager import ConfigManager
    ConfigManager._instance = None
    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: tmp_path / "config.json",
    )
    ConfigManager._instance = None

    r = flask_client.get("/api/status/pen")
    assert r.status_code == 200
    d = r.get_json()
    assert d["state"] == "ready"


def test_api_status_transmission(flask_client, temp_config):
    """GET /api/status/transmission returns idle state."""
    r = flask_client.get("/api/status/transmission")
    assert r.status_code == 200
    d = r.get_json()
    assert d["state"] == "idle"
    assert "progress_percent" in d
    assert "items_sent" in d


def test_api_status_system(flask_client, temp_config, monkeypatch):
    """GET /api/status/system returns a system state."""
    monkeypatch.setattr(subprocess, "call", lambda cmd, **kw: 1)

    r = flask_client.get("/api/status/system")
    assert r.status_code == 200
    d = r.get_json()
    assert "state" in d
    assert "label" in d


# ---------------------------------------------------------------------------
# /api/events endpoints
# ---------------------------------------------------------------------------

def test_api_events_empty(flask_client, temp_config):
    """GET /api/events returns empty list when no events exist."""
    from ipr_keyboard.web import api as api_mod
    api_mod._EVENTS.clear()
    api_mod._EVENT_COUNTER = 0

    r = flask_client.get("/api/events")
    assert r.status_code == 200
    d = r.get_json()
    assert d["items"] == []


def test_api_events_filter_by_category(flask_client, temp_config):
    """GET /api/events?category=bluetooth returns only bluetooth events."""
    from ipr_keyboard.web import api as api_mod
    api_mod._EVENTS.clear()
    api_mod._add_event("bluetooth", "info", "BT connected")
    api_mod._add_event("pen", "info", "Pen ready")
    api_mod._add_event("bluetooth", "warning", "BT reconnecting")

    r = flask_client.get("/api/events?category=bluetooth")
    d = r.get_json()
    assert all(e["category"] == "bluetooth" for e in d["items"])
    assert len(d["items"]) == 2


def test_api_events_limit(flask_client, temp_config):
    """GET /api/events?limit=1 returns at most 1 event."""
    from ipr_keyboard.web import api as api_mod
    api_mod._EVENTS.clear()
    for i in range(5):
        api_mod._add_event("system", "info", f"Event {i}")

    r = flask_client.get("/api/events?limit=1")
    d = r.get_json()
    assert len(d["items"]) == 1


def test_api_events_latest_no_events(flask_client, temp_config):
    """GET /api/events/latest returns null when no events."""
    from ipr_keyboard.web import api as api_mod
    api_mod._EVENTS.clear()

    r = flask_client.get("/api/events/latest")
    assert r.status_code == 200
    assert r.get_json() is None


def test_api_events_latest_returns_last(flask_client, temp_config):
    """GET /api/events/latest returns most recent event."""
    from ipr_keyboard.web import api as api_mod
    api_mod._EVENTS.clear()
    api_mod._add_event("pen", "info", "Pen attached")
    api_mod._add_event("bluetooth", "info", "BT connected")

    r = flask_client.get("/api/events/latest")
    d = r.get_json()
    assert d["summary"] == "BT connected"
    assert d["category"] == "bluetooth"


# ---------------------------------------------------------------------------
# /api/config endpoints
# ---------------------------------------------------------------------------

def test_api_config_get(flask_client, temp_config):
    """GET /api/config returns configuration shape."""
    r = flask_client.get("/api/config")
    assert r.status_code == 200
    d = r.get_json()
    assert "iris_pen_folder" in d
    assert "bluetooth" in d
    assert "pen" in d
    assert "diagnostics" in d


def test_api_config_post(flask_client, temp_config):
    """POST /api/config updates configuration."""
    r = flask_client.post(
        "/api/config",
        json={"iris_pen_folder": "/tmp/test-pen"},
        content_type="application/json",
    )
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True


def test_api_config_post_empty(flask_client, temp_config):
    """POST /api/config with no fields still returns ok."""
    r = flask_client.post("/api/config", json={}, content_type="application/json")
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True


# ---------------------------------------------------------------------------
# /api/actions endpoints
# ---------------------------------------------------------------------------

def test_api_action_pairing(flask_client, temp_config, monkeypatch):
    """POST /api/actions/pairing starts pairing mode."""
    calls = []

    def fake_popen(cmd):
        calls.append(cmd)
        return None

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    r = flask_client.post(
        "/api/actions/pairing",
        json={"enabled": True},
        content_type="application/json",
    )
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True


def test_api_action_rescan_pen(flask_client, temp_config):
    """POST /api/actions/rescan-pen returns ok."""
    r = flask_client.post("/api/actions/rescan-pen", json={}, content_type="application/json")
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True


def test_api_action_reconnect_bluetooth(flask_client, temp_config, monkeypatch):
    """POST /api/actions/reconnect-bluetooth returns ok."""
    monkeypatch.setattr(subprocess, "Popen", lambda cmd: None)

    r = flask_client.post(
        "/api/actions/reconnect-bluetooth",
        json={},
        content_type="application/json",
    )
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True


def test_api_action_reboot_requires_confirm(flask_client, temp_config):
    """POST /api/actions/reboot without confirm=true returns 400."""
    r = flask_client.post(
        "/api/actions/reboot",
        json={},
        content_type="application/json",
    )
    assert r.status_code == 400
    d = r.get_json()
    assert d["error"]["code"] == "confirmation_required"


def test_api_action_reboot_with_confirm(flask_client, temp_config, monkeypatch):
    """POST /api/actions/reboot with confirm=true triggers reboot."""
    monkeypatch.setattr(subprocess, "Popen", lambda cmd: None)

    r = flask_client.post(
        "/api/actions/reboot",
        json={"confirm": True},
        content_type="application/json",
    )
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True


def test_api_action_shutdown_requires_confirm(flask_client, temp_config):
    """POST /api/actions/shutdown without confirm=true returns 400."""
    r = flask_client.post(
        "/api/actions/shutdown",
        json={},
        content_type="application/json",
    )
    assert r.status_code == 400
    d = r.get_json()
    assert d["error"]["code"] == "confirmation_required"


def test_api_action_shutdown_with_confirm(flask_client, temp_config, monkeypatch):
    """POST /api/actions/shutdown with confirm=true triggers shutdown."""
    monkeypatch.setattr(subprocess, "Popen", lambda cmd: None)

    r = flask_client.post(
        "/api/actions/shutdown",
        json={"confirm": True},
        content_type="application/json",
    )
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True


# ---------------------------------------------------------------------------
# /api/logs/raw endpoint
# ---------------------------------------------------------------------------

def test_api_logs_raw(flask_client, temp_config, monkeypatch):
    """GET /api/logs/raw returns items list."""
    monkeypatch.setattr(
        subprocess, "check_output",
        lambda cmd, text=True, stderr=None, timeout=None, **kw: "2026-04-17 line one\n2026-04-17 line two\n",
    )
    r = flask_client.get("/api/logs/raw?limit=10")
    assert r.status_code == 200
    d = r.get_json()
    assert "items" in d
    assert len(d["items"]) == 2


def test_api_logs_raw_contains_filter(flask_client, temp_config, monkeypatch):
    """GET /api/logs/raw?contains= filters lines."""
    monkeypatch.setattr(
        subprocess, "check_output",
        lambda cmd, text=True, stderr=None, timeout=None, **kw: "ERROR: something bad\nINFO: all good\n",
    )
    r = flask_client.get("/api/logs/raw?contains=ERROR")
    assert r.status_code == 200
    d = r.get_json()
    assert len(d["items"]) == 1
    assert "ERROR" in d["items"][0]["line"]


# ---------------------------------------------------------------------------
# Dashboard HTML root
# ---------------------------------------------------------------------------

def test_dashboard_root(flask_client):
    """GET / serves the dashboard HTML page."""
    r = flask_client.get("/")
    assert r.status_code == 200
    assert b"IPR Pen Bridge" in r.data
