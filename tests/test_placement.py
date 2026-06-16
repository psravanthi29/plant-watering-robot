import pytest

import db
from crop_planner import (
    add_crop,
    assign_crop_zone,
    compute_crop_plan,
    crop_from_library,
    init_planner_db,
)
from placement import suggest_placement, zone_recommended_target
from zones import add_zone, init_zones_db


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    init_planner_db(":memory:", conn=c)
    init_zones_db(":memory:", conn=c)
    yield c
    c.close()


def _cp(key, household=10):
    crop = crop_from_library(key)
    return crop, compute_crop_plan(crop, household_size=household)


# --- the core constraint: don't mix water profiles in one zone ----------------

def test_crops_with_different_water_needs_go_to_different_zones():
    zones = [
        {"id": 1, "name": "A", "area_m2": 100.0, "sun": "full"},
        {"id": 2, "name": "B", "area_m2": 100.0, "sun": "full"},
    ]
    # tomato = high water, chilli = low water → must not share a zone
    result = suggest_placement([_cp("tomato"), _cp("chilli")], zones)
    assert not result["unplaced"]
    placed = {a["display"]: a["zone_id"] for a in result["assignments"]}
    assert placed["Tomato"] != placed["Chilli"]


def test_same_water_need_crops_can_share_a_zone():
    zones = [{"id": 1, "name": "A", "area_m2": 1000.0, "sun": "full"}]
    # tomato + cucumber are both "high" water
    result = suggest_placement([_cp("tomato"), _cp("cucumber")], zones)
    assert not result["unplaced"]
    zone_ids = {a["zone_id"] for a in result["assignments"]}
    assert zone_ids == {1}


# --- sun + area constraints ---------------------------------------------------

def test_full_sun_crop_rejected_from_shade_only_zone():
    zones = [{"id": 1, "name": "Shady", "area_m2": 100.0, "sun": "shade"}]
    result = suggest_placement([_cp("tomato")], zones)  # tomato needs full sun
    assert not result["assignments"]
    assert result["unplaced"][0]["crop_key"] == "tomato"
    assert "sun" in result["unplaced"][0]["reason"]


def test_crop_unplaced_when_no_zone_has_enough_area():
    zones = [{"id": 1, "name": "Tiny", "area_m2": 0.01, "sun": "full"}]
    result = suggest_placement([_cp("bottle_gourd")], zones)  # big spacing
    assert not result["assignments"]
    assert "area" in result["unplaced"][0]["reason"]


def test_no_zones_gives_helpful_reason():
    result = suggest_placement([_cp("tomato")], [])
    assert result["unplaced"][0]["reason"].startswith("no zones")


# --- recommended moisture target (auto-from-crops) ----------------------------

def test_zone_targets_reflect_committed_water_need():
    zones = [{"id": 1, "name": "A", "area_m2": 1000.0, "sun": "full"}]
    result = suggest_placement([_cp("tomato")], zones)  # high → 60%
    assert result["zone_targets"][1] == 60.0


def test_zone_recommended_target_uses_thirstiest_crop(conn):
    zid = add_zone(conn, {"name": "A", "area_m2": 1000.0, "sun": "full"})
    # add a medium and a high crop to the same zone (manual override scenario)
    add_crop(conn, crop_from_library("beans"))     # medium
    add_crop(conn, crop_from_library("cucumber"))  # high
    for row in conn.execute("SELECT id FROM garden_crops").fetchall():
        assign_crop_zone(conn, row[0], zid)
    assert zone_recommended_target(conn, zid) == 60.0  # thirstiest (high) wins


def test_zone_recommended_target_none_when_empty(conn):
    zid = add_zone(conn, {"name": "A", "area_m2": 5.0, "sun": "full"})
    assert zone_recommended_target(conn, zid) is None
