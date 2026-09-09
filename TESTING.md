# Testing — Alarm Clock CLI

---

## Automated Tests

Run with:
```bash
source .venv/bin/activate
pytest tests/ -v
```

### Results (as of submission)
```
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2

tests/test_cli.py::test_set_creates_alarm          PASSED
tests/test_cli.py::test_set_with_label             PASSED
tests/test_cli.py::test_set_invalid_time_fails     PASSED
tests/test_cli.py::test_set_invalid_format_fails   PASSED
tests/test_cli.py::test_list_empty                 PASSED
tests/test_cli.py::test_list_shows_alarms          PASSED
tests/test_cli.py::test_delete_existing            PASSED
tests/test_cli.py::test_delete_nonexistent_exits_1 PASSED
tests/test_cli.py::test_delete_all                 PASSED
tests/test_cli.py::test_snooze_creates_new_alarm   PASSED
tests/test_cli.py::test_snooze_nonexistent_exits_1 PASSED
tests/test_cli.py::test_status_no_alarms           PASSED
tests/test_cli.py::test_status_shows_next          PASSED
tests/test_store.py::test_store_empty_on_first_load PASSED
tests/test_store.py::test_add_and_load             PASSED
tests/test_store.py::test_add_persists_to_disk     PASSED
tests/test_store.py::test_delete_existing          PASSED
tests/test_store.py::test_delete_nonexistent_returns_false PASSED
tests/test_store.py::test_delete_all               PASSED
tests/test_store.py::test_update                   PASSED
tests/test_store.py::test_get_by_prefix            PASSED

============================== 21 passed in 0.06s ==============================
```

**Test isolation strategy**: Each test gets a fresh temporary JSON file via `ALARM_STORE_PATH` env override + `importlib.reload()`. No mocking of filesystem — real I/O, fast because files are tiny.

---

## Manual Test Cases

### TC-01: Happy Path — Set and Trigger

**Steps:**
```bash
# Set alarm 1 minute in the future
alarm set $(date -v+1M +%H:%M) --label "Test trigger"
alarm list          # verify alarm appears, status=active
alarm start         # wait ~1 min
```
**Expected**: Terminal bell sounds, formatted alarm message printed.  
**Result:** ✅ PASS

---

### TC-02: Invalid Time Formats

```bash
alarm set 25:00    # Hour out of range
alarm set 07:60    # Minute out of range  
alarm set 7:30     # Missing leading zero (single digit hour)
alarm set 07:3     # Missing leading zero (single digit minute)
alarm set morning  # Non-numeric
alarm set ""       # Empty string
```
**Expected**: Each exits with non-zero code and a clear error message. No crash, no partial write to `alarms.json`.  
**Result:** ✅ PASS — all rejected with `"Invalid time '...' Expected HH:MM"` message.

---

### TC-03: Persistence Across Restart

```bash
alarm set 22:00 --label "Evening"
cat alarms.json   # verify JSON is written
# Kill terminal, open new terminal
alarm list        # alarm still appears
```
**Expected**: Alarm survives process restart.  
**Result:** ✅ PASS

---

### TC-04: Delete by Partial ID

```bash
alarm set 10:00 --label "Test"
# Note the 6-char ID, e.g. "a1b2c3"
alarm delete a1b   # first 3 chars only
alarm list         # alarm gone
```
**Expected**: Prefix match works.  
**Result:** ✅ PASS

---

### TC-05: Delete Non-Existent ID

```bash
alarm delete zzzzzz
echo $?   # should be 1
```
**Expected**: Error message printed, exit code 1.  
**Result:** ✅ PASS

---

### TC-06: Multiple Alarms

```bash
alarm set 07:00 --label "Wake up"
alarm set 07:30 --label "Standup"
alarm set 12:00 --label "Lunch"
alarm list
alarm status   # should show 07:00 as next (if before 07:00)
```
**Expected**: All three appear in sorted order. Status shows correct next alarm.  
**Result:** ✅ PASS

---

### TC-07: Snooze

```bash
alarm set 08:00 --label "Meeting"
# Get ID from output
alarm snooze <id>
alarm list   # should show 2 alarms: original + snoozed "(snoozed) Meeting"
```
**Expected**: New alarm created at now+5min. Original unchanged.  
**Result:** ✅ PASS

---

### TC-08: Recurring Alarm (Daily Repeat)

```bash
alarm set $(date -v+1M +%H:%M) --label "Daily test" --repeat
alarm list   # shows 🔁 repeat icon
alarm start  # trigger fires
alarm list   # status should be "triggered ↻", not "done"
```
**Expected**: Alarm marked triggered but NOT removed. Resets at midnight.  
**Result:** ✅ PASS (triggered state verified; midnight reset verified by advancing system clock in testing)

---

### TC-09: Graceful Shutdown

```bash
alarm start
# Press Ctrl+C
echo $?   # should be 0
```
**Expected**: "Alarm monitor stopped." printed. Process exits cleanly (code 0).  
**Result:** ✅ PASS

---

### TC-10: Midnight Edge Case (00:00)

```bash
alarm set 00:00 --label "Midnight"
alarm list   # appears correctly
```
**Expected**: No error — 00:00 is valid 24-hour time.  
**Result:** ✅ PASS — regex `^([01]\d|2[0-3]):([0-5]\d)$` correctly accepts `00:00`.

---

### TC-11: Atomic Write Integrity

```bash
alarm set 09:00
# Interrupt mid-write (kill -9 during write is hard to reproduce manually)
# Instead: verify .tmp file is not left behind after normal operation
ls alarm_clock/*.tmp   # should show nothing
cat alarms.json        # should be valid JSON
python3 -c "import json; json.load(open('alarms.json'))"
```
**Expected**: No `.tmp` leftovers, valid JSON always.  
**Result:** ✅ PASS

---

## What I Chose NOT to Automate

**Scheduler trigger timing**: Testing "does the alarm fire at the right time" requires either:
- Mocking `datetime.now()` — adds complexity, tests the mock not the code
- Waiting 30+ seconds in a test — slow, brittle on CI

Instead, the trigger logic (`_check_alarms`) is 10 lines of simple string comparison. I validated it via TC-01 (manual). This is a deliberate tradeoff: over-testing timing logic provides false confidence.

---

## Known Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| ≤30s trigger latency | Alarm may fire up to 30s late | Acceptable at HH:MM granularity |
| No file locking | Race condition if two terminals run simultaneously | Atomic rename minimizes window |
| Terminal bell requires audio | Bell may be silent in some setups | Visual message always shown |
| `triggered_today` uses calendar day | If alarm set just before midnight, "tomorrow" resets it | Acceptable edge case |
