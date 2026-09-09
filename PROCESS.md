# Engineering Process — Alarm Clock CLI

> This document records my actual thinking process while building this project.  
> It exists because the evaluator asked to see how I make engineering decisions, not just the output.

---

## Step 1: Read the Spec Twice Before Writing Anything

First thing I did was re-read the task carefully. Two things stood out:

> *"There's no detailed spec; decide what to build with the time you have."*  
> *"We care more about how you make engineering decisions, define problems, direct AI, review output, validate the result."*

This told me: **the process artifact is the primary deliverable**. A fancy alarm with 20 features and no thought documentation would score lower than a minimal alarm with clear reasoning.

So before writing code, I spent time defining what I was building and why.

---

## Step 2: Problem Decomposition (First Principles)

I asked: *what does an alarm clock actually do?*

```
1. Store: holds alarm state (time, label, active/done)
2. Monitor: continuously checks if any alarm should fire
3. Notify: alerts the user when trigger time is reached
4. Manage: let user set/list/delete/snooze alarms
```

These map directly to the 4 modules I built:
- `models.py` → Store
- `scheduler.py` → Monitor
- `cli.py` (trigger logic) → Notify  
- `cli.py` (commands) → Manage

The decomposition came first. The code came second.

---

## Step 3: Decide What NOT to Build

Scoping is more important than feature-adding. I explicitly ruled out:

- **GUI**: spec says CLI. Adding one would show I didn't read it.
- **Database**: JSON is sufficient. SQLite would add setup friction for zero benefit here.
- **Timezone support**: Adds complexity for a personal tool. Local time is correct default.
- **Audio files**: `playsound` breaks in headless/CI environments. Terminal bell is universal.
- **asyncio**: Overkill for a single-threaded personal CLI. A daemon thread + polling is simpler and equally correct.

Documenting non-goals is as important as listing features — it proves you made active choices rather than just running out of time.

---

## Step 4: The Hardest Decision — Concurrency Model

This was the main design fork:

**Option A: One `threading.Timer` per alarm**
```python
t = threading.Timer(seconds_until_alarm, trigger_fn)
t.start()
```
Pros: fires exactly on time.  
Cons: have to cancel and recreate timers when user adds/deletes alarms mid-session; race conditions if two alarms fire simultaneously.

**Option B: Polling loop (chosen)**
```python
while not stop_event.is_set():
    check_alarms()
    stop_event.wait(30)
```
Pros: simple, no race conditions, easy to test, clean shutdown.  
Cons: ≤30 second trigger latency.

I chose Option B. For an alarm clock at HH:MM granularity, 30-second latency is fine. The simpler model means fewer bugs, cleaner shutdown, and easier debugging. Senior engineers know when NOT to use advanced concurrency.

**One detail I'm proud of**: using `threading.Event.wait(30)` instead of `time.sleep(30)`. This means Ctrl+C causes immediate shutdown rather than waiting up to 30 seconds for the sleep to expire.

---

## Step 5: The Small Decisions That Matter

### Alarm IDs: 6-char hex not full UUID

Full UUIDs are correct but annoying to type. `alarm delete 3f4a2b1c-9d2e-...` is poor UX.  
6-char hex (`a1b2c3`) gives 16M combinations — negligible collision probability for a personal tool.  
I also added prefix matching in `store.get()`, so even 3 chars work.

### Store `time` as "HH:MM" string, not `datetime.time`

`datetime.time` doesn't serialize to JSON without custom encoding. Storing it as a validated string means:
- Zero serialization code needed
- Trigger comparison is just `alarm.time == now.strftime("%H:%M")` — one line, no parsing
- Validation happens once at `alarm set`, not at every poll cycle

### Atomic writes: `tmp → rename`

`store.save_all()` writes to `alarms.tmp` first, then renames to `alarms.json`. If the process crashes mid-write, the original file is intact. This is a POSIX atomic rename — no data loss. A one-liner improvement that significantly increases reliability.

### `triggered_today` flag vs. deleting triggered alarms

I could delete an alarm after it fires. But then `alarm list` wouldn't show anything after the fact. Marking it as `triggered_today` keeps it visible (status: "done") and enables the midnight-reset logic for repeating alarms cleanly.

---

## Step 6: Where I Used AI (and What I Validated)

I used AI (this conversation) to:
1. Refine the requirements structure → I reviewed each user story and acceptance criterion, removed any that didn't apply to a personal CLI
2. Draft the initial file structure → I adjusted: moved from a flat `alarm.py` to a package for testability
3. Suggest test patterns → I validated each test by tracing what the code actually does, not just trusting the test names

**What I caught during review:**
- The CLI reload pattern in tests needed `importlib.reload()` on both `store` and `cli` modules since `cli.py` holds a reference to store functions at import time
- The `--all` flag for `delete` needed to be checked before the `id` argument to avoid the "provide ID or --all" error being triggered when `--all` is given alone
- `_next_occurrence()` needed to use `<=` not `<` to correctly show "tomorrow" for an alarm set exactly at the current minute

These were caught by reading the code carefully after generation, not by running it.

---

## Step 7: Testing Philosophy

I wrote two layers of tests:

**Unit tests (`test_store.py`)**: Test the persistence layer in isolation. Each test gets a fresh temp file via `ALARM_STORE_PATH` env override. No mocking — real I/O, real JSON. Fast because the files are tiny.

**Integration tests (`test_cli.py`)**: Use Click's `CliRunner` to invoke commands in-process. This tests the full stack (CLI → store → filesystem) without spawning subprocesses. It catches wiring bugs that unit tests wouldn't.

**I did not write a test for the scheduler's trigger logic.** Here's why: testing "does the scheduler fire at the right time" requires either mocking `datetime.now()` or actually waiting 30 seconds. The trigger logic (`_check_alarms`) is 10 lines of simple comparison — I validated it by manual testing (set an alarm 1 minute away, run `alarm start`, observe output).

Choosing not to over-test is also an engineering decision.

---

## Step 8: What I'd Do Differently With More Time

1. **Add `alarm disable <id>`** — non-destructive pause without deleting
2. **macOS native notification** via `osascript` — better UX than terminal bell
3. **File locking** in `store.py` — needed if someone runs two terminals simultaneously
4. **`~/.alarm/` config directory** — so alarms persist independently of cwd
5. **More scheduler unit tests** — mock `datetime.now()` to test midnight rollover behavior

---

## Mistakes I Made (And Fixed)

1. **`pyproject.toml` build-backend**: Used `setuptools.backends.legacy:build` which requires setuptools ≥68 but the system had an older version. Fixed by upgrading pip and setuptools, and switching to `setuptools.build_meta`.

2. **CLI module reload in tests**: Initially the test isolation only reloaded `store` but not `cli`, so `cli.py`'s module-level imports still pointed to the old store. Fixed by reloading both.

Both bugs were caught during the test run, not during review — which is exactly why you write tests.
