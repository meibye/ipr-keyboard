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


def test_run_cmd_success(temp_config, monkeypatch):
    """Test _run_cmd helper with successful command."""
    from ipr_keyboard.web.server import _run_cmd
    import subprocess
    
    def mock_check_output(cmd, text, stderr):
        return "command output"
    
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    
    result = _run_cmd(["echo", "test"])
    assert result == "command output"


def test_run_cmd_failure(temp_config, monkeypatch):
    """Test _run_cmd helper with failing command."""
    from ipr_keyboard.web.server import _run_cmd
    import subprocess
    
    def mock_check_output(cmd, text, stderr):
        raise subprocess.CalledProcessError(1, cmd, output="error")
    
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    
    result = _run_cmd(["bad", "command"])
    assert "ERROR" in result


def test_service_status_active(temp_config, monkeypatch):
    """Test _service_status helper with active service."""
    from ipr_keyboard.web.server import _service_status
    import subprocess
    
    def mock_call(cmd):
        if cmd == ["systemctl", "is-active", "--quiet", "test.service"]:
            return 0  # active
        return 1
    
    monkeypatch.setattr(subprocess, "call", mock_call)
    
    result = _service_status("test.service")
    assert result == "active"


def test_service_status_enabled_not_active(temp_config, monkeypatch):
    """Test _service_status helper with enabled but not active service."""
    from ipr_keyboard.web.server import _service_status
    import subprocess
    
    call_count = [0]
    
    def mock_call(cmd):
        call_count[0] += 1
        if call_count[0] == 1:  # First call: is-active
            return 1  # not active
        elif call_count[0] == 2:  # Second call: is-enabled
            return 0  # enabled
        return 1
    
    monkeypatch.setattr(subprocess, "call", mock_call)
    
    result = _service_status("test.service")
    assert result == "enabled-not-active"


def test_service_status_inactive(temp_config, monkeypatch):
    """Test _service_status helper with inactive service."""
    from ipr_keyboard.web.server import _service_status
    import subprocess
    
    def mock_call(cmd):
        return 1  # not active, not enabled
    
    monkeypatch.setattr(subprocess, "call", mock_call)
    
    result = _service_status("test.service")
    assert result == "inactive"


def test_service_status_exception(temp_config, monkeypatch):
    """Test _service_status helper with exception."""
    from ipr_keyboard.web.server import _service_status
    import subprocess
    
    def mock_call(cmd):
        raise OSError("Command not found")
    
    monkeypatch.setattr(subprocess, "call", mock_call)
    
    result = _service_status("test.service")
    assert result == "unknown"


def test_status_endpoint(flask_client, temp_config, monkeypatch):
    """Test /status endpoint.
    
    Verifies that status endpoint returns system information.
    """
    import subprocess
    
    # Mock subprocess calls for systemctl and bluetoothctl
    def mock_call(cmd):
        return 1  # inactive services
    
    def mock_check_output(cmd, text=True, stderr=None):
        if "bluetoothctl" in cmd:
            if "devices" in cmd:
                return "Device AA:BB:CC:DD:EE:FF TestDevice"
            elif "info" in cmd:
                return "Connected: yes"
            else:
                return "Adapter info"
        return ""
    
    monkeypatch.setattr(subprocess, "call", mock_call)
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    
    response = flask_client.get("/status")
    
    assert response.status_code == 200
    data = response.get_json()
    assert "env" in data
    assert "config" in data
    assert "log" in data
    assert "services" in data
    assert "bluetooth" in data


def test_status_endpoint_bluetooth_error(flask_client, temp_config, monkeypatch):
    """Test /status endpoint when bluetoothctl fails.
    
    Verifies that status endpoint handles bluetooth errors gracefully.
    """
    import subprocess
    
    # Mock subprocess calls
    def mock_call(cmd):
        return 1  # inactive services
    
    def mock_check_output(cmd, text=True, stderr=None):
        if "bluetoothctl" in cmd:
            if "devices" in cmd:
                raise subprocess.CalledProcessError(1, cmd)
        return "mock output"
    
    monkeypatch.setattr(subprocess, "call", mock_call)
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    
    response = flask_client.get("/status")
    
    assert response.status_code == 200
    data = response.get_json()
    assert "bluetooth" in data
    assert "devices" in data["bluetooth"]
    # Should contain error info
    assert len(data["bluetooth"]["devices"]) > 0
