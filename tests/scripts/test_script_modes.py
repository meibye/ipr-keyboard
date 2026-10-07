"""Every script is executable in git, not just on a provisioned device.

Git on Windows (core.fileMode=false) never records the execute bit unless told
to, and 36 scripts under scripts/ were tracked as 100644.  Provisioning hid it
by chmod-ing everything +x on install -- until a deploy straight from git
(`git archive | tar x`) laid eight of them back down without it, and the
post-provision audit failed I.1.  A deploy script run as `./script` then
fails with "Permission denied".

This mirrors the audit's own rule (test_provision.sh I.1): every .sh and .py
under scripts/, and provision/'s scripts, must be 100755 in the index, so
every way of getting the code onto a device -- clone, pull, archive -- gets
the right mode without anyone fixing it afterwards.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


def _index_modes(*pathspecs: str) -> dict[str, str]:
    out = subprocess.run(
        ["git", "ls-files", "-s", "--", *pathspecs],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    ).stdout
    modes = {}
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        modes[path] = meta.split()[0]
    return modes


def test_every_script_under_scripts_is_executable_in_git():
    modes = _index_modes(
        "scripts/*.sh", "scripts/*.py", "scripts/**/*.sh", "scripts/**/*.py"
    )
    assert modes, "found no scripts -- is this a git checkout?"
    missing = sorted(p for p, m in modes.items() if m != "100755")
    assert not missing, (
        "tracked without the execute bit -- fix with:\n"
        "  git update-index --chmod=+x " + " ".join(missing)
    )


def test_every_provisioning_script_is_executable_in_git():
    modes = _index_modes("provision/*.sh")
    missing = sorted(p for p, m in modes.items() if m != "100755")
    assert not missing, missing
