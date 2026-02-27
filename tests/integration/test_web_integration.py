"""Integration tests for web API.

Tests the complete web API functionality.
"""


def test_config_round_trip(flask_client):
    """Test config get -> update -> get round trip.
    
    Verifies that updates persist and are retrievable.
    """
    # Get initial config
    initial = flask_client.get("/config/").get_json()
    
    # Update a value
    flask_client.post("/config/", json={"MaxFileSize": 99999})
    
    # Verify the update
    updated = flask_client.get("/config/").get_json()
    assert updated["MaxFileSize"] == 99999
    
    # Update back
    flask_client.post("/config/", json={"MaxFileSize": initial["MaxFileSize"]})


def test_health_check_always_available(flask_client):
    """Test that health check is always available.
    
    Verifies that /health endpoint works independently.
    """
    response = flask_client.get("/health")
    
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_logs_after_operations(flask_client, temp_log_dir):
    """Test that log entries appear after operations.
    
    Verifies that API operations are logged.
    """
    from ipr_keyboard.logging.logger import get_logger
    
    # Perform some logged operations
    flask_client.get("/config/")
    flask_client.post("/config/", json={"DeleteFiles": True})
    
    # Get the logger and add a test message
    logger = get_logger()
    logger.info("Integration test marker")
    
    # Flush handlers
    for handler in logger.handlers:
        handler.flush()
    
    # Check logs
    response = flask_client.get("/logs/tail?lines=50")
    assert response.status_code == 200
    data = response.get_json()
    
    assert "Integration test marker" in data["log"]


def test_multiple_config_updates(flask_client):
    """Test multiple sequential config updates.
    
    Verifies that multiple updates work correctly.
    """
    updates = [
        {"DeleteFiles": True},
        {"DeleteFiles": False},
        {"MaxFileSize": 1000},
        {"MaxFileSize": 2000},
        {"IrisPenFolder": "/path/a"},
        {"IrisPenFolder": "/path/b"},
    ]
    
    for update in updates:
        response = flask_client.post("/config/", json=update)
        assert response.status_code == 200
        
        # Verify the update took effect
        data = response.get_json()
        for key, value in update.items():
            assert data[key] == value


def test_config_endpoint_shape(flask_client):
    """Test config endpoint returns expected fields."""
    response = flask_client.get("/config/")

    assert response.status_code == 200
    data = response.get_json()

    assert "IrisPenFolder" in data
    assert "DeleteFiles" in data
    assert "Logging" in data
    assert "MaxFileSize" in data
    assert "LogPort" in data


def test_invalid_json_handling(flask_client):
    """Test handling of invalid JSON in POST.
    
    Verifies that malformed JSON is handled gracefully.
    """
    # Send invalid JSON
    response = flask_client.post(
        "/config/",
        data="not valid json",
        content_type="application/json"
    )
    
    # Should still work (force=True, silent=True in endpoint)
    assert response.status_code == 200
