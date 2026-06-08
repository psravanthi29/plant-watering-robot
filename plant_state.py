"""Watering decision logic + state machine (SIMULATE-aware).

Run states: IDLE -> CHECKING <-> WATERING -> DONE (ERROR on fault).
No hardware imports here — SIMULATE stays True until we're at the wiring stage.

v2: water source is an always-available pressurized hose/pipe gated by a
solenoid valve (relay-switched), not a pump drawing from a reservoir — so
there's no tank/reservoir level to track. In exchange, a stuck-open valve can
flood rather than just run a reservoir dry, so every watering run is capped at
MAX_WATER_SECONDS as a hard safety cutoff (see run_valve()).
"""

import random
import sqlite3
from datetime import datetime

from scheduler import MAX_WATER_SECONDS, should_water

SIMULATE = True

DB_PATH = "plant.db"

STATE_IDLE = "IDLE"
STATE_CHECKING = "CHECKING"
STATE_WATERING = "WATERING"
STATE_DONE = "DONE"
STATE_ERROR = "ERROR"


def init_db(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            zone TEXT NOT NULL,
            moisture REAL,
            state TEXT NOT NULL,
            action TEXT NOT NULL,
            reason TEXT
        )
        """
    )
    conn.commit()
    return conn


def log_run(conn, zone, moisture, state, action, reason):
    conn.execute(
        "INSERT INTO runs (timestamp, zone, moisture, state, action, reason) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), zone, moisture, state, action, reason),
    )
    conn.commit()


def read_moisture(zone):
    """Simulated soil-moisture sensor reading (0-100%)."""
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
