"""Unit tests for the shared transmission state module."""

import threading
import importlib


def _reset():
    """Re-import the module to reset global state between tests."""
    import ipr_keyboard.transmission as tx
    import importlib
    importlib.reload(tx)
    return tx


def test_initial_state_is_idle():
    tx = _reset()
    assert tx.get()["state"] == "idle"
    assert tx.get()["label"] == "Idle"


def test_set_sending_updates_state():
    tx = _reset()
    tx.set_sending("test")
    state = tx.get()
    assert state["state"] == "sending"
    assert "test" in state["explanation"]


def test_set_success_increments_items_sent():
    tx = _reset()
    tx.set_sending()
    tx.set_success()
    assert tx.get()["items_sent"] == 1
    tx.set_sending()
    tx.set_success()
    assert tx.get()["items_sent"] == 2


def test_set_success_records_timestamp():
    tx = _reset()
    import time
    before = time.time()
    tx.set_sending()
    tx.set_success()
    after = time.time()
    ts = tx.get()["last_success_at"]
    assert ts is not None
    assert before <= ts <= after


def test_set_failed_records_reason():
    tx = _reset()
    tx.set_sending()
    tx.set_failed("timeout")
    state = tx.get()
    assert state["state"] == "failed"
    assert "timeout" in state["explanation"]


def test_set_failed_default_reason():
    tx = _reset()
    tx.set_failed()
    assert "failed" in tx.get()["explanation"].lower()


def test_set_idle_resets():
    tx = _reset()
    tx.set_sending()
    tx.set_idle()
    state = tx.get()
    assert state["state"] == "idle"
    assert state["label"] == "Idle"


def test_get_returns_copy():
    tx = _reset()
    s1 = tx.get()
    s1["state"] = "mutated"
    assert tx.get()["state"] == "idle"


def test_thread_safety():
    tx = _reset()
    errors = []

    def worker():
        try:
            for _ in range(10):
                tx.set_sending("thread")
                tx.set_success()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    state = tx.get()["state"]
    assert state in ("idle", "sending", "success", "failed")
