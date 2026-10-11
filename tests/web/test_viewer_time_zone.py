"""Times are shown in the viewer's time zone, not the device's.

The server sends instants only -- UTC "Z", or journal lines in short-iso with
their offset -- and static/localtime.js formats them in the browser's zone.
Before this, the event list showed the moment of the request for every event
(not the event's own time) as raw UTC text, the pen list showed raw UTC, and
the clocks and log lines showed the device's own zone.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess

import pytest

from ipr_keyboard.web import api, setup

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOCALTIME_JS = ROOT / "src" / "ipr_keyboard" / "web" / "static" / "localtime.js"


# --------------------------------------------------------------- server side


@pytest.mark.parametrize(
    "line",
    [
        "2026-10-10T19:27:40+02:00 ipr-prod-zero2 python[1]: Detected new file",
        "2026-10-10T19:27:40+0200 ipr-prod-zero2 python[1]: Detected new file",
        "2026-10-10T17:27:40Z ipr-prod-zero2 python[1]: Detected new file",
    ],
)
def test_a_journal_line_yields_its_own_instant_in_utc(line):
    at, rest = api._journal_line_time(line)
    assert at == "2026-10-10T17:27:40Z"
    assert rest == "ipr-prod-zero2 python[1]: Detected new file"


def test_a_line_without_a_stamp_is_left_alone():
    assert api._journal_line_time("-- No entries --") == (None, "-- No entries --")


def test_events_carry_the_journal_time_not_the_request_time():
    lines = [
        "2026-10-10T19:11:30+02:00 pi python[1]: transmission started",
        "2026-10-10T19:12:53+02:00 pi bt_hid_ble[2]: Bluetooth disconnected",
    ]
    events = api._parse_journalctl_events(lines, None, None, 10)
    assert [e["timestamp"] for e in events] == [
        "2026-10-10T17:12:53Z",
        "2026-10-10T17:11:30Z",
    ]
    # The text no longer embeds a device-zone time.
    assert all("19:1" not in e["details"] for e in events)


def test_journal_reads_ask_for_short_iso(flask_client, temp_config, monkeypatch):
    seen = []

    def fake(cmd, *a, **k):
        seen.append(cmd)
        return "2026-10-10T19:27:40+02:00 pi python[1]: hello\n"

    monkeypatch.setattr(api.subprocess, "check_output", fake)
    data = flask_client.get("/api/logs/raw").get_json()
    flask_client.get("/api/events")
    journal = [c for c in seen if c and c[0] == "journalctl"]
    assert journal and all(c[c.index("-o") + 1] == "short-iso" for c in journal)
    assert isinstance(data["device_epoch"], float)


def test_the_certificate_expiry_becomes_an_instant():
    assert (
        setup._openssl_date_to_iso("Oct  5 19:39:00 2036 GMT") == "2036-10-05T19:39:00Z"
    )
    assert setup._openssl_date_to_iso("something odd") == "something odd"


# -------------------------------------------------------------- browser side

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")

_DRIVER = """
require(process.argv[1]);
const t = globalThis.iprTime;
const out = {
  epoch: t.format(1791652060),
  iso: t.format("2026-10-10T17:27:40Z"),
  line: t.localizeLines("2026-10-10T19:27:40+02:00 pi python[1]: hi\\nno stamp here"),
  compact: t.localizeLines("2026-10-10T19:27:40+0200  irispen-mount.service failed"),
  bad: t.format("not a time"),
  none: t.format(null),
};
console.log(JSON.stringify(out));
"""


def _run_js(tz: str) -> dict:
    env = {**os.environ, "TZ": tz}
    out = subprocess.run(
        ["node", "-e", _DRIVER, str(LOCALTIME_JS)],
        capture_output=True,
        text=True,
        env=env,
        check=True,
        timeout=30,
    ).stdout
    return json.loads(out)


@needs_node
def test_the_page_shows_times_in_the_viewers_zone_copenhagen():
    r = _run_js("Europe/Copenhagen")
    assert r["epoch"] == "2026-10-10 19:07:40"  # 17:07:40Z in CEST
    assert r["iso"] == "2026-10-10 19:27:40"
    assert r["line"] == "2026-10-10 19:27:40 pi python[1]: hi\nno stamp here"
    assert r["compact"] == "2026-10-10 19:27:40  irispen-mount.service failed"


@needs_node
def test_the_same_instants_in_another_zone():
    r = _run_js("America/New_York")
    assert r["iso"] == "2026-10-10 13:27:40"  # EDT
    assert r["line"].startswith("2026-10-10 13:27:40 pi python[1]: hi")


@needs_node
def test_unusable_input_is_shown_unchanged():
    r = _run_js("UTC")
    assert r["bad"] == "not a time" and r["none"] == ""
