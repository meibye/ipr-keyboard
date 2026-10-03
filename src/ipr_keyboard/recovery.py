"""Recovery credentials shown on the panel, and the limits on showing them.

A device whose Wi-Fi settings have been deleted is reachable only through its
hotspot, and the hotspot key existed nowhere but the terminal that ran
provisioning.  The magnet menu can therefore show it -- but a password on a
screen is a password anyone can read, so two limits apply:

  * at most RecoveryRevealLimit reveals per boot, each after a confirming tap;
  * never again once the credentials have actually been used, recorded in
    USED_MARKER when the setup portal accepts a login with them.

The marker carries the secret's fingerprint, so regenerating the hotspot key
clears it: a new password has not been used yet.

See docs/architecture/magnet-menu-design.md section 3.5.
"""

from __future__ import annotations

import hashlib
import os

from .logging.logger import get_logger

logger = get_logger()

HOTSPOT_SECRET = "/etc/ipr-hotspot.secret"
# The dashboard's initial admin password, written by the app on first start and
# removed once the password is changed.  Shown alongside the hotspot key: a
# locked-out device needs both to be usable again, and hunting for the second
# one defeats the point of showing the first.
DASHBOARD_USER = "admin"
USED_MARKER = "/var/lib/ipr-keyboard/recovery_used"
# Reveals already spent, as "<fingerprint> <count>".  On disk because
# a reboot must not hand out a fresh allowance.
COUNT_FILE = "/var/lib/ipr-keyboard/recovery_reveals"
SETUP_URL = "10.42.0.1/setup"


def _dashboard_password(project_root=None) -> str:
    """The initial admin password, or "" once it has been changed away."""
    try:
        if project_root is None:
            from .utils.helpers import project_root as _root

            project_root = _root()
        path = os.path.join(str(project_root), "admin_initial_password.txt")
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except (OSError, ImportError):
        return ""


def _secret_fields(path: str = HOTSPOT_SECRET) -> tuple[str, str]:
    """(ssid, password) from the hotspot secret file; empty strings if absent."""
    ssid = password = ""
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("SSID="):
                    ssid = line[5:].strip().strip('"')
                elif line.startswith("PASSWORD=") or line.startswith("PASS="):
                    password = line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ssid, password


def fingerprint(path: str = HOTSPOT_SECRET) -> str:
    """Short digest of the current key, so a regenerated one is a new secret."""
    _, password = _secret_fields(path)
    if not password:
        return ""
    return hashlib.sha256(password.encode()).hexdigest()[:16]


def mark_used(path: str = HOTSPOT_SECRET, marker: str = USED_MARKER) -> None:
    """Record that these credentials have been used; stops further reveals."""
    fp = fingerprint(path)
    if not fp:
        return
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write(fp + "\n")
        logger.info("Recovery credentials marked as used; no further reveals")
    except OSError as exc:
        logger.warning("Could not write %s: %s", marker, exc)


def already_used(path: str = HOTSPOT_SECRET, marker: str = USED_MARKER) -> bool:
    """True when the marker matches the current key (a new key resets it)."""
    fp = fingerprint(path)
    if not fp:
        return False
    try:
        with open(marker, encoding="utf-8") as fh:
            return fh.read().strip() == fp
    except OSError:
        return False


class RecoveryInfo:
    """Counts the reveals a key has had, and renders the lines for the panel.

    The count is kept on disk against the key's fingerprint, not in memory:
    a reboot must not hand out a fresh allowance, or the limit means nothing
    to anyone who can power-cycle the device.  Generating a new key starts a
    new allowance, which is the documented way to get more
    (docs/hardware/oled-display.md).
    """

    def __init__(
        self,
        limit: int = 10,
        secret_path: str = HOTSPOT_SECRET,
        marker_path: str = USED_MARKER,
        count_path: str = COUNT_FILE,
        project_root=None,
    ) -> None:
        self._limit = max(0, int(limit))
        self._secret = secret_path
        self._marker = marker_path
        self._count = count_path
        self._project_root = project_root

    # -- the persisted counter --------------------------------------------

    def _used(self) -> int:
        """Reveals this key has already had; 0 for a key we have not seen."""
        fp = fingerprint(self._secret)
        if not fp:
            return 0
        try:
            with open(self._count, encoding="utf-8") as fh:
                stored_fp, _, stored_n = fh.read().strip().partition(" ")
        except OSError:
            return 0
        if stored_fp != fp:
            return 0  # a new key: a new allowance
        try:
            return int(stored_n)
        except ValueError:
            return 0

    def _record(self, used: int) -> None:
        fp = fingerprint(self._secret)
        if not fp:
            return
        try:
            os.makedirs(os.path.dirname(self._count), exist_ok=True)
            with open(self._count, "w", encoding="utf-8") as fh:
                fh.write(f"{fp} {used}\n")
        except OSError as exc:
            logger.warning("Could not record the reveal count: %s", exc)

    # -- what the menu asks -----------------------------------------------

    def reveals_left(self) -> int:
        if already_used(self._secret, self._marker):
            return 0
        ssid, password = _secret_fields(self._secret)
        if not (ssid and password):
            return 0
        return max(0, self._limit - self._used())

    def lines(self) -> tuple[str, ...]:
        """One reveal: costs a credit and returns the lines, or () when spent."""
        if self.reveals_left() <= 0:
            return ()
        ssid, password = _secret_fields(self._secret)
        used = self._used() + 1
        self._record(used)
        logger.warning(
            "Recovery credentials shown on the panel (%d of %d for this key)",
            used,
            self._limit,
        )
        lines = [f"Wi-Fi {ssid}", f"Key  {password}", f"Open {SETUP_URL}"]
        dash = _dashboard_password(self._project_root)
        if dash:
            lines.append(f"Web  {DASHBOARD_USER} / {dash}")
        return tuple(lines)
