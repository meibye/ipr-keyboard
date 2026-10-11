"""The incident log, explained (incidents.py) and served (/api/incidents).

The Home card used to show a red count and the last raw line in a tooltip:
nothing said what had failed, whether it still was, or what to do, and
nothing ever brought the count down.
"""

from __future__ import annotations

import subprocess

import pytest

from ipr_keyboard import incidents as il
from ipr_keyboard.web import api

LOG = (
    "2026-09-12T13:06:49+02:00  bt_hid_ble.service failed (result=exit-code)\n"
    "\n"
    "2026-10-10T19:18:42+02:00  irispen-mount.service failed (result=signal)\n"
)


# ------------------------------------------------------------------ parsing


def test_each_line_becomes_an_incident_with_its_instant_in_utc():
    items = il.parse(LOG)
    assert [(i.unit, i.result, i.at) for i in items] == [
        ("bt_hid_ble", "exit-code", "2026-09-12T11:06:49Z"),
        ("irispen-mount", "signal", "2026-10-10T17:18:42Z"),
    ]


def test_a_line_in_an_unknown_shape_is_kept_not_hidden():
    (item,) = il.parse("something odd happened\n")
    assert (
        item.unit == "unknown"
        and item.at is None
        and item.line == "something odd happened"
    )


def test_a_missing_log_is_no_incidents(tmp_path):
    assert il.read(tmp_path / "absent.log") == []


# --------------------------------------------------------------- explaining


def _one(line: str) -> il.Incident:
    return il.parse(line)[0]


def test_a_unit_running_again_says_so_and_needs_only_a_check():
    e = il.explain(
        _one("2026-10-10T19:18:42+02:00  bt_hid_ble.service failed (result=signal)"),
        "active",
        False,
    )
    assert e["title"] == "Bluetooth keyboard stopped"
    assert "stopped forcibly" in e["what"]
    assert e["now"] == "Running again" and e["now_state"] == "ready"
    assert "mark this as handled" in e["advice"]
    assert e["can_restart"] is False  # nothing to restart


def test_a_unit_still_down_says_what_to_do_and_offers_a_restart():
    e = il.explain(
        _one("2026-10-10T19:18:42+02:00  bt_hid_ble.service failed (result=exit-code)"),
        "failed",
        False,
    )
    assert e["now"] == "Not running" and e["now_state"] == "error"
    assert "Restart it" in e["advice"]
    assert e["can_restart"] is True


def test_the_pen_connection_down_is_normal_without_a_pen():
    e = il.explain(
        _one("2026-10-10T19:18:42+02:00  irispen-mount.service failed (result=signal)"),
        "inactive",
        False,
    )
    assert e["now_state"] == "muted"
    assert "normal while the pen is unplugged" in e["advice"]
    assert "unplug the pen" in e["advice"]
    assert e["can_restart"] is False  # not one the root helper controls


def test_an_unknown_result_and_unit_still_read_as_words():
    e = il.explain(
        _one("2026-10-10T19:18:42+02:00  odd.service failed (result=weird)"),
        "failed",
        False,
    )
    assert e["title"] == "odd stopped" and "(weird)" in e["what"]
    assert "Restart the device" in e["advice"]


def test_every_known_unit_and_result_has_words():
    for unit, info in il.UNITS.items():
        assert info.label and info.role and info.when_down, unit
    for result, text in il.RESULTS.items():
        assert text.endswith("."), result


# ------------------------------------------------------------------ handled


def test_handled_incidents_stop_counting_but_stay_in_the_log(tmp_path):
    items = il.parse(LOG)
    path = tmp_path / "handled.json"
    assert il.summary(items, il.handled(path)) == (2, 0, items[-1].line)
    assert il.mark_handled(path, [items[-1].id], items) == 1
    assert il.summary(items, il.handled(path)) == (1, 1, items[0].line)
    assert il.mark_handled(path, [items[-1].id], items) == 0  # already handled


def test_only_lines_still_in_the_log_are_kept_as_handled(tmp_path):
    items = il.parse(LOG)
    path = tmp_path / "handled.json"
    il.mark_handled(path, [i.id for i in items] + ["not in the log"], items)
    assert il.handled(path) == {i.id for i in items}
    # The log was replaced (a reinstall): the old acknowledgements fall away.
    fresh = il.parse(
        "2026-11-01T08:00:00+01:00  bt_hid_ble.service failed (result=timeout)\n"
    )
    il.mark_handled(path, [fresh[0].id], fresh)
    assert il.handled(path) == {fresh[0].id}


def test_a_damaged_handled_file_reads_as_nothing_handled(tmp_path):
    path = tmp_path / "handled.json"
    path.write_text("{not json", encoding="utf-8")
    assert il.handled(path) == set()


# -------------------------------------------------------------- unit state


def test_unit_states_is_one_systemctl_call(monkeypatch):
    calls = []

    def fake(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 3, stdout="active\nfailed\n", stderr="")

    monkeypatch.setattr(il.subprocess, "run", fake)
    assert il.unit_states(["irispen-mount", "bt_hid_ble", "bt_hid_ble", "unknown"]) == {
        "bt_hid_ble": "active",
        "irispen-mount": "failed",
    }
    assert calls == [
        ["systemctl", "is-active", "bt_hid_ble.service", "irispen-mount.service"]
    ]


def test_unit_states_without_systemctl_is_unknown(monkeypatch):
    def boom(cmd, **kw):
        raise OSError("no systemctl")

    monkeypatch.setattr(il.subprocess, "run", boom)
    assert il.unit_states(["bt_hid_ble"]) == {"bt_hid_ble": "unknown"}


# --------------------------------------------------------------------- API


@pytest.fixture
def incident_files(tmp_path, monkeypatch):
    log = tmp_path / "incidents.log"
    log.write_text(LOG, encoding="utf-8")
    handled = tmp_path / "incidents_handled.json"
    monkeypatch.setattr(api, "_INCIDENTS_FILE", log)
    monkeypatch.setattr(api, "_incidents_handled_path", lambda: handled)
    monkeypatch.setattr(
        il,
        "unit_states",
        lambda units: {u: ("failed" if u == "bt_hid_ble" else "active") for u in units},
    )
    return log, handled


def test_the_incidents_endpoint_explains_each_newest_first(
    flask_client, incident_files
):
    d = flask_client.get("/api/incidents").get_json()
    assert d["open_count"] == 2 and d["handled_count"] == 0
    assert [i["unit"] for i in d["items"]] == ["irispen-mount", "bt_hid_ble"]
    assert d["items"][0]["now"] == "Running again"
    assert d["items"][1]["now"] == "Not running" and d["items"][1]["can_restart"]


def test_marking_one_handled_takes_it_off_the_home_count(flask_client, incident_files):
    first = flask_client.get("/api/incidents").get_json()["items"][0]
    res = flask_client.post("/api/incidents/handled", json={"ids": [first["id"]]})
    assert res.get_json() == {"ok": True, "marked": 1}
    d = flask_client.get("/api/incidents").get_json()
    assert d["open_count"] == 1 and d["handled_count"] == 1
    assert d["items"][0]["handled"] is True
    dev = api._build_device_data()
    assert dev["incidents_count"] == 1 and dev["incidents_handled"] == 1
    assert "bt_hid_ble" in dev["last_incident"]


def test_mark_all_handled(flask_client, incident_files):
    assert (
        flask_client.post("/api/incidents/handled", json={"all": True}).get_json()[
            "marked"
        ]
        == 2
    )
    assert flask_client.get("/api/incidents").get_json()["open_count"] == 0


def test_marking_handled_needs_an_admin(flask_client, incident_files):
    with flask_client.session_transaction() as sess:
        sess["is_admin"] = False
    assert (
        flask_client.post("/api/incidents/handled", json={"all": True}).status_code
        == 403
    )
    assert (
        flask_client.post("/api/incidents/restart", json={"id": "x"}).status_code == 403
    )


def test_marking_handled_without_saying_which_is_refused(flask_client, incident_files):
    assert flask_client.post("/api/incidents/handled", json={}).status_code == 400


def test_the_log_is_the_units_journal_around_the_failure(
    flask_client, incident_files, monkeypatch
):
    seen = []

    def fake(cmd, *a, **k):
        seen.append(cmd)
        return "2026-10-10T19:18:40+02:00 pi jmtpfs[1]: killed\n"

    monkeypatch.setattr(api.subprocess, "check_output", fake)
    item = flask_client.get("/api/incidents").get_json()["items"][0]
    d = flask_client.get(
        "/api/incidents/log", query_string={"id": item["id"]}
    ).get_json()
    assert d["lines"] == ["2026-10-10T19:18:40+02:00 pi jmtpfs[1]: killed"]
    cmd = seen[0]
    assert cmd[cmd.index("-u") + 1] == "irispen-mount.service"
    at = 1791652722  # 2026-10-10T17:18:42Z
    assert cmd[cmd.index("--since") + 1] == f"@{at - 180}"
    assert cmd[cmd.index("--until") + 1] == f"@{at + 60}"


def test_the_log_of_an_unknown_incident_is_404(flask_client, incident_files):
    assert (
        flask_client.get("/api/incidents/log", query_string={"id": "nope"}).status_code
        == 404
    )


def test_restart_goes_through_the_root_helper(
    flask_client, incident_files, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        api,
        "_helper_service",
        lambda action, unit: calls.append((action, unit)) or (True, ""),
    )
    items = flask_client.get("/api/incidents").get_json()["items"]
    ble = next(i for i in items if i["unit"] == "bt_hid_ble")
    res = flask_client.post("/api/incidents/restart", json={"id": ble["id"]})
    assert res.status_code == 200 and calls == [("restart", "bt_hid_ble")]
    pen = next(i for i in items if i["unit"] == "irispen-mount")
    assert (
        flask_client.post("/api/incidents/restart", json={"id": pen["id"]}).status_code
        == 400
    )
