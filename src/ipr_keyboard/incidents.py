"""The incident log, explained for the dashboard.

Every core unit carries ``OnFailure=ipr-failure@%n.service`` (installed by
scripts/headless/install_observability.sh), which appends one line per
failure to /var/lib/ipr-keyboard/incidents.log::

    2026-10-10T19:18:42+02:00  irispen-mount.service failed (result=signal)

The dashboard used to show only how many lines there were, in red, with the
last one in a tooltip: no word on what had failed, whether it still was, or
what to do — and nothing ever made the count go down again.  This module
turns each line into what a person needs to act on it:

* what failed and what that means, in plain words;
* whether the unit is running again now (one ``systemctl is-active`` call);
* what to do about it;
* whether someone has marked it handled.

The log itself is never rewritten: it is the device's record of what went
wrong.  "Handled" is kept beside the application's own state (like
pen_state.json), as the set of lines a person has acknowledged.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

INCIDENTS_FILE = Path("/var/lib/ipr-keyboard/incidents.log")
HANDLED_FILE = "incidents_handled.json"
# A handled set larger than this only ever holds lines long gone from the log.
_HANDLED_CAP = 500

_LINE = re.compile(
    r"^(?P<at>\S+)\s+(?P<unit>\S+?)(?:\.service)?\s+failed\s*(?:\(result=(?P<result>[^)]*)\))?"
)


@dataclass(frozen=True)
class UnitInfo:
    label: str  # what the person calls it
    role: str  # what it does, so the failure means something
    when_down: str  # what to do while it is still not running
    restartable: bool = False  # the dashboard's root helper may restart it


UNITS: dict[str, UnitInfo] = {
    "ipr_keyboard": UnitInfo(
        "Main application",
        "watches the pen for new scans, types them on the PC and serves this dashboard",
        "Restart the device (Settings ▸ Restart).",
    ),
    "bt_hid_ble": UnitInfo(
        "Bluetooth keyboard",
        "presents the device to the PC as a keyboard; while it is down the PC receives nothing",
        "Restart it with the button below.  If it stops again, restart the device.",
        restartable=True,
    ),
    "bt_hid_agent_unified": UnitInfo(
        "Bluetooth pairing helper",
        "answers the PC's pairing requests and keeps the Bluetooth adapter ready",
        "Restart it with the button below.  If it stops again, restart the device.",
        restartable=True,
    ),
    "irispen-mount": UnitInfo(
        "Pen connection",
        "makes the pen's files readable over USB; while it is down new scans are not picked up",
        "Unplug the pen and plug it in again: the connection starts by itself.",
    ),
    "ipr-provision": UnitInfo(
        "Installation",
        "the one-time installation run that sets the device up",
        "Run the installation again (see the administrator manual, installation chapter).",
    ),
}

# systemd's Result= values, in words.
RESULTS: dict[str, str] = {
    "exit-code": "It stopped with an error.",
    "signal": "It was stopped forcibly — by another program, a person, or the system.",
    "core-dump": "It crashed.",
    "timeout": "It did not start or stop in time.",
    "watchdog": "It stopped responding.",
    "start-limit-hit": "It failed to start several times in a row, so the system gave up on it.",
    "oom-kill": "The device ran out of memory and the system stopped it.",
    "resources": "It could not get something it needs to start (a file, a folder or a permission).",
    "exception": "It stopped with an unexpected error.",
}


@dataclass(frozen=True)
class Incident:
    id: str  # the line itself identifies it; stable across reads
    line: str
    at: str | None  # UTC ISO "Z", or None when the line has no usable time
    unit: str  # bare name, without ".service"
    result: str

    @property
    def info(self) -> UnitInfo:
        return UNITS.get(
            self.unit,
            UnitInfo(
                self.unit,
                "a system service",
                "Restart the device (Settings ▸ Restart).",
            ),
        )


def _utc(stamp: str) -> str | None:
    if re.search(r"[+-]\d{4}$", stamp):  # +0200 -> +02:00 for fromisoformat
        stamp = stamp[:-2] + ":" + stamp[-2:]
    try:
        at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if at.tzinfo is None:
        return None
    return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(text: str) -> list[Incident]:
    """Each line of the log, oldest first; a line in an unknown shape is kept
    (as unit "unknown") rather than hidden — it still happened."""
    items = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _LINE.match(line)
        if not m:
            items.append(
                Incident(id=line, line=line, at=None, unit="unknown", result="")
            )
            continue
        items.append(
            Incident(
                id=line,
                line=line,
                at=_utc(m.group("at")),
                unit=m.group("unit"),
                result=(m.group("result") or "").strip(),
            )
        )
    return items


def read(path: Path = INCIDENTS_FILE) -> list[Incident]:
    try:
        return parse(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return []


# ------------------------------------------------------------------ handled


def handled(path: Path) -> set[str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {s for s in raw.get("handled", []) if isinstance(s, str)}
    except (OSError, ValueError, AttributeError):
        return set()


def mark_handled(path: Path, ids: list[str], current: list[Incident]) -> int:
    """Record `ids` as handled; returns how many were new.  Only lines still in
    the log are kept, so the file cannot grow past the log it describes."""
    in_log = {i.id for i in current}
    done = handled(path) & in_log
    new = {i for i in ids if i in in_log} - done
    if not new:
        return 0
    keep = sorted(done | new)[-_HANDLED_CAP:]
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".incidents_handled.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"handled": keep}, fh, indent=1)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return len(new)


# ------------------------------------------------------------------- now


def unit_states(units: list[str]) -> dict[str, str]:
    """`systemctl is-active` for each unit, in one call: active / failed /
    inactive / activating / ... ; "unknown" when systemctl cannot tell."""
    units = sorted(set(u for u in units if u != "unknown"))
    if not units:
        return {}
    names = [u + ".service" for u in units]
    try:
        out = subprocess.run(
            ["systemctl", "is-active", *names],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.split()
    except Exception:
        out = []
    if len(out) != len(units):
        return {u: "unknown" for u in units}
    return dict(zip(units, out))


def explain(incident: Incident, state: str, is_handled: bool) -> dict:
    """One incident, as the dashboard shows it."""
    info = incident.info
    result = RESULTS.get(
        incident.result,
        f"It failed ({incident.result})." if incident.result else "It failed.",
    )
    if state == "active":
        now, now_state = "Running again", "ready"
        advice = (
            "It recovered by itself.  Check that the device works — scan once — and then "
            "mark this as handled.  If the same incident keeps coming back, open the log "
            "and keep it for a fault report."
        )
    elif state in ("activating", "reloading"):
        now, now_state = "Starting", "warning"
        advice = "It is starting again.  Wait a minute and look again."
    elif state == "unknown":
        now, now_state = "Unknown", "muted"
        advice = "The device could not say whether it is running.  " + info.when_down
    elif incident.unit == "irispen-mount" and state == "inactive":
        # Not running is its normal state while no pen is plugged in.
        now, now_state = "Not running", "muted"
        advice = (
            "That is normal while the pen is unplugged.  If the pen is plugged in, "
            + info.when_down[0].lower()
            + info.when_down[1:]
        )
    else:
        now, now_state = "Not running", "error"
        advice = info.when_down
    if incident.unit == "ipr-provision" and state != "active":
        # Installation runs once and then stops on purpose: "not running" is
        # its finished state, and the failure itself is what matters.
        now, now_state = "Finished", "muted"
        advice = info.when_down
    return {
        "id": incident.id,
        "at": incident.at,
        "unit": incident.unit,
        "label": info.label,
        "title": f"{info.label} stopped",
        "what": f"The {info.label.lower()} {info.role}.  {result}",
        "result": incident.result,
        "now": now,
        "now_state": now_state,
        "advice": advice,
        "can_restart": info.restartable and state != "active",
        "handled": is_handled,
        "line": incident.line,
    }


def home_summary(
    incidents: list[Incident], handled_ids: set[str], states: dict[str, str]
) -> dict:
    """What the Home card shows.

    An open incident stays open until someone marks it handled -- a service
    that restarts by itself does not clear it, or one that fails every night
    would never be noticed.  But "a service is down now" and "something
    failed and recovered, have a look" are different things, and one red
    count for both read as a live fault.  So the open ones are split:

    attention  the service is still down (the panel says *Not running*)
    recovered  everything else open: running again, starting, finished, or
               not running because nothing needs it (the pen unplugged)
    """
    open_ = [i for i in incidents if i.id not in handled_ids]
    attention = sum(
        1
        for i in open_
        if explain(i, states.get(i.unit, "unknown"), False)["now_state"] == "error"
    )
    return {
        "open": len(open_),
        "attention": attention,
        "recovered": len(open_) - attention,
        "handled": len(incidents) - len(open_),
        "last": open_[-1].line if open_ else "",
    }
