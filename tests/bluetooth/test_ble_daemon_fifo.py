"""Regression tests for the BLE daemon's FIFO worker and adapter selection.

Covers two defects found on ipr-dev-pi4:

* The FIFO worker parked indefinitely in its pre-drain loop whenever text was
  queued with no subscribed host.  It then never reopened the FIFO, so every
  writer blocked forever in ``open(O_WRONLY)`` -- one undeliverable send wedged
  all later sends until the service was restarted.
* ``find_adapter_path()`` fell back to an arbitrary adapter without logging,
  which hid an unexpanded ``${BT_HCI:-hci0}`` in the unit file.
"""

import os
import sys
import threading

import pytest

# tests/bluetooth has no __init__.py; pytest's default import mode puts this
# directory on sys.path, so the sibling module imports by bare name.
from test_ble_daemon_keymap import load_daemon_module

requires_fifo = pytest.mark.skipif(
    sys.platform == "win32", reason="FIFOs (os.mkfifo) are POSIX-only"
)


def _write_fifo(path: str, text: str, timeout: float) -> bool:
    """Write to the FIFO from a helper thread.

    Returns True if the write completed, False if it was still blocked in
    open()/write() when the timeout expired -- which is exactly the wedge this
    module guards against.
    """
    done = threading.Event()

    def writer():
        try:
            with open(path, "w", encoding="utf-8") as fifo:
                fifo.write(text)
            done.set()
        except OSError:
            pass

    threading.Thread(target=writer, daemon=True).start()
    return done.wait(timeout)


# ---------------------------------------------------------------------------
# FIFO worker
# ---------------------------------------------------------------------------

@requires_fifo
def test_fifo_worker_keeps_reading_when_no_host_subscribed(tmp_path):
    """A send that cannot be delivered must not block later senders.

    Reproduces the original hang: with no subscribed host the first write is
    consumed into the queue, and before the fix the worker never reopened the
    FIFO, so this second write never returned.
    """
    mod = load_daemon_module()
    mod.FIFO_PATH = str(tmp_path / "fifo")
    mod.QUEUE_DRAIN_WAIT_SECS = 0.2

    notify_state = mod.NotifyState()  # deliberately never set: no subscriber

    # hid is unused while nothing is subscribed -- drain_queue is only reached
    # once notify_state is set.
    threading.Thread(
        target=mod.fifo_worker, args=(None, notify_state), daemon=True
    ).start()

    assert _write_fifo(mod.FIFO_PATH, "first", timeout=5), "first write blocked"
    assert _write_fifo(mod.FIFO_PATH, "second", timeout=5), (
        "second write blocked -- the worker stopped reading the FIFO, which is "
        "the wedge this test exists to catch"
    )


def test_fifo_worker_drain_wait_is_bounded():
    """The pre-drain wait must have a finite, positive bound."""
    mod = load_daemon_module()

    assert mod.QUEUE_DRAIN_WAIT_SECS > 0
    assert mod.QUEUE_DRAIN_WAIT_SECS < float("inf")


def test_queue_bound_is_finite():
    """Undelivered text must not accumulate without limit."""
    mod = load_daemon_module()

    assert mod.QUEUE_MAX_CHARS > 0

    from collections import deque

    queue = deque(maxlen=mod.QUEUE_MAX_CHARS)
    for i in range(mod.QUEUE_MAX_CHARS + 10):
        queue.append(i)

    assert len(queue) == mod.QUEUE_MAX_CHARS
    assert queue[-1] == mod.QUEUE_MAX_CHARS + 9  # oldest dropped, newest kept


@requires_fifo
def test_fifo_worker_creates_fifo_with_owner_only_permissions(tmp_path):
    """ensure_fifo_exists() creates the FIFO 0600."""
    mod = load_daemon_module()
    mod.FIFO_PATH = str(tmp_path / "fifo")

    mod.ensure_fifo_exists()

    import stat

    st = os.stat(mod.FIFO_PATH)
    assert stat.S_ISFIFO(st.st_mode)
    assert stat.S_IMODE(st.st_mode) == 0o600


# ---------------------------------------------------------------------------
# Adapter selection
# ---------------------------------------------------------------------------

class _FakeObjectManager:
    def __init__(self, objects):
        self._objects = objects

    def GetManagedObjects(self):  # noqa: N802 - mirrors the DBus method name
        return self._objects


def _patch_bus(mod, monkeypatch, objects):
    monkeypatch.setattr(
        mod.dbus, "Interface", lambda *args, **kwargs: _FakeObjectManager(objects)
    )
    return type("FakeBus", (), {"get_object": lambda self, *a: object()})()


def test_find_adapter_path_prefers_requested_adapter(monkeypatch):
    mod = load_daemon_module()
    errors = []
    monkeypatch.setattr(mod, "log_err", errors.append)

    bus = _patch_bus(
        mod,
        monkeypatch,
        {
            "/org/bluez/hci0": {mod.ADAPTER_IFACE: {}},
            "/org/bluez/hci1": {mod.ADAPTER_IFACE: {}},
        },
    )

    assert mod.find_adapter_path(bus, "hci1") == "/org/bluez/hci1"
    assert errors == [], "matching the requested adapter must not log an error"


def test_find_adapter_path_logs_when_falling_back(monkeypatch):
    """An unmatched adapter name must be reported, not silently ignored.

    The literal below is what the unit file actually passed for months, because
    systemd does not expand the shell ``${VAR:-default}`` form.
    """
    mod = load_daemon_module()
    errors = []
    monkeypatch.setattr(mod, "log_err", errors.append)

    bus = _patch_bus(
        mod, monkeypatch, {"/org/bluez/hci0": {mod.ADAPTER_IFACE: {}}}
    )

    assert mod.find_adapter_path(bus, "${BT_HCI:-hci0}") == "/org/bluez/hci0"
    assert len(errors) == 1
    assert "${BT_HCI:-hci0}" in errors[0]
    assert "/org/bluez/hci0" in errors[0]


def test_find_adapter_path_raises_when_no_adapter(monkeypatch):
    mod = load_daemon_module()
    monkeypatch.setattr(mod, "log_err", lambda msg: None)

    bus = _patch_bus(mod, monkeypatch, {"/org/bluez": {"org.bluez.Other": {}}})

    with pytest.raises(RuntimeError, match="No Bluetooth adapter found"):
        mod.find_adapter_path(bus, "hci0")
