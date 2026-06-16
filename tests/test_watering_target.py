from datetime import datetime

import db
from crop_planner import add_crop, assign_crop_zone, crop_from_library, init_planner_db
from plant_state import zone_moisture_target
from scheduler import should_water
from zones import add_zone, init_zones_db


def _conn():
    c = db.connect(":memory:")
    init_planner_db(":memory:", conn=c)
    init_zones_db(":memory:", conn=c)
    return c


def test_zone_target_prefers_explicit_override():
    c = _conn()
    add_zone(c, {"name": "A", "sensor_key": "zone-1", "area_m2": 100,
                 "sun": "full", "moisture_target": 42.0})
    assert zone_moisture_target("zone-1", c) == 42.0


def test_zone_target_derived_from_crops_when_no_override():
    c = _conn()
    zid = add_zone(c, {"name": "A", "sensor_key": "zone-1", "area_m2": 100, "sun": "full"})
    add_crop(c, crop_from_library("tomato"))  # high -> 60
    cid = c.execute("SELECT id FROM garden_crops LIMIT 1").fetchone()[0]
    assign_crop_zone(c, cid, zid)
    assert zone_moisture_target("zone-1", c) == 60.0


def test_zone_target_none_for_unknown_zone():
    assert zone_moisture_target("does-not-exist", _conn()) is None


def test_should_water_respects_per_zone_threshold():
    noon = datetime(2026, 6, 16, 12, 0)
    # 45% moisture: dry relative to a thirsty crop (60), fine for the default (30)
    assert should_water(45, noon, threshold=60)[0] is True
    assert should_water(45, noon)[0] is False
