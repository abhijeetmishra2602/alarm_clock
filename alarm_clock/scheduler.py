"""
scheduler.py — Background alarm monitoring.

Design decision: use threading.Thread (not multiprocessing, not asyncio).
Rationale:
  - No CPU-bound work; we just sleep and poll → threads are fine.
  - asyncio would add complexity without benefit for a CLI tool.
  - multiprocessing would make the store-reload pattern harder.

Check interval: 30 seconds.
  - Alarms fire at HH:MM granularity; 30s polling means ≤30s latency.
  - 1s polling would work but wastes CPU while sleeping.

Midnight reset: the scheduler detects day rollover and clears
triggered_today on repeat alarms — simpler than a separate cron job.
"""

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime

from rich.console import Console

from . import store
from .models import Alarm

console = Console()

# How often (seconds) we check whether any alarm should fire
POLL_INTERVAL = 30


def _trigger(alarm: Alarm) -> None:
    """Fire an alarm: ring terminal bell + print a rich notification."""
    sys.stdout.write("\a")  # terminal bell
    sys.stdout.flush()
    console.print(
        f"\n🔔  [bold yellow]ALARM![/bold yellow]  "
        f"[bold white]{alarm.time}[/bold white]  "
        f"[dim]{'— ' + alarm.label if alarm.label else ''}[/dim]  "
        f"[dim](ID: {alarm.id})[/dim]"
    )
    console.print(
        "[dim]  Run [bold]alarm snooze {id}[/bold] to snooze 5 min.[/dim]".format(
            id=alarm.id
        )
    )


def _check_alarms(last_day: int) -> int:
    """
    Evaluate all alarms against current time.
    Returns current day-of-year (used by caller to detect midnight rollover).
    """
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")
    current_day = now.timetuple().tm_yday

    alarms = store.load_all()
    changed = False

    # Midnight rollover: reset triggered_today on repeat alarms
    if current_day != last_day:
        for alarm in alarms:
            if alarm.repeat and alarm.triggered_today:
                alarm.triggered_today = False
                changed = True

    # Check each alarm
    for alarm in alarms:
        if not alarm.enabled:
            continue
        if alarm.triggered_today:
            continue
        if alarm.time == current_time_str:
            _trigger(alarm)
            alarm.triggered_today = True
            changed = True

    if changed:
        store.save_all(alarms)

    return current_day


class AlarmScheduler(threading.Thread):
    """
    Daemon thread that polls alarms every POLL_INTERVAL seconds.

    Daemon=True means it exits automatically when the main thread ends,
    so we don't need explicit cleanup when the CLI process exits.
    """

    def __init__(self) -> None:
        super().__init__(daemon=True, name="AlarmScheduler")
        self._stop_event = threading.Event()

    def run(self) -> None:
        last_day = datetime.now().timetuple().tm_yday
        while not self._stop_event.is_set():
            last_day = _check_alarms(last_day)
            self._stop_event.wait(timeout=POLL_INTERVAL)

    def stop(self) -> None:
        self._stop_event.set()
