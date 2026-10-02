"""Unattended provisioning: the answer handling in provision_wizard.sh.

The wizard is sourced in library mode (PROVISION_WIZARD_LIB_ONLY=1), so these
tests exercise the decision functions without provisioning anything.  What is
guarded here is the property the unattended mode rests on: no question is ever
read from stdin, and every answer comes from the answer file or its documented
default.
"""

import pathlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WIZARD = REPO_ROOT / "provision" / "provision_wizard.sh"

BASH = shutil.which("bash")
requires_bash = pytest.mark.skipif(BASH is None, reason="bash not available")
pytestmark = pytest.mark.skipif(
    sys.platform == "win32" and BASH is None, reason="needs a POSIX shell"
)


def run_lib(snippet: str, answer_file: Path | None = None, stdin: str = "") -> str:
    """Source the wizard in library mode and run ``snippet``."""
    pre = ""
    if answer_file is not None:
        pre = f'ANSWER_FILE="{answer_file.as_posix()}"\n'
    script = (
        f'PROVISION_WIZARD_LIB_ONLY=1 source "{WIZARD.as_posix()}"\n' + pre + snippet
    )
    res = subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, input=stdin, timeout=60
    )
    assert res.returncode == 0, f"stdout={res.stdout!r} stderr={res.stderr!r}"
    return res.stdout


@requires_bash
def test_help_and_step_list_need_no_root():
    for flag in ("--help", "--list-steps"):
        res = subprocess.run(
            [BASH, str(WIZARD), flag], capture_output=True, text=True, timeout=60
        )
        assert res.returncode == 0, res.stderr
        assert res.stdout.strip()
    res = subprocess.run(
        [BASH, str(WIZARD), "--list-steps"], capture_output=True, text=True, timeout=60
    )
    assert "Verify: System and service check" in res.stdout


@requires_bash
def test_unknown_option_is_rejected():
    res = subprocess.run(
        [BASH, str(WIZARD), "--nonsense"], capture_output=True, text=True, timeout=60
    )
    assert res.returncode == 2 and "Unknown option" in res.stderr


@requires_bash
def test_answer_for_reads_the_answer_file_else_the_default(tmp_path):
    env = tmp_path / "ipr_common.env"
    env.write_text(
        '# a comment\nINSTALL_COPILOT_TOOLS="no"\nRECLONE_REPO = yes\nUNRELATED=x\n',
        encoding="utf-8",
    )
    out = run_lib(
        "answer_for INSTALL_COPILOT_TOOLS yes\n"
        "answer_for RECLONE_REPO no\n"
        "answer_for AUTO_REBOOT yes\n",
        answer_file=env,
    )
    assert out.split() == ["no", "yes", "yes"]


@requires_bash
def test_answer_for_falls_back_when_the_file_is_absent(tmp_path):
    out = run_lib("answer_for ANYTHING fallback\n", answer_file=tmp_path / "absent")
    assert out.strip() == "fallback"


@requires_bash
def test_unattended_never_reads_stdin(tmp_path):
    """The decisive property: stdin is closed and nothing blocks or consumes it."""
    env = tmp_path / "env"
    env.write_text("RECLONE_REPO=yes\n", encoding="utf-8")
    out = run_lib(
        "UNATTENDED=1\n"
        'if ask_yes_no "Delete and re-clone?" no RECLONE_REPO; then echo YES; else echo NO; fi\n'
        'if ask_yes_no "Something with no key?" no; then echo YES2; else echo NO2; fi\n'
        "prompt_continue && echo CONTINUED\n"
        "cat  # would hang or echo if stdin had been consumed\n",
        answer_file=env,
        stdin="",
    )
    assert "YES" in out and "NO2" in out and "CONTINUED" in out


@requires_bash
def test_interactive_ask_yes_no_still_reads_the_answer(tmp_path):
    out = run_lib(
        'UNATTENDED=0\nif ask_yes_no "Proceed?" no; then echo YES; else echo NO; fi\n',
        answer_file=tmp_path / "absent",
        stdin="y\n",
    )
    assert "YES" in out


@requires_bash
def test_interactive_empty_answer_takes_the_default(tmp_path):
    out = run_lib(
        'UNATTENDED=0\nif ask_yes_no "Proceed?" yes; then echo YES; else echo NO; fi\n',
        answer_file=tmp_path / "absent",
        stdin="\n",
    )
    assert "YES" in out


@requires_bash
def test_yes_no_spellings():
    out = run_lib(
        "for v in yes YES y 1 true; do is_yes $v && echo y || echo n; done\n"
        "for v in no NO n 0 false; do is_no $v && echo y || echo n; done\n"
    )
    assert out.split() == ["y"] * 10


@requires_bash
def test_the_resume_menu_is_skipped_before_it_can_prompt():
    """--resume/--unattended must reach the steps without the start-over menu."""
    text = WIZARD.read_text(encoding="utf-8")
    resume_branch = text.index("elif (( RESUME ))")
    menu_branch = text.index('elif [[ -f "$STATE_FILE" ]]')
    assert resume_branch < menu_branch, "the menu would be reached while resuming"
    assert "Enter choice [1/2/3]" in text[menu_branch:], "menu prompts moved"


@requires_bash
def test_no_unguarded_prompt_in_the_provisioning_steps():
    """Every read in the step bodies sits behind an UNATTENDED check."""
    text = WIZARD.read_text(encoding="utf-8")
    body = text.split("# Step 1: Install git", 1)[1]
    unguarded = []
    for block in body.split("read -r")[:-1]:
        tail = block[-900:]
        if "UNATTENDED" not in tail:
            unguarded.append(tail.strip().splitlines()[-1][:80])
    assert not unguarded, f"unguarded prompts: {unguarded}"


@requires_bash
def test_a_crlf_answer_file_is_read_correctly(tmp_path):
    """common.env is edited on Windows; a trailing CR must not flip an answer."""
    env = tmp_path / "crlf.env"
    env.write_bytes(b'INSTALL_COPILOT_TOOLS="no"\r\nAUTO_REBOOT=yes\r\n')
    out = run_lib(
        "UNATTENDED=1\n"
        'if is_no "$(answer_for INSTALL_COPILOT_TOOLS yes)"; then echo SKIP; else echo INSTALL; fi\n'
        'if is_yes "$(answer_for AUTO_REBOOT no)"; then echo REBOOT; else echo STAY; fi\n',
        answer_file=env,
    )
    assert "SKIP" in out and "REBOOT" in out


@requires_bash
def test_crlf_on_stdin_does_not_break_an_interactive_answer(tmp_path):
    out = run_lib(
        'UNATTENDED=0\nif ask_yes_no "Proceed?" no; then echo YES; else echo NO; fi\n',
        answer_file=tmp_path / "absent",
        stdin="y\r\n",
    )
    assert "YES" in out


@requires_bash
def test_the_venv_script_never_prompts_for_sudo():
    """It runs as the app user, where a prompting sudo has no terminal.

    Provisioning step 03 reaches scripts/sys_setup_venv.sh through
    `sudo -u "$APP_USER"`, so a bare `sudo` inside it cannot ask for a
    password: it killed an unattended run at step 9 while installing tmux.
    Only `sudo -n`, which fails instead of prompting, is allowed.
    (sys_install_packages.sh is deliberately not covered: its sudo calls sit
    in the --system-only branch, which the wizard runs as root.)
    """
    import re

    path = REPO_ROOT / "scripts" / "sys_setup_venv.sh"
    text = path.read_text(encoding="utf-8")
    assert "# sudo: no" in text, "the script's own header no longer claims sudo: no"

    offenders = []
    for num, line in enumerate(text.splitlines(), 1):
        code = line.split("#", 1)[0]
        code = re.sub(r"\"[^\"]*\"|'[^']*'", "", code)  # drop quoted text
        for match in re.finditer(r"\bsudo\b(.*)", code):
            if not match.group(1).lstrip().startswith("-n"):
                offenders.append(f"{num}: {line.strip()[:70]}")
    assert not offenders, "sudo that could prompt:\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# The audit leaves a report behind
# ---------------------------------------------------------------------------

AUDIT = REPO_ROOT / "scripts" / "headless" / "test_provision.sh"


@requires_bash
def test_the_audit_writes_a_colour_free_report_and_keeps_its_exit_code():
    """Extracted verbatim from the audit so the contract is exercised, not read.

    A standalone audit used to leave nothing behind: its result lived only in
    the terminal it was typed in.  The report must strip colour escapes, must
    not swallow the failure count, and must never turn an unwritable path into
    a failed audit.
    """
    # The scripts are stored with CRLF; bash would take the stray CR as part
    # of the last token on every line.
    text = AUDIT.read_text(encoding="utf-8").replace("\r\n", "\n")
    start = text.index('REPORT_FILE="${REPORT_FILE:-')
    end = text.index("# ── result tracking")
    harness = (
        "#!/usr/bin/env bash\nset -uo pipefail\n"
        + text[start:end]
        + '\nprintf "plain line\n"\n'
        + "printf '\033[0;32mgreen line\033[0m\n'\n"
        + 'if [ -n "${_REPORT_ACTIVE:-}" ]; then exec 1>&- 2>&-; wait 2>/dev/null || true; fi\n'
        + "exit 3\n"
    )
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        script = f"{tmp}/audit_head.sh"
        report = f"{tmp}/report.log"
        with open(script, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(harness)

        res = subprocess.run(
            [BASH, script, "--auto", "--report", report],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert res.returncode == 3, "the failure count must survive the report"
        assert "\x1b[" in res.stdout, "the terminal keeps its colours"
        with open(report, encoding="utf-8") as fh:
            written = fh.read()
        assert "plain line" in written and "green line" in written
        assert "\x1b[" not in written, "the report must be colour-free"

        # An unwritable path costs the report, not the audit.
        res = subprocess.run(
            [BASH, script, "--auto", "--report", "/proc/nope/report.log"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert res.returncode == 3
        assert "cannot write" in res.stderr


@requires_bash
def test_the_audit_targets_the_app_user_not_whoever_ran_it(tmp_path):
    """Started from the wizard's systemd unit there is no SUDO_USER.

    The audit then resolved to root and checked /root/dev/ipr-keyboard: 14
    checks failed on a healthy device and the unattended run reported failure
    when it had in fact succeeded.  APP_USER from the env file is the
    authoritative answer to "which account is this audit about".
    """
    import os
    import subprocess

    # The scripts are stored with CRLF; bash would take the stray CR as part
    # of the last token on every line.
    text = AUDIT.read_text(encoding="utf-8").replace("\r\n", "\n")
    block = text[
        text.index('IPR_COMMON_ENV="${IPR_COMMON_ENV:-') : text.index("# ── arguments")
    ]

    env_file = tmp_path / "ipr_common.env"
    env_file.write_text(
        'APP_USER="someapp"\nREPO_DIR="/srv/elsewhere/ipr-keyboard"\n',
        encoding="utf-8",
        newline="\n",
    )
    script = tmp_path / "resolve.sh"
    script.write_text(
        "#!/usr/bin/env bash\nset -uo pipefail\n"
        + block
        + '\necho "USER=$_INVOKING_USER"\necho "DIR=$PROJECT_DIR"\n',
        encoding="utf-8",
        newline="\n",
    )

    def resolve(**overrides):
        env = {**os.environ, "USER": "nobody"}
        env.pop("SUDO_USER", None)
        env.update(overrides)
        return subprocess.run(
            [BASH, script.as_posix()],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        ).stdout

    # No SUDO_USER at all -- the resume-unit case.  The env file decides.
    out = resolve(IPR_COMMON_ENV=env_file.as_posix())
    assert "USER=someapp" in out, out
    assert "DIR=/srv/elsewhere/ipr-keyboard" in out, out

    # Without an env file it falls back to SUDO_USER, then $USER.
    absent = (tmp_path / "absent").as_posix()
    assert "USER=admin" in resolve(IPR_COMMON_ENV=absent, SUDO_USER="admin")
    assert "USER=nobody" in resolve(IPR_COMMON_ENV=absent)
