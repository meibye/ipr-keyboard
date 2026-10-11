"""07_show_info.sh prints the device's passwords only to a terminal.

The provisioning wizard tees everything it prints into
/opt/ipr_state/provision_wizard.log, and after a reboot it runs as a service
whose output lands in the journal.  Step 14 printed the hotspot key and the
first dashboard password there -- into a file any user on the device could
read.  Off a terminal the summary now points at credentials.txt (root only),
which always gets the values.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "provision" / "07_show_info.sh"
LF = "\n"
HOTSPOT_PASS = "Hs-Secret-4711"
ADMIN_PASS = "Adm-Secret-0815"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")


@pytest.fixture
def show_info(tmp_path):
    # Relative paths and a driver FILE, as in test_hotspot_boot_counter.py:
    # every bash agrees on those, on Windows too.
    shutil.copy(SCRIPT, tmp_path / "show_info.sh")
    (tmp_path / "bin").mkdir()
    # The script insists on root; `id -u` answers 0 here.
    (tmp_path / "bin" / "id").write_text("#!/bin/sh" + LF + "echo 0" + LF, newline=LF)
    (tmp_path / "common.env").write_text('REPO_DIR="."' + LF, newline=LF)
    (tmp_path / "hotspot.secret").write_text(
        "SSID=ipr-setup-test" + LF + f"PASS={HOTSPOT_PASS}" + LF, newline=LF
    )
    (tmp_path / "admin_initial_password.txt").write_text(ADMIN_PASS + LF, newline=LF)

    def run(*args: str) -> tuple[str, str]:
        (tmp_path / "driver.sh").write_text(
            LF.join(
                [
                    'chmod +x bin/id; PATH="./bin:$PATH"',
                    "export IPR_COMMON_ENV=common.env",
                    "export IPR_HOTSPOT_SECRET=hotspot.secret",
                    "export IPR_CREDENTIALS_FILE=state/credentials.txt",
                    "bash show_info.sh " + " ".join(args),
                    "",
                ]
            ),
            newline=LF,
        )
        out = subprocess.run(
            ["bash", "driver.sh"],
            capture_output=True,  # stdout is a pipe, as under the wizard
            text=True,
            encoding="utf-8",  # the summary draws boxes in UTF-8
            errors="replace",
            timeout=30,
            cwd=tmp_path,
        )
        assert out.returncode == 0, out.stderr
        creds = (tmp_path / "state" / "credentials.txt").read_text(encoding="utf-8")
        return out.stdout, creds

    return run


def test_piped_output_holds_no_password(show_info):
    stdout, creds = show_info()
    assert HOTSPOT_PASS not in stdout and ADMIN_PASS not in stdout
    assert "state/credentials.txt" in stdout  # where to find them instead
    assert "SSID" in stdout and "ipr-setup-test" in stdout  # the rest is shown


def test_credentials_file_always_has_them(show_info):
    _, creds = show_info()
    assert f"hotspot_password      = {HOTSPOT_PASS}" in creds
    assert f"admin / {ADMIN_PASS}" in creds


def test_show_secrets_prints_them(show_info):
    stdout, _ = show_info("--show-secrets")
    assert HOTSPOT_PASS in stdout and ADMIN_PASS in stdout


def test_hide_secrets_never_prints_them(show_info):
    stdout, _ = show_info("--hide-secrets")
    assert HOTSPOT_PASS not in stdout and ADMIN_PASS not in stdout


def test_an_unknown_option_is_refused(show_info, tmp_path):
    with pytest.raises(AssertionError):
        show_info("--everything")


def test_the_wizard_log_is_root_only_and_step_14_bypasses_it():
    wizard = (ROOT / "provision" / "provision_wizard.sh").read_text(encoding="utf-8")
    tee = wizard.index('exec > >(tee -a "$LOG_FILE")')
    assert 'chmod 0600 "$LOG_FILE"' in wizard[:tee]
    assert "07_show_info.sh --show-secrets > /dev/tty" in wizard
