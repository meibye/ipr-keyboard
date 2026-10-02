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

    def shutdown(self):
        self.calls.append("shutdown")


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


def test_press_blinks_white_then_goes_dark_before_arming():
    rig = Rig()
    rig.ready()
    rig.advance(40)  # idle
    rig.press()
    assert rig.frame == Frame(WHITE), "magnet registered"
    seen = {rig.frame}
    for _ in range(int(gm.ACK_BLINK_SECS / 0.05)):
        seen.add(rig.advance(0.05))
    assert seen == {Frame(WHITE), Frame(OFF)}, "the blink toggles"
    rig.advance(1)
    assert rig.frame == Frame(OFF), "dark after the acknowledgement"
    assert rig.logic.armed is None
    rig.release()
    assert rig.frame == Frame(GREEN)


def test_ack_blink_pattern_starts_lit_and_toggles():
    assert gm.ack_frame(0.0) == Frame(WHITE)
    assert gm.ack_frame(gm.ACK_BLINK_HALF_SECS + 0.01) == Frame(OFF)
    assert gm.ack_frame(2 * gm.ACK_BLINK_HALF_SECS + 0.01) == Frame(WHITE)


def test_press_while_hotspot_on_goes_dark_so_blue_blink_is_visible():
    rig = Rig(FakeProbe(hotspot=True))
    rig.ready()
    assert rig.frame == Frame(BLUE)
    rig.press()
    rig.advance(1)  # past the acknowledgement blink
    assert rig.frame == Frame(OFF)
    rig.advance(2.5)
    assert rig.frame == Frame(BLUE)


def test_phase_change_shows_a_dark_gap():
    rig = Rig()
    rig.ready()
    rig.press()
    rig.advance(3.05)  # ~3.1 s held: just past the threshold, inside the gap
    assert rig.frame == Frame(OFF)
    rig.advance(0.5)
    assert rig.frame == Frame(BLUE)
    rig.advance(2.6)  # ~6.2 s held: shutdown phase, gap again
    assert rig.frame == Frame(OFF)
    rig.advance(0.5)
    assert rig.frame == Frame(WHITE)


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
    rig.advance(3.5)
    assert rig.logic.armed == "hotspot"
    assert rig.frame == Frame(BLUE), "steady colour while held"


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


def test_hold_10s_arms_mode_and_blinks_purple():
    rig = Rig()
    rig.ready()
    rig.press()
    rig.advance(3.5)
    assert rig.frame == Frame(BLUE)
    rig.advance(3)
    assert rig.frame == Frame(WHITE)
    rig.advance(4)
    assert rig.logic.armed == "mode"
    assert rig.frame == Frame(PURPLE)


def test_release_after_10s_toggles_mode_and_confirms_purple():
    rig = Rig()
    rig.ready()
    rig.hold(10.5)
    assert rig.actions.calls == ["mode"]
    assert rig.logic.phase == Phase.MODE_CONFIRM
    assert rig.frame == Frame(PURPLE)
    rig.advance(gm.MODE_CONFIRM_SECS + 0.2)
    assert rig.logic.phase == Phase.STATUS
    assert rig.probe.development is True
    rig.hold(10.5)
    rig.advance(gm.MODE_CONFIRM_SECS + 0.2)
    assert rig.probe.development is False


def test_hold_between_3_and_6s_still_toggles_hotspot():
    rig = Rig()
    rig.ready()
    rig.hold(5.0)
    assert rig.actions.calls == ["start"]


def test_hold_6s_arms_shutdown_white_and_release_powers_off():
    rig = Rig()
    rig.ready()
    rig.press()
    rig.advance(6.5)
    assert rig.logic.armed == "shutdown"
    assert rig.frame == Frame(WHITE)
    rig.release()
    assert rig.actions.calls == ["shutdown"]
    assert rig.logic.phase == Phase.SHUTTING_DOWN
    assert rig.frame == Frame(WHITE)
    rig.advance(30)
    assert rig.frame == Frame(WHITE), "stays white until the OS halts"
    rig.hold(3.5)
    assert rig.actions.calls == ["shutdown"], "no gestures while shutting down"


def test_hold_20s_cancels_everything():
    rig = Rig()
    rig.ready()
    rig.press()
    rig.advance(15.5)
    assert rig.frame == Frame(RED)
    rig.advance(5)
    assert rig.logic.armed == "cancel"
    assert rig.frame == Frame(OFF)
    rig.release()
    assert rig.actions.calls == []
    assert rig.logic.phase == Phase.STATUS


def test_development_mode_never_blinks_the_led():
    """The mode is shown on the OLED badge; the LED has no blink for it."""
    rig = Rig(FakeProbe(development=True))
    rig.ready()
    frames = {rig.advance(0.05) for _ in range(400)}  # 20 s of idle status
    assert frames == {Frame(GREEN)}, "no periodic blip on top of the status"
    assert not hasattr(rig.logic, "dev_blip")


# ---------------------------------------------------------------------------
# Factory reset gesture
# ---------------------------------------------------------------------------


def test_hold_15s_arms_reset_and_blinks_red():
    rig = Rig()
    rig.ready()
    rig.press()
    rig.advance(3.5)
    assert rig.frame == Frame(BLUE)
    rig.advance(3)
    assert rig.frame == Frame(WHITE)
    rig.advance(4)
    assert rig.frame == Frame(PURPLE)
    rig.advance(5)
    assert rig.logic.armed == "reset"
    assert rig.frame == Frame(RED)


def test_release_after_15s_triggers_reset_and_stays_red():
    rig = Rig()
    rig.ready()
    rig.hold(15.5)
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


def test_monitor_stop_keeps_cyan_while_shutting_down():
    import time

    backend = FakeBackend()
    probe = FakeProbe()
    actions = FakeActions(probe)
    mon = gm.GpioMonitor(probe=probe, actions=actions, backend=backend)
    mon.TICK_SECS = 0.005
    mon.start()
    mon.set_ready()
    time.sleep(0.05)
    backend.closed = True
    time.sleep(0.05)
    mon._logic._press_start -= 7.0  # pretend the magnet was held 7 s
    time.sleep(0.05)
    backend.closed = False
    time.sleep(0.05)
    assert actions.calls == ["shutdown"]
    mon.stop()
    assert not backend.cleaned
    assert backend.colors[-1] == WHITE


def test_monitor_without_gpio_is_inert(monkeypatch):
    monkeypatch.setattr(gm, "_GPIO_AVAILABLE", False)
    mon = gm.GpioMonitor()
    mon.start()
    assert not mon.active
    mon.stop()  # must not raise


# ---------------------------------------------------------------------------
# The magnet menu (only where a display can show it)
# ---------------------------------------------------------------------------


def _menu_rig(**probe_kw):
    """A rig whose LedLogic has a menu, as on a device with a working panel."""
    from ipr_keyboard.menu import MenuLogic

    rig = Rig(FakeProbe(**probe_kw))
    timeouts = []
    menu = MenuLogic(
        hotspot_active=lambda: rig.probe.hotspot_active,
        development=lambda: rig.probe.development,
        display_timeout_min=lambda: 30,
        reveals_left=lambda: 3,
    )
    rig.logic._menu = menu
    rig.logic._on_display_timeout = timeouts.append
    rig.logic._recovery_info = lambda: ("Wi-Fi ipr-setup-abcd", "Key 0123456789")
    rig.menu = menu
    rig.timeouts = timeouts
    rig.ready()
    return rig


def _menu_tap(rig):
    rig.press()
    rig.advance(0.3)
    rig.release()


def _menu_select(rig):
    rig.press()
    rig.advance(2.0)
    rig.release()


def test_a_three_second_hold_opens_the_menu_instead_of_arming_the_ladder():
    rig = _menu_rig()
    rig.press()
    rig.advance(3.5)
    assert rig.logic.armed == "menu", "the ladder is not used when a menu exists"
    rig.release()
    assert rig.logic.phase == Phase.MENU and rig.menu.open
    assert rig.frame == Frame(BLUE), "steady blue says: in a menu"


def test_the_ladder_still_works_without_a_display():
    rig = Rig()  # no menu wired: the panel-less case
    rig.ready()
    rig.press()
    rig.advance(3.5)
    assert rig.logic.armed == "hotspot"
    rig.advance(3)
    assert rig.logic.armed == "shutdown"


def test_taps_move_and_a_long_press_activates():
    rig = _menu_rig()
    rig.press()
    rig.advance(3.5)
    rig.release()
    assert rig.menu.view().lines[rig.menu.view().selected] == "Hotspot on"
    _menu_select(rig)
    assert rig.logic.phase == Phase.HOTSPOT_BUSY
    assert rig.actions.calls == ["start"]


def test_the_menu_can_set_the_display_timeout():
    rig = _menu_rig()
    rig.press()
    rig.advance(3.5)
    rig.release()
    while rig.menu.view().lines[rig.menu.view().selected] != "Display":
        _menu_tap(rig)
    _menu_select(rig)
    while "5 min" not in rig.menu.view().lines[rig.menu.view().selected]:
        _menu_tap(rig)
    _menu_select(rig)
    assert rig.timeouts == [5]


def test_a_factory_reset_from_the_menu_needs_two_taps():
    rig = _menu_rig()
    rig.press()
    rig.advance(3.5)
    rig.release()
    while rig.menu.view().lines[rig.menu.view().selected] != "Factory reset":
        _menu_tap(rig)
    _menu_select(rig)
    assert rig.actions.calls == [], "selection alone does nothing"
    _menu_tap(rig)
    assert rig.actions.calls == [], "one tap is not enough"
    _menu_tap(rig)
    assert rig.actions.calls == ["reset"]
    assert rig.logic.phase == Phase.RESETTING


def test_recovery_info_reaches_the_panel_only_after_a_confirming_tap():
    rig = _menu_rig()
    rig.press()
    rig.advance(3.5)
    rig.release()
    while not rig.menu.view().lines[rig.menu.view().selected].startswith("Recovery"):
        _menu_tap(rig)
    _menu_select(rig)
    assert rig.menu.view().title == "CONFIRM?"
    _menu_tap(rig)
    view = rig.menu.view()
    assert view.title == "RECOVERY" and "ipr-setup-abcd" in view.detail[0]


def test_the_menu_closes_itself_and_the_led_returns_to_status():
    rig = _menu_rig()
    rig.press()
    rig.advance(3.5)
    rig.release()
    rig.advance(25)
    assert not rig.menu.open
    assert rig.logic.phase == Phase.STATUS


def test_the_snapshot_carries_the_menu_for_the_display():
    rig = _menu_rig()
    assert rig.logic.snapshot(rig.now).menu is None
    rig.press()
    rig.advance(3.5)
    rig.release()
    assert rig.logic.snapshot(rig.now).menu is not None
