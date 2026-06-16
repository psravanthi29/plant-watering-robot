"""Garden crop planner — succession sowing, plant counts, spacing/area.

Software-only. Helps plan a terrace garden for near-continuous year-round produce:
given a target crop list and household size, it computes
  - how many plants are needed to meet weekly demand,
  - a staggered (succession) sowing calendar so harvests don't all land at once,
  - the growing area required.

Pure planning math lives in compute_crop_plan() / generate_sowing_calendar()
(no DB, easy to test). Persistence is a small additive set of tables in plant.db.

This is v1 — sowing/quantity/spacing only. Nutrient suggestions, plant-care
schedules, etc. are intended follow-ons (see memory/ docs).

All horticultural numbers in SEED_LIBRARY are rough, India-terrace estimates and
are meant to be edited per the user's actual varieties/conditions.
"""

import math
import sqlite3
from datetime import date, datetime, timedelta

import db
from plant_state import DB_PATH

DEFAULT_HOUSEHOLD_SIZE = 10

# Crop "type" controls the planning model:
#   continuous  — cut-and-come-again / repeat-fruiting; harvested over a window
#   single      — whole plant harvested once (heads, roots)
#   perennial   — fruit trees/plants; planted once, yearly yield basis
#
# Fields: days_to_maturity (sow->first harvest), harvest_window_days (productive
# span once started), yield_per_plant_kg (total over window; for perennial = per
# YEAR), spacing_cm (plant footprint), succession_interval_days (how often to sow
# a fresh batch), seed_to_transplant_days (0 = direct sow), per_person_weekly_g
# (default household demand basis).
#
# DATA PROVENANCE (verified June 2026): days_to_maturity, spacing_cm, and growth
# `type` are corrected against horticulture references (OSU/UMD/Clemson/Virginia
# Tech extension guides, Old Farmer's Almanac, agrifarming.in / agriculture.institute
# / IndiaAgroNet for India-specific crops) — see memory/garden-planner.md for the
# source list. yield_per_plant_kg are MID-RANGE home-garden estimates (per-plant
# yield genuinely varies 2-3x by variety, soil, and care). per_person_weekly_g are
# consumption defaults (a household preference, not a horticultural fact) — tune
# them, or just override weekly demand per crop in the planner.
SEED_LIBRARY = {
    # --- Leafy greens (continuous) ---
    "spinach":     {"display": "Spinach (Palak)",      "category": "leafy", "type": "continuous", "days_to_maturity": 30, "harvest_window_days": 50, "yield_per_plant_kg": 0.25, "spacing_cm": 10, "succession_interval_days": 21, "seed_to_transplant_days": 0, "per_person_weekly_g": 150},
    "amaranth":    {"display": "Amaranth (Thotakura)", "category": "leafy", "type": "continuous", "days_to_maturity": 30, "harvest_window_days": 40, "yield_per_plant_kg": 0.20, "spacing_cm": 20, "succession_interval_days": 18, "seed_to_transplant_days": 0, "per_person_weekly_g": 120},
    "fenugreek":   {"display": "Fenugreek (Methi)",    "category": "leafy", "type": "continuous", "days_to_maturity": 25, "harvest_window_days": 25, "yield_per_plant_kg": 0.12, "spacing_cm": 10, "succession_interval_days": 15, "seed_to_transplant_days": 0, "per_person_weekly_g": 80},
    "coriander":   {"display": "Coriander (Cilantro)", "category": "leafy", "type": "continuous", "days_to_maturity": 30, "harvest_window_days": 30, "yield_per_plant_kg": 0.08, "spacing_cm": 8,  "succession_interval_days": 15, "seed_to_transplant_days": 0, "per_person_weekly_g": 60},
    "lettuce":     {"display": "Lettuce",              "category": "leafy", "type": "continuous", "days_to_maturity": 45, "harvest_window_days": 35, "yield_per_plant_kg": 0.30, "spacing_cm": 25, "succession_interval_days": 21, "seed_to_transplant_days": 21, "per_person_weekly_g": 100},
    "spring_onion":{"display": "Spring Onion",         "category": "leafy", "type": "continuous", "days_to_maturity": 60, "harvest_window_days": 30, "yield_per_plant_kg": 0.05, "spacing_cm": 8,  "succession_interval_days": 21, "seed_to_transplant_days": 0, "per_person_weekly_g": 50},

    # --- Leafy greens — Andhra/Telangana staples ---
    "gongura":     {"display": "Gongura (Roselle/Sorrel)", "category": "leafy", "type": "continuous", "days_to_maturity": 45, "harvest_window_days": 60, "yield_per_plant_kg": 0.30, "spacing_cm": 45, "succession_interval_days": 30, "seed_to_transplant_days": 0, "per_person_weekly_g": 150},
    "malabar_spinach": {"display": "Malabar Spinach (Bachali)", "category": "leafy", "type": "continuous", "days_to_maturity": 45, "harvest_window_days": 90, "yield_per_plant_kg": 0.50, "spacing_cm": 30, "succession_interval_days": 45, "seed_to_transplant_days": 0, "per_person_weekly_g": 120},
    "mint":        {"display": "Mint (Pudina)",        "category": "leafy", "type": "perennial",  "days_to_maturity": 60, "harvest_window_days": 200, "yield_per_plant_kg": 0.80, "spacing_cm": 20, "succession_interval_days": 0, "seed_to_transplant_days": 0, "per_person_weekly_g": 40},
    "sorrel_chukka": {"display": "Sorrel (Chukkakura)", "category": "leafy", "type": "continuous", "days_to_maturity": 40, "harvest_window_days": 50, "yield_per_plant_kg": 0.20, "spacing_cm": 20, "succession_interval_days": 30, "seed_to_transplant_days": 0, "per_person_weekly_g": 100},
    "curry_leaf":  {"display": "Curry Leaf (Karivepaku)", "category": "leafy", "type": "perennial",  "days_to_maturity": 365, "harvest_window_days": 200, "yield_per_plant_kg": 2.0, "spacing_cm": 150, "succession_interval_days": 0, "seed_to_transplant_days": 0, "per_person_weekly_g": 30},

    # --- Vegetables (continuous / repeat-fruiting) ---
    "tomato":      {"display": "Tomato",       "category": "vegetable", "type": "continuous", "days_to_maturity": 75, "harvest_window_days": 90,  "yield_per_plant_kg": 3.5, "spacing_cm": 60,  "succession_interval_days": 45, "seed_to_transplant_days": 25, "per_person_weekly_g": 500},
    "okra":        {"display": "Okra (Bhindi)", "category": "vegetable", "type": "continuous", "days_to_maturity": 55, "harvest_window_days": 70,  "yield_per_plant_kg": 1.0, "spacing_cm": 45,  "succession_interval_days": 30, "seed_to_transplant_days": 0,  "per_person_weekly_g": 300},
    "brinjal":     {"display": "Brinjal (Eggplant)", "category": "vegetable", "type": "continuous", "days_to_maturity": 75, "harvest_window_days": 120, "yield_per_plant_kg": 2.5, "spacing_cm": 60,  "succession_interval_days": 60, "seed_to_transplant_days": 30, "per_person_weekly_g": 300},
    "chilli":      {"display": "Chilli",       "category": "vegetable", "type": "continuous", "days_to_maturity": 90, "harvest_window_days": 150, "yield_per_plant_kg": 1.5, "spacing_cm": 50,  "succession_interval_days": 90, "seed_to_transplant_days": 30, "per_person_weekly_g": 100},
    "capsicum":    {"display": "Capsicum (Bell Pepper)", "category": "vegetable", "type": "continuous", "days_to_maturity": 80, "harvest_window_days": 90, "yield_per_plant_kg": 1.0, "spacing_cm": 45, "succession_interval_days": 60, "seed_to_transplant_days": 30, "per_person_weekly_g": 200},
    "beans":       {"display": "Beans",        "category": "vegetable", "type": "continuous", "days_to_maturity": 50, "harvest_window_days": 45,  "yield_per_plant_kg": 0.6, "spacing_cm": 20,  "succession_interval_days": 21, "seed_to_transplant_days": 0,  "per_person_weekly_g": 300},
    "cucumber":    {"display": "Cucumber",     "category": "vegetable", "type": "continuous", "days_to_maturity": 55, "harvest_window_days": 45,  "yield_per_plant_kg": 2.5, "spacing_cm": 60,  "succession_interval_days": 30, "seed_to_transplant_days": 0,  "per_person_weekly_g": 300},
    "bottle_gourd":{"display": "Bottle Gourd", "category": "vegetable", "type": "continuous", "days_to_maturity": 80, "harvest_window_days": 90,  "yield_per_plant_kg": 8.0, "spacing_cm": 100, "succession_interval_days": 60, "seed_to_transplant_days": 0,  "per_person_weekly_g": 400},
    "ridge_gourd": {"display": "Ridge Gourd",  "category": "vegetable", "type": "continuous", "days_to_maturity": 65, "harvest_window_days": 80,  "yield_per_plant_kg": 4.0, "spacing_cm": 80,  "succession_interval_days": 45, "seed_to_transplant_days": 0,  "per_person_weekly_g": 300},

    # --- Vegetables — Andhra/Telangana gourds & beans (continuous) ---
    "bitter_gourd":{"display": "Bitter Gourd (Kakarakaya)", "category": "vegetable", "type": "continuous", "days_to_maturity": 60, "harvest_window_days": 70, "yield_per_plant_kg": 1.5, "spacing_cm": 60,  "succession_interval_days": 30, "seed_to_transplant_days": 0, "per_person_weekly_g": 200},
    "snake_gourd": {"display": "Snake Gourd (Potlakaya)",   "category": "vegetable", "type": "continuous", "days_to_maturity": 65, "harvest_window_days": 70, "yield_per_plant_kg": 3.5, "spacing_cm": 80,  "succession_interval_days": 45, "seed_to_transplant_days": 0, "per_person_weekly_g": 300},
    "ash_gourd":   {"display": "Ash Gourd (Boodida Gummadi)", "category": "vegetable", "type": "continuous", "days_to_maturity": 90, "harvest_window_days": 60, "yield_per_plant_kg": 6.0, "spacing_cm": 120, "succession_interval_days": 90, "seed_to_transplant_days": 0, "per_person_weekly_g": 300},
    "pumpkin":     {"display": "Pumpkin (Gummadikaya)",     "category": "vegetable", "type": "continuous", "days_to_maturity": 100, "harvest_window_days": 60, "yield_per_plant_kg": 8.0, "spacing_cm": 150, "succession_interval_days": 90, "seed_to_transplant_days": 0, "per_person_weekly_g": 300},
    "dosakaya":    {"display": "Dosakaya (Yellow Cucumber)", "category": "vegetable", "type": "continuous", "days_to_maturity": 60, "harvest_window_days": 45, "yield_per_plant_kg": 2.0, "spacing_cm": 60,  "succession_interval_days": 30, "seed_to_transplant_days": 0, "per_person_weekly_g": 250},
    "cluster_beans":{"display": "Cluster Beans (Goru Chikkudu)", "category": "vegetable", "type": "continuous", "days_to_maturity": 50, "harvest_window_days": 45, "yield_per_plant_kg": 0.5, "spacing_cm": 30, "succession_interval_days": 21, "seed_to_transplant_days": 0, "per_person_weekly_g": 250},
    "field_beans": {"display": "Field/Hyacinth Beans (Chikkudu)", "category": "vegetable", "type": "continuous", "days_to_maturity": 70, "harvest_window_days": 90, "yield_per_plant_kg": 1.0, "spacing_cm": 40, "succession_interval_days": 45, "seed_to_transplant_days": 0, "per_person_weekly_g": 250},
    "cowpea":      {"display": "Cowpea / Long Beans (Alasandalu)", "category": "vegetable", "type": "continuous", "days_to_maturity": 45, "harvest_window_days": 50, "yield_per_plant_kg": 0.6, "spacing_cm": 25, "succession_interval_days": 21, "seed_to_transplant_days": 0, "per_person_weekly_g": 250},

    # --- Vegetables — perennial vine / tree (plant once) ---
    "ivy_gourd":   {"display": "Ivy Gourd (Dondakaya)", "category": "vegetable", "type": "perennial", "days_to_maturity": 90, "harvest_window_days": 200, "yield_per_plant_kg": 4.0, "spacing_cm": 100, "succession_interval_days": 0, "seed_to_transplant_days": 0, "per_person_weekly_g": 200},
    "drumstick":   {"display": "Drumstick / Moringa (Munaga)", "category": "vegetable", "type": "perennial", "days_to_maturity": 240, "harvest_window_days": 150, "yield_per_plant_kg": 15.0, "spacing_cm": 300, "succession_interval_days": 0, "seed_to_transplant_days": 0, "per_person_weekly_g": 200},

    # --- Vegetables (single harvest: heads / roots) ---
    "cabbage":     {"display": "Cabbage",     "category": "vegetable", "type": "single", "days_to_maturity": 90,  "harvest_window_days": 7,  "yield_per_plant_kg": 1.0,  "spacing_cm": 45, "succession_interval_days": 30, "seed_to_transplant_days": 28, "per_person_weekly_g": 300},
    "cauliflower": {"display": "Cauliflower", "category": "vegetable", "type": "single", "days_to_maturity": 90,  "harvest_window_days": 7,  "yield_per_plant_kg": 0.8,  "spacing_cm": 50, "succession_interval_days": 30, "seed_to_transplant_days": 28, "per_person_weekly_g": 250},
    "carrot":      {"display": "Carrot",      "category": "vegetable", "type": "single", "days_to_maturity": 70,  "harvest_window_days": 14, "yield_per_plant_kg": 0.10, "spacing_cm": 6,  "succession_interval_days": 21, "seed_to_transplant_days": 0,  "per_person_weekly_g": 200},
    "radish":      {"display": "Radish",      "category": "vegetable", "type": "single", "days_to_maturity": 28,  "harvest_window_days": 10, "yield_per_plant_kg": 0.10, "spacing_cm": 5, "succession_interval_days": 14, "seed_to_transplant_days": 0,  "per_person_weekly_g": 150},
    "beetroot":    {"display": "Beetroot",    "category": "vegetable", "type": "single", "days_to_maturity": 60,  "harvest_window_days": 14, "yield_per_plant_kg": 0.15, "spacing_cm": 8, "succession_interval_days": 21, "seed_to_transplant_days": 0,  "per_person_weekly_g": 150},
    "onion":       {"display": "Onion",       "category": "vegetable", "type": "single", "days_to_maturity": 110, "harvest_window_days": 14, "yield_per_plant_kg": 0.12, "spacing_cm": 10, "succession_interval_days": 90, "seed_to_transplant_days": 40, "per_person_weekly_g": 400},
    "potato":      {"display": "Potato",      "category": "vegetable", "type": "single", "days_to_maturity": 100, "harvest_window_days": 14, "yield_per_plant_kg": 0.60, "spacing_cm": 30, "succession_interval_days": 90, "seed_to_transplant_days": 0,  "per_person_weekly_g": 600},
    "colocasia":   {"display": "Colocasia/Taro (Chamadumpa)", "category": "vegetable", "type": "single", "days_to_maturity": 180, "harvest_window_days": 14, "yield_per_plant_kg": 0.40, "spacing_cm": 50, "succession_interval_days": 90, "seed_to_transplant_days": 0, "per_person_weekly_g": 200},
    "sweet_potato":{"display": "Sweet Potato (Chilakada Dumpa)", "category": "vegetable", "type": "single", "days_to_maturity": 100, "harvest_window_days": 14, "yield_per_plant_kg": 0.50, "spacing_cm": 30, "succession_interval_days": 90, "seed_to_transplant_days": 0, "per_person_weekly_g": 250},
    "garlic":      {"display": "Garlic (Vellulli)", "category": "vegetable", "type": "single", "days_to_maturity": 180, "harvest_window_days": 14, "yield_per_plant_kg": 0.05, "spacing_cm": 10, "succession_interval_days": 120, "seed_to_transplant_days": 0, "per_person_weekly_g": 100},
    "ginger":      {"display": "Ginger (Allam)", "category": "vegetable", "type": "single", "days_to_maturity": 300, "harvest_window_days": 21, "yield_per_plant_kg": 0.30, "spacing_cm": 25, "succession_interval_days": 240, "seed_to_transplant_days": 0, "per_person_weekly_g": 80},

    # --- Fruit (perennial: planted once, yearly yield basis) ---
    "banana":      {"display": "Banana",  "category": "fruit", "type": "perennial", "days_to_maturity": 390, "harvest_window_days": 60,  "yield_per_plant_kg": 25.0, "spacing_cm": 200, "succession_interval_days": 0, "seed_to_transplant_days": 0, "per_person_weekly_g": 500},
    "papaya":      {"display": "Papaya",  "category": "fruit", "type": "perennial", "days_to_maturity": 240, "harvest_window_days": 120, "yield_per_plant_kg": 30.0, "spacing_cm": 200, "succession_interval_days": 0, "seed_to_transplant_days": 0, "per_person_weekly_g": 400},
    "lemon":       {"display": "Lemon",   "category": "fruit", "type": "perennial", "days_to_maturity": 730, "harvest_window_days": 120, "yield_per_plant_kg": 30.0, "spacing_cm": 450, "succession_interval_days": 0, "seed_to_transplant_days": 0, "per_person_weekly_g": 150},
    "guava":       {"display": "Guava",   "category": "fruit", "type": "perennial", "days_to_maturity": 730, "harvest_window_days": 120, "yield_per_plant_kg": 40.0, "spacing_cm": 400, "succession_interval_days": 0, "seed_to_transplant_days": 0, "per_person_weekly_g": 200},
    "mango":        {"display": "Mango (Mamidi)",       "category": "fruit", "type": "perennial", "days_to_maturity": 1095, "harvest_window_days": 60,  "yield_per_plant_kg": 50.0, "spacing_cm": 1000, "succession_interval_days": 0, "seed_to_transplant_days": 0, "per_person_weekly_g": 300},
    "sapota":       {"display": "Sapota (Chikoo)",      "category": "fruit", "type": "perennial", "days_to_maturity": 1095, "harvest_window_days": 120, "yield_per_plant_kg": 40.0, "spacing_cm": 600, "succession_interval_days": 0, "seed_to_transplant_days": 0, "per_person_weekly_g": 150},
    "custard_apple":{"display": "Custard Apple (Sitaphal)", "category": "fruit", "type": "perennial", "days_to_maturity": 730, "harvest_window_days": 90, "yield_per_plant_kg": 20.0, "spacing_cm": 400, "succession_interval_days": 0, "seed_to_transplant_days": 0, "per_person_weekly_g": 100},
    "pomegranate":  {"display": "Pomegranate (Danimma)", "category": "fruit", "type": "perennial", "days_to_maturity": 730, "harvest_window_days": 90, "yield_per_plant_kg": 25.0, "spacing_cm": 400, "succession_interval_days": 0, "seed_to_transplant_days": 0, "per_person_weekly_g": 150},
}

# --------------------------------------------------------------------------- #
# Water / sun needs — the link to the watering hardware                         #
# --------------------------------------------------------------------------- #
# One zone = one moisture sensor + one valve, so every crop in a zone is watered
# together. Crops are therefore grouped into zones by WATER need (placement.py),
# and a zone's moisture target is derived from the crops in it (WATER_TARGET).
# These are coarse, editable defaults — category default + per-crop overrides —
# rather than another column on all 47 library rows.

WATER_TARGET = {"high": 60.0, "medium": 50.0, "low": 40.0}  # target soil-moisture %
WATER_RANK = {"low": 0, "medium": 1, "high": 2}

_WATER_NEED_DEFAULT_BY_CATEGORY = {"leafy": "high", "vegetable": "medium", "fruit": "low"}
_WATER_NEED_OVERRIDE = {
    # thirsty fruiting/vining vegetables and moisture-loving crops
    "tomato": "high", "cucumber": "high", "bottle_gourd": "high", "ridge_gourd": "high",
    "snake_gourd": "high", "bitter_gourd": "high", "ash_gourd": "high", "pumpkin": "high",
    "dosakaya": "high", "ginger": "high", "colocasia": "high",
    "banana": "high", "papaya": "high", "malabar_spinach": "high", "mint": "high",
    # drought-tolerant
    "chilli": "low", "drumstick": "low", "curry_leaf": "low", "garlic": "low",
    # in-between
    "gongura": "medium", "ivy_gourd": "medium", "sweet_potato": "medium",
}

_SUN_NEED_DEFAULT_BY_CATEGORY = {"leafy": "partial", "vegetable": "full", "fruit": "full"}
_SUN_NEED_OVERRIDE = {
    "ginger": "partial", "colocasia": "partial", "mint": "partial", "curry_leaf": "partial",
}


def _default_water_need(key, category) -> str:
    return _WATER_NEED_OVERRIDE.get(key) or _WATER_NEED_DEFAULT_BY_CATEGORY.get(category, "medium")


def _default_sun_need(key, category) -> str:
    return _SUN_NEED_OVERRIDE.get(key) or _SUN_NEED_DEFAULT_BY_CATEGORY.get(category, "full")


def crop_water_need(crop: dict) -> str:
    """'low' | 'medium' | 'high' — stored value wins, else curated default."""
    return crop.get("water_need") or _default_water_need(crop.get("key"), crop.get("category"))


def crop_sun_need(crop: dict) -> str:
    """'shade' | 'partial' | 'full' — the crop's minimum acceptable sun."""
    return crop.get("sun_need") or _default_sun_need(crop.get("key"), crop.get("category"))


# Columns persisted per target crop (mirrors a normalized library entry + demand override).
CROP_FIELDS = [
    "key", "display", "category", "type", "days_to_maturity", "harvest_window_days",
    "yield_per_plant_kg", "spacing_cm", "succession_interval_days",
    "seed_to_transplant_days", "per_person_weekly_g", "weekly_demand_kg",
    "water_need", "sun_need",
]


# --------------------------------------------------------------------------- #
# Pure planning math (no DB) — unit-testable                                   #
# --------------------------------------------------------------------------- #

def effective_weekly_demand(crop: dict, household_size: int) -> float:
    """Weekly demand in kg: explicit override if set, else per-person × household."""
    override = crop.get("weekly_demand_kg")
    if override not in (None, "", 0, 0.0):
        return float(override)
    return (float(crop["per_person_weekly_g"]) * household_size) / 1000.0


def compute_crop_plan(crop: dict, household_size: int = DEFAULT_HOUSEHOLD_SIZE) -> dict:
    """Compute plant count, batch size/cadence, and area for one crop.

    Returns a dict with: weekly_demand_kg, type, plants_needed, batch_size,
    num_batches, succession_interval_days, area_m2, and (perennial) note.
    """
    demand = effective_weekly_demand(crop, household_size)
    ctype = crop["type"]
    spacing_m = float(crop["spacing_cm"]) / 100.0
    yield_per_plant = float(crop["yield_per_plant_kg"])

    plan = {"weekly_demand_kg": round(demand, 2), "type": ctype}

    if ctype == "perennial":
        annual_demand = demand * 52
        plants = math.ceil(annual_demand / yield_per_plant) if yield_per_plant else 0
        plan.update(
            plants_needed=plants, batch_size=plants, num_batches=1,
            succession_interval_days=None,
            area_m2=round(plants * spacing_m * spacing_m, 2),
            note="Perennial — plant once; based on yearly yield per plant.",
        )
        return plan

    if ctype == "single":
        weeks_per_batch = float(crop["succession_interval_days"]) / 7.0
        batch = math.ceil(demand * weeks_per_batch / yield_per_plant) if yield_per_plant else 0
        pipeline = max(1, math.ceil(float(crop["days_to_maturity"]) / float(crop["succession_interval_days"])))
        plants = batch * pipeline
    else:  # continuous
        weekly_yield_per_plant = yield_per_plant / (float(crop["harvest_window_days"]) / 7.0)
        plants = math.ceil(demand / weekly_yield_per_plant) if weekly_yield_per_plant else 0
        pipeline = max(1, round(float(crop["harvest_window_days"]) / float(crop["succession_interval_days"])))
        batch = math.ceil(plants / pipeline) if pipeline else plants

    plan.update(
        plants_needed=plants,
        batch_size=batch,
        num_batches=pipeline,
        succession_interval_days=crop["succession_interval_days"],
        area_m2=round(plants * spacing_m * spacing_m, 2),
    )
    return plan


def generate_sowing_calendar(crop: dict, plan: dict, start_date: date,
                             horizon_days: int = 365) -> list:
    """Staggered sow events from start_date over horizon_days.

    Each event: {sow_date, batch_size, transplant_date, first_harvest_date}.
    Perennials return a single one-time planting event.
    """
    if crop["type"] == "perennial":
        return [{
            "sow_date": start_date,
            "batch_size": plan["plants_needed"],
            "transplant_date": start_date,
            "first_harvest_date": start_date + timedelta(days=int(crop["days_to_maturity"])),
            "one_time": True,
        }]

    interval = int(crop["succession_interval_days"])
    if interval <= 0:
        interval = horizon_days  # safety: avoid div-by-zero / infinite batches

    events = []
    n = horizon_days // interval + 1
    for i in range(n):
        sow = start_date + timedelta(days=i * interval)
        transplant = sow + timedelta(days=int(crop.get("seed_to_transplant_days", 0)))
        harvest = sow + timedelta(days=int(crop["days_to_maturity"]))
        events.append({
            "sow_date": sow,
            "batch_size": plan["batch_size"],
            "transplant_date": transplant,
            "first_harvest_date": harvest,
            "one_time": False,
        })
    return events


def upcoming_sowings(crops_with_plans: list, start_date: date,
                     within_days: int = 60) -> list:
    """Across all crops, sow events whose sow_date falls within the next window.

    crops_with_plans: list of (crop_dict, plan_dict). Returns events sorted by
    date, each annotated with the crop display name.
    """
    horizon = within_days
    cutoff = start_date + timedelta(days=within_days)
    out = []
    for crop, plan in crops_with_plans:
        for ev in generate_sowing_calendar(crop, plan, start_date, horizon_days=horizon):
            if start_date <= ev["sow_date"] <= cutoff:
                out.append({**ev, "crop": crop["display"], "type": crop["type"]})
    out.sort(key=lambda e: e["sow_date"])
    return out


# --------------------------------------------------------------------------- #
# Persistence (additive tables in plant.db)                                    #
# --------------------------------------------------------------------------- #

def init_planner_db(path: str = DB_PATH, conn: sqlite3.Connection | None = None):
    own = conn is None
    if own:
        conn = db.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS garden_settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS garden_tasks (
            id          {db.auto_pk(path)},
            crop_row_id INTEGER NOT NULL,
            crop_key    TEXT,
            display     TEXT NOT NULL,
            sow_date    TEXT NOT NULL,
            batch_size  INTEGER,
            status      TEXT NOT NULL DEFAULT 'pending',
            done_on     TEXT,
            UNIQUE(crop_row_id, sow_date)
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS garden_crops (
            id                       {db.auto_pk(path)},
            key                      TEXT,
            display                  TEXT NOT NULL,
            category                 TEXT,
            type                     TEXT NOT NULL,
            days_to_maturity         INTEGER,
            harvest_window_days      INTEGER,
            yield_per_plant_kg       REAL,
            spacing_cm               INTEGER,
            succession_interval_days INTEGER,
            seed_to_transplant_days  INTEGER,
            per_person_weekly_g      REAL,
            weekly_demand_kg         REAL,
            water_need               TEXT,
            sun_need                 TEXT,
            zone_id                  INTEGER
        )
        """
    )
    conn.commit()
    # Migrate older databases that predate the integration columns.
    for col, coldef in (("water_need", "TEXT"), ("sun_need", "TEXT"), ("zone_id", "INTEGER")):
        _add_column_if_missing(conn, "garden_crops", col, coldef, path)
    return conn


def _table_columns(conn, table: str, path: str) -> set:
    if db._is_pg(path):
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
            (table,),
        ).fetchall()
        return {r[0] for r in rows}
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def _add_column_if_missing(conn, table: str, column: str, coldef: str, path: str) -> None:
    if column not in _table_columns(conn, table, path):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coldef}")
        conn.commit()


def get_setting(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM garden_settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute(
        "INSERT INTO garden_settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()


def get_household_size(conn: sqlite3.Connection) -> int:
    return int(get_setting(conn, "household_size", DEFAULT_HOUSEHOLD_SIZE))


def get_plan_start_date(conn: sqlite3.Connection) -> date:
    raw = get_setting(conn, "plan_start_date")
    if raw:
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


def add_crop(conn: sqlite3.Connection, crop: dict) -> None:
    cols = ", ".join(CROP_FIELDS)
    placeholders = ", ".join("?" for _ in CROP_FIELDS)
    values = [crop.get(f) for f in CROP_FIELDS]
    conn.execute(f"INSERT INTO garden_crops ({cols}) VALUES ({placeholders})", values)
    conn.commit()


def list_crops(conn: sqlite3.Connection) -> list:
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM garden_crops ORDER BY category, display").fetchall()
    return [dict(r) for r in rows]


def remove_crop(conn: sqlite3.Connection, crop_id: int) -> None:
    conn.execute("DELETE FROM garden_crops WHERE id = ?", (crop_id,))
    conn.commit()


def set_crop_demand(conn: sqlite3.Connection, crop_id: int, weekly_demand_kg) -> None:
    """Set (or clear) a crop's weekly-demand override.

    weekly_demand_kg=None reverts the crop to AUTO (household × per-person basis).
    """
    conn.execute(
        "UPDATE garden_crops SET weekly_demand_kg = ? WHERE id = ?",
        (weekly_demand_kg, crop_id),
    )
    conn.commit()


def is_demand_auto(crop: dict) -> bool:
    """True if this crop's demand is auto-derived from household size (no override)."""
    return crop.get("weekly_demand_kg") in (None, "", 0, 0.0)


# --------------------------------------------------------------------------- #
# Sowing tasks — trackable to-dos with pending/done state                      #
# --------------------------------------------------------------------------- #

def sync_tasks(conn: sqlite3.Connection, crops_with_plans: list,
               start_date: date, within_days: int = 60) -> None:
    """Materialize upcoming sow events as persistent tasks (idempotent).

    Each (crop_row_id, sow_date) pair is inserted once; re-running never
    duplicates and never touches tasks the user already marked done.
    Tasks for crops that were removed from the plan are cleaned up
    (unless already done — those stay as history).
    """
    cutoff = start_date + timedelta(days=within_days)
    for crop, plan in crops_with_plans:
        for ev in generate_sowing_calendar(crop, plan, start_date,
                                           horizon_days=within_days):
            if not (start_date <= ev["sow_date"] <= cutoff):
                continue
            conn.execute(
                db.insert_or_ignore(
                    "garden_tasks",
                    ["crop_row_id", "crop_key", "display", "sow_date", "batch_size"],
                    ["crop_row_id", "sow_date"],
                ),
                (crop["id"], crop.get("key"), crop["display"],
                 ev["sow_date"].isoformat(), ev["batch_size"]),
            )
    # Drop pending tasks whose crop is no longer in the plan
    conn.execute(
        "DELETE FROM garden_tasks WHERE status = 'pending' "
        "AND crop_row_id NOT IN (SELECT id FROM garden_crops)"
    )
    conn.commit()


def list_tasks(conn: sqlite3.Connection) -> list:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM garden_tasks ORDER BY status DESC, sow_date"
    ).fetchall()  # 'pending' > 'done' alphabetically reversed → pending first
    return [dict(r) for r in rows]


def get_task(conn: sqlite3.Connection, task_id: int):
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM garden_tasks WHERE id = ?", (task_id,)
    ).fetchone()
    return dict(row) if row else None


def mark_task_done(conn: sqlite3.Connection, task_id: int,
                   done_on: date | None = None) -> None:
    done_on = done_on or date.today()
    conn.execute(
        "UPDATE garden_tasks SET status = 'done', done_on = ? WHERE id = ?",
        (done_on.isoformat(), task_id),
    )
    conn.commit()


def mark_task_pending(conn: sqlite3.Connection, task_id: int) -> None:
    """Undo an accidental 'done'."""
    conn.execute(
        "UPDATE garden_tasks SET status = 'pending', done_on = NULL WHERE id = ?",
        (task_id,),
    )
    conn.commit()


def crop_from_library(key: str, weekly_demand_kg=None) -> dict:
    """Build a normalized crop dict from the seed library (optional demand override)."""
    lib = SEED_LIBRARY[key]
    crop = {"key": key, **lib}
    crop["weekly_demand_kg"] = weekly_demand_kg
    crop["water_need"] = _default_water_need(key, lib.get("category"))
    crop["sun_need"] = _default_sun_need(key, lib.get("category"))
    return crop


# --------------------------------------------------------------------------- #
# Crop ↔ zone assignment (the planner side of the integration)                  #
# --------------------------------------------------------------------------- #

def assign_crop_zone(conn: sqlite3.Connection, crop_id: int, zone_id) -> None:
    """Place a crop in a zone (zone_id=None unassigns it)."""
    conn.execute("UPDATE garden_crops SET zone_id = ? WHERE id = ?", (zone_id, crop_id))
    conn.commit()


def crops_in_zone(conn: sqlite3.Connection, zone_id: int) -> list:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM garden_crops WHERE zone_id = ? ORDER BY category, display",
        (zone_id,),
    ).fetchall()
    return [dict(r) for r in rows]
