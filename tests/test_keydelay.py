"""The typing speed handed to the BLE daemon at runtime.

The point of this module is that changing the typing speed must not restart
the daemon — a restart drops the BLE link and makes the user pair again — and
that nothing here can stop the device typing.
"""

from __future__ import annotations

import pytest

from ipr_keyboard import keydelay


@pytest.fixture(autouse=True)
def _tmp_path_file(tmp_path, monkeypatch):
    monkeypatch.setattr(keydelay, "PATH", tmp_path / "ipr_bt_key_delay")
    yield


def test_nothing_in_force_when_the_daemon_never_created_the_file():
    """An older daemon creates no file; that is not an error."""
    assert keydelay.read() is None


def test_apply_then_read_round_trips():
    assert keydelay.apply(12) is True
    assert keydelay.read() == 12


def test_apply_is_a_no_op_when_the_value_is_unchanged():
    """The main loop calls this every iteration, so it must not rewrite."""
    keydelay.apply(12)
    before = keydelay.PATH.stat().st_mtime_ns
    assert keydelay.apply(12) is True
    assert keydelay.PATH.stat().st_mtime_ns == before


@pytest.mark.parametrize(
    "given,expected",
    [(0, keydelay.MIN_MS), (-5, keydelay.MIN_MS), (9999, keydelay.MAX_MS), (12, 12)],
)
def test_values_are_clamped_to_the_usable_range(given, expected):
    assert keydelay.clamp(given) == expected
    keydelay.apply(given)
    assert keydelay.read() == expected


@pytest.mark.parametrize("junk", ["", "   ", "fast", "12ms", "1e3"])
def test_unparsable_contents_read_as_nothing_in_force(junk):
    """A corrupt file must not be mistaken for a speed."""
    keydelay.PATH.write_text(junk, encoding="ascii")
    assert keydelay.read() is None


@pytest.mark.parametrize("out_of_range", ["0", "-20", "5000"])
def test_out_of_range_contents_read_as_nothing_in_force(out_of_range):
    keydelay.PATH.write_text(out_of_range, encoding="ascii")
    assert keydelay.read() is None


def test_apply_reports_failure_instead_of_raising(monkeypatch):
    """/run is root-owned until the daemon hands the file over.

    This is called from the send path and the main loop, so it reports rather
    than raises: a device that cannot set the speed must still type.
    """

    def _boom(*_a, **_kw):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(type(keydelay.PATH), "write_text", _boom, raising=False)
    assert keydelay.apply(8) is False


def test_chars_per_second_counts_both_hid_reports():
    """Press and release, so the delay is paid twice per character."""
    assert keydelay.chars_per_second(20) == pytest.approx(25.0)
    assert keydelay.chars_per_second(12) == pytest.approx(41.7, abs=0.1)
    assert keydelay.chars_per_second(4) == pytest.approx(125.0)


def test_the_offered_ladder_matches_the_documented_one():
    """docs/operations/performance.md tunes in these steps."""
    assert [ms for ms, _, _ in keydelay.CHOICES] == [20, 12, 8, 4]
    for ms, name, detail in keydelay.CHOICES:
        assert keydelay.MIN_MS <= ms <= keydelay.MAX_MS
        assert name.strip() == name and name
        assert detail.strip() == detail and detail


def test_a_speed_is_named_the_same_way_everywhere():
    """Settings and the Debug trial must not describe one speed two ways.

    They did: Settings said "Normal - 25 characters a second" while the trial
    reported raw milliseconds per report beside milliseconds per character.
    Different quantities, so the two screens looked unrelated.
    """
    for ms, name, _ in keydelay.CHOICES:
        assert keydelay.name_for(ms) == name
        label = keydelay.label_for(ms)
        assert label.startswith(name)
        assert f"{ms} ms" in label, label
        # The nominal rate in the label is the one the trial compares against.
        assert str(round(keydelay.chars_per_second(ms))) in label


def test_a_hand_tuned_speed_still_gets_a_name_and_a_label():
    assert keydelay.name_for(15) == "15 ms"
    label = keydelay.label_for(15)
    assert "15 ms" in label and "33" in label  # 1000 / (2 * 15)


def test_the_daemon_and_the_application_agree_on_path_and_range():
    """Both sides declare these; a mismatch silently disables the setting.

    PATH is monkeypatched for the other tests, so compare the source files:
    the daemon runs as root from /usr/local/bin and shares nothing but these
    three literals with the application.
    """
    import re
    from pathlib import Path

    daemon = Path("scripts/service/bin/bt_hid_ble_daemon.py").read_text(encoding="utf-8")
    app = Path("src/ipr_keyboard/keydelay.py").read_text(encoding="utf-8")

    daemon_path = re.search(r'KEY_DELAY_PATH = "([^"]+)"', daemon).group(1)
    app_path = re.search(r'PATH = Path\("([^"]+)"\)', app).group(1)
    assert daemon_path == app_path, (daemon_path, app_path)

    assert f"KEY_DELAY_MIN_MS = {keydelay.MIN_MS}" in daemon
    assert f"KEY_DELAY_MAX_MS = {keydelay.MAX_MS}" in daemon
