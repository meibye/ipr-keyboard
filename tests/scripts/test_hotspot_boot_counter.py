"""The triple-power-cycle hotspot trigger counts boots, not script runs.

It used to count every execution of ipr-provision.sh, and the service is
restarted by install_provision_service.sh -- which a routine full update
runs.  So "update, it fails, update again, reboot" inside the 120 s window
reached the trigger and took the device off its home Wi-Fi into hotspot mode,
for no reason anyone could see.  The kernel's per-boot ID now tells a reboot
from a restart.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "headless" / "net_provision_hotspot.sh"
LF = "\n"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")


def _function_source() -> str:
    text = SCRIPT.read_text(encoding="utf-8").replace("\r\n", LF)
    start = text.index("check_boot_count() {")
    end = text.index(LF + "}" + LF, start) + 3
    return text[start:end]


@pytest.fixture
def boot(tmp_path):
    # Relative paths, run from tmp_path: Git Bash wants /c/Users/..., WSL's
    # bash wants /mnt/c/..., and neither accepts C:/Users/... -- but every
    # bash agrees on a relative path.
    (tmp_path / "fn.sh").write_text(_function_source(), encoding="utf-8", newline=LF)
    counter = tmp_path / "boot-count"
    bootid = tmp_path / "boot_id"

    # The driver goes in a FILE.  Passed as `bash -c <script>` it crosses the
    # Windows command line, where MSYS bash re-parses the quoting differently
    # from how Python built it: `cut -d" "` lost its quoted delimiter and the
    # test read nothing.  A file is read by bash itself, on every platform.
    (tmp_path / "driver.sh").write_text(
        LF.join(
            [
                "log() { :; }",
                'BOOT_COUNT_FILE="boot-count"',
                "BOOT_COUNT_WINDOW=120",
                "BOOT_COUNT_TRIGGER=3",
                'BOOT_ID_FILE="boot_id"',
                'source "./fn.sh"',
                "if check_boot_count; then echo HOTSPOT; "
                'else cut -d" " -f1 "$BOOT_COUNT_FILE"; fi',
                "",
            ]
        ),
        encoding="utf-8",
        newline=LF,
    )

    def run(boot_id: str) -> str:
        bootid.write_text(boot_id + LF, encoding="ascii", newline=LF)
        out = subprocess.run(
            ["bash", "driver.sh"],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=tmp_path,
        )
        assert out.returncode == 0, out.stderr
        return out.stdout.strip()

    run.counter = counter
    return run


def test_restarting_the_service_within_one_boot_does_not_count(boot):
    assert boot("A") == "1"
    assert [boot("A") for _ in range(5)] == ["1"] * 5


def test_three_real_boots_in_the_window_still_start_the_hotspot(boot):
    assert boot("A") == "1"
    assert boot("B") == "2"
    assert boot("C") == "HOTSPOT"


def test_an_update_run_twice_then_a_reboot_does_not_trigger_it(boot):
    """The scenario that used to take the device off its Wi-Fi."""
    assert boot("A") == "1"  # the update restarts the service
    assert boot("A") == "1"  # ... and runs again after a failure
    assert boot("B") == "2"  # then a reboot


def test_a_counter_file_from_before_the_fix_still_works(boot):
    """Devices in the field have "count time" with no boot ID."""
    boot.counter.write_text(f"2 {int(time.time())}" + LF, encoding="ascii", newline=LF)
    assert boot("Z") == "HOTSPOT"
