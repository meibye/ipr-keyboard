"""How hard the BLE daemon advertises, and why it is driven by the link.

A reboot drops the BLE link and the device is a peripheral: it advertises and
waits for the PC to come back.  Measured on a Zero 2 W with the old default
interval, a Windows host took 26 minutes.  Advertising fast closes that gap —
but only if the device is still advertising fast when the host looks, which is
what these tests are about.
"""

from __future__ import annotations

import pytest

from test_ble_daemon_keymap import load_daemon_module


@pytest.fixture
def daemon():
    mod = load_daemon_module()
    # The shared stub maps dbus.Array to list, which takes no signature kwarg,
    # and has no UInt32 at all -- the keymap tests never build an
    # advertisement.  Make those two tolerant for this module only.
    mod.dbus.Array = lambda seq, signature=None: list(seq)
    mod.dbus.UInt32 = int
    mod.dbus.Boolean = bool
    # Each test starts from "nothing has ever connected", as after a boot.
    mod._adv_state["connected"] = None
    mod._adv_state["disconnected_since"] = 1000.0
    mod._adv_control["set_mode"] = None
    return mod


# ---------------------------------------------------------------------------
# The policy
# ---------------------------------------------------------------------------


def test_a_connected_host_earns_the_slow_interval(daemon):
    """Nothing needs to find us while the PC is already here."""
    assert daemon.desired_adv_mode(True, now=1000.0) == "slow"
    assert daemon.desired_adv_mode(True, now=9_999_999.0) == "slow"


def test_fast_right_after_the_link_goes(daemon):
    """A host that has just lost us is the one scanning soonest."""
    assert daemon.desired_adv_mode(False, now=1000.0) == "fast"
    assert (
        daemon.desired_adv_mode(False, now=1000.0 + daemon.FAST_ADV_SECS - 1) == "fast"
    )


def test_it_never_goes_quiet_while_the_pc_is_missing(daemon):
    """The bug this guards, and it was shipped once.

    The first version backed straight off to the SLOW interval once
    FAST_ADV_SECS expired, even though no host had ever connected.  A device
    still waiting for its PC therefore went quiet exactly five minutes in —
    the worst possible moment — and that is what happened on the device: fast
    from 18:07:34, slow from 18:12:34, with the PC still absent.
    """
    later = 1000.0 + daemon.FAST_ADV_SECS + 1
    assert daemon.desired_adv_mode(False, now=later) == "medium"
    # ... and stays findable for as long as it takes, not just for a while.
    assert daemon.desired_adv_mode(False, now=1000.0 + 86_400) == "medium"


def test_medium_is_between_the_two_and_still_findable(daemon):
    fast_lo, fast_hi = daemon.ADV_MODES["fast"]
    med_lo, med_hi = daemon.ADV_MODES["medium"]
    slow_lo, slow_hi = daemon.ADV_MODES["slow"]
    assert fast_lo < med_lo < slow_lo
    assert fast_hi < med_hi < slow_hi
    # Well under BlueZ's default of over a second, which is the whole point.
    assert med_hi <= 500


# ---------------------------------------------------------------------------
# Reacting to the link
# ---------------------------------------------------------------------------


def test_losing_the_host_re_arms_the_fast_interval(daemon):
    """The back-off used to be one-way, so a PC that slept was never chased."""
    seen = []
    daemon._adv_control["set_mode"] = seen.append

    daemon.note_link_state(True, now=2000.0)
    assert seen[-1] == "slow"

    daemon.note_link_state(False, now=2100.0)
    assert seen[-1] == "fast", "a dropped link must bring the fast interval back"

    # The clock restarts from the disconnect, not from boot.
    assert (
        daemon.desired_adv_mode(False, now=2100.0 + daemon.FAST_ADV_SECS - 1) == "fast"
    )
    assert (
        daemon.desired_adv_mode(False, now=2100.0 + daemon.FAST_ADV_SECS + 1)
        == "medium"
    )


def test_a_repeated_state_does_not_restart_the_clock(daemon):
    """The 30 s tick reports "still disconnected" over and over."""
    daemon._adv_control["set_mode"] = lambda _m: None
    daemon.note_link_state(False, now=3000.0)
    for t in range(3030, 3300, 30):
        daemon.note_link_state(False, now=float(t))
    # The window is measured from the disconnect, so it has really elapsed.
    assert daemon._adv_state["disconnected_since"] == 3000.0


def test_a_failing_set_mode_cannot_break_the_connection(daemon):
    """Advertising is a convenience; typing is the job."""

    def _boom(_mode):
        raise RuntimeError("bluez said no")

    daemon._adv_control["set_mode"] = _boom
    daemon.note_link_state(True, now=4000.0)  # must not raise


def test_no_control_registered_is_harmless(daemon):
    """note_link_state runs before the stack is registered, at startup."""
    daemon._adv_control["set_mode"] = None
    daemon.note_link_state(False, now=5000.0)


# ---------------------------------------------------------------------------
# What BlueZ is actually asked for
# ---------------------------------------------------------------------------


def test_the_advertisement_carries_the_interval_for_its_mode(daemon):
    adv = daemon.Advertisement(None, 0, [daemon.UUID_HID_SERVICE], "IPR Keyboard")
    assert adv.mode == "fast", "a fresh daemon has nobody connected"

    props = adv.get_properties()[daemon.ADVERTISEMENT_IFACE]
    assert props["MinInterval"] == daemon.FAST_ADV_MIN_MS
    assert props["MaxInterval"] == daemon.FAST_ADV_MAX_MS
    assert props["Discoverable"] is True

    adv.mode = "slow"
    props = adv.get_properties()[daemon.ADVERTISEMENT_IFACE]
    assert props["MinInterval"] == daemon.SLOW_ADV_MIN_MS


def test_an_interval_bluez_refuses_leaves_us_still_advertising(daemon):
    """Without an advertisement the host could never come back at all.

    BlueZ ignores properties it does not know, so an older one just advertises
    at its own rate; one that actively refuses the value must not cost us the
    advertisement itself.
    """
    adv = daemon.Advertisement(None, 0, [daemon.UUID_HID_SERVICE], "IPR Keyboard")
    adv.with_intervals = False
    props = adv.get_properties()[daemon.ADVERTISEMENT_IFACE]
    assert "MinInterval" not in props and "MaxInterval" not in props
    # The parts that matter for being found at all are still there.
    assert props["Discoverable"] is True
    assert props["LocalName"] == "IPR Keyboard"
    assert props["Appearance"] == daemon.APPEARANCE_KEYBOARD
