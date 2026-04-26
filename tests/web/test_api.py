"""Tests for /api/ endpoints defined in docs/ui/api-contract.md."""

import io
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


# ---------------------------------------------------------------------------
# Debug endpoints
# ---------------------------------------------------------------------------

def test_debug_services_lists_all_six(flask_client, temp_config, monkeypatch):
    """GET /api/debug/services returns all 6 services."""
    monkeypatch.setattr(subprocess, "call", lambda cmd, **kw: 0)

    res = flask_client.get("/api/debug/services")

    assert res.status_code == 200
    data = res.get_json()
    assert "services" in data
    assert len(data["services"]) == 6
    for svc in data["services"]:
        assert "name" in svc
        assert "label" in svc
        assert "description" in svc
        assert "active" in svc


def test_debug_services_reflects_inactive(flask_client, temp_config, monkeypatch):
    """GET /api/debug/services marks bt_hid_ble inactive when systemctl returns 1."""
    def mock_call(cmd, **kw):
        if "bt_hid_ble" in " ".join(cmd):
            return 1
        return 0

    monkeypatch.setattr(subprocess, "call", mock_call)

    res = flask_client.get("/api/debug/services")

    assert res.status_code == 200
    data = res.get_json()
    by_name = {s["name"]: s for s in data["services"]}
    assert by_name["bt_hid_ble"]["active"] is False
    assert by_name["bluetooth"]["active"] is True


def test_debug_service_action_start(flask_client, temp_config, monkeypatch):
    """POST /api/debug/services/bt_hid_ble/start calls systemctl start."""
    run_calls = []

    class FakeResult:
        returncode = 0
        stderr = ""

    def fake_run(cmd, **kw):
        run_calls.append(cmd)
        return FakeResult()

    monkeypatch.setattr(subprocess, "run", fake_run)

    res = flask_client.post("/api/debug/services/bt_hid_ble/start")

    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert any("start" in str(c) and "bt_hid_ble" in str(c) for c in run_calls)


def test_debug_service_action_rejects_unknown_service(flask_client, temp_config):
    """POST /api/debug/services/<unknown>/restart returns 400."""
    res = flask_client.post("/api/debug/services/evil-service/restart")

    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data


def test_debug_service_action_rejects_unknown_action(flask_client, temp_config):
    """POST /api/debug/services/bluetooth/<unknown-action> returns 400."""
    res = flask_client.post("/api/debug/services/bluetooth/nuke")

    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data


def test_debug_send_text_success(flask_client, temp_config, monkeypatch):
    """POST /api/debug/send-text sends text via bt_kb_send."""
    run_calls = []

    class FakeResult:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, **kw):
        run_calls.append(cmd)
        return FakeResult()

    monkeypatch.setattr(subprocess, "run", fake_run)

    res = flask_client.post(
        "/api/debug/send-text",
        json={"text": "hello"},
        content_type="application/json",
    )

    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert any("hello" in " ".join(c) for c in run_calls)


def test_debug_send_text_empty_rejected(flask_client, temp_config):
    """POST /api/debug/send-text with empty text returns 400."""
    res = flask_client.post(
        "/api/debug/send-text",
        json={"text": ""},
        content_type="application/json",
    )

    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data


def test_debug_send_text_failure_propagates(flask_client, temp_config, monkeypatch):
    """POST /api/debug/send-text returns ok=False when helper fails."""
    def fake_run(cmd, **kw):
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd, stderr="FIFO not ready")

    monkeypatch.setattr(subprocess, "run", fake_run)

    res = flask_client.post(
        "/api/debug/send-text",
        json={"text": "x"},
        content_type="application/json",
    )

    assert res.status_code == 500
    data = res.get_json()
    assert data["ok"] is False


def test_debug_send_file_success(flask_client, temp_config, monkeypatch, tmp_path):
    """POST /api/debug/send-file sends file via bt_kb_send_file."""
    run_calls = []

    class FakeResult:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, **kw):
        run_calls.append(cmd)
        return FakeResult()

    monkeypatch.setattr(subprocess, "run", fake_run)

    content = b"Hello from file"
    res = flask_client.post(
        "/api/debug/send-file",
        data={"file": (io.BytesIO(content), "test.txt")},
        content_type="multipart/form-data",
    )

    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert any("--file" in str(c) for c in run_calls)


def test_debug_pen_files_empty(flask_client, temp_config, monkeypatch, tmp_path):
    """GET /api/debug/pen-files returns empty list for empty folder."""
    from ipr_keyboard.config.manager import ConfigManager
    pen_dir = tmp_path / "pen"
    pen_dir.mkdir()
    ConfigManager.instance().update(IrisPenFolder=str(pen_dir))

    res = flask_client.get("/api/debug/pen-files")

    assert res.status_code == 200
    data = res.get_json()
    assert data["files"] == []
    assert str(pen_dir) in data["folder"]


def test_debug_pen_files_lists_files(flask_client, temp_config, monkeypatch, tmp_path):
    """GET /api/debug/pen-files lists files with content."""
    from ipr_keyboard.config.manager import ConfigManager
    pen_dir = tmp_path / "pen"
    pen_dir.mkdir()
    (pen_dir / "note.txt").write_text("Hello pen", encoding="utf-8")
    ConfigManager.instance().update(IrisPenFolder=str(pen_dir))

    res = flask_client.get("/api/debug/pen-files")

    assert res.status_code == 200
    data = res.get_json()
    assert len(data["files"]) == 1
    f = data["files"][0]
    assert f["name"] == "note.txt"
    assert "Hello pen" in f["content"]
    assert "size_bytes" in f
    assert "modified_at" in f


def test_debug_pen_files_content_cap(flask_client, temp_config, monkeypatch, tmp_path):
    """GET /api/debug/pen-files truncates content to 8 KB."""
    from ipr_keyboard.config.manager import ConfigManager
    pen_dir = tmp_path / "pen"
    pen_dir.mkdir()
    large = "x" * 20000
    (pen_dir / "big.txt").write_text(large, encoding="utf-8")
    ConfigManager.instance().update(IrisPenFolder=str(pen_dir))

    res = flask_client.get("/api/debug/pen-files")

    assert res.status_code == 200
    data = res.get_json()
    assert len(data["files"]) == 1
    f = data["files"][0]
    assert len(f["content"]) <= 8192
    assert f["truncated"] is True


def test_debug_requires_auth(temp_config):
    """GET /api/debug/services returns 401 for unauthenticated requests."""
    from ipr_keyboard.web.server import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        res = client.get("/api/debug/services")
    assert res.status_code == 401
