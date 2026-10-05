"""`cmd | grep -q` under `set -o pipefail` is a race; no script may use it.

grep -q exits at its first match and closes the pipe.  If cmd is still
writing, it dies of SIGPIPE (status 141) and pipefail reports the whole
pipeline as failed -- so a check for something that IS there reports it
missing, intermittently, depending on how much output follows the match.

Found when diag_status.sh reported bt_hid_ble.service as "inactive/missing"
while systemctl showed it running: `systemctl list-units | grep -q`.  A
producer that matched early and kept writing reproduced it 30 times out of
30.  It was in 45 pipelines across 20 scripts, including the provisioning
audit, where a false failure fails a good install.

Use `grepq` (defined in each script: `grepq() { grep "$@" >/dev/null; }`),
which reads to the end and has the same exit status.  A file argument with no
pipe is fine -- there is no producer to kill.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
PIPE_GREP_Q = re.compile(r"\|\s*grep\s+-[A-Za-z]*q")


def _pipefail_scripts():
    for p in sorted((ROOT / "scripts").rglob("*.sh")) + sorted((ROOT / "provision").rglob("*.sh")):
        text = p.read_text(encoding="utf-8", errors="replace")
        if "pipefail" in text:
            yield p, text


def test_no_pipeline_ends_in_grep_q_under_pipefail():
    offenders = []
    for path, text in _pipefail_scripts():
        for n, line in enumerate(text.splitlines(), 1):
            code = line.split("#", 1)[0]  # the explanatory comments quote it
            if PIPE_GREP_Q.search(code):
                offenders.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()}")
    assert not offenders, "use grepq instead:\n" + "\n".join(offenders)


def test_every_script_that_uses_grepq_defines_it():
    """An undefined grepq fails just as silently as the race it replaces."""
    missing = []
    for path, text in _pipefail_scripts():
        if re.search(r"\|\s*grepq\b", text) and "grepq()" not in text:
            missing.append(str(path.relative_to(ROOT)))
    assert not missing, missing
