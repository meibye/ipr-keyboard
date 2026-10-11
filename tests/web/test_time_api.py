"""Settings > Date and time: read the device's clock, correct it, set its zone.

The device has no battery-backed clock.  With internet, systemd-timesyncd
keeps it right; without (on the hotspot) it can come up wrong after being
off, and before this the only way to correct it was a shell.
"""

from __future__ import annotations

import subprocess

import pytest

from ipr_keyboard.web import api


@pytest.fixture
def device(monkeypatch):
    """Fake timedatectl answers and the root helper; records helper calls."""
    calls: list[list[str]] = []
    state = {"synced": "yes", "helper_rc": 0, "helper_err": ""}

    def fake_run_cmd(cmd, timeout=5):
        if cmd[:2] == ["timedatectl", "show"]:
            return f"Timezone=Europe/Copenhagen\nNTP=yes\nNTPSynchronized={state['synced']}\n"
        if cmd[:2] == ["timedatectl", "show-timesync"]:
            return "0.debian.pool.ntp.org\n"
        if cmd[:2] == ["timedatectl", "list-timezones"]:
            return "America/New_York\nEurope/Copenhagen\nUTC\n"
        raise AssertionError(cmd)

    def fake_subprocess_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(
            cmd, state["helper_rc"], stdout="", stderr=state["helper_err"]
        )

    monkeypatch.setattr(api, "_run", fake_run_cmd)
    monkeypatch.setattr(api.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(api, "_time_zones", [])
    return calls, state


def test_the_time_state_says_whether_the_clock_is_set_from_the_internet(
    flask_client, device
):
    d = flask_client.get("/api/time").get_json()
    assert d["time_zone"] == "Europe/Copenhagen"
    assert d["ntp_enabled"] is True and d["synchronized"] is True
    assert d["time_server"] == "0.debian.pool.ntp.org"
    assert isinstance(d["device_epoch"], float)


def test_not_yet_synchronised_reads_as_such(flask_client, device):
    device[1]["synced"] = "no"
    assert flask_client.get("/api/time").get_json()["synchronized"] is False


def test_the_zone_list_comes_from_the_device(flask_client, device):
    assert flask_client.get("/api/time/zones").get_json()["items"] == [
        "America/New_York",
        "Europe/Copenhagen",
        "UTC",
    ]


def test_sync_goes_through_the_root_helper(flask_client, device):
    res = flask_client.post("/api/time", json={"action": "sync"})
    assert res.status_code == 200 and res.get_json()["ok"] is True
    assert device[0] == [["sudo", "-n", api._HOTSPOT_CTL, "time", "sync"]]


def test_set_sends_whole_utc_seconds(flask_client, device):
    res = flask_client.post(
        "/api/time", json={"action": "set", "epoch": 1791722192.731}
    )
    assert res.status_code == 200
    assert device[0] == [["sudo", "-n", api._HOTSPOT_CTL, "time", "set", "1791722192"]]


@pytest.mark.parametrize("epoch", [None, "soon", 0, 1600000000, 5000000000])
def test_an_implausible_time_is_refused_before_the_helper(flask_client, device, epoch):
    res = flask_client.post("/api/time", json={"action": "set", "epoch": epoch})
    assert res.status_code == 400 and device[0] == []


def test_zone_must_be_one_the_device_knows(flask_client, device):
    assert (
        flask_client.post(
            "/api/time", json={"action": "zone", "zone": "Mars/Base"}
        ).status_code
        == 400
    )
    assert (
        flask_client.post(
            "/api/time", json={"action": "zone", "zone": "; rm -rf /"}
        ).status_code
        == 400
    )
    assert device[0] == []
    res = flask_client.post("/api/time", json={"action": "zone", "zone": "UTC"})
    assert res.status_code == 200
    assert device[0] == [["sudo", "-n", api._HOTSPOT_CTL, "time", "zone", "UTC"]]


def test_a_failing_helper_says_why(flask_client, device):
    device[1].update(helper_rc=1, helper_err="No time server answered within 15 s.")
    res = flask_client.post("/api/time", json={"action": "sync"})
    assert res.status_code == 500
    assert res.get_json()["message"] == "No time server answered within 15 s."


def test_an_unknown_action_is_refused(flask_client, device):
    assert flask_client.post("/api/time", json={"action": "reset"}).status_code == 400


def test_changing_the_time_needs_an_admin(flask_client, device):
    with flask_client.session_transaction() as sess:
        sess["is_admin"] = False
    assert flask_client.post("/api/time", json={"action": "sync"}).status_code == 403
    assert flask_client.get("/api/time").status_code == 200  # reading is fine
