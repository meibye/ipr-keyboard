"""OledManager on-policy and redraw behaviour — fake display, source and clock."""

import time

import pytest

from ipr_keyboard.gpio_monitor import LedSnapshot, Phase
from ipr_keyboard.oled import manager as mg


class FakeDisplay:
    def __init__(self):
        self.calls: list = []
        self.frames = 0

    def setup(self):
        self.calls.append("setup")

    def show(self, image):
        self.frames += 1
        self.calls.append(("show", image))

    def sleep(self):
        self.calls.append("sleep")

    def wake(self):
        self.calls.append("wake")

    def contrast(self, v):
        self.calls.append(("contrast", v))

    def close(self):
        self.calls.append("close")


class FakeRenderer:
    """No Pillow: returns the Screen itself as the 'image'."""

    def __init__(self, rolling=False):
        self.rolling = rolling
        self.resets = 0

    def render(self, screen, now):
        return screen, self.rolling

    def reset(self):
        self.resets += 1


class FakeSource:
    def __init__(self, **kw):
        self.state = dict(
            phase=Phase.STATUS,
            armed=None,
            held_secs=0.0,
            ready=True,
            hotspot_active=False,
            wifi_connected=True,
            bt_connected=False,
            development=False,
            services_ok=True,
            failed_services=(),
            ssid="Net",
            ip="10.0.0.2",
        )
        self.state.update(kw)

    def set(self, **kw):
        self.state.update(kw)

    def snapshot(self):
        return LedSnapshot(**self.state)


class Rig:
    def __init__(self, rolling=False, **source_kw):
        self.now = 100.0
        self.display = FakeDisplay()
        self.renderer = FakeRenderer(rolling)
        self.source = FakeSource(**source_kw)
        self.pen = "ready"
        self.tx = dict(
            state="idle", chars=0, items_sent=0, explanation="", last_success_at=None
        )
        self.host_calls = 0
        self.ssid_calls = 0

        def bt_host():
            self.host_calls += 1
            return "Laptop"

        def hotspot_ssid():
            self.ssid_calls += 1
            return "ipr-setup-abcd"

        self.mgr = mg.OledManager(
            idle_seconds=30,
            send_hold_seconds=10,
            source=self.source,
            display=self.display,
            renderer=self.renderer,
            clock=lambda: self.now,
            pen=lambda: self.pen,
            tx=lambda: dict(self.tx),
            bt_host=bt_host,
            hotspot_ssid=hotspot_ssid,
        )
        self.mgr._awake = True  # as after start()
        self.mgr._on_since = self.now

    def tick(self, dt=0.25):
        self.now += dt
        return self.mgr._tick(self.now)

    def run(self, seconds):
        for _ in range(int(seconds / 0.25)):
            self.tick()

    @property
    def screen(self):
        shows = [
            c for c in self.display.calls if isinstance(c, tuple) and c[0] == "show"
        ]
        return shows[-1][1] if shows else None


def test_draws_once_and_only_redraws_on_change():
    rig = Rig()
    rig.tick()
    assert rig.display.frames == 1 and rig.screen.header == "READY"
    rig.run(2)
    assert rig.display.frames == 1
    rig.pen = "missing"
    rig.tick()
    assert rig.display.frames == 2 and rig.screen.lines[1].text == "Plug in the pen"


def test_sleeps_when_led_goes_idle_and_wakes_on_tap():
    rig = Rig()
    rig.tick()
    rig.source.set(phase=Phase.IDLE)
    rig.tick()
    assert rig.display.calls[-1] == "sleep"
    assert rig.renderer.resets == 1
    rig.run(5)
    assert rig.display.calls.count("sleep") == 1  # not repeated
    rig.source.set(phase=Phase.STATUS)  # magnet tap
    rig.tick()
    assert rig.display.calls[-2] == "wake" and rig.screen.header == "READY"


def test_status_change_wakes_idle_panel_for_the_idle_window():
    rig = Rig()
    rig.tick()
    rig.source.set(phase=Phase.IDLE)
    rig.tick()
    assert rig.display.calls[-1] == "sleep"
    rig.source.set(bt_connected=True)  # PC connects
    rig.tick()
    assert "wake" in rig.display.calls and rig.screen.lines[0].text == "Laptop"
    rig.run(29)
    assert rig.display.calls[-1] != "sleep"
    rig.run(2)
    assert rig.display.calls[-1] == "sleep"


def test_gesture_screen_while_held():
    rig = Rig()
    rig.tick()
    rig.source.set(phase=Phase.IDLE)
    rig.tick()
    rig.source.set(held_secs=4.0, armed="hotspot")
    rig.tick()
    assert rig.screen.header == "RELEASE → HOTSPOT"


def test_send_shows_sending_then_sent_for_hold_then_status():
    rig = Rig(bt_connected=True)
    rig.tick()
    assert rig.host_calls == 1  # fetched once on the connected edge
    rig.source.set(phase=Phase.IDLE)
    rig.tick()
    rig.tx.update(state="sending", chars=42)
    rig.tick()
    assert (
        rig.screen.header == "SENDING…" and rig.screen.lines[1].text == "42 characters"
    )
    rig.tx.update(state="success", items_sent=1, last_success_at=1.0)
    rig.tick()
    assert rig.screen.header == "SENT ✓"
    rig.run(9)
    assert rig.screen.header == "SENT ✓" and rig.display.calls[-1] != "sleep"
    rig.run(2)
    assert rig.display.calls[-1] == "sleep"
    rig.source.set(phase=Phase.STATUS)  # tap later: status, not the old SENT
    rig.tick()
    assert rig.screen.header == "READY"
    assert rig.host_calls == 1


def test_failed_send_is_shown():
    rig = Rig()
    rig.tick()
    rig.tx.update(state="failed", explanation="Helper timed out")
    rig.tick()
    assert (
        rig.screen.header == "SEND FAILED"
        and rig.screen.lines[0].text == "Helper timed out"
    )


def test_hotspot_screen_reads_ssid_once_and_stays_on():
    rig = Rig()
    rig.tick()
    rig.source.set(phase=Phase.HOTSPOT_ON, hotspot_active=True)
    rig.run(60)
    assert rig.ssid_calls == 1
    assert (
        rig.screen.header == "SETUP MODE"
        and "ipr-setup-abcd" in rig.screen.lines[0].text
    )
    assert "sleep" not in rig.display.calls


def test_dims_after_five_minutes_on_and_restores_on_next_wake():
    rig = Rig()
    rig.tick()
    rig.source.set(phase=Phase.HOTSPOT_ON, hotspot_active=True)
    rig.run(mg.LOW_CONTRAST_AFTER_SECS + 2)
    assert ("contrast", 128 // mg.LOW_CONTRAST_DIVISOR) in rig.display.calls
    rig.source.set(phase=Phase.IDLE, hotspot_active=False)
    rig.run(31)  # the hotspot going down is a status change: idle window first
    assert rig.display.calls[-1] == "sleep"
    rig.source.set(phase=Phase.STATUS)
    rig.tick()
    assert rig.display.calls[-3:-1] == [("contrast", 128), "wake"]


def test_rolling_line_requests_faster_ticks_and_redraws():
    rig = Rig(rolling=True)
    assert rig.tick() is True
    rig.tick()
    rig.tick()
    assert rig.display.frames == 3  # redrawn although the screen did not change


def test_stop_blanks_panel_except_during_shutdown():
    rig = Rig()
    rig.mgr.stop()
    assert rig.display.calls[-2:] == ["sleep", "close"]

    rig = Rig(phase=Phase.SHUTTING_DOWN)
    rig.mgr.stop()
    assert "sleep" not in rig.display.calls and rig.display.calls[-1] == "close"


def test_start_is_inert_when_disabled_or_pil_missing(monkeypatch, caplog):
    m = mg.OledManager(enabled=False)
    m.start()
    assert not m.active

    monkeypatch.setattr(mg, "pil_available", lambda: False)
    m = mg.OledManager()
    m.start()
    assert not m.active
    assert mg.LOG_DISABLED in caplog.text


def test_start_is_inert_without_device_node(monkeypatch):
    monkeypatch.setattr(mg, "pil_available", lambda: True)
    monkeypatch.setattr(mg.os.path, "exists", lambda p: False)
    m = mg.OledManager(renderer=FakeRenderer())
    m.start()
    assert not m.active


def test_start_is_inert_when_nothing_answers(monkeypatch):
    monkeypatch.setattr(mg, "pil_available", lambda: True)
    monkeypatch.setattr(mg.os.path, "exists", lambda p: True)
    monkeypatch.setattr(mg, "probe", lambda bus, addr: False)
    m = mg.OledManager(renderer=FakeRenderer())
    m.start()
    assert not m.active


def test_thread_runs_with_fake_display_and_stops():
    display = FakeDisplay()
    m = mg.OledManager(
        source=FakeSource(),
        display=display,
        renderer=FakeRenderer(),
        pen=lambda: "ready",
        tx=lambda: {"state": "idle"},
        bt_host=lambda: "",
        hotspot_ssid=lambda: "",
    )
    m.start()
    assert m.active and display.calls[0] == "setup"
    deadline = time.monotonic() + 2
    while display.frames == 0 and time.monotonic() < deadline:
        time.sleep(0.02)
    assert display.frames >= 1
    m.stop()
    assert display.calls[-1] == "close"


def test_standalone_source_boot_status_idle():
    now = [0.0]
    probe = type(
        "P",
        (),
        {
            "hotspot_active": False,
            "wifi_connected": True,
            "bt_connected": False,
            "development": False,
        },
    )()
    probe.refresh = lambda: None
    src = mg.StandaloneSource(idle_seconds=30, probe=probe, clock=lambda: now[0])
    assert src.snapshot().phase == Phase.BOOT
    src.set_ready()
    assert src.snapshot().phase == Phase.STATUS and src.snapshot().ready
    now[0] = 31.0
    assert src.snapshot().phase == Phase.IDLE
    assert src.snapshot().wifi_connected


def test_set_ready_forwards_to_standalone_source_only():
    src = FakeSource(phase=Phase.BOOT)
    m = mg.OledManager(source=src, display=FakeDisplay(), renderer=FakeRenderer())
    m.set_ready()  # no-op for a GpioMonitor-like source
    assert src.snapshot().phase == Phase.BOOT


@pytest.mark.parametrize("phase", [Phase.BOOT, Phase.STATUS, Phase.RESETTING])
def test_phase_enum_maps_to_screen_names(phase):
    rig = Rig(phase=phase)
    rig.tick()
    assert rig.screen is not None
    expected = {
        Phase.BOOT: "STARTING…",
        Phase.STATUS: "READY",
        Phase.RESETTING: "RESETTING…",
    }[phase]
    assert rig.screen.header == expected
