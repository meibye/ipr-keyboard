"""Shared transmission state for BLE keyboard sends.

Thread-safe module-level store with no application-level imports,
so it can be imported from both bluetooth/keyboard.py and web/api.py
without circular dependency.
"""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_state: dict = {
    "state": "idle",
    "label": "Idle",
    "explanation": "No active send",
    "progress_percent": None,
    "items_sent": 0,
    "retry_count": 0,
    "last_success_at": None,
}


def get() -> dict:
    """Return a snapshot copy of the current transmission state."""
    with _lock:
        return dict(_state)


def set_sending(source: str = "keyboard") -> None:
    """Mark transmission as in-progress."""
    with _lock:
        _state["state"] = "sending"
        _state["label"] = "Sending"
        _state["explanation"] = f"Transmitting via {source}"
        _state["progress_percent"] = None


def set_success() -> None:
    """Mark last transmission as successful and increment counter."""
    with _lock:
        _state["state"] = "success"
        _state["label"] = "Sent"
        _state["explanation"] = "Last send completed"
        _state["last_success_at"] = time.time()
        _state["items_sent"] = _state["items_sent"] + 1


def set_failed(reason: str = "") -> None:
    """Mark transmission as failed."""
    with _lock:
        _state["state"] = "failed"
        _state["label"] = "Failed"
        _state["explanation"] = reason or "Send failed"


def set_idle() -> None:
    """Reset transmission state to idle."""
    with _lock:
        _state["state"] = "idle"
        _state["label"] = "Idle"
        _state["explanation"] = "No active send"
