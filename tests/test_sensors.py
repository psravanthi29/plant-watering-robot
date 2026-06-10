from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

import plant_state
from plant_state import (
    STATE_DONE,
    check_and_water,
    init_db,
    latest_reading,
    log_reading,
    read_moisture,
)

MORNING = datetime(2026, 6, 10, 9, 0)


@pytest.fixture
def conn():
    c = init_db(":memory:")
    yield c
    c.close()


def test_init_db_creates_sensor_readings_table(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(sensor_readings)").fetchall()]
    assert {"timestamp", "zone", "sensor", "value", "source"} <= set(cols)


def test_log_and_latest_reading_roundtrip(conn):
    log_reading(conn, "tomato", 33.5, sensor="moisture", source="agent")
    assert latest_reading("tomato", conn=conn) == 33.5


def test_latest_reading_returns_most_recent(conn):
    log_reading(conn, "tomato", 20.0)
    log_reading(conn, "tomato", 45.0)
    assert latest_reading("tomato", conn=conn) == 45.0


def test_latest_reading_none_when_missing(conn):
    assert latest_reading("nope", conn=conn) is None


def test_latest_reading_stale_is_ignored(conn):
    # Insert a reading with an old timestamp directly
    old = (datetime.now() - timedelta(hours=3)).isoformat()
    conn.execute(
        "INSERT INTO sensor_readings (timestamp, zone, sensor, value, source) "
        "VALUES (?, ?, ?, ?, ?)",
        (old, "tomato", "moisture", 30.0, "agent"),
    )
    conn.commit()
    # default max age is 3600s → 3h-old reading is stale
    assert latest_reading("tomato", conn=conn) is None
    # but a generous max_age accepts it
    assert latest_reading("tomato", max_age_seconds=999999, conn=conn) == 30.0


def test_read_moisture_db_mode_uses_pushed_reading(conn, monkeypatch):
    monkeypatch.setattr(plant_state, "MOISTURE_SOURCE", "db")
    monkeypatch.setattr(plant_state, "latest_reading", lambda zone, **k: 27.0)
    assert read_moisture("tomato") == 27.0


def test_read_moisture_db_mode_errors_when_no_reading(conn, monkeypatch):
    monkeypatch.setattr(plant_state, "MOISTURE_SOURCE", "db")
    monkeypatch.setattr(plant_state, "latest_reading", lambda zone, **k: None)
    with pytest.raises(RuntimeError, match="offline"):
        read_moisture("tomato")


def test_check_and_water_consumes_pushed_reading_end_to_end(conn, monkeypatch):
    """Full path: a pushed reading drives the watering decision in db mode."""
    monkeypatch.setattr(plant_state, "MOISTURE_SOURCE", "db")
    log_reading(conn, "zone-1", 15.0)  # dry → should water
    # latest_reading opens its own conn by default; point it at our in-memory one
    monkeypatch.setattr(plant_state, "latest_reading",
                        lambda zone, **k: latest_reading(zone, conn=conn, **k))
    with patch("plant_state.run_valve", return_value=(True, 15)) as valve:
        state = check_and_water(zone="zone-1", conn=conn, now=MORNING)
    assert state == STATE_DONE
    valve.assert_called_once()
    row = conn.execute("SELECT moisture, action FROM runs").fetchone()
    assert row[0] == 15.0 and row[1] == "watered"
