"""End-to-end tests for the main user dashboard.

Runs against a local in-process server by default.  Set IPR_BASE_URL to test a
real device instead, e.g.:
    IPR_BASE_URL=http://192.168.1.42:8080 pytest tests/e2e/test_web_e2e.py -v

Add --e2e to require the device: missing variables and failed logins then fail
rather than skip.  See tests/e2e/conftest.py.
"""

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def test_health(base_url):
    """GET /health returns {"status": "ok"}."""
    res = requests.get(f"{base_url}/health", verify=False, timeout=10)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_login_page_reachable(base_url):
    """GET /login returns the login HTML page."""
    res = requests.get(f"{base_url}/login", verify=False, timeout=10, allow_redirects=True)
    assert res.status_code == 200
    assert b"login" in res.content.lower()


def test_api_status_unauthenticated(base_url):
    """GET /api/status without credentials returns 401."""
    res = requests.get(f"{base_url}/api/status", verify=False, timeout=10)
    assert res.status_code == 401


def test_api_status_authenticated(base_url, dashboard_session):
    """GET /api/status with a valid session returns system state."""
    res = dashboard_session.get(f"{base_url}/api/status", timeout=10)
    assert res.status_code == 200
    data = res.json()
    assert "overall" in data
    assert "bluetooth" in data
    assert "system" in data
