"""The first scan into an empty pen folder is typed.

Observed on a freshly installed device: the pen's "Scan text and save" folder
was empty (earlier deliveries had deleted every scan), and the watch loop
skipped an empty folder before recording it.  The first scan to land in it
was then taken as the folder's baseline -- "1 existing file(s) left
untouched" -- and never typed.
"""

from __future__ import annotations

import os

from ipr_keyboard.delivery import DeliveryLog
from ipr_keyboard.main import _next_new_scan


def _scan(folder, name, mtime):
    f = folder / name
    f.write_text("scanned text", encoding="utf-8")
    os.utime(f, (mtime, mtime))
    return f


def test_an_empty_folder_is_baselined_so_the_first_scan_is_typed(tmp_path):
    folder = tmp_path / "Scan text and save"
    folder.mkdir()
    log = DeliveryLog(tmp_path / "pen_state.json")

    assert _next_new_scan(log, folder) is None  # empty: baselined, nothing to type
    assert log.knows(folder)

    scan = _scan(folder, "20261010190346.txt", 1_791_651_827)
    assert _next_new_scan(log, folder) == scan


def test_the_empty_baseline_survives_a_restart(tmp_path):
    folder = tmp_path / "Scan text and save"
    folder.mkdir()
    _next_new_scan(DeliveryLog(tmp_path / "pen_state.json"), folder)

    scan = _scan(folder, "20261010190346.txt", 1_791_651_827)
    assert _next_new_scan(DeliveryLog(tmp_path / "pen_state.json"), folder) == scan


def test_scans_already_there_at_first_sight_are_still_left_alone(tmp_path):
    folder = tmp_path / "Scan text and save"
    folder.mkdir()
    _scan(folder, "20260901120000.txt", 1_788_000_000)
    log = DeliveryLog(tmp_path / "pen_state.json")

    assert _next_new_scan(log, folder) is None
    assert _next_new_scan(log, folder) is None  # and not on the next poll either
