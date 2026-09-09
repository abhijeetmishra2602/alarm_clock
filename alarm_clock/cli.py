"""
cli.py — Click-based CLI interface.

Design decision: Click over argparse/typer.
  - Click is widely used, well-documented, and produces clean --help output.
  - Typer would be cleaner but adds FastAPI dependency chain.
  - argparse is stdlib but verbose for nested sub-commands.

All output goes through `rich` for consistent, readable formatting.
All errors raise SystemExit(1) with a clear message (no stack traces to users).
"""

from __future__ import annotations

import re
import signal
import sys
from datetime import datetime, timedelta

import click
from rich.console import Console
from rich.table import Table

from . import store
from .models import Alarm
from .scheduler import AlarmScheduler, POLL_INTERVAL

console = Console()

# HH:MM validation regex — accepts 00:00 to 23:59
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _validate_time(time_str: str) -> str:
    """Validate HH:MM format; raise UsageError on failure."""
    if not _TIME_RE.match(time_str):
        raise click.UsageError(
            f"Invalid time '{time_str}'. Expected HH:MM (24-hour), e.g. 07:30 or 23:45."
        )
    return time_str


def _next_occurrence(time_str: str) -> str:
    """Return 'today' or 'tomorrow' based on whether the time has passed."""
    now = datetime.now()
    alarm_dt = datetime.strptime(time_str, "%H:%M").replace(
        year=now.year, month=now.month, day=now.day
    )
    if alarm_dt <= now:
        alarm_dt += timedelta(days=1)
        return f"tomorrow at {time_str}"
    return f"today at {time_str}"


# ------------------------------------------------------------------
# CLI group
# ------------------------------------------------------------------

@click.group()
@click.version_option("1.0.0", prog_name="alarm")
def cli() -> None:
    """🔔  Alarm Clock CLI — set, manage, and monitor terminal alarms."""


# ------------------------------------------------------------------
# alarm set
# ------------------------------------------------------------------

@cli.command("set")
@click.argument("time")
@click.option("--label", "-l", default="", help="Optional label for the alarm.")
@click.option("--repeat", "-r", is_flag=True, default=False, help="Repeat daily.")
def cmd_set(time: str, label: str, repeat: bool) -> None:
    """Set a new alarm for TIME (format: HH:MM, 24-hour)."""
    _validate_time(time)
    alarm = Alarm(time=time, label=label, repeat=repeat)
    store.add(alarm)

    repeat_str = " [bold magenta](repeating daily)[/bold magenta]" if repeat else ""
    occurrence = _next_occurrence(time)
    console.print(
        f"✓  Alarm set for [bold cyan]{time}[/bold cyan]{repeat_str}  "
        f"[dim]{occurrence}[/dim]"
    )
    if label:
        console.print(f"   Label: [italic]{label}[/italic]")
    console.print(f"   ID:    [dim]{alarm.id}[/dim]")


# ------------------------------------------------------------------
# alarm list
# ------------------------------------------------------------------

@cli.command("list")
def cmd_list() -> None:
    """List all alarms."""
    alarms = store.load_all()
    if not alarms:
        console.print("[dim]No alarms set. Use [bold]alarm set HH:MM[/bold] to create one.[/dim]")
        return

    table = Table(title="Active Alarms", show_lines=True)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Time", style="bold cyan", no_wrap=True)
    table.add_column("Label", style="italic")
    table.add_column("Repeat", justify="center")
    table.add_column("Status", justify="center")

    for alarm in sorted(alarms, key=lambda a: a.time):
        repeat_icon = "🔁" if alarm.repeat else "—"
        status = alarm.status_str
        status_style = {
            "active": "[green]active[/green]",
            "done": "[dim]done[/dim]",
            "disabled": "[red]disabled[/red]",
            "triggered (repeating)": "[yellow]triggered ↻[/yellow]",
        }.get(status, status)

        table.add_row(
            alarm.id,
            alarm.time,
            alarm.display_label,
            repeat_icon,
            status_style,
        )

    console.print(table)


# ------------------------------------------------------------------
# alarm delete
# ------------------------------------------------------------------

@cli.command("delete")
@click.argument("id", required=False)
@click.option("--all", "delete_all", is_flag=True, default=False, help="Delete all alarms.")
def cmd_delete(id: str | None, delete_all: bool) -> None:
    """Delete an alarm by ID, or all alarms with --all."""
    if delete_all:
        count = store.delete_all()
        console.print(f"✓  Deleted [bold]{count}[/bold] alarm(s).")
        return

    if not id:
        raise click.UsageError("Provide an alarm ID or use --all to delete all alarms.")

    removed = store.delete(id)
    if removed:
        console.print(f"✓  Alarm [dim]{id}[/dim] deleted.")
    else:
        console.print(f"[red]Error:[/red] Alarm '{id}' not found.", err=True)
        sys.exit(1)


# ------------------------------------------------------------------
# alarm snooze
# ------------------------------------------------------------------

@cli.command("snooze")
@click.argument("id")
@click.option("--minutes", "-m", default=5, show_default=True, help="Minutes to snooze.")
def cmd_snooze(id: str, minutes: int) -> None:
    """Snooze an alarm by ID — reschedules it N minutes from now."""
    alarm = store.get(id)
    if not alarm:
        console.print(f"[red]Error:[/red] Alarm '{id}' not found.", err=True)
        sys.exit(1)

    new_time = (datetime.now() + timedelta(minutes=minutes)).strftime("%H:%M")
    new_alarm = Alarm(
        time=new_time,
        label=f"(snoozed) {alarm.label}".strip(),
        repeat=False,
    )
    store.add(new_alarm)
    console.print(
        f"💤  Snoozed. New alarm at [bold cyan]{new_time}[/bold cyan]  "
        f"[dim](ID: {new_alarm.id})[/dim]"
    )


# ------------------------------------------------------------------
# alarm status
# ------------------------------------------------------------------

@cli.command("status")
def cmd_status() -> None:
    """Show next upcoming alarm and countdown."""
    now = datetime.now()
    now_str = now.strftime("%H:%M")

    alarms = [
        a for a in store.load_all()
        if a.enabled and not (a.triggered_today and not a.repeat)
    ]

    if not alarms:
        console.print("[dim]No active alarms.[/dim]")
        return

    def minutes_until(t: str) -> int:
        h, m = map(int, t.split(":"))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target <= now:
            target = target + timedelta(days=1)
        return int((target - now).total_seconds() // 60)

    next_alarm = min(alarms, key=lambda a: minutes_until(a.time))
    mins = minutes_until(next_alarm.time)
    hours, remainder = divmod(mins, 60)
    countdown = f"{hours}h {remainder}m" if hours else f"{remainder}m"

    console.print(
        f"⏰  Next alarm: [bold cyan]{next_alarm.time}[/bold cyan]  "
        f"[dim]{next_alarm.display_label}[/dim]  "
        f"→  [bold yellow]{countdown}[/bold yellow] away"
    )


# ------------------------------------------------------------------
# alarm start  (foreground monitor)
# ------------------------------------------------------------------

@cli.command("start")
def cmd_start() -> None:
    """Start the alarm monitor (foreground, Ctrl+C to stop)."""
    alarms = store.load_all()
    active = [a for a in alarms if a.enabled and not (a.triggered_today and not a.repeat)]

    console.print(
        f"[bold green]Monitoring alarms...[/bold green]  "
        f"[dim]({len(active)} active, checking every {POLL_INTERVAL}s)[/dim]"
    )
    console.print("[dim]  Press Ctrl+C to stop.[/dim]\n")

    scheduler = AlarmScheduler()
    scheduler.start()

    # Register SIGTERM handler for graceful shutdown in addition to KeyboardInterrupt
    def _shutdown(sig, frame):  # noqa: ANN001
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            # Keep main thread alive; scheduler runs in background daemon thread
            scheduler.join(timeout=1)
    except KeyboardInterrupt:
        scheduler.stop()
        console.print("\n[dim]Alarm monitor stopped.[/dim]")
