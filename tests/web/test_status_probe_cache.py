"""The dashboard's status builds do not run bluetoothctl on every tick.

Every open dashboard rebuilds the status each StatusIntervalSeconds (SSE), and
each `bluetoothctl` run registers and drops an "Adv Monitor app" with
bluetoothd: two per build, per tab, was ~24 a minute on the device.  The
kernel's link list (sysfs) now says when a host comes or goes; bluetoothctl
is asked only then, or once a minute, and the two service checks share one
cached systemctl call.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from ipr_keyboard.web import api


@pytest.fixture
def probe(monkeypatch):
    """Fake clock, sysfs links, bluetoothctl and systemctl; counts the calls."""
    st = SimpleNamespace(now=1000.0, links=(), bluetoothctl=0, systemctl=0,
                         host="Device AA:BB:CC:DD:EE:FF MSI", active="active\nactive\n")

    def fake_run_cmd(cmd, timeout=5):
        assert cmd[0] == "bluetoothctl"
        st.bluetoothctl += 1
        return "Powered: yes\n" if cmd[1] == "show" else st.host + "\n"

    def fake_subprocess_run(cmd, **kwargs):
        assert cmd[:2] == ["systemctl", "is-active"]
        st.systemctl += 1
        return subprocess.CompletedProcess(cmd, 0, stdout=st.active, stderr="")

    monkeypatch.setattr(api.time, "monotonic", lambda: st.now)
    monkeypatch.setattr(api, "_bt_links", lambda: st.links)
    monkeypatch.setattr(api, "_run", fake_run_cmd)
    monkeypatch.setattr(api.subprocess, "run", fake_subprocess_run)
    api._reset_status_cache()
    yield st
    api._reset_status_cache()


def _tick(st, secs=5.0):
    st.now += secs
    bt = api._build_bluetooth_state()
    return bt, api._build_system_state(bt)


def test_a_steady_dashboard_asks_bluetoothctl_once_a_minute(probe):
    probe.links = ("hci0:64",)
    for _ in range(24):  # two minutes of 5 s ticks
        bt, system = _tick(probe)
        assert bt["state"] == "connected" and bt["host_name"] == "MSI"
        assert system["state"] == "healthy"
    # was 2 bluetoothctl + 3 systemctl per tick: 48 and 72
    assert probe.bluetoothctl <= 2 * 2
    assert probe.systemctl <= 12


def test_a_host_leaving_shows_on_the_next_tick(probe):
    probe.links = ("hci0:64",)
    assert _tick(probe)[0]["state"] == "connected"
    probe.links = ()  # the kernel drops the link
    bt, _ = _tick(probe, 1.0)
    assert bt["state"] == "waiting" and bt["host_name"] is None


def test_a_host_arriving_shows_on_the_next_tick_with_its_name(probe):
    assert _tick(probe)[0]["state"] == "waiting"
    probe.links = ("hci0:65",)
    bt, _ = _tick(probe, 1.0)
    assert bt["state"] == "connected" and bt["explanation"] == "Paired with MSI"


def test_a_stopped_service_shows_within_the_cache_age(probe):
    probe.links = ("hci0:64",)
    _tick(probe)
    probe.active = "inactive\nactive\n"
    bt, system = _tick(probe, api._SERVICES_MAX_AGE_SECS)
    assert bt["state"] == "error" and system["state"] == "warning"


def test_a_service_action_forgets_the_cached_answers(probe):
    _tick(probe)
    calls = probe.systemctl
    api._reset_status_cache()
    _tick(probe, 0.1)
    assert probe.systemctl == calls + 1


def test_systemctl_failing_reads_as_not_running(probe, monkeypatch):
    def boom(cmd, **kwargs):
        raise OSError("no systemctl")

    monkeypatch.setattr(api.subprocess, "run", boom)
    bt, system = _tick(probe)
    assert bt["state"] == "error" and system["state"] == "warning"


def test_the_kernel_link_list_is_read_from_sysfs(monkeypatch):
    tree = {
        "/sys/class/bluetooth": ["hci0", "rfkill0"],
        "/sys/class/bluetooth/hci0": ["power", "hci0:64", "subsystem"],
    }
    monkeypatch.setattr(api.os, "listdir", lambda path: tree[str(path).replace("\\", "/")])
    assert api._bt_links() == ("hci0:64",)


def test_no_bluetooth_in_sysfs_means_no_links(monkeypatch):
    def missing(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr(api.os, "listdir", missing)
    assert api._bt_links() == ()
