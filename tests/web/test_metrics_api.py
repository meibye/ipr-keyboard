"""Tests for /api/metrics and the diagnostics.metrics_enabled config switch."""
from __future__ import annotations

import pytest

from ipr_keyboard import metrics
from ipr_keyboard.config.manager import ConfigManager


@pytest.fixture(autouse=True)
def _clean_metrics():
    metrics.reset()
    metrics.set_enabled(False)
    yield
    metrics.reset()
    metrics.set_enabled(False)


# ---------------------------------------------------------------------------
# /api/metrics
# ---------------------------------------------------------------------------

def test_metrics_disabled_by_default(flask_client, temp_config):
    r = flask_client.get("/api/metrics")
    assert r.status_code == 200
    data = r.get_json()
    assert data["enabled"] is False
    assert set(data["kpis"]) == set(metrics.KPIS)
    assert "platform" in data and "boot" in data


def test_metrics_reflects_saved_config(flask_client, temp_config):
    ConfigManager.instance().update(MetricsEnabled=True)
    r = flask_client.get("/api/metrics")
    assert r.get_json()["enabled"] is True


def test_metrics_returns_recorded_stats(flask_client, temp_config):
    ConfigManager.instance().update(MetricsEnabled=True)
    metrics.set_enabled(True)
    for v in (5.0, 15.0, 25.0):
        metrics.record("e2e_latency_ms", v)
    data = flask_client.get("/api/metrics").get_json()
    st = data["kpis"]["e2e_latency_ms"]
    assert st["count"] == 3
    assert st["p50"] == 15.0
    assert st["unit"] == "ms"
    assert st["description"]


def test_metrics_requires_login(temp_config, monkeypatch, tmp_path):
    """Same rule as every other /api endpoint."""
    from ipr_keyboard.web import auth as auth_module
    from ipr_keyboard.web.server import create_app
    monkeypatch.setattr(auth_module, "users_path", lambda: tmp_path / "users.json")
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        r = c.get("/api/metrics")
        assert r.status_code in (401, 302)


def test_metrics_reset_clears(flask_client, temp_config):
    metrics.set_enabled(True)
    metrics.record("send_ms", 1.0)
    r = flask_client.post("/api/metrics/reset")
    assert r.status_code == 200 and r.get_json()["ok"] is True
    assert metrics.snapshot()["kpis"]["send_ms"]["count"] == 0


# ---------------------------------------------------------------------------
# Config switch round-trip
# ---------------------------------------------------------------------------

def test_config_exposes_metrics_enabled(flask_client, temp_config):
    data = flask_client.get("/api/config").get_json()
    assert data["diagnostics"]["metrics_enabled"] is False


def test_config_post_enables_metrics(flask_client, temp_config):
    r = flask_client.post("/api/config", json={"diagnostics": {"metrics_enabled": True}})
    assert r.status_code == 200
    assert ConfigManager.instance().get().MetricsEnabled is True
    assert metrics.is_enabled() is True   # applied at once in the web process
    assert flask_client.get("/api/config").get_json()["diagnostics"]["metrics_enabled"] is True


def test_config_post_disables_metrics(flask_client, temp_config):
    flask_client.post("/api/config", json={"diagnostics": {"metrics_enabled": True}})
    r = flask_client.post("/api/config", json={"diagnostics": {"metrics_enabled": False}})
    assert r.status_code == 200
    assert ConfigManager.instance().get().MetricsEnabled is False
    assert metrics.is_enabled() is False


def test_config_post_rejects_non_boolean(flask_client, temp_config):
    r = flask_client.post("/api/config", json={"diagnostics": {"metrics_enabled": "yes"}})
    assert r.status_code == 400
    assert r.get_json()["error"]["code"] == "validation_error"
    assert ConfigManager.instance().get().MetricsEnabled is False


def test_config_default_and_persistence(temp_config):
    """New field defaults False and survives a save/reload cycle."""
    mgr = ConfigManager.instance()
    assert mgr.get().MetricsEnabled is False
    mgr.update(MetricsEnabled=True)
    ConfigManager._instance = None  # force a fresh load from disk
    assert ConfigManager.instance().get().MetricsEnabled is True
