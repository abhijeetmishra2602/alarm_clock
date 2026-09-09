"""
tests/test_cli.py — Integration tests for the CLI using Click's test runner.

Click's CliRunner invokes commands in-process without spawning a subprocess,
making tests fast and debuggable. We isolate the store the same way as
test_store.py (env var + module reload).
"""

import importlib
import os

import pytest
from click.testing import CliRunner


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    store_path = tmp_path / "test_alarms.json"
    monkeypatch.setenv("ALARM_STORE_PATH", str(store_path))
    import alarm_clock.store as store_mod
    importlib.reload(store_mod)
    # Also reload cli so it picks up the reloaded store
    import alarm_clock.cli as cli_mod
    importlib.reload(cli_mod)
    return cli_mod


@pytest.fixture
def runner():
    return CliRunner()


def get_cli(isolated_store):
    return isolated_store.cli


# ------------------------------------------------------------------
# alarm set
# ------------------------------------------------------------------

def test_set_creates_alarm(runner, isolated_store):
    result = runner.invoke(get_cli(isolated_store), ["set", "07:30"])
    assert result.exit_code == 0
    assert "07:30" in result.output
    assert "✓" in result.output


def test_set_with_label(runner, isolated_store):
    result = runner.invoke(get_cli(isolated_store), ["set", "08:00", "--label", "standup"])
    assert result.exit_code == 0
    assert "standup" in result.output


def test_set_invalid_time_fails(runner, isolated_store):
    result = runner.invoke(get_cli(isolated_store), ["set", "25:00"])
    assert result.exit_code != 0
    assert "Invalid time" in result.output


def test_set_invalid_format_fails(runner, isolated_store):
    result = runner.invoke(get_cli(isolated_store), ["set", "7:3"])
    assert result.exit_code != 0


# ------------------------------------------------------------------
# alarm list
# ------------------------------------------------------------------

def test_list_empty(runner, isolated_store):
    result = runner.invoke(get_cli(isolated_store), ["list"])
    assert result.exit_code == 0
    assert "No alarms" in result.output


def test_list_shows_alarms(runner, isolated_store):
    runner.invoke(get_cli(isolated_store), ["set", "09:00", "--label", "breakfast"])
    result = runner.invoke(get_cli(isolated_store), ["list"])
    assert result.exit_code == 0
    assert "09:00" in result.output
    assert "breakfast" in result.output


# ------------------------------------------------------------------
# alarm delete
# ------------------------------------------------------------------

def test_delete_existing(runner, isolated_store):
    runner.invoke(get_cli(isolated_store), ["set", "10:00"])
    import alarm_clock.store as s
    alarm_id = s.load_all()[0].id

    result = runner.invoke(get_cli(isolated_store), ["delete", alarm_id])
    assert result.exit_code == 0
    assert "✓" in result.output
    assert s.load_all() == []


def test_delete_nonexistent_exits_1(runner, isolated_store):
    result = runner.invoke(get_cli(isolated_store), ["delete", "zzzzzz"])
    assert result.exit_code == 1


def test_delete_all(runner, isolated_store):
    runner.invoke(get_cli(isolated_store), ["set", "10:00"])
    runner.invoke(get_cli(isolated_store), ["set", "11:00"])
    result = runner.invoke(get_cli(isolated_store), ["delete", "--all"])
    assert result.exit_code == 0
    assert "2" in result.output


# ------------------------------------------------------------------
# alarm snooze
# ------------------------------------------------------------------

def test_snooze_creates_new_alarm(runner, isolated_store):
    runner.invoke(get_cli(isolated_store), ["set", "10:00", "--label", "test"])
    import alarm_clock.store as s
    alarm_id = s.load_all()[0].id

    result = runner.invoke(get_cli(isolated_store), ["snooze", alarm_id])
    assert result.exit_code == 0
    assert "💤" in result.output
    # Should now have 2 alarms (original + snoozed)
    assert len(s.load_all()) == 2


def test_snooze_nonexistent_exits_1(runner, isolated_store):
    result = runner.invoke(get_cli(isolated_store), ["snooze", "zzzzzz"])
    assert result.exit_code == 1


# ------------------------------------------------------------------
# alarm status
# ------------------------------------------------------------------

def test_status_no_alarms(runner, isolated_store):
    result = runner.invoke(get_cli(isolated_store), ["status"])
    assert result.exit_code == 0
    assert "No active alarms" in result.output


def test_status_shows_next(runner, isolated_store):
    runner.invoke(get_cli(isolated_store), ["set", "23:59"])
    result = runner.invoke(get_cli(isolated_store), ["status"])
    assert result.exit_code == 0
    assert "⏰" in result.output
