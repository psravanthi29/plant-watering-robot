"""Garden zones — the shared backbone linking the planner and the watering system.

A *zone* is one physical patch served by exactly ONE moisture sensor + ONE valve.
Its ``sensor_key`` matches the string the ESP32 reports (e.g. "zone-1"), so the
watering side (sensor_readings/runs use that same string) and the planning side
(garden_crops.zone_id points here) finally share one entity.

Because a single valve waters the whole zone at once, all crops assigned to a
zone must share similar water needs — that constraint is enforced when crops are
placed into zones (see placement.suggest_placement). A zone's moisture target is
normally derived from the crops in it (placement.zone_recommended_target) but can
be overridden per zone via ``moisture_target``.
"""

import sqlite3

import db
from plant_state import DB_PATH

# Higher = more sun. A crop fits a zone when zone-sun >= the crop's minimum.
SUN_LEVELS = {"shade": 0, "partial": 1, "full": 2}

# Fields a caller may set/update on a zone (id and sensor_key handled specially).
ZONE_FIELDS = [
    "name", "sensor_key", "area_m2", "sun", "container_type",
    "moisture_target", "window_start", "window_end", "max_water_seconds", "notes",
]


def init_zones_db(path: str = DB_PATH, conn: sqlite3.Connection | None = None):
    own = conn is None
    if own:
        conn = db.connect(path)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS zones (
            id                {db.auto_pk(path)},
            name              TEXT NOT NULL,
            sensor_key        TEXT UNIQUE,
            area_m2           REAL,
            sun               TEXT,
            container_type    TEXT,
            moisture_target   REAL,
            window_start      INTEGER,
            window_end        INTEGER,
            max_water_seconds INTEGER,
            notes             TEXT
        )
        """
    )
    conn.commit()
    return conn


def add_zone(conn: sqlite3.Connection, zone: dict) -> int:
    """Insert a zone; returns the new zone id."""
    cols = [f for f in ZONE_FIELDS if f in zone]
    placeholders = ", ".join("?" for _ in cols)
    values = [zone[c] for c in cols]
    conn.execute(
        f"INSERT INTO zones ({', '.join(cols)}) VALUES ({placeholders})", values
    )
    conn.commit()
    row = conn.execute("SELECT id FROM zones ORDER BY id DESC LIMIT 1").fetchone()
    return row[0]


def list_zones(conn: sqlite3.Connection) -> list:
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM zones ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_zone(conn: sqlite3.Connection, zone_id: int):
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM zones WHERE id = ?", (zone_id,)).fetchone()
    return dict(row) if row else None


def get_zone_by_sensor_key(conn: sqlite3.Connection, sensor_key: str):
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM zones WHERE sensor_key = ?", (sensor_key,)
    ).fetchone()
    return dict(row) if row else None


def update_zone(conn: sqlite3.Connection, zone_id: int, fields: dict) -> None:
    """Update only the provided, allowed fields on a zone."""
    cols = [f for f in ZONE_FIELDS if f in fields]
    if not cols:
        return
    set_clause = ", ".join(f"{c} = ?" for c in cols)
    values = [fields[c] for c in cols] + [zone_id]
    conn.execute(f"UPDATE zones SET {set_clause} WHERE id = ?", values)
    conn.commit()


def remove_zone(conn: sqlite3.Connection, zone_id: int) -> None:
    """Delete a zone and unassign any crops that pointed at it."""
    conn.execute("UPDATE garden_crops SET zone_id = NULL WHERE zone_id = ?", (zone_id,))
    conn.execute("DELETE FROM zones WHERE id = ?", (zone_id,))
    conn.commit()
