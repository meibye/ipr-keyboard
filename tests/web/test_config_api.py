"""Tests for configuration API endpoints.

Tests the Flask web API for viewing and updating configuration.
"""
from ipr_keyboard.web.server import create_app
from ipr_keyboard.config.manager import ConfigManager


def test_config_api(monkeypatch, tmp_path):
    """Test configuration GET and POST endpoints.
    
    Verifies that the /config/ endpoints correctly retrieve and update
    configuration values.
    """
    from ipr_keyboard.utils.helpers import save_json

    cfg_file = tmp_path / "config.json"
    save_json(cfg_file, {"IrisPenFolder": "/tmp/usb"})

    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: cfg_file,
    )
    # re-init instance
    ConfigManager._instance = None  # type: ignore[attr-defined]
    ConfigManager.instance()

    app = create_app()
    client = app.test_client()

    res = client.get("/config/")
    assert res.status_code == 200
    data = res.get_json()
    assert data["IrisPenFolder"] == "/tmp/usb"

    res2 = client.post("/config/", json={"DeleteFiles": False})
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert data2["DeleteFiles"] is False
