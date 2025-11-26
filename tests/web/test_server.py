"""Tests for Flask web server.

Tests the Flask application factory and endpoints.
"""


def test_create_app(temp_config):
    """Test Flask application factory.
    
    Verifies that create_app returns a configured Flask application.
    """
    from ipr_keyboard.web.server import create_app
    from flask import Flask
    
    app = create_app()
    
    assert isinstance(app, Flask)


def test_health_endpoint(flask_client):
    """Test /health endpoint.
    
    Verifies that health check returns status ok.
    """
    response = flask_client.get("/health")
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"


def test_blueprints_registered(temp_config):
    """Test that blueprints are registered.
    
    Verifies that config and logs blueprints are active.
    """
    from ipr_keyboard.web.server import create_app
    
    app = create_app()
    
    # Check that blueprints are registered
    assert "config" in app.blueprints
    assert "logs" in app.blueprints


def test_config_endpoint_registered(flask_client):
    """Test that /config/ endpoint is accessible.
    
    Verifies that the config blueprint is working.
    """
    response = flask_client.get("/config/")
    
    assert response.status_code == 200


def test_logs_endpoint_registered(flask_client, temp_log_dir):
    """Test that /logs/ endpoint is accessible.
    
    Verifies that the logs blueprint is working.
    """
    response = flask_client.get("/logs/")
    
    assert response.status_code == 200


def test_404_for_unknown_route(flask_client):
    """Test that unknown routes return 404.
    
    Verifies that the application handles unknown routes.
    """
    response = flask_client.get("/unknown/route")
    
    assert response.status_code == 404
