"""Which scans get typed — the bug was losing one, not repeating one.

An MTP listing is not immediately consistent: a scan can appear *after* files
written later have already been delivered.  The old high-water mark then
skipped it for good, which is how a scan sat on the pen, visible in the
dashboard, and was never typed.
"""

import json

from ipr_keyboard.delivery import MAX_KEYS_PER_FOLDER, DeliveryLog


def _scan(folder, name, text="hello", mtime=None):
    p = folder / name
    p.write_text(text, encoding="utf-8")
    if mtime is not None:
        import os

        os.utime(p, (mtime, mtime))
    return p


def test_a_new_folder_is_baselined_and_nothing_is_typed(tmp_path):
    folder = tmp_path / "pen"
    folder.mkdir()
    old = [_scan(folder, f"old{i}.txt") for i in range(3)]
    log = DeliveryLog(tmp_path / "state.json")

    assert not log.knows(folder)
    log.baseline(folder, old)
    assert log.knows(folder)
    assert log.next_undelivered(folder, old) is None, "nothing already there is typed"


def test_a_scan_that_appears_late_is_still_delivered(tmp_path):
    """The defect: an older file surfacing after newer ones were delivered."""
    folder = tmp_path / "pen"
    folder.mkdir()
    log = DeliveryLog(tmp_path / "state.json")
    log.baseline(folder, [])

    later = _scan(folder, "20261003145155.txt", mtime=1791032000)
    assert log.next_undelivered(folder, [later]) == later
    log.mark(folder, later)

    # Now the MTP listing finally shows a scan written BEFORE it.
    earlier = _scan(folder, "20261003143851.txt", mtime=1791031133)
    assert log.next_undelivered(folder, [earlier, later]) == earlier, (
        "an older timestamp must not mean 'already delivered'"
    )


def test_a_delivered_scan_is_never_typed_twice(tmp_path):
    folder = tmp_path / "pen"
    folder.mkdir()
    log = DeliveryLog(tmp_path / "state.json")
    log.baseline(folder, [])
    f = _scan(folder, "a.txt")
    log.mark(folder, f)
    assert log.next_undelivered(folder, [f]) is None


def test_the_log_survives_a_restart(tmp_path):
    """The property the high-water mark existed to provide."""
    folder = tmp_path / "pen"
    folder.mkdir()
    state = tmp_path / "state.json"
    f = _scan(folder, "a.txt")

    log = DeliveryLog(state)
    log.baseline(folder, [])
    log.mark(folder, f)

    restarted = DeliveryLog(state)
    assert restarted.knows(folder)
    assert restarted.next_undelivered(folder, [f]) is None


def test_a_rewritten_file_with_the_same_name_is_a_new_scan(tmp_path):
    folder = tmp_path / "pen"
    folder.mkdir()
    log = DeliveryLog(tmp_path / "state.json")
    log.baseline(folder, [])
    f = _scan(folder, "scan.txt", text="first", mtime=1000)
    log.mark(folder, f)
    assert log.next_undelivered(folder, [f]) is None

    _scan(folder, "scan.txt", text="second scan, same name", mtime=2000)
    assert log.next_undelivered(folder, [f]) == f


def test_the_old_high_water_format_re_baselines(tmp_path):
    """Upgrading must not suddenly type a pile of old scans."""
    folder = tmp_path / "pen"
    folder.mkdir()
    state = tmp_path / "state.json"
    state.write_text(json.dumps({str(folder): 1791032067.0}), encoding="utf-8")

    log = DeliveryLog(state)
    assert not log.knows(folder), "the old mark cannot say which files it covered"


def test_the_log_is_bounded(tmp_path):
    folder = tmp_path / "pen"
    folder.mkdir()
    log = DeliveryLog(tmp_path / "state.json")
    log.baseline(folder, [])
    for i in range(MAX_KEYS_PER_FOLDER + 50):
        f = _scan(folder, f"s{i}.txt", mtime=1000 + i)
        log.mark(folder, f)
    stored = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert len(stored[str(folder)]) == MAX_KEYS_PER_FOLDER


def test_an_unwritable_state_file_is_not_fatal(tmp_path):
    folder = tmp_path / "pen"
    folder.mkdir()
    log = DeliveryLog(tmp_path / "nonexistent-dir" / "state.json")
    log.baseline(folder, [])
    f = _scan(folder, "a.txt")
    log.mark(folder, f)  # must not raise
    assert log.next_undelivered(folder, [f]) is None
