"""The magnet menu state machine (pure: no hardware, no real clock).

What matters here is that a destructive action cannot happen by accident --
the reason the timed gesture ladder was replaced at all.
"""

import pytest

from ipr_keyboard import menu as mn
from ipr_keyboard.menu import MenuLogic


class Rig:
    """Drives MenuLogic with a fake clock."""

    def __init__(self, **kw):
        self.now = 100.0
        self.hotspot = kw.pop("hotspot", False)
        self.development = kw.pop("development", False)
        self.timeout_min = kw.pop("timeout_min", 30)
        self.reveals = kw.pop("reveals", 3)
        self.logic = MenuLogic(
            hotspot_active=lambda: self.hotspot,
            development=lambda: self.development,
            display_timeout_min=lambda: self.timeout_min,
            reveals_left=lambda: self.reveals,
        )
        self.logic.enter(self.now)

    def advance(self, secs):
        self.now += secs
        self.logic.tick(self.now)

    def tap(self, n=1):
        for _ in range(n):
            self.now += 0.3
            self.logic.tap(self.now)

    def select(self):
        self.now += 1.6
        self.logic.select(self.now)

    def actions(self):
        out = []
        while True:
            a = self.logic.take_action()
            if a is None:
                return out
            out.append(a)

    @property
    def labels(self):
        return list(self.logic.view().lines)

    @property
    def current(self):
        v = self.logic.view()
        return v.lines[v.selected] if v.lines else None

    def goto(self, text):
        """Tap until the selection starts with `text`.  Bounded: a label that
        is not there fails the test instead of looping forever."""
        for _ in range(len(self.logic.items()) + 1):
            if self.current and self.current.strip().startswith(text):
                return self.current
            self.tap()
        raise AssertionError(f"{text!r} not in {[i.label for i in self.logic.items()]}")


def test_tap_moves_through_the_list_and_wraps():
    rig = Rig()
    first = rig.current
    seen = [first]
    for _ in range(len(rig.logic.items()) - 1):
        rig.tap()
        seen.append(rig.current)
    assert len(set(seen)) == len(rig.logic.items()), seen
    rig.tap()
    assert rig.current == first, "the list wraps"


def test_a_long_list_scrolls_so_the_selection_stays_visible():
    rig = Rig()
    for _ in range(len(rig.logic.items())):
        v = rig.logic.view()
        assert 0 <= v.selected < len(v.lines), v
        assert len(v.lines) <= mn.VISIBLE_LINES
        rig.tap()


def test_a_harmless_item_fires_at_once():
    rig = Rig()
    assert rig.current == "Hotspot: to on"
    rig.select()
    assert rig.actions() == ["hotspot"]


def test_the_hotspot_label_follows_the_current_state():
    assert Rig(hotspot=True).current == "Hotspot: to off"
    assert Rig(hotspot=False).current == "Hotspot: to on"


def test_a_disruptive_item_needs_one_tap():
    rig = Rig()
    rig.goto("Power")
    rig.select()
    rig.goto("Shut down")
    rig.select()
    assert rig.actions() == [], "nothing happens on selection alone"
    assert rig.logic.view().title == "CONFIRM?"
    rig.tap()
    assert rig.actions() == ["shutdown"]


def test_the_factory_reset_needs_two_taps_and_says_what_it_deletes():
    rig = Rig()
    rig.goto("Factory reset")
    rig.select()
    view = rig.logic.view()
    assert view.title == "CONFIRM?"
    assert "Wi-Fi" in view.detail[0], view.detail
    assert "2 taps" in view.detail[1]
    rig.tap()
    assert rig.actions() == [], "one tap is not enough"
    assert "1 tap" in rig.logic.view().detail[1]
    rig.tap()
    assert rig.actions() == ["reset"]


def test_a_confirmation_that_times_out_cancels():
    rig = Rig()
    rig.goto("Factory reset")
    rig.select()
    rig.advance(mn.CONFIRM_SECS + 1)
    assert rig.actions() == [], "the window closed without the action"
    assert rig.logic.view().title != "CONFIRM?"


def test_a_long_press_during_a_confirmation_cancels_it():
    rig = Rig()
    rig.goto("Power")
    rig.select()
    rig.goto("Shut down")
    rig.select()
    rig.select()
    assert rig.actions() == []
    assert rig.logic.view().title == "POWER", "cancelled, still in the submenu"


def test_the_menu_closes_when_nothing_happens():
    rig = Rig()
    rig.advance(mn.DEFAULT_INACTIVITY_SECS + 1)
    assert not rig.logic.open


def test_activity_keeps_the_menu_open():
    rig = Rig()
    for _ in range(5):
        rig.advance(mn.DEFAULT_INACTIVITY_SECS - 2)
        rig.tap()
    assert rig.logic.open


def test_the_display_submenu_marks_and_sets_the_timeout():
    rig = Rig(timeout_min=30)
    rig.goto("Display")
    rig.select()
    labels = rig.labels
    assert any(line.startswith("*") and "30 min" in line for line in labels), labels
    rig.goto("5 min")
    rig.select()
    assert rig.actions() == ["timeout:5"]
    assert rig.logic.view().title == "MENU", "returns to the root menu"


def test_the_display_submenu_has_a_way_back():
    rig = Rig()
    rig.goto("Display")
    rig.select()
    rig.goto("Back")
    rig.select()
    assert rig.logic.view().title == "MENU"
    assert rig.actions() == []


def test_recovery_needs_a_confirming_tap_and_respects_the_limit():
    rig = Rig(reveals=1)
    rig.goto("Recovery")
    rig.select()
    assert rig.actions() == [], "not shown on selection alone"
    rig.tap()
    assert rig.actions() == ["recovery"]

    rig.reveals = 0
    rig2 = Rig(reveals=0)
    rig2.goto("Recovery")
    assert "none left" in rig2.current
    rig2.select()
    assert rig2.actions() == [], "nothing is revealed once the limit is spent"


def test_a_reveal_is_dismissed_by_any_input():
    rig = Rig()
    rig.logic.show_detail(("Wi-Fi ipr-setup-abcd", "Key 0123456789"), rig.now)
    assert rig.logic.view().title == "RECOVERY"
    rig.tap()
    assert rig.logic.view().title == "MENU"


def test_shutdown_and_reset_close_the_menu():
    for label, action in (("Factory reset", "reset"),):
        rig = Rig()
        while rig.current != label:
            rig.tap()
        rig.select()
        rig.tap(2)
        assert rig.actions() == [action]
        assert not rig.logic.open


def test_exit_closes_without_doing_anything():
    rig = Rig()
    rig.goto("Exit")
    rig.select()
    assert not rig.logic.open
    assert rig.actions() == []


def test_inputs_are_ignored_when_the_menu_is_closed():
    rig = Rig()
    rig.logic.leave()
    rig.tap()
    rig.select()
    assert rig.actions() == [] and not rig.logic.open


@pytest.mark.parametrize(
    "dev,expected", [(True, "to production"), (False, "to development")]
)
def test_the_mode_item_names_the_target(dev, expected):
    rig = Rig(development=dev)
    rig.goto("Mode")
    assert expected in rig.current


def test_a_scrolling_menu_says_where_you_are():
    """Four lines fit; without a position the fourth looks like the end.

    "Menu timeout" is the fifth item of six under Display, and stayed
    invisible because nothing said the list continued.
    """
    rig = Rig()
    view = rig.logic.view()
    assert view.position == (1, len(rig.logic.items()))
    rig.tap()
    assert rig.logic.view().position == (2, len(rig.logic.items()))

    rig.goto("Display")
    rig.select()
    assert rig.logic.view().title == "DISPLAY"
    assert rig.logic.view().position == (1, 6), "four durations, Menu timeout, Back"
    assert rig.goto("Menu timeout"), "reachable by tapping"


def test_a_short_menu_has_no_position():
    rig = Rig()
    rig.goto("Power")
    rig.select()
    assert len(rig.logic.items()) <= mn.VISIBLE_LINES
    assert rig.logic.view().position is None


def test_the_menu_timeout_submenu_sets_the_value():
    rig = Rig()
    rig.goto("Display")
    rig.select()
    rig.goto("Menu timeout")
    rig.select()
    assert rig.logic.view().title == "CLOSES"
    rig.goto("2 min")
    rig.select()
    assert rig.actions() == ["menusecs:120"]
    assert rig.logic.view().title == "DISPLAY", "back to where it was chosen"
