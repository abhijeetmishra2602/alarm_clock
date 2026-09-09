"""
models.py — Alarm data model.

Design decision: dataclass over namedtuple because we need mutability
(triggered_today needs to be reset daily, enabled can be toggled).
We derive a short 6-char hex ID from uuid4 — unique enough for a
personal-use CLI tool, more readable than a full UUID.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


def _new_id() -> str:
    """Generate a short, human-readable 6-char hex ID."""
    return uuid.uuid4().hex[:6]


@dataclass
class Alarm:
    time: str          # "HH:MM" 24-hour format
    label: str = ""    # Optional human label
    repeat: bool = False       # If True, resets daily after trigger
    enabled: bool = True       # False = soft-deleted/paused
    triggered_today: bool = False  # Guards against double-firing
    id: str = field(default_factory=_new_id)
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "time": self.time,
            "label": self.label,
            "repeat": self.repeat,
            "enabled": self.enabled,
            "triggered_today": self.triggered_today,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Alarm":
        return cls(
            id=data["id"],
            time=data["time"],
            label=data.get("label", ""),
            repeat=data.get("repeat", False),
            enabled=data.get("enabled", True),
            triggered_today=data.get("triggered_today", False),
            created_at=data.get("created_at", ""),
        )

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    @property
    def display_label(self) -> str:
        return self.label if self.label else "—"

    @property
    def status_str(self) -> str:
        if not self.enabled:
            return "disabled"
        if self.triggered_today and not self.repeat:
            return "done"
        if self.triggered_today and self.repeat:
            return "triggered (repeating)"
        return "active"
