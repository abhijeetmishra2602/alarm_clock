"""
store.py — JSON persistence layer.

Design decision: keep I/O in one place so the scheduler and CLI never
touch the file directly.  File locking via portalocker is avoided (out
of scope for a personal tool); instead we do atomic write-then-rename
to prevent corruption on crash.

The store lives next to the package by default but is overridable via
ALARM_STORE_PATH env var — makes testing easy without monkey-patching.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import List

from .models import Alarm

# Resolve store path: env override → default next to package root
_DEFAULT_STORE = Path(__file__).parent.parent / "alarms.json"
STORE_PATH = Path(os.environ.get("ALARM_STORE_PATH", _DEFAULT_STORE))


def _load_raw() -> list[dict]:
    """Read raw JSON list from disk, returning [] if file absent/corrupt."""
    if not STORE_PATH.exists():
        return []
    try:
        return json.loads(STORE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _save_raw(data: list[dict]) -> None:
    """Atomic write: write to temp file then rename — crash-safe."""
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(STORE_PATH)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def load_all() -> List[Alarm]:
    """Return all alarms from disk."""
    return [Alarm.from_dict(d) for d in _load_raw()]


def save_all(alarms: List[Alarm]) -> None:
    """Persist the full list of alarms to disk."""
    _save_raw([a.to_dict() for a in alarms])


def add(alarm: Alarm) -> None:
    """Append a new alarm and save."""
    alarms = load_all()
    alarms.append(alarm)
    save_all(alarms)


def get(alarm_id: str) -> Alarm | None:
    """Find alarm by ID prefix match (allows short IDs)."""
    for alarm in load_all():
        if alarm.id.startswith(alarm_id):
            return alarm
    return None


def update(alarm: Alarm) -> None:
    """Replace the matching alarm (by ID) and save."""
    alarms = load_all()
    for i, a in enumerate(alarms):
        if a.id == alarm.id:
            alarms[i] = alarm
            save_all(alarms)
            return
    raise KeyError(f"Alarm {alarm.id} not found in store.")


def delete(alarm_id: str) -> bool:
    """Remove alarm by ID. Returns True if found and deleted."""
    alarms = load_all()
    new_list = [a for a in alarms if not a.id.startswith(alarm_id)]
    if len(new_list) == len(alarms):
        return False  # nothing removed
    save_all(new_list)
    return True


def delete_all() -> int:
    """Delete all alarms. Returns count removed."""
    alarms = load_all()
    save_all([])
    return len(alarms)
