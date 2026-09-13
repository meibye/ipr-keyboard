"""Unit tests for the LED / reed-switch state machine (no hardware needed)."""

from __future__ import annotations

import pytest

from ipr_keyboard import gpio_monitor as gm
from ipr_keyboard.gpio_monitor import (
    AMBER,
    BLUE,
    GREEN,
    OFF,
    PURPLE,
    RED,
    WHITE,
    FAST_HZ,
    SLOW_HZ,
    Frame,
    LedLogic,
    Phase,
)


class FakeProbe:
    def __init__(self, hotspot=False, wifi=True, bt=True, development=False):
        self.hotspot_active = hotspot
        self.wifi_connected = wifi
        self.bt_connected = bt
        self.development = development
        self.services_ok = True
        self.pending_mode: bool | None = None  # applied on next refresh
        self.refreshes = 0
        self.pending: bool | None = None  # hotspot state applied on next refresh

    def refresh(self):
        self.refreshes += 1
        if self.pending is not None:
            self.hotspot_active, self.pending = self.pending, None
        if self.pending_mode is not None:
            self.development, self.pending_mode = self.pending_mode, None


class FakeActions:
    def __init__(self, probe: FakeProbe, succeed=True):
        self.probe = probe
        self.succeed = succeed
        self.calls: list[str] = []

    def hotspot_start(self):
        self.calls.append("start")
        if self.succeed:
            self.probe.pending = True

    def hotspot_stop(self):
        self.calls.append("stop")
        if self.succeed:
            self.probe.pending = False

    def factory_reset(self):
        self.calls.append("reset")

    def mode_toggle(self):
        self.calls.append("mode")
        self.probe.pending_mode = not self.probe.development


class Rig:
    """Drives LedLogic with a fake clock at 20 Hz."""

    def __init__(self, probe=None, succeed=True, idle_timeout=30.0):
        self.probe = probe or FakeProbe()
        self.actions = FakeActions(self.probe, succeed)
        self.logic = LedLogic(self.probe, self.actions, idle_timeout=idle_timeout)
        self.now = 100.0
        self.reed = False
        self.frame = self.logic.tick(self.now, False)

    def advance(self, secs: float) -> Frame:
        steps = max(1, int(secs / 0.05))
        for _ in range(steps):
            self.now += 0.05
            self.frame = self.logic.tick(self.now, self.reed)
        return self.frame

    def press(self):
        self.reed = True
        return self.advance(0.05)

    def release(self):
        self.reed = False
        return self.advance(0.05)

    def tap(self):
        self.press()
        return self.release()

    def hold(self, secs: float):
        self.press()
        self.advance(secs)
        return self.release()

    def ready(self):
        self.logic.set_ready()
        return self.advance(0.05)


# ---------------------------------------------------------------------------
# Frame rendering
# ---------------------------------------------------------------------------


def test_solid_frame_is_always_on():
    f = Frame(GREEN)
    assert f.is_on(0.0) and f.is_on(0.37) and f.is_on(99.9)


def test_off_frame_is_never_on():
    assert not Frame(OFF).is_on(0.0)


def test_blink_frame_toggles_at_rate():
    f = Frame(RED, 1.0)  # 1 Hz -> 0.5 s on, 0.5 s off
    assert f.is_on(0.0)
    assert not f.is_on(0.6)
    assert f.is_on(1.1)


# ---------------------------------------------------------------------------
# Boot phase
# ---------------------------------------------------------------------------


def test_boot_blinks_white_until_ready():
    rig = Rig()
    assert rig.logic.phase == Phase.BOOT
    assert rig.frame == Frame(WHITE, FAST_HZ)
    rig.advance(60)
    assert rig.logic.phase == Phase.BOOT, "boot never times out on its own"
    rig.ready()
    assert rig.logic.phase == Phase.STATUS
    assert rig.frame == Frame(GREEN)


def test_gestures_ignored_during_boot():
    rig = Rig()
    rig.hold(4)
    assert rig.actions.calls == []
    assert rig.logic.phase == Phase.BOOT


# ---------------------------------------------------------------------------
# Status display and idle
# ---------------------------------------------------------------------------


def test_status_shown_for_idle_timeout_then_off():
    rig = Rig(idle_timeout=30)
    rig.ready()
    rig.advance(29)
    assert rig.frame == Frame(GREEN)
    rig.advance(2)
    assert rig.logic.phase == Phase.IDLE
    assert rig.frame == Frame(OFF)


def test_tap_wakes_status_from_idle():
    rig = Rig(idle_timeout=30)
    rig.ready()
    rig.advance(40)
    assert rig.frame == Frame(OFF)
    rig.tap()
    assert rig.logic.phase == Phase.STATUS
    assert rig.frame == Frame(GREEN)


@pytest.mark.parametrize(
    "wifi,bt,expected",
    [
        (True, True, Frame(GREEN)),
        (True, False, Frame(AMBER)),
        (False, False, Frame(RED, SLOW_HZ)),
        (False, True, Frame(RED, SLOW_HZ)),
    ],
)
def test_status_colours(wifi, bt, expected):
    rig = Rig(FakeProbe(wifi=wifi, bt=bt))
    rig.ready()
    assert rig.frame == expected


def test_core_service_down_shows_solid_red():
    rig = Rig()
    rig.ready()
    assert rig.frame == Frame(GREEN)
    rig.probe.services_ok = False
    rig.advance(gm.PROBE_INTERVAL_ACTIVE_SECS + 0.1)
    assert rig.frame == Frame(RED)


def test_status_refreshes_while_shown():
    rig = Rig(FakeProbe(bt=False))
    rig.ready()
    assert rig.frame == Frame(AMBER)
    rig.probe.bt_connected = True
    rig.advance(gm.PROBE_INTERVAL_ACTIVE_SECS + 0.1)
    assert rig.frame == Frame(GREEN)


def test_press_shows_status_colour_before_arming():
    rig = Rig()
    rig.ready()
    rig.advance(40)  # idle
    rig.press()
    rig.advance(1)
    assert rig.frame == Frame(GREEN)
    assert rig.logic.armed is None


def test_long_hold_does_not_time_out_status():
    rig = Rig(idle_timeout=5)
    rig.ready()
    rig.press()
    rig.advance(2.5)
    assert rig.logic.phase == Phase.STATUS
    rig.advance(4)  # beyond the 5 s deadline but still held
    assert rig.logic.phase == Phase.STATUS


# ---------------------------------------------------------------------------
# Hotspot gesture
# ---------------------------------------------------------------------------


def test_hold_3s_arms_hotspot_and_blinks_blue():
    rig = Rig()
    rig.ready()
    rig.press()
    rig.advance(3.1)
    assert rig.logic.armed == "hotspot"
    assert rig.frame == Frame(BLUE, FAST_HZ)


def test_release_after_3s_starts_hotspot_then_solid_blue():
    rig = Rig()
    rig.ready()
    rig.hold(3.5)
    assert rig.actions.calls == ["start"]
    assert rig.logic.phase == Phase.HOTSPOT_BUSY
    assert rig.frame == Frame(BLUE, FAST_HZ)
    rig.advance(gm.PROBE_INTERVAL_ACTIVE_SECS + 0.1)
    assert rig.logic.phase == Phase.HOTSPOT_ON
    assert rig.frame == Frame(BLUE)


def test_hotspot_solid_blue_never_times_out():
    rig = Rig()
    rig.ready()
    rig.hold(3.5)
    rig.advance(300)
    assert rig.logic.phase == Phase.HOTSPOT_ON
    assert rig.frame == Frame(BLUE)


def test_hold_3s_while_hotspot_on_stops_it():
    rig = Rig()
    rig.ready()
    rig.hold(3.5)
    rig.advance(5)
    assert rig.logic.phase == Phase.HOTSPOT_ON
    rig.hold(3.5)
    assert rig.actions.calls == ["start", "stop"]
    rig.advance(gm.PROBE_INTERVAL_ACTIVE_SECS + 0.1)
    assert rig.logic.phase == Phase.STATUS
    assert rig.frame == Frame(GREEN)


def test_hotspot_failure_flashes_red_then_status():
    rig = Rig(succeed=False)
    rig.ready()
    rig.hold(3.5)
    rig.advance(gm.HOTSPOT_REQUEST_TIMEOUT_SECS + 0.2)
    assert rig.logic.phase == Phase.FAIL_FLASH
    assert rig.frame == Frame(RED, FAST_HZ)
    rig.advance(gm.FAIL_FLASH_SECS + 0.2)
    assert rig.logic.phase == Phase.STATUS


def test_hotspot_started_elsewhere_is_shown_blue():
    """Hotspot brought up by the boot marker / CLI, not by the magnet."""
    rig = Rig()
    rig.ready()
    rig.advance(40)  # idle, LED off
    rig.probe.hotspot_active = True
    rig.advance(gm.PROBE_INTERVAL_IDLE_SECS + 0.1)
    assert rig.logic.phase == Phase.HOTSPOT_ON
    assert rig.frame == Frame(BLUE)
    rig.probe.hotspot_active = False
    rig.advance(gm.PROBE_INTERVAL_IDLE_SECS + 0.1)
    assert rig.logic.phase == Phase.STATUS


def test_tap_while_hotspot_on_keeps_blue():
    rig = Rig()
    rig.ready()
    rig.hold(3.5)
    rig.advance(5)
    rig.tap()
    assert rig.logic.phase == Phase.HOTSPOT_ON
    assert rig.frame == Frame(BLUE)


def test_repeated_hold_during_busy_is_ignored():
    rig = Rig(succeed=False)
    rig.ready()
    rig.hold(3.5)
    rig.hold(3.5)
    assert rig.actions.calls == ["start"]


# ---------------------------------------------------------------------------
# Mode toggle gesture (6 s) and development heartbeat
# ---------------------------------------------------------------------------


def test_hold_6s_arms_mode_and_blinks_purple():
    rig = Rig()
    rig.ready()
    rig.press()
    rig.advance(3.5)
    assert rig.frame == Frame(BLUE, FAST_HZ)
    rig.advance(3)
    assert rig.logic.armed == "mode"
    assert rig.frame == Frame(PURPLE, FAST_HZ)


def test_release_after_6s_toggles_mode_and_confirms_purple():
    rig = Rig()
    rig.ready()
    rig.hold(6.5)
    assert rig.actions.calls == ["mode"]
    assert rig.logic.phase == Phase.MODE_CONFIRM
    assert rig.frame == Frame(PURPLE)
    rig.advance(gm.MODE_CONFIRM_SECS + 0.2)
    assert rig.logic.phase == Phase.STATUS
    assert rig.probe.development is True
    rig.hold(6.5)
    rig.advance(gm.MODE_CONFIRM_SECS + 0.2)
    assert rig.probe.development is False


def test_hold_between_3_and_6s_still_toggles_hotspot_not_mode():
    rig = Rig()
    rig.ready()
    rig.hold(5.0)
    assert rig.actions.calls == ["start"]


def test_dev_blip_only_in_development_mode():
    rig = Rig(FakeProbe(development=False))
    rig.ready()
    assert not any(rig.logic.dev_blip(100.0 + k * 0.05) for k in range(200))
    rig.probe.development = True
    ons = [rig.logic.dev_blip(t / 100) for t in range(0, int(gm.DEV_BLIP_PERIOD_SECS * 100))]
    assert any(ons) and not all(ons)
    assert ons[0] and not ons[int(gm.DEV_BLIP_ON_SECS * 100) + 2]


def test_dev_blip_suppressed_while_booting_or_arming():
    rig = Rig(FakeProbe(development=True))
    assert not rig.logic.dev_blip(100.0)  # BOOT
    rig.ready()
    assert rig.logic.dev_blip(100.0)
    rig.press()
    rig.advance(3.5)  # armed: hotspot
    assert not rig.logic.dev_blip(rig.now - rig.now % gm.DEV_BLIP_PERIOD_SECS)


# ---------------------------------------------------------------------------
# Factory reset gesture
# ---------------------------------------------------------------------------


def test_hold_10s_arms_reset_and_blinks_red():
    rig = Rig()
    rig.ready()
    rig.press()
    rig.advance(3.5)
    assert rig.frame == Frame(BLUE, FAST_HZ)
    rig.advance(3)
    assert rig.frame == Frame(PURPLE, FAST_HZ)
    rig.advance(4)
    assert rig.logic.armed == "reset"
    assert rig.frame == Frame(RED, FAST_HZ)


def test_release_after_10s_triggers_reset_and_stays_red():
    rig = Rig()
    rig.ready()
    rig.hold(10.5)
    assert rig.actions.calls == ["reset"]
    assert rig.logic.phase == Phase.RESETTING
    rig.advance(30)
    assert rig.frame == Frame(RED, FAST_HZ)
    rig.hold(3.5)
    assert rig.actions.calls == ["reset"], "nothing else fires while resetting"


# ---------------------------------------------------------------------------
# Probe cadence
# ---------------------------------------------------------------------------


def test_idle_probes_slowly():
    rig = Rig()
    rig.ready()
    rig.advance(40)
    before = rig.probe.refreshes
    rig.advance(gm.PROBE_INTERVAL_IDLE_SECS * 4)
    assert 3 <= rig.probe.refreshes - before <= 5


def test_probe_exception_does_not_break_loop():
    class BadProbe(FakeProbe):
        def refresh(self):
            raise RuntimeError("nmcli missing")

    rig = Rig(BadProbe())
    rig.ready()
    rig.advance(10)
    assert rig.frame == Frame(GREEN)


# ---------------------------------------------------------------------------
# GpioMonitor thread with a fake backend
# ---------------------------------------------------------------------------


class FakeBackend:
    def __init__(self):
        self.closed = False
        self.colors: list[tuple[int, int, int]] = []
        self.cleaned = False

    def setup(self):
        pass

    def reed_closed(self):
        return self.closed

    def led(self, color):
        self.colors.append(color)

    def cleanup(self):
        self.cleaned = True


def test_monitor_thread_renders_boot_blink_and_stops_cleanly():
    import time

    backend = FakeBackend()
    probe = FakeProbe()
    mon = gm.GpioMonitor(probe=probe, actions=FakeActions(probe), backend=backend)
    mon.TICK_SECS = 0.005
    mon.start()
    assert mon.active
    time.sleep(0.3)
    assert WHITE in backend.colors and OFF in backend.colors, "white blink rendered"
    mon.set_ready()
    time.sleep(0.1)
    assert mon.phase == Phase.STATUS
    assert backend.colors[-1] == GREEN
    mon.stop()
    assert backend.cleaned


def test_monitor_without_gpio_is_inert(monkeypatch):
    monkeypatch.setattr(gm, "_GPIO_AVAILABLE", False)
    mon = gm.GpioMonitor()
    mon.start()
    assert not mon.active
    mon.stop()  # must not raise
