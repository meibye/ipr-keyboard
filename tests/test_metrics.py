"""Unit tests for ipr_keyboard.metrics -- the performance KPI store.

The module's whole value is that it is cheap and bounded, so these tests
check exactly those properties rather than just the happy path.
"""
from __future__ import annotations

import threading

import pytest

from ipr_keyboard import metrics


@pytest.fixture(autouse=True)
def _clean():
    metrics.reset()
    metrics.set_enabled(False)
    yield
    metrics.reset()
    metrics.set_enabled(False)


# ---------------------------------------------------------------------------
# Off by default, and a no-op when off
# ---------------------------------------------------------------------------

def test_disabled_by_default():
    assert metrics.is_enabled() is False


def test_record_is_noop_when_disabled():
    metrics.record("send_ms", 12.0)
    metrics.record_poll_scan(0.5)
    metrics.record_file_pipeline(1.0, 2.0, 3.0, 4.0, 10)
    snap = metrics.snapshot()
    assert snap["enabled"] is False
    assert all(v["count"] == 0 for v in snap["kpis"].values())


def test_snapshot_answers_even_when_disabled():
    """The dashboard must be able to tell 'disabled' from 'no data yet'."""
    snap = metrics.snapshot()
    assert set(snap) >= {"enabled", "platform", "boot", "kpis", "buffer_size"}
    assert set(snap["kpis"]) == set(metrics.KPIS)


# ---------------------------------------------------------------------------
# Recording and statistics
# ---------------------------------------------------------------------------

def test_record_unknown_kpi_is_ignored():
    metrics.set_enabled(True)
    metrics.record("not_a_kpi", 1.0)  # must not raise, must not appear
    assert "not_a_kpi" not in metrics.snapshot()["kpis"]


def test_stats_on_known_values():
    metrics.set_enabled(True)
    for v in [10, 20, 30, 40, 100]:
        metrics.record("send_ms", v)
    st = metrics.snapshot()["kpis"]["send_ms"]
    assert st["count"] == 5
    assert st["total"] == 5
    assert st["min"] == 10 and st["max"] == 100
    assert st["mean"] == 40.0
    assert st["p50"] == 30
    assert st["p95"] == 100
    assert st["last"] == 100
    assert st["unit"] == "ms"


def test_single_sample_percentiles():
    metrics.set_enabled(True)
    metrics.record("read_ms", 7.5)
    st = metrics.snapshot()["kpis"]["read_ms"]
    assert st["p50"] == 7.5 and st["p95"] == 7.5 and st["mean"] == 7.5


def test_ring_buffer_is_bounded_but_total_keeps_counting():
    """Memory must stay fixed however long the device runs."""
    metrics.set_enabled(True)
    n = metrics._MAXLEN + 50
    for i in range(n):
        metrics.record("send_ms", float(i))
    st = metrics.snapshot()["kpis"]["send_ms"]
    assert st["count"] == metrics._MAXLEN       # what the stats are over
    assert st["total"] == n                      # lifetime
    assert st["min"] == 50.0                     # oldest 50 evicted


def test_file_pipeline_records_every_stage():
    metrics.set_enabled(True)
    t_mtime, t_det, t_read, t_send = 100.000, 100.400, 100.410, 100.910
    metrics.record_file_pipeline(t_mtime, t_det, t_read, t_send, chars=50)
    k = metrics.snapshot()["kpis"]
    assert k["detect_latency_ms"]["last"] == 400.0
    assert k["read_ms"]["last"] == 10.0
    assert k["send_ms"]["last"] == 500.0
    assert k["send_ms_per_char"]["last"] == 10.0
    assert k["e2e_latency_ms"]["last"] == 910.0


def test_file_pipeline_without_send_records_only_detect_and_read():
    """BT unavailable or unreadable file: no send figures, no division by zero."""
    metrics.set_enabled(True)
    metrics.record_file_pipeline(1.0, 1.2, 1.3, None, chars=0)
    k = metrics.snapshot()["kpis"]
    assert k["detect_latency_ms"]["count"] == 1
    assert k["read_ms"]["count"] == 1
    assert k["send_ms"]["count"] == 0
    assert k["send_ms_per_char"]["count"] == 0
    assert k["e2e_latency_ms"]["count"] == 0


def test_file_pipeline_zero_chars_with_send_skips_per_char():
    metrics.set_enabled(True)
    metrics.record_file_pipeline(1.0, 1.1, 1.2, 1.3, chars=0)
    k = metrics.snapshot()["kpis"]
    assert k["send_ms"]["count"] == 1
    assert k["send_ms_per_char"]["count"] == 0


def test_poll_scan_is_sampled_one_in_ten():
    metrics.set_enabled(True)
    for _ in range(30):
        metrics.record_poll_scan(0.001)
    assert metrics.snapshot()["kpis"]["poll_scan_ms"]["count"] == 3


def test_reset_clears_samples_and_totals():
    metrics.set_enabled(True)
    metrics.record("sse_build_ms", 3.0)
    metrics.reset()
    st = metrics.snapshot()["kpis"]["sse_build_ms"]
    assert st["count"] == 0 and st["total"] == 0


def test_toggle_at_runtime():
    metrics.set_enabled(True)
    metrics.record("send_ms", 1.0)
    metrics.set_enabled(False)
    metrics.record("send_ms", 2.0)  # ignored
    metrics.set_enabled(True)
    metrics.record("send_ms", 3.0)
    st = metrics.snapshot()["kpis"]["send_ms"]
    assert st["count"] == 2 and st["last"] == 3.0


# ---------------------------------------------------------------------------
# Concurrency: the loop, the BT wrapper and the SSE thread all record
# ---------------------------------------------------------------------------

def test_concurrent_records_do_not_lose_or_corrupt():
    metrics.set_enabled(True)
    per_thread = 500

    def work():
        for i in range(per_thread):
            metrics.record("sse_build_ms", float(i))

    threads = [threading.Thread(target=work) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    st = metrics.snapshot()["kpis"]["sse_build_ms"]
    assert st["total"] == 4 * per_thread
    assert st["count"] == metrics._MAXLEN


# ---------------------------------------------------------------------------
# Platform info: must never raise off-device
# ---------------------------------------------------------------------------

def test_platform_info_has_machine_and_python():
    info = metrics.platform_info()
    assert info["machine"]
    assert info["python"]
    assert "model" in info
