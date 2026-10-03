import pathlib
p = pathlib.Path("src/ipr_keyboard/menu.py")
s = p.read_text(encoding="utf-8", newline="")
CR = "\r\n" if "\r\n" in s else "\n"
def crlf(b): return b.replace("\n", CR)
def sub1(old, new):
    global s
    o, n = crlf(old), crlf(new)
    assert s.count(o) == 1, old[:60]
    s = s.replace(o, n)

sub1('''_TITLES = {
    "root": "MENU",
    "display": "DISPLAY",
    "menutimeout": "MENU TIMEOUT",
    "power": "POWER",
}''',
'''_TITLES = {
    "root": "MENU",
    "display": "DISPLAY",
    "displaytimeout": "SCREEN OFF",
    "menutimeout": "MENU CLOSES",
    "system": "SYSTEM",
    "power": "POWER",
}''')

sub1('''    def items(self) -> tuple[Item, ...]:
        if self.state.menu == "display":
            return tuple(
                Item(f"timeout:{m}", self._timeout_label(m)) for m in TIMEOUT_CHOICES
            ) + (
                Item("menutimeout", "Menu timeout", submenu="menutimeout"),
                Item("back", "Back", submenu="root"),
            )
        if self.state.menu == "menutimeout":
            # Named so the header reads MENU TIMEOUT rather than MENUTIMEOUT.
            return tuple(
                Item(f"menusecs:{t}", self._menu_timeout_label(t))
                for t in MENU_TIMEOUT_CHOICES
            ) + (Item("back", "Back", submenu="display"),)
        if self.state.menu == "power":
            return (
                Item("shutdown", "Shut down", confirm=1),
                Item("reboot", "Restart", confirm=1),
                Item("back", "Back", submenu="root"),
            )''',
'''    def items(self) -> tuple[Item, ...]:
        # Display holds the two timings, one submenu each, so neither list has
        # to share a screen with the other.
        if self.state.menu == "display":
            return (
                Item("displaytimeout", "Display timeout", submenu="displaytimeout"),
                Item("menutimeout", "Menu timeout", submenu="menutimeout"),
                Item("back", "Back", submenu="root"),
            )
        if self.state.menu == "displaytimeout":
            return tuple(
                Item(f"timeout:{m}", self._timeout_label(m)) for m in TIMEOUT_CHOICES
            ) + (Item("back", "Back", submenu="display"),)
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
        # The rarely-used, administrator-only actions live together, out of the
        # way of anything a user reaches for day to day.
        if self.state.menu == "system":
            mode = (
                "Mode: to production" if self._development() else "Mode: to development"
            )
            return (
                Item("mode", mode, confirm=1),
                Item("reset", "Factory reset", confirm=2),
                Item("back", "Back", submenu="root"),
            )''')

sub1('''        hotspot = "Hotspot: to off" if self._hotspot_active() else "Hotspot: to on"
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
        )''',
'''        hotspot = "Hotspot: to off" if self._hotspot_active() else "Hotspot: to on"
        left = self._reveals_left()
        recovery = "Recovery info" if left > 0 else "Recovery info (none left)"
        return (
            Item("hotspot", hotspot),
            Item("display", "Display", submenu="display"),
            # Recovery stays at the top level: it is what a locked-out device
            # needs, and burying it costs exactly when it matters.
            Item("recovery", recovery, confirm=1 if left > 0 else 0),
            Item("power", "Power", submenu="power"),
            Item("system", "System", submenu="system"),
            Item("exit", "Exit"),
        )''')

# after choosing a value, go back to the submenu it was chosen from
sub1('''        if item.key.startswith("menusecs:"):
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
            return''',
'''        if item.key.startswith("menusecs:") or item.key.startswith("timeout:"):
            self.state.pending.append(item.key)
            self.state.menu = "display"  # back to where the choice was made
            self.state.index = 0
            self.state.top = 0
            return''')
p.write_text(s, encoding="utf-8", newline="")
print("ok")
