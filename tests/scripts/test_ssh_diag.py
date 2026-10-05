"""Tests for scripts/lib/ssh_diag.sh.

The deploy scripts used to discard ssh's stderr, so every failed key login --
device off, name not resolving, new host key, key not installed -- surfaced as a
bare FAIL and read as "install the key".  The suggested ``ssh-copy-id`` then got
run against the bare address, which skips the alias's ``User`` line and logs in
as the local user.  These tests pin the diagnosis and that every suggested
command uses the alias.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "scripts" / "lib" / "ssh_diag.sh"

BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="bash not available")

# Stands in for `ssh -G`, which resolves the alias through ~/.ssh/config.
FAKE_SSH = """
ssh() { printf 'user meibye\nhostname 192.168.1.97\n'; }
"""


def explain(stderr: str, alias: str = "ipr-prod-zero2") -> str:
    script = f'{FAKE_SSH}\nsource "$1"\nssh_explain_failure "$2" "$3"\n'
    result = subprocess.run(
        [BASH, "-c", script, "bash", LIB.as_posix(), alias, stderr],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_changed_host_key_names_the_resolved_address():
    out = explain(
        "Host key for 192.168.1.97 has changed and you have requested "
        "strict checking.\nHost key verification failed."
    )
    assert "ssh-keygen -R 192.168.1.97" in out


def test_permission_denied_suggests_ssh_copy_id_with_the_alias():
    out = explain("meibye@192.168.1.97: Permission denied (publickey).")
    assert "ssh-copy-id -i ~/.ssh/ipr_rpi.pub ipr-prod-zero2" in out
    assert "ssh-copy-id -i ~/.ssh/ipr_rpi.pub 192.168.1.97" not in out
    assert "'meibye'" in out


@pytest.mark.parametrize(
    "stderr, expected",
    [
        (
            "ssh: Could not resolve hostname ipr-dev-pi4.local: Name or service not known",
            "does not resolve",
        ),
        (
            "ssh: connect to host 192.168.1.96 port 22: Connection timed out",
            "No answer",
        ),
        ("ssh: connect to host 192.168.1.96 port 22: No route to host", "No answer"),
        (
            "ssh: connect to host 192.168.1.97 port 22: Connection refused",
            "SSH is not running",
        ),
    ],
)
def test_unreachable_device_is_not_reported_as_a_key_problem(stderr, expected):
    out = explain(stderr)
    assert expected in out
    assert "ssh-copy-id" not in out


def test_unknown_error_passes_ssh_message_through():
    out = explain(
        "debug noise\nkex_exchange_identification: Connection reset by peer\n"
    )
    assert "ssh said: kex_exchange_identification: Connection reset by peer" in out


@pytest.mark.parametrize(
    "script",
    ["scripts/deploy/wsl_setup_ssh.sh", "scripts/deploy/host_push_to_device.sh"],
)
def test_deploy_scripts_keep_ssh_stderr(script):
    text = (REPO_ROOT / script).read_text(encoding="utf-8")
    assert "ssh_diag.sh" in text
    assert "ssh_explain_failure" in text
    assert "true 2>/dev/null; then" not in text.replace("sudo -n true", "")
