"""Fixtures for end-to-end tests against a live device.

Tests are skipped automatically when the required environment variables are absent.

Environment variables:
  IPR_BASE_URL          Base URL of the device's web server, e.g. http://192.168.1.42:8080
  IPR_SETUP_URL         Base URL when connected to the hotspot, e.g. http://10.42.0.1:8080
                        Falls back to IPR_BASE_URL when absent.
  IPR_PASSWORD          Password for the main dashboard admin user (default: "admin")
  IPR_SETUP_PASSWORD    Password for the setup interface (hotspot secret)
"""

import os

import pytest
import requests


def _require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        pytest.skip(f"E2E test skipped: {name} not set")
    return value


@pytest.fixture(scope="session")
def base_url() -> str:
    return _require_env("IPR_BASE_URL").rstrip("/")


@pytest.fixture(scope="session")
def setup_url() -> str:
    url = os.environ.get("IPR_SETUP_URL", os.environ.get("IPR_BASE_URL", "")).rstrip("/")
    if not url:
        pytest.skip("E2E test skipped: IPR_SETUP_URL (or IPR_BASE_URL) not set")
    return url


@pytest.fixture(scope="session")
def dashboard_session(base_url) -> requests.Session:
    """Authenticated requests.Session for the main dashboard."""
    password = os.environ.get("IPR_PASSWORD", "admin")
    sess = requests.Session()
    sess.verify = False  # self-signed cert on device
    res = sess.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": password},
        timeout=10,
    )
    if res.status_code != 200:
        pytest.skip(f"E2E dashboard login failed ({res.status_code}) — check IPR_PASSWORD")
    return sess


@pytest.fixture(scope="session")
def setup_session(setup_url) -> requests.Session:
    """Authenticated requests.Session for the setup interface."""
    password = _require_env("IPR_SETUP_PASSWORD")
    sess = requests.Session()
    sess.verify = False
    res = sess.post(
        f"{setup_url}/setup/login",
        data={"username": "ipr", "password": password},
        allow_redirects=True,
        timeout=10,
    )
    if res.status_code not in (200, 302):
        pytest.skip(f"E2E setup login failed ({res.status_code}) — check IPR_SETUP_PASSWORD")
    return sess
