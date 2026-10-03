"""The magnet menu — a pure state machine, no hardware and no clock of its own.

The magnet is the device's only control.  It used to select actions by how long
it was held; a factory reset was triggered that way by accident, so the
duration ladder is replaced by a list the user steps through and confirms.
See docs/architecture/magnet-menu-design.md.

Inputs are the two things a reed switch can say: tap() (a short press) and
select() (a long one).  Time is always passed in, so tests drive it with a
fake clock.  Nothing here touches the display or the GPIO: the OLED reads
view() and the owner acts on what take_action() returns.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

DEFAULT_INACTIVITY_SECS = 20.0  # leave the menu when nothing happens
CONFIRM_SECS = 10.0  # window for the confirming tap(s)
VISIBLE_LINES = 4  # the panel's compact layout

# Display timeouts offered by the Display submenu, in minutes.
TIMEOUT_CHOICES = (5, 15, 30, 60)
# How long the menu waits before closing itself, in seconds.
MENU_TIMEOUT_CHOICES = (20, 60, 120, 300)


@dataclass(frozen=True)
class Item:
    """One line of a menu.

    confirm is the number of taps the user must give after activating it;
    0 means the action fires immediately.
    """

    key: str
    label: str
    confirm: int = 0
    submenu: str | None = None


@dataclass(frozen=True)
class MenuView:
    """What the display should draw.  Pure data, like screens.Screen."""

    title: str
    lines: tuple[str, ...]
    selected: int  # index within lines
    detail: tuple[str, ...] = ()  # confirmation / reveal text instead of a list


@dataclass
class _Confirm:
    item: Item
    taps: int
    deadline: float


@dataclass
class MenuState:
    """Everything the menu remembers between inputs."""

    menu: str = "root"
    index: int = 0
    top: int = 0  # first visible line, so the selection shows
    confirm: _Confirm | None = None
    detail: tuple[str, ...] = ()  # a reveal (recovery info) being shown
    last_input: float = 0.0
    pending: list = field(default_factory=list)  # actions for the owner


class MenuLogic:
    """Steps through the menus and reports the actions the owner must run.

    The owner (gpio_monitor.LedLogic) feeds it reed events and drains
    take_action(); it never calls back into the hardware itself.
    """

    def __init__(
        self,
        *,
        hotspot_active: Callable[[], bool] = lambda: False,
        development: Callable[[], bool] = lambda: False,
        display_timeout_min: Callable[[], int] = lambda: 30,
        reveals_left: Callable[[], int] = lambda: 0,
        menu_timeout_secs: Callable[[], int] = lambda: int(DEFAULT_INACTIVITY_SECS),
    ) -> None:
        self._hotspot_active = hotspot_active
        self._development = development
        self._display_timeout_min = display_timeout_min
        self._reveals_left = reveals_left
        self._menu_timeout_secs = menu_timeout_secs
        self.state = MenuState()
        self.open = False

    # -- lifecycle --------------------------------------------------------

    def enter(self, now: float) -> None:
        self.state = MenuState(last_input=now)
        self.open = True

    def leave(self) -> None:
        # Keep anything already queued: shutdown and reset close the menu in
        # the same breath as asking for the action, and a fresh MenuState()
        # would drop it before the owner ever drained it.
        pending = self.state.pending
        self.open = False
        self.state = MenuState(pending=pending)

    def tick(self, now: float) -> None:
        """Close the menu, or a confirmation, when nothing happens for a while."""
        if not self.open:
            return
        if self.state.confirm and now >= self.state.confirm.deadline:
            self.state.confirm = None  # a timeout always cancels
        if self.state.detail:
            # A reveal stays until it is dismissed.  It exists to be written
            # down, and a key that vanishes mid-transcription is worse than
            # one that waits.
            return
        if now - self.state.last_input >= self._menu_timeout_secs():
            self.leave()

    # -- the two inputs ---------------------------------------------------

    def tap(self, now: float) -> None:
        if not self.open:
            return
        self.state.last_input = now

        if self.state.detail:  # any tap dismisses a reveal
            self.state.detail = ()
            return

        if self.state.confirm is not None:
            c = self.state.confirm
            c.taps += 1
            if c.taps >= c.item.confirm:
                self.state.confirm = None
                self._fire(c.item, now)
            return

        items = self.items()
        self.state.index = (self.state.index + 1) % len(items)
        self._scroll()

    def select(self, now: float) -> None:
        """A long press: activate the highlighted item."""
        if not self.open:
            return
        self.state.last_input = now

        if self.state.detail:
            self.state.detail = ()
            return
        if self.state.confirm is not None:
            self.state.confirm = None  # a long press is not a confirming tap
            return

        item = self.items()[self.state.index]
        if item.confirm:
            self.state.confirm = _Confirm(item, 0, now + CONFIRM_SECS)
            return
        self._fire(item, now)

    def take_action(self) -> str | None:
        """Pop one pending action key, or None.  Drained by the owner."""
        return self.state.pending.pop(0) if self.state.pending else None

    # -- contents ---------------------------------------------------------

    def items(self) -> tuple[Item, ...]:
        if self.state.menu == "display":
            return tuple(
                Item(f"timeout:{m}", self._timeout_label(m)) for m in TIMEOUT_CHOICES
            ) + (
                Item("menutimeout", "Menu timeout", submenu="menutimeout"),
                Item("back", "Back", submenu="root"),
            )
        if self.state.menu == "menutimeout":
            return tuple(
                Item(f"menusecs:{t}", self._menu_timeout_label(t))
                for t in MENU_TIMEOUT_CHOICES
            ) + (Item("back", "Back", submenu="display"),)
        if self.state.menu == "power":
            return (
                Item("shutdown", "Shut down", confirm=1),
                Item("reboot", "Restart", confirm=1),
                Item("back", "Back", submenu="root"),
            )
        # "to on" / "to off" says what choosing it will DO, like Mode -- the
        # label then also tells you which state the device is in now.
        hotspot = "Hotspot: to off" if self._hotspot_active() else "Hotspot: to on"
        mode = "Mode: to production" if self._development() else "Mode: to development"
        left = self._reveals_left()
        recovery = "Recovery info" if left > 0 else "Recovery info (none left)"
        return (
            Item("hotspot", hotspot),
            Item("display", "Display", submenu="display"),
            Item("recovery", recovery, confirm=1 if left > 0 else 0),
            Item("mode", mode, confirm=1),
            Item("power", "Power", submenu="power"),
            Item("reset", "Factory reset", confirm=2),
            Item("exit", "Exit"),
        )

    def _timeout_label(self, minutes: int) -> str:
        mark = "*" if minutes == self._display_timeout_min() else " "
        text = "1 hour" if minutes == 60 else f"{minutes} min"
        return f"{mark} {text}"

    def _menu_timeout_label(self, secs: int) -> str:
        mark = "*" if secs == self._menu_timeout_secs() else " "
        text = f"{secs} s" if secs < 60 else f"{secs // 60} min"
        return f"{mark} {text}"

    # -- internals --------------------------------------------------------

    def _scroll(self) -> None:
        if self.state.index < self.state.top:
            self.state.top = self.state.index
        elif self.state.index >= self.state.top + VISIBLE_LINES:
            self.state.top = self.state.index - VISIBLE_LINES + 1

    def _fire(self, item: Item, now: float) -> None:
        if item.submenu:
            self.state.menu = item.submenu
            self.state.index = 0
            self.state.top = 0
            return
        if item.key == "exit":
            self.leave()
            return
        if item.key.startswith("menusecs:"):
            self.state.pending.append(item.key)
            self.state.menu = "display"
            self.state.index = 0
            self.state.top = 0
            return
        if item.key.startswith("timeout:"):
            self.state.pending.append(item.key)
            self.state.menu = "root"
            self.state.index = 0
            self.state.top = 0
            return
        if item.key == "recovery" and self._reveals_left() <= 0:
            return
        self.state.pending.append(item.key)
        if item.key in ("shutdown", "reboot", "reset"):
            self.leave()  # the device is going away; nothing left to show

    # -- rendering --------------------------------------------------------

    def view(self) -> MenuView:
        if self.state.detail:
            return MenuView("RECOVERY", (), 0, detail=self.state.detail)

        if self.state.confirm is not None:
            c = self.state.confirm
            left = c.item.confirm - c.taps
            word = "tap" if left == 1 else "taps"
            detail = (_confirm_text(c.item), f"{left} {word} to confirm")
            return MenuView("CONFIRM?", (), 0, detail=detail)

        items = self.items()
        top = self.state.top
        window = items[top : top + VISIBLE_LINES]
        title = "MENU" if self.state.menu == "root" else self.state.menu.upper()
        return MenuView(title, tuple(i.label for i in window), self.state.index - top)

    def show_detail(self, lines: tuple[str, ...], now: float) -> None:
        """The owner supplies text to display (recovery credentials)."""
        self.state.detail = lines
        self.state.last_input = now


def _confirm_text(item: Item) -> str:
    return {
        "reset": "Deletes all Wi-Fi settings",
        "shutdown": "Switches the device off",
        "reboot": "Restarts the device",
        "mode": "Opens or closes ports",
        "recovery": "Shows the hotspot key",
    }.get(item.key, item.label)
