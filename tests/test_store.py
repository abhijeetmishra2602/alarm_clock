"""
tests/test_store.py — Unit tests for the persistence layer.

Strategy: override ALARM_STORE_PATH via env var to use a temp file per test.
This avoids touching the real alarms.json during testing.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Redirect the store to a temp file for each test."""
    store_file = tmp_path / "test_alarms.json"
    monkeypatch.setenv("ALARM_STORE_PATH", str(store_file))

    # Force reimport so module-level STORE_PATH picks up the env var
    import importlib
    import alarm_clock.store as store_mod
    importlib.reload(store_mod)
    yield store_mod


def test_store_empty_on_first_load(isolated_store):
    alarms = isolated_store.load_all()
    assert alarms == []


def test_add_and_load(isolated_store):
    from alarm_clock.models import Alarm
    alarm = Alarm(time="07:30", label="test")
    isolated_store.add(alarm)

    loaded = isolated_store.load_all()
    assert len(loaded) == 1
    assert loaded[0].time == "07:30"
    assert loaded[0].label == "test"


def test_add_persists_to_disk(isolated_store, tmp_path):
    from alarm_clock.models import Alarm
    alarm = Alarm(time="08:00")
    isolated_store.add(alarm)

    # Read raw JSON to verify disk persistence
    store_path = Path(os.environ["ALARM_STORE_PATH"])
    raw = json.loads(store_path.read_text())
    assert len(raw) == 1
    assert raw[0]["time"] == "08:00"


def test_delete_existing(isolated_store):
    from alarm_clock.models import Alarm
    alarm = Alarm(time="09:00")
    isolated_store.add(alarm)

    removed = isolated_store.delete(alarm.id)
    assert removed is True
    assert isolated_store.load_all() == []


def test_delete_nonexistent_returns_false(isolated_store):
    removed = isolated_store.delete("ffffff")
    assert removed is False


def test_delete_all(isolated_store):
    from alarm_clock.models import Alarm
    isolated_store.add(Alarm(time="10:00"))
    isolated_store.add(Alarm(time="11:00"))

    count = isolated_store.delete_all()
    assert count == 2
    assert isolated_store.load_all() == []


def test_update(isolated_store):
    from alarm_clock.models import Alarm
    alarm = Alarm(time="12:00", label="original")
    isolated_store.add(alarm)

    alarm.label = "updated"
    isolated_store.update(alarm)

    loaded = isolated_store.get(alarm.id)
    assert loaded.label == "updated"


def test_get_by_prefix(isolated_store):
    from alarm_clock.models import Alarm
    alarm = Alarm(time="13:00")
    isolated_store.add(alarm)

    # Get by full ID
    found = isolated_store.get(alarm.id)
    assert found is not None
    assert found.time == "13:00"

    # Get by prefix (first 3 chars)
    found_prefix = isolated_store.get(alarm.id[:3])
    assert found_prefix is not None

    # Get nonexistent
    assert isolated_store.get("zzzzzz") is None
