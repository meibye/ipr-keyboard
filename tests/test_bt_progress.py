"""Reading the BLE daemon's typing progress.

bt_kb_send.sh returns as soon as the text is on the FIFO, so without this the
application cannot tell when the characters actually reached the host: a send
looked finished in milliseconds while the daemon typed for seconds.
"""

import json

from ipr_keyboard import bt_progress as bp


def _write(path, state="typing", total=100, sent=10, at=None):
    import time

    path.write_text(
        json.dumps(
            {"state": state, "total": total, "sent": sent, "at": at or time.time()}
        ),
        encoding="utf-8",
    )
    return str(path)


def test_reads_the_daemons_progress(tmp_path):
    p = _write(tmp_path / "progress.json", sent=25, total=100)
    got = bp.read(p)
    assert got.typing and got.known
    assert got.sent == 25 and got.total == 100
    assert abs(got.fraction - 0.25) < 1e-9


def test_no_file_means_unknown_not_idle(tmp_path):
    """An older daemon publishes nothing; callers must not wait on it."""
    got = bp.read(str(tmp_path / "absent"))
    assert not got.known and not got.typing


def test_a_stale_file_is_not_treated_as_news(tmp_path):
    p = _write(tmp_path / "progress.json", at=1000.0)
    assert not bp.read(p, now=1000.0 + bp.STALE_AFTER_S + 1).known


def test_rubbish_is_not_fatal(tmp_path):
    p = tmp_path / "progress.json"
    p.write_text("not json at all", encoding="utf-8")
    assert not bp.read(str(p)).known


def test_waiting_returns_at_once_when_the_daemon_says_nothing(tmp_path):
    """A send must never hang because progress reporting is missing."""
    calls = []
    got = bp.wait_until_idle(str(tmp_path / "absent"), sleep=lambda _s: calls.append(1))
    assert not got.known and calls == []


def test_waiting_returns_when_typing_finishes(tmp_path):
    p = tmp_path / "progress.json"
    _write(p, state="typing", total=3, sent=0)
    steps = iter([("typing", 1), ("typing", 2), ("idle", 3)])
    seen = []

    def fake_sleep(_s):
        try:
            state, sent = next(steps)
        except StopIteration:
            return
        _write(p, state=state, total=3, sent=sent)

    got = bp.wait_until_idle(
        str(p), sleep=fake_sleep, on_progress=lambda pr: seen.append(pr.sent)
    )
    assert got.state == "idle" and got.sent == 3
    assert seen, "progress was reported while waiting"


def test_waiting_gives_up_rather_than_hanging(tmp_path):
    p = _write(tmp_path / "progress.json", state="typing")
    ticks = iter(range(1000))
    got = bp.wait_until_idle(
        p, timeout_s=5, clock=lambda: next(ticks), sleep=lambda _s: None
    )
    assert got.typing, "the daemon died mid-text; we stop waiting"


def test_a_stale_file_still_proves_the_daemon_publishes(tmp_path):
    p = _write(tmp_path / "progress.json", at=1000.0)
    assert bp.publishes(p), "age says nothing about whether it reports at all"
    assert not bp.publishes(str(tmp_path / "absent"))


def test_waiting_does_not_give_up_on_a_send_that_follows_a_quiet_spell(tmp_path):
    """The bug this guards: no panel progress and no measurement after idling.

    When the wait begins, the text has only been QUEUED -- the newest reading
    is the previous send's, which `read` collapses to UNKNOWN once it is older
    than STALE_AFTER_S.  Treating that as "this daemon says nothing" skipped
    the wait entirely, so every send that followed more than two minutes of
    quiet showed no progress on the panel and recorded no typing metric.  That
    is the commonest case there is: an idle device, then one scan.
    """
    p = tmp_path / "progress.json"
    _write(p, state="idle", total=3, sent=3, at=1.0)  # ancient: UNKNOWN to read()
    assert not bp.read(str(p)).known

    steps = iter([("typing", 1), ("typing", 2), ("idle", 3)])

    def _tick(_s):
        try:
            state, sent = next(steps)
        except StopIteration:
            return
        _write(p, state=state, total=3, sent=sent)

    seen = []
    got = bp.wait_until_idle(
        str(p), poll_s=0.0, sleep=_tick, on_progress=lambda pr: seen.append(pr.sent)
    )
    assert got.state == "idle" and got.sent == 3, got
    assert seen, "the caller was told about the typing it would otherwise have missed"


def test_waiting_gives_up_when_the_typing_never_starts(tmp_path):
    """No host subscribed: cost the start timeout, then behave as before."""
    p = _write(tmp_path / "progress.json", state="idle", at=1.0)
    ticks = []
    t = [0.0]

    def _clock():
        return t[0]

    def _sleep(_s):
        ticks.append(1)
        t[0] += 0.1

    got = bp.wait_until_idle(
        p, poll_s=0.1, clock=_clock, sleep=_sleep, start_timeout_s=0.5
    )
    assert not got.typing
    assert 1 <= len(ticks) <= 10, len(ticks)

