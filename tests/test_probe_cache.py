"""The status probe does not start a D-Bus client every few seconds.

Each refresh used to run nmcli and systemctl, and each run opens a new system
D-Bus connection: ~35,000 a day on the device, from the LED loop alone.  The
probe now reuses their answers until sysfs says the WiFi link (or our
address) changed, or the answer ages out -- and asks again at once when a
person is looking: a tap that wakes the status, or a hotspot request.
"""

from __future__ import annotations

import pytest

from ipr_keyboard import gpio_monitor as gm
from ipr_keyboard.gpio_monitor import LedLogic, Phase, SystemProbe


class CountingProbe(SystemProbe):
    def __init__(self):
        super().__init__()
        self.nmcli = 0
        self.systemctl = 0
        self.link = (("wlan0", "up"),)
        self.address = "192.168.1.97"
        self.hotspot = False

    def _network_state(self):
        self.nmcli += 1
        return self.hotspot, not self.hotspot, "" if self.hotspot else "home"

    def _failed_services(self):
        self.systemctl += 1
        return ()

    def _link_state(self):
        return self.link

    def _ip_state(self):
        return self.address

    @staticmethod
    def _bt_state():
        return False

    @staticmethod
    def _mode_state():
        return False


def _run(probe, start, secs, every=gm.PROBE_INTERVAL_IDLE_SECS):
    t = start
    while t < start + secs:
        probe.refresh(now=t)
        t += every
    return t


def test_an_idle_hour_starts_a_few_hundred_clients_not_fourteen_hundred():
    probe = CountingProbe()
    _run(probe, 0.0, 3600)
    # Before: one nmcli + one systemctl per 5 s refresh = 1440 an hour.
    assert (
        probe.nmcli <= 3600 / gm.NETWORK_MAX_AGE_SECS + gm.NETWORK_SETTLE_SECS / 5 + 1
    )
    assert probe.systemctl <= 3600 / gm.SERVICES_MAX_AGE_SECS + 1
    assert probe.nmcli + probe.systemctl < 1440 / 5


def test_a_link_change_is_seen_on_the_next_refresh():
    probe = CountingProbe()
    t = _run(probe, 0.0, 120)
    assert probe.wifi_connected and not probe.hotspot_active
    probe.hotspot, probe.address = True, "10.42.0.1"  # the hotspot came up
    probe.refresh(now=t)
    assert probe.hotspot_active and not probe.wifi_connected


def test_nmcli_is_asked_again_while_a_change_settles():
    """NetworkManager may list the connection a moment after the link flips."""
    probe = CountingProbe()
    t = _run(probe, 0.0, 120)
    probe.address = ""  # link changed, NM has not caught up yet
    probe.refresh(now=t)
    probe.hotspot, probe.address = True, "10.42.0.1"
    probe.refresh(now=t + 5)
    probe.address = "10.42.0.1"
    probe.refresh(now=t + 10)  # link steady again, still in the settle window
    assert probe.hotspot_active


def test_an_unchanged_link_still_reaches_nmcli_when_the_answer_ages():
    probe = CountingProbe()
    _run(probe, 0.0, gm.NETWORK_SETTLE_SECS + 1)
    before = probe.nmcli
    probe.ssid = "stale"
    probe.refresh(now=gm.NETWORK_SETTLE_SECS + gm.NETWORK_MAX_AGE_SECS + 2)
    assert probe.nmcli == before + 1 and probe.ssid == "home"


def test_a_stopped_service_shows_within_the_service_age():
    probe = CountingProbe()
    _run(probe, 0.0, 60)
    probe._failed_services = lambda: ("bt_hid_ble.service",)
    probe.refresh(now=60 + gm.SERVICES_MAX_AGE_SECS)
    assert probe.failed_services == ("bt_hid_ble.service",) and not probe.services_ok


def test_invalidate_asks_both_again():
    probe = CountingProbe()
    _run(probe, 0.0, 120)
    n, s = probe.nmcli, probe.systemctl
    probe.invalidate()
    probe.refresh(now=121)
    assert (probe.nmcli, probe.systemctl) == (n + 1, s + 1)


class _NoActions:
    def __getattr__(self, _name):
        return lambda *a, **k: None


def _logic(probe):
    logic = LedLogic(probe, _NoActions())
    logic.set_ready()
    return logic


def test_a_tap_that_wakes_the_status_gets_fresh_answers():
    probe = CountingProbe()
    logic = _logic(probe)
    t = 0.0
    while t < 200:  # settle into IDLE on the cache
        logic.tick(t, False)
        t += 0.5
    assert logic.phase == Phase.IDLE
    n = probe.nmcli
    logic._enter_status(t)
    logic.tick(t, False)
    assert probe.nmcli == n + 1


def test_a_hotspot_request_asks_nmcli_on_every_probe():
    probe = CountingProbe()
    logic = _logic(probe)
    logic.phase = Phase.HOTSPOT_BUSY
    logic._deadline = 1e9
    n = probe.nmcli
    for i in range(5):
        logic._next_probe = 0.0
        logic._maybe_probe(1000.0 + i)
    assert probe.nmcli == n + 5


@pytest.mark.parametrize("phase", [Phase.IDLE, Phase.STATUS])
def test_ordinary_probes_use_the_cache(phase):
    probe = CountingProbe()
    probe.refresh(now=0.0)
    probe._net_changed_at = -1e9  # long settled
    logic = _logic(probe)
    logic._maybe_probe(5.0)  # set_ready() woke the status: that one is fresh
    probe._net_changed_at = -1e9
    logic.phase = phase
    n = probe.nmcli
    logic._next_probe = 0.0
    logic._maybe_probe(10.0)
    assert probe.nmcli == n
