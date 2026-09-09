# Design Document — Alarm Clock CLI

**Version:** 1.0  
**Author:** Abhijeet Mishra

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        User (Terminal)                      │
└───────────────────────────┬─────────────────────────────────┘
                            │  alarm <command> [args]
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  cli.py  (Click commands)                                   │
│  set | list | delete | snooze | status | start              │
└──────────┬──────────────────────────┬────────────────────────┘
           │ read/write               │ start
           ▼                          ▼
┌──────────────────┐        ┌──────────────────────┐
│  store.py        │        │  scheduler.py         │
│  (JSON I/O)      │◄───────│  (daemon thread)      │
│  alarms.json     │        │  poll every 30s       │
└──────────────────┘        └──────────────────────┘
           ▲
           │  serialized via
┌──────────────────┐
│  models.py       │
│  Alarm dataclass │
└──────────────────┘
```

The system has **3 independent concerns**, each in its own module:

| Module | Responsibility | Depends On |
|---|---|---|
| `models.py` | Data shape, serialization | nothing |
| `store.py` | JSON read/write | models |
| `scheduler.py` | Background polling, trigger | store, models |
| `cli.py` | User-facing commands | all above |

This means each layer is independently testable. The CLI never touches the filesystem directly — it always goes through `store.py`.

---

## 2. Key Design Decisions

### 2.1 Polling vs. Event-Driven Scheduling

**Options considered:**

| Approach | Pros | Cons |
|---|---|---|
| `threading.Timer` per alarm | Exact trigger time | Complex: cancel/restart on each edit; race conditions |
| `sched` module | Stdlib, designed for scheduling | Blocking by default; harder to integrate with CLI |
| `asyncio` event loop | Modern, cancellable | Overkill for CLI; requires async/await throughout |
| **Single daemon thread + polling (chosen)** | Simple, debuggable, crash-safe | ≤30s latency to trigger |

**Decision: polling every 30 seconds.**

Rationale:
- Alarms are specified at HH:MM granularity (minute-level precision)
- 30s polling means ≤30s trigger latency — acceptable for a personal alarm clock
- A single thread is easy to reason about, test, and shut down cleanly
- `threading.Event.wait(timeout=30)` means we can stop immediately on Ctrl+C without waiting for the sleep to expire

### 2.2 Persistence: JSON vs. No Persistence vs. SQLite

**Options considered:**

| Approach | Pros | Cons |
|---|---|---|
| In-memory only | No I/O complexity | Alarms lost on restart |
| SQLite | Structured queries | Dependency; overkill for key-value data |
| **JSON file (chosen)** | Human-readable; zero dependency; survives restart | Manual schema migration if model changes |

**Decision: `alarms.json` with atomic write.**

The write strategy is `write to .tmp → rename`, which is crash-safe: if the process dies mid-write, the original file is intact.

**Why not `portalocker` for file locking?**  
Out of scope for a single-user personal tool. The monitor thread and CLI commands aren't concurrent writers in the common case. The `start` command is foreground-only.

### 2.3 Click vs. argparse vs. Typer

| Approach | Pros | Cons |
|---|---|---|
| `argparse` (stdlib) | No dependency | Verbose for subcommands; less readable `--help` |
| **`click` (chosen)** | Clean subcommand API; auto help; composable decorators | Single external dependency |
| `typer` | Type-hint driven, very clean | Pulls in FastAPI ecosystem |

**Decision: `click`.**

`click` has one dependency (`colorama` on Windows), is widely understood, and produces clear `--help` output. The tradeoff of one external dependency is worth the readability gain.

### 2.4 Notification Strategy

**Options:**
1. Terminal bell (`\a`) only — works everywhere, no dependency
2. `playsound` / `pygame` — plays audio file; adds dependency, breaks in headless environments
3. macOS `osascript` / Linux `notify-send` — platform-specific

**Decision: terminal bell + `rich`-formatted print.**

This works on all platforms (macOS, Linux, WSL) with zero additional dependencies. The evaluator can verify the trigger visually even without audio.

### 2.5 Alarm ID Design

Short 6-character hex IDs (`uuid4().hex[:6]`) rather than full UUIDs.

Rationale:
- Full UUIDs are unwieldy to type (`alarm delete 3f4a2b1c-...`)
- 6-char hex gives 16^6 = 16.7M combinations — collision probability negligible for a personal tool with < 100 alarms
- Users can type partial IDs; `store.get()` does prefix matching

### 2.6 `triggered_today` vs. Deleting Triggered Alarms

Two options for handling a fired, non-repeating alarm:
- **Delete it immediately** — simpler, but user can't see what fired
- **Mark as `triggered_today=True`** (chosen) — alarm stays visible in `list` with "done" status; gets auto-cleaned on next start

The flag also enables the midnight-reset logic for repeating alarms without needing a separate cron entry.

---

## 3. Data Model

```python
@dataclass
class Alarm:
    time: str           # "HH:MM" — string, not datetime.time
    label: str          # optional user label
    repeat: bool        # daily repeat flag
    enabled: bool       # soft-disable (future: pause without deleting)
    triggered_today: bool  # prevents double-firing within same minute
    id: str             # 6-char hex
    created_at: str     # ISO8601 timestamp string
```

**Why store `time` as a string ("HH:MM") rather than `datetime.time`?**

- `datetime.time` doesn't serialize to JSON without custom encoding
- The comparison (`alarm.time == now.strftime("%H:%M")`) is a simple string equality — no `datetime` parsing needed at trigger time
- Validation happens once at `alarm set` time, not repeatedly in the polling loop

---

## 4. Concurrency Model

```
Main Thread (CLI)          Scheduler Thread (daemon)
─────────────────          ─────────────────────────
alarm set 07:30            ← sleeping (Event.wait 30s)
  → store.add(alarm)
                           ← wakes up
                           → store.load_all()
                           → compare each alarm.time vs now
                           → trigger if match
                           → store.save_all()
                           ← sleeping again
alarm delete abc123
  → store.delete("abc123")
```

The CLI and scheduler both call `store.load_all()` / `store.save_all()`. The only shared state is the JSON file. This is safe because:
1. The `start` command is foreground — the user can't run other `alarm` commands in the same terminal session
2. `store.save_all()` does atomic rename — no partial write visible to the other side
3. For future multi-terminal use, a file lock (e.g., `portalocker`) could be added to `store.py` without changing any other module

---

## 5. Error Handling Strategy

| Scenario | Handling |
|---|---|
| Invalid time format | `click.UsageError` → clean error, exit 1 |
| Unknown alarm ID | Print error to stderr, `sys.exit(1)` |
| Corrupt `alarms.json` | `store._load_raw()` returns `[]` on `JSONDecodeError` |
| Ctrl+C during `alarm start` | `KeyboardInterrupt` → `scheduler.stop()` → clean exit |
| SIGTERM | Signal handler converts to `KeyboardInterrupt` for same clean path |

---

## 6. What I'd Add With More Time

| Feature | Complexity | Value |
|---|---|---|
| Timezone support (`--tz "Asia/Kolkata"`) | Medium | High for multi-region use |
| File locking (`portalocker`) | Low | High for multi-terminal safety |
| `alarm disable <id>` | Low | Medium UX improvement |
| macOS notification (`osascript`) | Low | High on macOS |
| `alarm edit <id> --time` | Medium | Medium UX |
| Config file (`~/.alarm/config.toml`) | Low | Medium for custom store path |
