"""End-to-end tests for the /setup/ provisioning interface.

Runs against a local in-process server by default.  Set these to test a real
device instead, e.g.:
    IPR_SETUP_URL=http://10.42.0.1:8080 \
    IPR_SETUP_PASSWORD=<hotspot-secret> \
    pytest tests/e2e/test_setup_e2e.py -v

IPR_SETUP_URL falls back to IPR_BASE_URL when absent.
Add --e2e to require the device: missing variables and failed logins then fail
rather than skip.  See tests/e2e/conftest.py.
"""

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def test_health_reachable(setup_url):
    """GET /health is reachable from the hotspot network."""
    import requests

    res = requests.get(f"{setup_url}/health", verify=False, timeout=10)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_setup_login_page_reachable(setup_url):
    """GET /setup/login returns the login form."""
    import requests

    res = requests.get(
        f"{setup_url}/setup/login", verify=False, timeout=10, allow_redirects=True
    )
    assert res.status_code == 200
    assert b"login" in res.content.lower()


def test_setup_login_and_home(setup_url, setup_session):
    """Authenticated GET /setup/ returns the setup home page."""
    res = setup_session.get(f"{setup_url}/setup/", timeout=10)
    assert res.status_code == 200


def test_setup_wifi_page(setup_url, setup_session):
    """GET /setup/wifi returns the Wi-Fi scanner page."""
    res = setup_session.get(f"{setup_url}/setup/wifi", timeout=10)
    assert res.status_code == 200


def test_setup_status_page(setup_url, setup_session):
    """GET /setup/status returns service and Bluetooth status."""
    res = setup_session.get(f"{setup_url}/setup/status", timeout=10)
    assert res.status_code == 200


def test_setup_logs_page(setup_url, setup_session):
    """GET /setup/logs returns the journal log viewer."""
    res = setup_session.get(f"{setup_url}/setup/logs", timeout=10)
    assert res.status_code == 200
