"""Tests for shell helpers in scripts/.

Two defects are guarded here:

* ``systemctl list-unit-files | ... | grep -q "$unit"`` under ``set -o pipefail``
  reports an *installed* unit as missing.  ``grep -q`` exits at the first match,
  the still-writing producer dies with SIGPIPE (141), and pipefail surfaces that
  as the pipeline's status.  Observed on ipr-dev-pi4 as ``PIPESTATUS=0 141 0``.
* ``bt_kb_send`` wrote to the FIFO with no timeout, so a daemon that had stopped
  reading blocked the caller forever.
"""

import os
import re
import shutil
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

BASH = shutil.which("bash")
requires_bash = pytest.mark.skipif(BASH is None, reason="bash not available")
requires_posix = pytest.mark.skipif(
    sys.platform == "win32", reason="FIFOs and POSIX signals are not available"
)

# Every script that defines the unit_installed helper.
SCRIPTS_WITH_HELPER = [
    "scripts/ble/diag_pairing.sh",
    "scripts/ble/test_pairing.sh",
    "scripts/diag_troubleshoot.sh",
    "scripts/test_e2e_systemd.sh",
]


def _extract_function(script: Path, name: str) -> str:
    """Pull a shell function's source out of a script.

    Tests the shipped implementation rather than a copy that can drift.
    """
    text = script.read_text(encoding="utf-8")
    match = re.search(
        rf"^(?:function\s+)?{re.escape(name)}\s*\(\)\s*\{{.*?^\}}",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, f"{name}() not found in {script}"
    return match.group(0)


def _make_systemctl_stub(tmp_path: Path, loaded_units: list[str]) -> Path:
    """A fake systemctl whose list-unit-files output is large.

    The size matters: SIGPIPE only fires when the producer is still writing
    when grep exits, so a short output would not reproduce the bug.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    stub = bindir / "systemctl"
    stub.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            LOADED="{' '.join(loaded_units)}"
            if [[ "$1" == "show" ]]; then
                unit="${{@: -1}}"
                for u in $LOADED; do
                    if [[ "$u" == "$unit" ]]; then echo "loaded"; exit 0; fi
                done
                echo "not-found"
                exit 0
            fi
            if [[ "$1" == "is-active" || "$1" == "is-enabled" ]]; then
                unit="${{@: -1}}"
                for u in $LOADED; do
                    if [[ "$u" == "$unit" ]]; then exit 0; fi
                done
                exit 3
            fi
            if [[ "$1" == "list-unit-files" ]]; then
                for u in $LOADED; do echo "$u enabled enabled"; done
                for i in $(seq 1 3000); do echo "filler-$i.service enabled enabled"; done
                exit 0
            fi
            exit 1
            """
        ),
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bindir


def _run_bash(script_body: str, path_prepend: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = f"{path_prepend}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        [BASH, "-c", script_body],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


# ---------------------------------------------------------------------------
# unit_installed()
# ---------------------------------------------------------------------------

@requires_bash
@pytest.mark.parametrize("script_rel", SCRIPTS_WITH_HELPER)
def test_unit_installed_reports_installed_unit(tmp_path, script_rel):
    """An installed unit must report as installed, even under pipefail."""
    fn = _extract_function(REPO_ROOT / script_rel, "unit_installed")
    bindir = _make_systemctl_stub(tmp_path, ["bt_hid_ble.service"])

    result = _run_bash(
        f'set -eo pipefail\n{fn}\n'
        'if unit_installed "bt_hid_ble.service"; then echo INSTALLED; '
        'else echo MISSING; fi',
        bindir,
    )

    assert result.stdout.strip() == "INSTALLED", result.stderr


@requires_bash
@pytest.mark.parametrize("script_rel", SCRIPTS_WITH_HELPER)
def test_unit_installed_reports_absent_unit(tmp_path, script_rel):
    """A unit that is genuinely absent must still report as missing."""
    fn = _extract_function(REPO_ROOT / script_rel, "unit_installed")
    bindir = _make_systemctl_stub(tmp_path, ["bt_hid_ble.service"])

    result = _run_bash(
        f'set -eo pipefail\n{fn}\n'
        'if unit_installed "nope.service"; then echo INSTALLED; '
        'else echo MISSING; fi',
        bindir,
    )

    assert result.stdout.strip() == "MISSING", result.stderr


@pytest.mark.parametrize("script_rel", SCRIPTS_WITH_HELPER)
def test_no_list_unit_files_grep_pipeline_remains(script_rel):
    """Guard against reintroducing the SIGPIPE-prone pattern."""
    text = (REPO_ROOT / script_rel).read_text(encoding="utf-8")
    offenders = [
        line
        for line in text.splitlines()
        if "list-unit-files" in line
        and re.search(r"\|\s*grep\s+-\w*q", line)
        and not line.lstrip().startswith("#")
    ]
    assert offenders == [], f"{script_rel} still pipes list-unit-files into grep -q"


# ---------------------------------------------------------------------------
# bt_kb_send FIFO write timeout
# ---------------------------------------------------------------------------

@requires_bash
@requires_posix
def test_bt_kb_send_times_out_when_no_reader(tmp_path):
    """With no reader on the FIFO the helper must exit, not hang.

    124 is GNU timeout's exit code for "the command timed out".
    """
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo, 0o666)
    bindir = _make_systemctl_stub(tmp_path, ["bt_hid_ble.service"])

    script = (REPO_ROOT / "scripts/ble/bt_kb_send.sh").read_text(encoding="utf-8")
    # Point the helper at the test FIFO instead of /run.
    script = script.replace(
        'FIFO="/run/ipr_bt_keyboard_fifo"', f'FIFO="{fifo}"', 1
    )
    patched = tmp_path / "bt_kb_send.sh"
    patched.write_text(script, encoding="utf-8")

    env = dict(os.environ)
    env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
    env["BT_KB_WRITE_TIMEOUT_SECS"] = "1"

    result = subprocess.run(
        [BASH, str(patched), "hello"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,  # generous: a regression hangs forever, so this bounds it
    )

    assert result.returncode == 124, (
        f"expected timeout exit 124, got {result.returncode}\n{result.stderr}"
    )
    assert "timed out" in result.stderr.lower()


@requires_bash
@requires_posix
def test_bt_kb_send_succeeds_with_a_reader(tmp_path):
    """The timeout must not break the normal path."""
    import threading

    fifo = tmp_path / "fifo"
    os.mkfifo(fifo, 0o666)
    bindir = _make_systemctl_stub(tmp_path, ["bt_hid_ble.service"])

    received = []

    def reader():
        with open(fifo, "r", encoding="utf-8") as handle:
            received.append(handle.read())

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()

    script = (REPO_ROOT / "scripts/ble/bt_kb_send.sh").read_text(encoding="utf-8")
    script = script.replace(
        'FIFO="/run/ipr_bt_keyboard_fifo"', f'FIFO="{fifo}"', 1
    )
    patched = tmp_path / "bt_kb_send.sh"
    patched.write_text(script, encoding="utf-8")

    env = dict(os.environ)
    env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
    env["BT_KB_WRITE_TIMEOUT_SECS"] = "5"

    result = subprocess.run(
        [BASH, str(patched), "hello"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    thread.join(timeout=5)
    assert received == ["hello"]
