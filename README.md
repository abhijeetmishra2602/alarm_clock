# 🔔 Alarm Clock CLI

A minimal, robust alarm clock for your terminal — no GUI, no database, no fuss.

Built as a 30-minute engineering exercise. The focus is on **clean architecture**, **explicit design decisions**, and **verifiable behavior via tests** — not feature count.

---

## Design Decisions

| Concern | Choice | Why |
|---|---|---|
| Persistence | `alarms.json` (atomic write) | Human-readable, crash-safe, no DB dependency |
| Monitoring | Background daemon thread | Non-blocking; set multiple alarms in one session |
| Time format | 24-hour HH:MM | Unambiguous; no AM/PM parsing errors |
| Notification | Terminal bell + `rich` print | Zero extra dependencies for the core trigger |
| Snooze | Create new alarm (+N min) | Reuses existing `set` logic; simplest correct impl |
| Recurring | `--repeat` flag + daily reset | Common use case; single boolean on data model |

---

## Architecture

```
alarm_clock/
├── alarm_clock/
│   ├── models.py      # Alarm dataclass + serialization
│   ├── store.py       # JSON read/write (atomic, env-overridable)
│   ├── scheduler.py   # Background thread (30s poll, midnight reset)
│   └── cli.py         # Click commands (set/list/delete/snooze/status/start)
├── tests/
│   ├── test_store.py  # Unit tests for persistence layer
│   └── test_cli.py    # Integration tests via Click's CliRunner
├── main.py            # Thin entry point
├── pyproject.toml
└── REQUIREMENTS.md    # Full requirements + user stories + acceptance criteria
```

**Data flow:**
```
CLI command → store.py (read/write alarms.json) ← scheduler.py (background thread)
```

---

## Setup

```bash
# Clone
git clone <repo-url>
cd alarm_clock

# Create virtual environment (Python 3.9+)
python3 -m venv .venv
source .venv/bin/activate

# Install (editable mode — registers `alarm` as a command)
pip install -e .
```

---

## Usage

```bash
# Set an alarm
alarm set 07:30
alarm set 07:30 --label "Morning standup"
alarm set 22:00 --label "Evening run" --repeat   # repeats daily

# List all alarms
alarm list

# See next alarm + countdown
alarm status

# Start the monitor (foreground — runs in terminal, fires alarm when time hits)
alarm start

# Delete an alarm by ID
alarm delete a1b2c3

# Delete all alarms
alarm delete --all

# Snooze an alarm (reschedule +5 min)
alarm snooze a1b2c3

# Snooze by custom duration
alarm snooze a1b2c3 --minutes 10
```

### Example session

```
$ alarm set 07:30 --label "Standup"
✓  Alarm set for 07:30  today at 07:30
   Label: Standup
   ID:    4f2a1c

$ alarm list
          Active Alarms
┌────────┬───────┬─────────┬────────┬────────┐
│ ID     │ Time  │ Label   │ Repeat │ Status │
├────────┼───────┼─────────┼────────┼────────┤
│ 4f2a1c │ 07:30 │ Standup │   —    │ active │
└────────┴───────┴─────────┴────────┴────────┘

$ alarm status
⏰  Next alarm: 07:30  Standup  →  6h 49m away

$ alarm start
Monitoring alarms...  (1 active, checking every 30s)
  Press Ctrl+C to stop.

🔔  ALARM!  07:30  — Standup  (ID: 4f2a1c)
  Run alarm snooze 4f2a1c to snooze 5 min.
```

---

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## What's Out of Scope

- GUI / Web UI
- Database (SQLite, Postgres, etc.)
- Mobile / push notifications
- Multi-user support
- Timezone awareness (uses local system time)
- Audio file playback (terminal bell only)

See [REQUIREMENTS.md](REQUIREMENTS.md) for full rationale.

---

## Author

Abhijeet Mishra — submission for Senior Software Engineer role at Better.
