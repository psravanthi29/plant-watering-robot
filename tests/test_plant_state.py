from datetime import datetime
from unittest.mock import patch

import pytest

from plant_state import (
    MAX_WATER_SECONDS,
    STATE_DONE,
    STATE_ERROR,
    check_and_water,
    init_db,
    log_run,
    run_valve,
)

MORNING = datetime(2026, 6, 8, 9, 0)
NIGHT = datetime(2026, 6, 8, 22, 0)


@pytest.fixture
def conn():
    """A fresh in-memory DB per test — never touches plant.db on disk."""
    c = init_db(":memory:")
    yield c
    c.close()


# --- DB plumbing -----------------------------------------------------------

def test_init_db_creates_runs_table(conn):
    cols = [row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()]
    assert {"timestamp", "zone", "moisture", "state", "action", "reason"} <= set(cols)
    assert "tank_level" not in cols  # v2: no reservoir/tank tracking


def test_log_run_persists_a_row(conn):
    log_run(conn, "zone-1", 42.0, STATE_DONE, "watered", "soil dry and in window")
    row = conn.execute("SELECT zone, moisture, state, action, reason FROM runs").fetchone()
    assert row == ("zone-1", 42.0, STATE_DONE, "watered", "soil dry and in window")


# --- run_valve safety cutoff ------------------------------------------------

def test_run_valve_reports_success_within_limit():
    ok, seconds = run_valve("zone-1", seconds=5)
    assert ok is True
    assert seconds == 5


def test_run_valve_hard_caps_at_max_water_seconds():
    """Even if asked to run longer, it must never exceed MAX_WATER_SECONDS.

    This is the software backstop against the v2 failure mode (a stuck-open
    valve flooding from an always-pressurized line) — it must hold even if
    a caller passes a bad value.
    """
    ok, seconds = run_valve("zone-1", seconds=MAX_WATER_SECONDS * 10)
    assert ok is True
    assert seconds == MAX_WATER_SECONDS


# --- check_and_water state machine -----------------------------------------

def test_waters_and_logs_when_dry_and_in_window(conn):
    with patch("plant_state.read_moisture", return_value=20.0):
        state = check_and_water(zone="zone-1", conn=conn, now=MORNING)

    assert state == STATE_DONE
    row = conn.execute("SELECT moisture, state, action, reason FROM runs").fetchone()
    assert row[0] == 20.0
    assert row[1] == STATE_DONE
    assert row[2] == "watered"
    assert "dry" in row[3]


def test_skips_and_logs_when_soil_already_moist(conn):
    with patch("plant_state.read_moisture", return_value=55.0):
        state = check_and_water(zone="zone-1", conn=conn, now=MORNING)

    assert state == STATE_DONE
    row = conn.execute("SELECT action, reason FROM runs").fetchone()
    assert row[0] == "skipped"
    assert "moisture" in row[1]


def test_skips_and_logs_when_outside_watering_window(conn):
    with patch("plant_state.read_moisture", return_value=20.0):
        state = check_and_water(zone="zone-1", conn=conn, now=NIGHT)

    assert state == STATE_DONE
    row = conn.execute("SELECT action, reason FROM runs").fetchone()
    assert row[0] == "skipped"
    assert "window" in row[1]


def test_sensor_failure_logs_error_state_and_does_not_water(conn):
    with patch("plant_state.read_moisture", side_effect=RuntimeError("sensor disconnected")):
        with patch("plant_state.run_valve") as mock_valve:
            state = check_and_water(zone="zone-1", conn=conn, now=MORNING)
            mock_valve.assert_not_called()

    assert state == STATE_ERROR
    row = conn.execute("SELECT moisture, state, action, reason FROM runs").fetchone()
    assert row[0] is None
    assert row[1] == STATE_ERROR
    assert row[2] == "none"
    assert "sensor disconnected" in row[3]


def test_watering_run_calls_run_valve_exactly_once(conn):
    with patch("plant_state.read_moisture", return_value=15.0), \
         patch("plant_state.run_valve", return_value=(True, MAX_WATER_SECONDS)) as mock_valve:
        state = check_and_water(zone="zone-1", conn=conn, now=MORNING)

    assert state == STATE_DONE
    mock_valve.assert_called_once_with("zone-1")
