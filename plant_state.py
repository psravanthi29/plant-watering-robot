"""Watering decision logic + state machine (SIMULATE-aware).

Run states: IDLE -> CHECKING <-> WATERING -> DONE (ERROR on fault).
No hardware imports here — SIMULATE stays True until we're at the wiring stage.

v2: water source is an always-available pressurized hose/pipe gated by a
solenoid valve (relay-switched), not a pump drawing from a reservoir — so
there's no tank/reservoir level to track. In exchange, a stuck-open valve can
flood rather than just run a reservoir dry, so every watering run is capped at
MAX_WATER_SECONDS as a hard safety cutoff (see run_valve()).
"""

import os
import random
import sqlite3
from datetime import datetime

import db
from scheduler import MAX_WATER_SECONDS, should_water

SIMULATE = True

DB_PATH = "plant.db"

# Where the watering logic gets its moisture reading from:
#   "simulate" — random value (default, no hardware)
#   "db"       — latest reading pushed by a networked sensor agent (see
#                sensor_agent.py); the server itself never touches GPIO
#   "gpio"     — read the sensor locally on this machine (Pi with ADC) [future]
MOISTURE_SOURCE = os.environ.get("MOISTURE_SOURCE", "simulate")

# A pushed reading older than this is treated as stale (sensor offline).
READING_MAX_AGE_SECONDS = int(os.environ.get("READING_MAX_AGE_SECONDS", "3600"))

STATE_IDLE = "IDLE"
STATE_CHECKING = "CHECKING"
STATE_WATERING = "WATERING"
STATE_DONE = "DONE"
STATE_ERROR = "ERROR"


def init_db(path=DB_PATH):
    conn = db.connect(path)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS runs (
            id {db.auto_pk(path)},
            timestamp TEXT NOT NULL,
            zone TEXT NOT NULL,
            moisture REAL,
            state TEXT NOT NULL,
            action TEXT NOT NULL,
            reason TEXT
        )
        """
    )
    # Readings pushed over the network by sensor agents (one row per reading).
    # Additive — independent of the runs/watering log.
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id {db.auto_pk(path)},
            timestamp TEXT NOT NULL,
            zone TEXT NOT NULL,
            sensor TEXT NOT NULL,
            value REAL NOT NULL,
            source TEXT
        )
        """
    )
    conn.commit()
    return conn


def log_reading(conn, zone, value, sensor="moisture", source="agent"):
    """Persist one sensor reading pushed from a networked sensor agent."""
    conn.execute(
        "INSERT INTO sensor_readings (timestamp, zone, sensor, value, source) "
        "VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), zone, sensor, value, source),
    )
    conn.commit()


def latest_reading(zone, sensor="moisture", max_age_seconds=READING_MAX_AGE_SECONDS,
                   conn=None):
    """Most recent pushed reading for a zone, or None if missing/stale.

    Staleness guards against acting on a reading from a sensor that has gone
    offline — a stale reading is treated the same as no reading.
    """
    own = conn is None
    if own:
        conn = db.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT value, timestamp FROM sensor_readings "
            "WHERE zone = ? AND sensor = ? ORDER BY id DESC LIMIT 1",
            (zone, sensor),
        ).fetchone()
    finally:
        if own:
            conn.close()
    if not row:
        return None
    value, ts = row
    if max_age_seconds is not None:
        age = (datetime.now() - datetime.fromisoformat(ts)).total_seconds()
        if age > max_age_seconds:
            return None
    return value


def log_run(conn, zone, moisture, state, action, reason):
    conn.execute(
        "INSERT INTO runs (timestamp, zone, moisture, state, action, reason) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), zone, moisture, state, action, reason),
    )
    conn.commit()


def read_moisture(zone):
    """Soil-moisture reading (0-100%) from the configured MOISTURE_SOURCE.

    "db" mode is the networked-sensor path: a sensor agent POSTs readings to
    the server (see sensor_agent.py + /api/reading), and the watering logic
    here simply consumes the latest fresh one — the server never reads GPIO.
    """
    if MOISTURE_SOURCE == "db":
        value = latest_reading(zone, sensor="moisture")
        if value is None:
            raise RuntimeError(
                f"no fresh moisture reading for {zone} — sensor agent offline?"
            )
        return value
    if SIMULATE:
        return round(random.uniform(10, 60), 1)
    raise NotImplementedError("Real sensor support not wired up yet")


def run_valve(zone, seconds=MAX_WATER_SECONDS):
    """Simulated solenoid-valve activation, hard-capped at MAX_WATER_SECONDS.

    The cap matters more here than it would for a pump: the hose is always
    pressurized, so a relay/valve fault that fails to close would otherwise
    flood rather than just run a reservoir dry.
    """
    if SIMULATE:
        return True, min(seconds, MAX_WATER_SECONDS)
    raise NotImplementedError("Real valve/relay support not wired up yet")


def zone_moisture_target(zone, conn):
    """Per-zone moisture threshold from the zones table, or None.

    Prefers an explicit ``moisture_target`` override, else derives it from the
    crops planted in the zone (placement.zone_recommended_target). Returns None
    when zones aren't set up (table missing / unknown zone) so the caller falls
    back to the global default threshold — keeps existing single-zone behavior.
    """
    try:
        import zones as _zones
        import placement as _placement
        z = _zones.get_zone_by_sensor_key(conn, zone)
        if not z:
            return None
        if z.get("moisture_target") is not None:
            return z["moisture_target"]
        return _placement.zone_recommended_target(conn, z["id"])
    except Exception:
        return None


def check_and_water(zone="zone-1", conn=None, now=None):
    """One pass of the CHECKING -> (WATERING) -> DONE state machine for a zone."""
    own_conn = conn is None
    if own_conn:
        conn = init_db()
    now = now or datetime.now()

    state = STATE_CHECKING
    try:
        moisture = read_moisture(zone)
    except Exception as exc:
        log_run(conn, zone, None, STATE_ERROR, "none", str(exc))
        if own_conn:
            conn.close()
        return STATE_ERROR

    target = zone_moisture_target(zone, conn)
    if target is not None:
        decision, reason = should_water(moisture, now, threshold=target)
    else:
        decision, reason = should_water(moisture, now)

    if decision:
        state = STATE_WATERING
        run_valve(zone)
        action = "watered"
    else:
        action = "skipped"

    state = STATE_DONE
    log_run(conn, zone, moisture, state, action, reason)

    if own_conn:
        conn.close()
    return state


if __name__ == "__main__":
    result = check_and_water()
    print(f"Run finished with state: {result}")
