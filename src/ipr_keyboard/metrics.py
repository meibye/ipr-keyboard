"""Lightweight performance metrics (KPIs) for the IPR Pen Bridge.

Design constraints, in priority order:

1. **Off by default, zero cost when off.**  Every recording call starts with a
   single boolean check.  ``MetricsEnabled`` in ``config.json`` turns it on;
   the main loop re-applies the flag each iteration, so it can be toggled at
   runtime from the dashboard without a restart.

2. **Negligible cost when on.**  A recording is one ``time`` read plus one
   ``deque.append`` under a lock.  Buffers are bounded (``_MAXLEN``), so memory
   is fixed no matter how long the device runs.  Statistics (mean, p50, p95)
   are computed only when somebody asks for them, never on the hot path.

3. **No application imports.**  Like ``transmission.py`` this module is a
   leaf, so ``main.py``, ``bluetooth/keyboard.py`` and ``web/api.py`` can all
   import it without a cycle.

What is measured, and what is not
---------------------------------
The device can observe a scan from the moment the file appears on the
IrisPen mount until the BLE helper has handed the text to the HID daemon.
It cannot see the keystrokes arrive at the PC.  ``e2e_latency_ms`` here is
therefore *device-side* end-to-end.  The true pen-to-PC figure needs a probe
on the receiving PC -- see ``scripts/perf/perf_keystroke_probe.py``.
"""
from __future__ import annotations

import platform
import threading
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Optional

_MAXLEN = 200

_lock = threading.Lock()
_enabled = False

#: KPI name -> (unit, description).  Kept here so the API and the dashboard
#: never have to guess what a number means.
KPIS: Dict[str, tuple] = {
    "detect_latency_ms": (
        "ms",
        "File written on the pen -> noticed by the poll loop. Bounded below by PollIntervalSeconds.",
    ),
    "read_ms": ("ms", "Reading the scan file from the mount."),
    "send_ms": ("ms", "bt_kb_send handing the text to the BLE HID daemon (whole file)."),
    "send_ms_per_char": ("ms/char", "send_ms divided by characters sent."),
    "e2e_latency_ms": (
        "ms",
        "File written on the pen -> text handed to the BLE daemon. Device-side end-to-end.",
    ),
    "poll_scan_ms": ("ms", "Cost of one idle poll over all folders (sampled 1 in 10)."),
    "sse_build_ms": ("ms", "Building one dashboard status update (SSE)."),
}

_samples: Dict[str, Deque[float]] = {k: deque(maxlen=_MAXLEN) for k in KPIS}
_counts: Dict[str, int] = {k: 0 for k in KPIS}

# Seconds since kernel boot at the moment this module was imported, i.e. how
# long the device took to get the application process running.  Read once;
# costs nothing afterwards.
try:
    _boot_to_process_s: Optional[float] = float(Path("/proc/uptime").read_text().split()[0])
except Exception:  # not Linux, or /proc unavailable
    _boot_to_process_s = None
_process_start = time.time()
_poll_counter = 0


# ---------------------------------------------------------------------------
# Enable / disable
# ---------------------------------------------------------------------------
def set_enabled(flag: bool) -> None:
    """Turn recording on or off.  Cheap enough to call every loop iteration."""
    global _enabled
    _enabled = bool(flag)


def is_enabled() -> bool:
    return _enabled


def reset() -> None:
    """Drop all samples.  Used by tests and by the perf harness between runs."""
    global _poll_counter
    with _lock:
        for k in _samples:
            _samples[k].clear()
            _counts[k] = 0
        _poll_counter = 0


# ---------------------------------------------------------------------------
# Recording (hot path -- keep these tiny)
# ---------------------------------------------------------------------------
def record(name: str, value_ms: float) -> None:
    """Append one sample.  No-op when disabled or for an unknown KPI."""
    if not _enabled or name not in _samples:
        return
    with _lock:
        _samples[name].append(value_ms)
        _counts[name] += 1


def record_poll_scan(duration_s: float) -> None:
    """Sample the idle poll cost 1 in 10, so the sampling itself stays cheap."""
    global _poll_counter
    if not _enabled:
        return
    _poll_counter += 1
    if _poll_counter % 10 == 0:
        record("poll_scan_ms", duration_s * 1000.0)


def record_file_pipeline(
    file_mtime: float,
    detected_at: float,
    read_done_at: float,
    send_done_at: Optional[float],
    chars: int,
) -> None:
    """Record every KPI for one processed scan file in a single locked section.

    ``send_done_at`` is None when no send happened (BT unavailable or the file
    was unreadable); only the detect and read figures are recorded then.
    """
    if not _enabled:
        return
    with _lock:
        def _put(k: str, v: float) -> None:
            _samples[k].append(v)
            _counts[k] += 1

        _put("detect_latency_ms", (detected_at - file_mtime) * 1000.0)
        _put("read_ms", (read_done_at - detected_at) * 1000.0)
        if send_done_at is not None:
            send_ms = (send_done_at - read_done_at) * 1000.0
            _put("send_ms", send_ms)
            if chars > 0:
                _put("send_ms_per_char", send_ms / chars)
            _put("e2e_latency_ms", (send_done_at - file_mtime) * 1000.0)


# ---------------------------------------------------------------------------
# Reading (cold path -- statistics are computed here, never on record)
# ---------------------------------------------------------------------------
def _percentile(sorted_vals: list, pct: float) -> float:
    """Nearest-rank percentile on an already sorted list (len >= 1)."""
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = max(0, min(len(sorted_vals) - 1, int(round(pct / 100.0 * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def _stats(vals: list) -> dict:
    if not vals:
        return {"count": 0}
    s = sorted(vals)
    return {
        "count": len(s),
        "last": round(vals[-1], 2),
        "min": round(s[0], 2),
        "max": round(s[-1], 2),
        "mean": round(sum(s) / len(s), 2),
        "p50": round(_percentile(s, 50), 2),
        "p95": round(_percentile(s, 95), 2),
    }


def platform_info() -> dict:
    """Which board and OS this is -- so numbers from three devices can be compared."""
    info: dict = {"machine": platform.machine(), "python": platform.python_version()}
    try:
        info["model"] = Path("/proc/device-tree/model").read_text().rstrip("\x00").strip()
    except Exception:
        info["model"] = platform.node()
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                info["os"] = line.split("=", 1)[1].strip().strip('"')
                break
    except Exception:
        pass
    try:
        info["cpu_count"] = __import__("os").cpu_count()
    except Exception:
        pass
    return info


def snapshot() -> dict:
    """Everything the API exposes.  Safe to call from any thread."""
    with _lock:
        kpis = {}
        for name, (unit, desc) in KPIS.items():
            st = _stats(list(_samples[name]))
            st["total"] = _counts[name]  # lifetime count, beyond the ring buffer
            st["unit"] = unit
            st["description"] = desc
            kpis[name] = st
    return {
        "enabled": _enabled,
        "platform": platform_info(),
        "boot": {
            "boot_to_process_s": None if _boot_to_process_s is None else round(_boot_to_process_s, 2),
            "process_uptime_s": round(time.time() - _process_start, 1),
        },
        "kpis": kpis,
        "buffer_size": _MAXLEN,
    }
