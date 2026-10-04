"""Which PCs are paired with this device, and whether one is here.

The panel has to tell two situations apart, because the user's next move is
different in each:

* no PC has ever been paired  -> pair one (see the manual)
* a PC is paired but away     -> reconnect it **from the PC**

The device cannot do the second itself.  It is a BLE peripheral: it advertises
and waits, and the host decides when to come back.  After one reboot a Windows
host took 26 minutes, with the panel saying only "Waiting for PC…" throughout
— true, but it gave no hint that the next move was on the PC.

BlueZ keeps bonds in /var/lib/bluetooth, which is 0700 root, so the
application cannot read them.  The BLE daemon runs as root and already holds a
D-Bus connection, so it publishes this to a file on tmpfs instead (LINK_FILE
in bt_hid_ble_daemon.py).  Nothing here is required: an older daemon publishes
nothing and the panel keeps its previous wording.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

LINK_FILE = os.environ.get("BT_LINK_FILE", "/run/ipr_bt_link.json")
# The daemon rewrites this every 30 s.  Allow a couple of misses before
# treating it as silence: a stale answer about which PCs are paired is still a
# good answer, since bonds change only when someone pairs or unpairs.
STALE_AFTER_S = 180.0


@dataclass(frozen=True)
class Link:
    """What the daemon last said about the paired hosts."""

    bonded: int = 0
    names: tuple[str, ...] = ()
    connected: bool = False
    known: bool = False  # False when the daemon told us nothing

    @property
    def has_bond(self) -> bool:
        """A PC has been paired, so reconnecting it is a thing the user can do."""
        return self.known and self.bonded > 0

    @property
    def first_name(self) -> str:
        return self.names[0] if self.names else ""


UNKNOWN = Link()


def read(path: str = LINK_FILE, now: float | None = None) -> Link:
    """The daemon's latest view, or UNKNOWN when there is none to read."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return UNKNOWN
    if not isinstance(raw, dict):
        return UNKNOWN
    at = float(raw.get("at", 0.0) or 0.0)
    if (now or time.time()) - at > STALE_AFTER_S:
        return UNKNOWN
    names = raw.get("names")
    if not isinstance(names, list):
        names = []
    return Link(
        bonded=int(raw.get("bonded", 0) or 0),
        names=tuple(n for n in names if isinstance(n, str) and n.strip()),
        connected=bool(raw.get("connected", False)),
        known=True,
    )
