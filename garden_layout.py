"""Garden layout — the physical, to-scale map of beds and containers.

A *feature* is one physical planting object the gardener places on a top-down
canvas: a raised bed, pot, grow bag, drum, trough, etc. It carries its real-world
shape and size (cm), its position on the canvas (cm from the top-left origin),
sun exposure, and an optional ``zone_id`` linking it to a watering zone.

This is the spatial layer *under* zones: you draw the garden here, then group
features into zones (one sensor + one valve each, see zones.py / placement.py).
Area drives plant counts (placement), sun drives what can grow, and proximity
guides which features should share a valve.
"""

import math
import sqlite3

import db
from plant_state import DB_PATH

# Fields a caller may set/update on a feature (id handled specially).
FEATURE_FIELDS = [
    "name", "template", "kind", "shape", "width_cm", "length_cm",
    "x_cm", "y_cm", "rotation_deg", "sun", "zone_id", "notes",
]


def init_layout_db(path: str = DB_PATH, conn: sqlite3.Connection | None = None):
    own = conn is None
    if own:
        conn = db.connect(path)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS garden_features (
            id            {db.auto_pk(path)},
            name          TEXT,
            template      TEXT,
            kind          TEXT,            -- 'bed' | 'container'
            shape         TEXT,            -- 'rect' | 'circle'
            width_cm      REAL,
            length_cm     REAL,            -- circle: width_cm = length_cm = diameter
            x_cm          REAL DEFAULT 0,
            y_cm          REAL DEFAULT 0,
            rotation_deg  REAL DEFAULT 0,
            sun           TEXT,
            zone_id       INTEGER,
            notes         TEXT
        )
        """
    )
    conn.commit()
    return conn


def feature_area_m2(feature: dict) -> float:
    """Real planting area in m² from the shape + dimensions (cm)."""
    w = feature.get("width_cm") or 0
    l = feature.get("length_cm") or 0
    if feature.get("shape") == "circle":
        r_cm = (w or l) / 2.0
        return round(math.pi * r_cm * r_cm / 10000.0, 3)
    return round((w * l) / 10000.0, 3)


def add_feature(conn: sqlite3.Connection, feature: dict) -> int:
    cols = [f for f in FEATURE_FIELDS if f in feature]
    placeholders = ", ".join("?" for _ in cols)
    values = [feature[c] for c in cols]
    conn.execute(
        f"INSERT INTO garden_features ({', '.join(cols)}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM garden_features ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row[0]


def list_features(conn: sqlite3.Connection) -> list:
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM garden_features ORDER BY id").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["area_m2"] = feature_area_m2(d)
        out.append(d)
    return out


def get_feature(conn: sqlite3.Connection, feature_id: int):
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM garden_features WHERE id = ?", (feature_id,)
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["area_m2"] = feature_area_m2(d)
    return d


def update_feature(conn: sqlite3.Connection, feature_id: int, fields: dict) -> None:
    cols = [f for f in FEATURE_FIELDS if f in fields]
    if not cols:
        return
    set_clause = ", ".join(f"{c} = ?" for c in cols)
    values = [fields[c] for c in cols] + [feature_id]
    conn.execute(
        f"UPDATE garden_features SET {set_clause} WHERE id = ?", values
    )
    conn.commit()


def remove_feature(conn: sqlite3.Connection, feature_id: int) -> None:
    conn.execute("DELETE FROM garden_features WHERE id = ?", (feature_id,))
    conn.commit()


def unassign_zone(conn: sqlite3.Connection, zone_id: int) -> None:
    """Detach features from a zone that's being deleted (keep the features)."""
    conn.execute(
        "UPDATE garden_features SET zone_id = NULL WHERE zone_id = ?", (zone_id,)
    )
    conn.commit()
