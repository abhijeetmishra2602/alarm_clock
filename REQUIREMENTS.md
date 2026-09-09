# Alarm Clock CLI — Requirements Document

**Version:** 1.0  
**Author:** Abhijeet Mishra  
**Date:** 2026-09-10  
**Context:** 30-minute build exercise for Senior Software Engineer role at Better

---

## 1. Problem Statement

Build a command-line alarm clock that allows a user to set, monitor, and manage time-based alerts from their terminal — with no GUI, no web interface, and no database dependency.

---

## 2. Scope Decision Rationale

Before listing features, I made explicit trade-offs:

| Concern | Decision | Rationale |
|---|---|---|
| Persistence | JSON file (`alarms.json`) | Survives restarts; human-readable; no DB dependency |
| Monitoring | Background thread | Non-blocking CLI; user can set multiple alarms in one session |
| Time format | 24-hour HH:MM | Unambiguous; avoids AM/PM parsing errors |
| Notification | Terminal bell (`\a`) + formatted message | Zero external dependencies for core trigger |
| Snooze | Creates a new alarm (+5 min) | Simplest correct implementation; reuses existing set logic |
| Recurring | `--repeat` flag (daily) | Common use case; single boolean on data model |

---

## 3. User Stories

### Must-Have (MVP)

| ID | As a user, I want to... | So that... |
|---|---|---|
| US-01 | Set an alarm for a specific time (HH:MM) with an optional label | I know which alarm is which |
| US-02 | List all active alarms with their ID, time, label, and status | I can see what's scheduled |
| US-03 | Delete an alarm by its ID | I can cancel alarms I no longer need |
| US-04 | Receive a terminal notification (bell + message) when alarm time is reached | I am alerted without watching the screen |
| US-05 | Start the alarm monitor so alarms are actively checked | Triggering happens in the background |

### Nice-to-Have (Time Permitting)

| ID | As a user, I want to... | So that... |
|---|---|---|
| US-06 | Snooze a triggered alarm for 5 minutes | I can delay without losing the alarm |
| US-07 | Set a recurring (daily) alarm | I don't have to re-set it every day |
| US-08 | Delete all alarms at once | I can reset quickly |
| US-09 | See a countdown to the next alarm | I have situational awareness |

---

## 4. Acceptance Criteria

### US-01: Set Alarm
- **Given** I run `alarm set 07:30 --label "Morning standup"`
- **Then** the alarm is saved to `alarms.json` with a unique ID
- **And** confirmation is printed: `✓ Alarm set for 07:30 [Morning standup] (ID: abc123)`
- **Error case:** Invalid time format → clear error message, no crash

### US-02: List Alarms
- **Given** I run `alarm list`
- **Then** a formatted table is printed with columns: ID, Time, Label, Repeat, Status
- **Edge case:** No alarms → print "No alarms set."

### US-03: Delete Alarm
- **Given** I run `alarm delete <id>`
- **Then** the alarm is removed from `alarms.json`
- **Error case:** Unknown ID → `Error: Alarm <id> not found.`

### US-04: Trigger Notification
- **Given** the monitor is running and alarm time matches current HH:MM
- **Then** terminal bell (`\a`) is emitted and a formatted message is printed
- **And** the alarm is marked as triggered (won't fire again unless recurring)

### US-05: Start Monitor
- **Given** I run `alarm start`
- **Then** the process runs in the foreground, checking alarms every 30 seconds
- **And** prints "Monitoring alarms... (Ctrl+C to stop)"
- **And** gracefully exits on Ctrl+C

### US-06: Snooze (Nice-to-have)
- **Given** an alarm has triggered
- **Then** I can run `alarm snooze <id>` to reschedule it for now + 5 minutes

### US-07: Recurring Alarms (Nice-to-have)
- **Given** I set an alarm with `--repeat` flag
- **Then** after it triggers, it is automatically rescheduled for the same time next day

---

## 5. Data Model

```json
{
  "id": "a1b2c3",
  "time": "07:30",
  "label": "Morning standup",
  "repeat": false,
  "enabled": true,
  "triggered_today": false,
  "created_at": "2026-09-10T00:40:00"
}
```

**Fields:**
- `id` — 6-char hex string (short, readable, unique enough for a personal tool)
- `time` — HH:MM 24-hour string
- `label` — optional freetext string
- `repeat` — boolean; if true, resets `triggered_today` at midnight
- `enabled` — soft delete / disable without removing
- `triggered_today` — prevents double-firing within same minute

---

## 6. CLI Interface Contract

```
alarm set <HH:MM> [--label TEXT] [--repeat]
alarm list
alarm delete <id>
alarm delete --all
alarm start          # foreground monitor loop
alarm snooze <id>    # reschedule +5 min
alarm status         # show next alarm + countdown
```

---

## 7. Non-Goals (Explicitly Out of Scope)

- ❌ GUI / Web UI / React
- ❌ Database (SQLite, Postgres, etc.)
- ❌ Mobile / push notifications
- ❌ Multi-user support
- ❌ Timezone-aware scheduling (all times are local system time)
- ❌ Sound file playback (terminal bell only — avoids `playsound`/`pygame` dependency)
- ❌ Cron-like scheduling syntax (only daily repeat supported)
- ❌ Cloud sync

---

## 8. Technical Constraints

- Python 3.9+
- Dependencies: `click` (CLI framework), `rich` (terminal formatting)
- No dependency on system cron / launchd — self-contained
- Must work on macOS and Linux

---

## 9. Definition of Done

- [ ] All US-01 through US-05 acceptance criteria pass
- [ ] `alarm --help` shows clean usage
- [ ] `README.md` has setup + usage examples
- [ ] Code is modular (model / store / scheduler / CLI separated)
- [ ] Works after process restart (persistence verified)
