from datetime import date

import pytest

from crop_planner import (
    SEED_LIBRARY,
    compute_crop_plan,
    crop_from_library,
    effective_weekly_demand,
    generate_sowing_calendar,
    upcoming_sowings,
)

REQUIRED_FIELDS = {
    "display", "category", "type", "days_to_maturity", "harvest_window_days",
    "yield_per_plant_kg", "spacing_cm", "succession_interval_days",
    "seed_to_transplant_days", "per_person_weekly_g",
}


# --- library integrity (guards every entry, incl. new AP/Telangana crops) ---

def test_every_library_entry_is_well_formed_and_plannable():
    for key, c in SEED_LIBRARY.items():
        missing = REQUIRED_FIELDS - set(c.keys())
        assert not missing, f"{key} missing fields: {missing}"
        assert c["type"] in ("continuous", "single", "perennial"), f"{key} bad type"
        assert c["category"] in ("leafy", "vegetable", "fruit"), f"{key} bad category"
        assert c["yield_per_plant_kg"] > 0, f"{key} needs positive yield"
        assert c["spacing_cm"] > 0, f"{key} needs positive spacing"
        if c["type"] != "perennial":
            assert c["succession_interval_days"] > 0, f"{key} needs succession interval"
        # full plan + calendar must compute without error for a 10-person household
        crop = crop_from_library(key)
        plan = compute_crop_plan(crop, household_size=10)
        assert plan["plants_needed"] >= 1, f"{key} computed 0 plants"
        cal = generate_sowing_calendar(crop, plan, date(2026, 6, 10), horizon_days=120)
        assert len(cal) >= 1, f"{key} produced no sowing events"


def test_andhra_telangana_staples_present():
    expected = {
        "gongura", "malabar_spinach", "curry_leaf", "mint",
        "bitter_gourd", "snake_gourd", "ash_gourd", "pumpkin", "dosakaya",
        "cluster_beans", "field_beans", "cowpea",
        "ivy_gourd", "drumstick",
        "colocasia", "sweet_potato", "garlic", "ginger",
        "mango", "sapota", "custard_apple", "pomegranate",
    }
    missing = expected - set(SEED_LIBRARY.keys())
    assert not missing, f"missing AP/Telangana crops: {missing}"


# --- demand -----------------------------------------------------------------

def test_weekly_demand_uses_per_person_times_household_when_no_override():
    crop = crop_from_library("spinach")  # 150 g/person/week
    # 150g * 10 people = 1500g = 1.5kg
    assert effective_weekly_demand(crop, household_size=10) == pytest.approx(1.5)


def test_weekly_demand_override_wins():
    crop = crop_from_library("spinach", weekly_demand_kg=3.0)
    assert effective_weekly_demand(crop, household_size=10) == 3.0


# --- continuous crops -------------------------------------------------------

def test_continuous_plan_scales_with_household():
    crop = crop_from_library("spinach")
    small = compute_crop_plan(crop, household_size=2)
    big = compute_crop_plan(crop, household_size=20)
    assert big["plants_needed"] > small["plants_needed"]
    assert big["type"] == "continuous"


def test_continuous_batch_size_never_exceeds_total_plants():
    for key, c in SEED_LIBRARY.items():
        if c["type"] != "continuous":
            continue
        crop = crop_from_library(key)
        plan = compute_crop_plan(crop, household_size=10)
        assert plan["batch_size"] <= plan["plants_needed"]
        assert plan["num_batches"] >= 1


# --- single-harvest crops ---------------------------------------------------

def test_single_harvest_plant_count_positive():
    crop = crop_from_library("cabbage")
    plan = compute_crop_plan(crop, household_size=10)
    assert plan["type"] == "single"
    assert plan["plants_needed"] >= plan["batch_size"] >= 1


# --- perennials -------------------------------------------------------------

def test_perennial_uses_annual_yield_and_plants_once():
    crop = crop_from_library("banana")
    plan = compute_crop_plan(crop, household_size=10)
    assert plan["type"] == "perennial"
    assert plan["num_batches"] == 1
    # banana: 500 g/person/wk * 10 = 5 kg/wk -> 260 kg/yr / 25 kg per plant = 11 plants
    assert plan["plants_needed"] == 11
    cal = generate_sowing_calendar(crop, plan, date(2026, 6, 10))
    assert len(cal) == 1 and cal[0]["one_time"] is True


# --- sowing calendar & succession ------------------------------------------

def test_sowing_calendar_is_staggered_by_interval():
    crop = crop_from_library("radish")  # succession every 14 days
    plan = compute_crop_plan(crop, household_size=10)
    cal = generate_sowing_calendar(crop, plan, date(2026, 6, 10), horizon_days=60)
    gaps = [(cal[i + 1]["sow_date"] - cal[i]["sow_date"]).days for i in range(len(cal) - 1)]
    assert all(g == 14 for g in gaps)
    # first harvest is sow + days_to_maturity
    assert (cal[0]["first_harvest_date"] - cal[0]["sow_date"]).days == crop["days_to_maturity"]


def test_transplant_offset_applied_for_transplanted_crops():
    crop = crop_from_library("tomato")  # seed_to_transplant_days = 25
    plan = compute_crop_plan(crop, household_size=10)
    cal = generate_sowing_calendar(crop, plan, date(2026, 6, 10), horizon_days=30)
    assert (cal[0]["transplant_date"] - cal[0]["sow_date"]).days == 25


def test_upcoming_sowings_filters_to_window_and_sorts():
    crops = [
        (crop_from_library("radish"), compute_crop_plan(crop_from_library("radish"), 10)),
        (crop_from_library("spinach"), compute_crop_plan(crop_from_library("spinach"), 10)),
    ]
    start = date(2026, 6, 10)
    events = upcoming_sowings(crops, start, within_days=30)
    assert events, "expected at least one upcoming sow event"
    assert all(start <= e["sow_date"] <= date(2026, 7, 10) for e in events)
    assert events == sorted(events, key=lambda e: e["sow_date"])
