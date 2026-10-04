"""Which PCs are paired, as published by the BLE daemon.

The point of this module is that the panel can tell "no PC has ever been
paired" from "a PC is paired but away", because the user's next move differs:
pair one, or reconnect it from the PC.  The device cannot reconnect itself —
it is a BLE peripheral.
"""

from __future__ import annotations

import json
import time

from ipr_keyboard import bt_link as bl


def _write(path, bonded=1, names=("MSI",), connected=False, at=None):
    path.write_text(
        json.dumps(
            {
                "bonded": bonded,
                "names": list(names),
                "connected": connected,
                "at": at if at is not None else time.time(),
            }
        ),
        encoding="utf-8",
    )
    return str(path)


def test_no_file_means_unknown_so_the_panel_keeps_its_old_wording(tmp_path):
    """An older daemon publishes nothing; that must not invent a bond."""
    link = bl.read(str(tmp_path / "absent"))
    assert not link.known and not link.has_bond


def test_a_bonded_host_is_reported(tmp_path):
    link = bl.read(_write(tmp_path / "link.json", bonded=1, names=("MSI",)))
    assert link.known and link.has_bond
    assert link.first_name == "MSI"
    assert not link.connected


def test_no_bond_is_not_the_same_as_unknown(tmp_path):
    """Nothing paired yet: the panel should say wait, not reconnect."""
    link = bl.read(_write(tmp_path / "link.json", bonded=0, names=()))
    assert link.known, "the daemon did answer"
    assert not link.has_bond, "but there is nothing to reconnect"


def test_a_stale_file_is_not_trusted(tmp_path):
    p = _write(tmp_path / "link.json", at=1000.0)
    assert not bl.read(p, now=1000.0 + bl.STALE_AFTER_S + 1).known


def test_a_file_within_the_stale_window_is_trusted(tmp_path):
    """Bonds change rarely, so a slightly old answer is still a good one."""
    p = _write(tmp_path / "link.json", at=1000.0)
    assert bl.read(p, now=1000.0 + bl.STALE_AFTER_S - 1).has_bond


def test_rubbish_is_not_fatal(tmp_path):
    p = tmp_path / "link.json"
    for junk in ("not json", "[]", '{"bonded": "two"}'):
        p.write_text(junk, encoding="utf-8")
        assert not bl.read(str(p)).has_bond


def test_only_real_names_reach_the_panel(tmp_path):
    """str(None) is the word "None", which would have been shown as a host."""
    p = tmp_path / "link.json"
    p.write_text(
        json.dumps(
            {"bonded": 3, "names": ["MSI", "", None, "  ", 7], "at": time.time()}
        ),
        encoding="utf-8",
    )
    link = bl.read(str(p))
    assert link.has_bond
    assert link.names == ("MSI",), link.names
    assert link.first_name == "MSI"


def test_the_daemon_and_the_application_agree_on_the_path():
    """Both sides declare it; a mismatch silently disables the hint."""
    import re
    from pathlib import Path

    daemon = Path("scripts/service/bin/bt_hid_ble_daemon.py").read_text(
        encoding="utf-8"
    )
    declared = re.search(r'LINK_FILE = "([^"]+)"', daemon).group(1)
    assert declared == bl.LINK_FILE, (declared, bl.LINK_FILE)
