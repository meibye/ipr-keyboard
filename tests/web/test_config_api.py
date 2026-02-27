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


def test_get_config(flask_client):
    """Test GET /config/ returns configuration.
    
    Verifies that configuration values are returned as JSON.
    """
    response = flask_client.get("/config/")
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Check required fields exist
    assert "IrisPenFolder" in data
    assert "DeleteFiles" in data
    assert "Logging" in data
    assert "MaxFileSize" in data
    assert "LogPort" in data


def test_update_config(flask_client):
    """Test POST /config/ updates configuration.
    
    Verifies that configuration can be updated via POST.
    """
    response = flask_client.post("/config/", json={
        "DeleteFiles": False,
        "MaxFileSize": 5000
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["DeleteFiles"] is False
    assert data["MaxFileSize"] == 5000


def test_update_config_partial(flask_client):
    """Test that partial updates only change specified fields.
    
    Verifies that unspecified fields retain their values.
    """
    # Get initial config
    initial = flask_client.get("/config/").get_json()
    original_folder = initial["IrisPenFolder"]
    
    # Update only one field
    flask_client.post("/config/", json={"DeleteFiles": False})
    
    # Verify other fields unchanged
    updated = flask_client.get("/config/").get_json()
    assert updated["IrisPenFolder"] == original_folder
    assert updated["DeleteFiles"] is False


def test_update_config_invalid_keys(flask_client):
    """Test that invalid keys are ignored.
    
    Verifies that unknown keys don't cause errors.
    """
    response = flask_client.post("/config/", json={
        "UnknownKey": "value",
        "DeleteFiles": False
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert "UnknownKey" not in data
    assert data["DeleteFiles"] is False


def test_update_config_empty_body(flask_client):
    """Test POST with empty body.
    
    Verifies that empty updates don't cause errors.
    """
    response = flask_client.post("/config/", json={})
    
    assert response.status_code == 200


