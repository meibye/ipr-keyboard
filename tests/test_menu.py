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
    assert rig.current == "Hotspot on"
    rig.select()
    assert rig.actions() == ["hotspot"]


def test_the_hotspot_label_follows_the_current_state():
    assert Rig(hotspot=True).current == "Hotspot off"
    assert Rig(hotspot=False).current == "Hotspot on"


def test_a_disruptive_item_needs_one_tap():
    rig = Rig()
    while rig.current != "Shutdown":
        rig.tap()
    rig.select()
    assert rig.actions() == [], "nothing happens on selection alone"
    assert rig.logic.view().title == "CONFIRM?"
    rig.tap()
    assert rig.actions() == ["shutdown"]


def test_the_factory_reset_needs_two_taps_and_says_what_it_deletes():
    rig = Rig()
    while rig.current != "Factory reset":
        rig.tap()
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
    while rig.current != "Factory reset":
        rig.tap()
    rig.select()
    rig.advance(mn.CONFIRM_SECS + 1)
    assert rig.actions() == [], "the window closed without the action"
    assert rig.logic.view().title != "CONFIRM?"


def test_a_long_press_during_a_confirmation_cancels_it():
    rig = Rig()
    while rig.current != "Shutdown":
        rig.tap()
    rig.select()
    rig.select()
    assert rig.actions() == []
    assert rig.logic.view().title == "MENU"


def test_the_menu_closes_when_nothing_happens():
    rig = Rig()
    rig.advance(mn.INACTIVITY_SECS + 1)
    assert not rig.logic.open


def test_activity_keeps_the_menu_open():
    rig = Rig()
    for _ in range(5):
        rig.advance(mn.INACTIVITY_SECS - 2)
        rig.tap()
    assert rig.logic.open


def test_the_display_submenu_marks_and_sets_the_timeout():
    rig = Rig(timeout_min=30)
    while rig.current != "Display":
        rig.tap()
    rig.select()
    labels = rig.labels
    assert any(line.startswith("*") and "30 min" in line for line in labels), labels
    while "5 min" not in rig.current:
        rig.tap()
    rig.select()
    assert rig.actions() == ["timeout:5"]
    assert rig.logic.view().title == "MENU", "returns to the root menu"


def test_the_display_submenu_has_a_way_back():
    rig = Rig()
    while rig.current != "Display":
        rig.tap()
    rig.select()
    while rig.current != "Back":
        rig.tap()
    rig.select()
    assert rig.logic.view().title == "MENU"
    assert rig.actions() == []


def test_recovery_needs_a_confirming_tap_and_respects_the_limit():
    rig = Rig(reveals=1)
    while not rig.current.startswith("Recovery"):
        rig.tap()
    rig.select()
    assert rig.actions() == [], "not shown on selection alone"
    rig.tap()
    assert rig.actions() == ["recovery"]

    rig.reveals = 0
    rig2 = Rig(reveals=0)
    while not rig2.current.startswith("Recovery"):
        rig2.tap()
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
    for label, action in (("Shutdown", "shutdown"), ("Factory reset", "reset")):
        rig = Rig()
        while rig.current != label:
            rig.tap()
        rig.select()
        rig.tap(2)
        assert rig.actions() == [action]
        assert not rig.logic.open


def test_exit_closes_without_doing_anything():
    rig = Rig()
    while rig.current != "Exit":
        rig.tap()
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
    while not rig.current.startswith("Mode"):
        rig.tap()
    assert expected in rig.current
