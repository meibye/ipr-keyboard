"""Recovery credential reveals: the limits that keep a password off the screen."""

from ipr_keyboard import recovery as rc


def _secret(tmp_path, password="0123456789abcdef", ssid="ipr-setup-abcd"):
    p = tmp_path / "ipr-hotspot.secret"
    p.write_text(f'SSID="{ssid}"\nPASSWORD="{password}"\n', encoding="utf-8")
    return str(p)


def _info(tmp_path, limit=3, **kw):
    return rc.RecoveryInfo(
        limit=limit,
        secret_path=_secret(tmp_path, **kw),
        marker_path=str(tmp_path / "recovery_used"),
        count_path=str(tmp_path / "recovery_reveals"),
    )


def test_a_reveal_returns_the_credentials_and_costs_a_credit(tmp_path):
    info = _info(tmp_path, limit=2)
    assert info.reveals_left() == 2
    lines = info.lines()
    assert any("ipr-setup-abcd" in line for line in lines)
    assert any("0123456789abcdef" in line for line in lines)
    assert any(rc.SETUP_URL in line for line in lines)
    assert info.reveals_left() == 1


def test_the_limit_is_enforced(tmp_path):
    info = _info(tmp_path, limit=2)
    assert info.lines() and info.lines()
    assert info.reveals_left() == 0
    assert info.lines() == (), "nothing once the limit is spent"


def test_a_limit_of_zero_never_reveals(tmp_path):
    info = _info(tmp_path, limit=0)
    assert info.reveals_left() == 0 and info.lines() == ()


def test_used_credentials_are_never_shown_again(tmp_path):
    secret = _secret(tmp_path)
    marker = str(tmp_path / "recovery_used")
    count = str(tmp_path / "recovery_reveals")
    info = rc.RecoveryInfo(
        limit=3, secret_path=secret, marker_path=marker, count_path=count
    )
    assert info.reveals_left() == 3

    rc.mark_used(secret, marker)  # the portal accepted a login with them
    assert info.reveals_left() == 0
    assert info.lines() == ()
    # and it survives a restart
    assert rc.RecoveryInfo(3, secret, marker, count).reveals_left() == 0


def test_a_regenerated_key_clears_the_used_mark(tmp_path):
    secret = _secret(tmp_path)
    marker = str(tmp_path / "recovery_used")
    rc.mark_used(secret, marker)
    assert rc.already_used(secret, marker)

    _secret(tmp_path, password="a-brand-new-key")  # provisioning regenerated it
    assert not rc.already_used(secret, marker), "a new password has not been used"
    assert (
        rc.RecoveryInfo(
            3, secret, marker, str(tmp_path / "recovery_reveals")
        ).reveals_left()
        == 3
    )


def test_a_missing_secret_reveals_nothing(tmp_path):
    info = rc.RecoveryInfo(
        limit=3,
        secret_path=str(tmp_path / "absent"),
        marker_path=str(tmp_path / "recovery_used"),
        count_path=str(tmp_path / "recovery_reveals"),
    )
    assert info.reveals_left() == 0 and info.lines() == ()
    assert rc.fingerprint(str(tmp_path / "absent")) == ""


def test_marking_an_unreadable_secret_is_not_fatal(tmp_path):
    rc.mark_used(str(tmp_path / "absent"), str(tmp_path / "marker"))
    assert not (tmp_path / "marker").exists()


def test_the_count_survives_a_restart(tmp_path):
    """A reboot must not hand out a fresh allowance."""
    secret = _secret(tmp_path)
    marker = str(tmp_path / "recovery_used")
    count = str(tmp_path / "recovery_reveals")

    first = rc.RecoveryInfo(
        limit=3, secret_path=secret, marker_path=marker, count_path=count
    )
    assert first.lines() and first.lines()
    assert first.reveals_left() == 1

    # a new process (the device rebooted) reads the same file
    after_reboot = rc.RecoveryInfo(
        limit=3, secret_path=secret, marker_path=marker, count_path=count
    )
    assert after_reboot.reveals_left() == 1
    assert after_reboot.lines()
    assert after_reboot.reveals_left() == 0
    assert rc.RecoveryInfo(3, secret, marker, count).lines() == ()


def test_a_new_key_starts_a_new_allowance(tmp_path):
    secret = _secret(tmp_path)
    marker = str(tmp_path / "recovery_used")
    count = str(tmp_path / "recovery_reveals")
    info = rc.RecoveryInfo(
        limit=1, secret_path=secret, marker_path=marker, count_path=count
    )
    assert info.lines() and info.reveals_left() == 0

    _secret(tmp_path, password="a-freshly-generated-key")
    assert rc.RecoveryInfo(1, secret, marker, count).reveals_left() == 1
