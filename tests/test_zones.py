import pytest

import db
from zones import (
    add_zone,
    get_zone,
    get_zone_by_sensor_key,
    init_zones_db,
    list_zones,
    remove_zone,
    update_zone,
)
from crop_planner import add_crop, crop_from_library, crops_in_zone, init_planner_db


@pytest.fixture
def conn():
    """One in-memory DB holding BOTH zones and planner tables."""
    c = db.connect(":memory:")
    init_planner_db(":memory:", conn=c)
    init_zones_db(":memory:", conn=c)
    yield c
    c.close()


def test_init_creates_zones_table(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(zones)").fetchall()]
    assert {"name", "sensor_key", "area_m2", "sun", "moisture_target"} <= set(cols)


def test_add_and_get_zone(conn):
    zid = add_zone(conn, {"name": "Bed A", "sensor_key": "zone-1",
                          "area_m2": 2.0, "sun": "full"})
    z = get_zone(conn, zid)
    assert z["name"] == "Bed A"
    assert z["sensor_key"] == "zone-1"
    assert z["area_m2"] == 2.0


def test_lookup_by_sensor_key_links_to_hardware(conn):
    add_zone(conn, {"name": "Bed A", "sensor_key": "zone-1", "area_m2": 2.0, "sun": "full"})
    z = get_zone_by_sensor_key(conn, "zone-1")
    assert z and z["name"] == "Bed A"
    assert get_zone_by_sensor_key(conn, "nope") is None


def test_update_zone_only_touches_given_fields(conn):
    zid = add_zone(conn, {"name": "Bed A", "area_m2": 2.0, "sun": "full"})
    update_zone(conn, zid, {"moisture_target": 55.0, "sun": "partial"})
    z = get_zone(conn, zid)
    assert z["moisture_target"] == 55.0
    assert z["sun"] == "partial"
    assert z["name"] == "Bed A"  # untouched


def test_remove_zone_unassigns_its_crops(conn):
    zid = add_zone(conn, {"name": "Bed A", "area_m2": 5.0, "sun": "full"})
    add_crop(conn, crop_from_library("tomato"))
    crop_id = conn.execute("SELECT id FROM garden_crops LIMIT 1").fetchone()[0]
    conn.execute("UPDATE garden_crops SET zone_id = ? WHERE id = ?", (zid, crop_id))
    conn.commit()
    assert len(crops_in_zone(conn, zid)) == 1

    remove_zone(conn, zid)
    assert get_zone(conn, zid) is None
    # crop survives but is unassigned
    row = conn.execute("SELECT zone_id FROM garden_crops WHERE id = ?", (crop_id,)).fetchone()
    assert row[0] is None
