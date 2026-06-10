---
name: garden-planner
description: "Software-only crop planner — succession sowing dates, plant counts, spacing/area for year-round produce for ~10 people; v1 built, roadmap for nutrient/plant-care add-ons"
metadata: 
  node_type: memory
  type: project
  originSessionId: 35cf2a60-e45d-4853-a712-a41c0d845e9e
---

# Garden Planner — succession sowing, plant counts, spacing

**Status: v1 BUILT (software-only, 10 June 2026).** Lives in `crop_planner.py` +
Flask pages in `app.py`. See also [[image-feedback-vision]], [[scaling-to-terrace-garden]],
[[plant-treatment-expansion]], [[soil-root-robot]].

## Goal
Help plan the terrace garden to feed ~10 people year-round. User provides a target
crop list + household size; the app computes:
- **When to sow** — staggered (succession) sowing calendar for near-continuous harvest
- **How many plants** — to meet weekly demand
- **Spacing / area** — growing footprint required
- **Upcoming sowing alerts** — next 60 days of sow tasks on the planner page

## What's built (v1)
- `crop_planner.py`:
  - `SEED_LIBRARY` — ~25 India-terrace crops (leafy / vegetable / fruit) with
    rough, EDITABLE horticultural defaults (days_to_maturity, harvest window,
    yield/plant, spacing, succession interval, transplant offset, per-person
    weekly demand).
  - Three planning models by crop `type`:
    - **continuous** (leafy greens, tomato, okra, beans…): harvested over a
      window; plants_needed = weekly_demand ÷ weekly-yield-per-plant.
    - **single** (cabbage, carrot, radish…): whole plant harvested once;
      batch sized to cover one succession interval of demand.
    - **perennial** (banana, papaya, lemon, guava): planted once; count = annual
      demand ÷ annual yield per plant; no succession calendar.
  - Pure, unit-tested math: `compute_crop_plan`, `generate_sowing_calendar`,
    `upcoming_sowings` (tests in `tests/test_crop_planner.py`, 9 passing).
  - Persistence: additive `garden_settings` + `garden_crops` tables in `plant.db`
    (does NOT touch `runs` / `vision_logs`).
- `app.py` routes:
  - `GET /planner` — page: settings, add-crop (from library), plan table,
    upcoming-sowing alerts, totals (plants + area).
  - `POST /planner/settings|add|remove` — manage household size, start date, crops.
  - `GET /api/planner/plan` — full plan as JSON.
  - Linked from the main dashboard.

## Key modeling notes
- Demand basis: per-person weekly grams × household size, OR an explicit per-crop
  kg/week override entered by the user.
- Succession = sow a fresh batch every `succession_interval_days` so harvests
  overlap instead of arriving all at once → near-continuous supply.
- Area = plants × (spacing_cm/100)² — a rough peak footprint; real beds fit more
  via vertical growing / intercropping. Presented as an estimate, not a hard number.
- All crop numbers are explicitly editable estimates — the user should tune them
  to their actual varieties, climate, and yields over time.

## v2 additions (10 June 2026) — task tracking + care plans + UX overhaul
- **Sowing tasks with state** (`garden_tasks` table): upcoming sow events become
  persistent to-dos with ✓ Mark sown / ↩ undo. Idempotent sync; done tasks survive
  crop removal as history. Overdue tasks flagged.
- **Post-sowing care plans** (`crop_care.py`): marking a task done unlocks a dated
  care timeline anchored to the actual sown date — germination check, thinning,
  transplant, feeding cadence (every ~21 d), trellis/staking for CLIMBERS set,
  flowering-time pest watch, extra feed for HEAVY_FEEDERS, harvest window, wind-down.
  Plus crop-specific tips (CROP_NOTES) for tomato/chilli/brinjal/okra/gongura/mint/
  coriander/banana/drumstick/curry leaf. Route: `/planner/care/<task_id>`.
  Past steps collapse; "next up" highlighted.
- **Mobile-first UX rewrite**: card grid for crops, big touch targets, chips
  (auto/custom, plant-once, overdue), empty states, collapsible Settings,
  page order = To-do → Growing now → My crops → Add → Settings.
- Tests: tests/test_crop_care.py — schedule generation validated for ALL library
  crops + task lifecycle (32 tests passing project-wide).

## Roadmap (build on this as we go — user's stated intent)
1. **Custom crops** — let users add crops not in the library (full field entry)
   and edit/override library defaults per crop. (Next obvious increment.)
2. **Nutrient suggestions** — per-crop feeding schedule (N/P/K emphasis by growth
   stage); ties into [[plant-treatment-expansion]] dosing hardware later. (Generic
   feeding cadence now exists in care plans; this item = crop/stage-specific NPK.)
3. **Plant-care calendar** — ✅ BUILT in v2 as per-planting care plans (see above).
   Remaining: aggregate "today's care across all plantings" view.
4. **Geo/season awareness** — sowing windows by climate/region (currently the user
   sets a start date; future: per-crop sow-month windows for their location).
5. **Real alerts** — push upcoming sow/transplant/care tasks via the WhatsApp
   notify skill and/or the schedule (cron) skill, not just on-page.
6. **Harvest logging + feedback loop** — record actual yields to refine the
   per-plant yield estimates over seasons (mirrors the watering run-log idea).
7. **Tie-in with vision** — link a planned crop/zone to its photo timeline for
   end-to-end plan → grow → diagnose.

## Crop data provenance (verified 10 June 2026)
The SEED_LIBRARY was initially seeded from general knowledge (rough estimates). On
10 June 2026 it was expanded with ~22 Andhra/Telangana crops and then **verified
against horticulture references**:
- **`type` (continuous/single/perennial)** — reviewed for every crop. Fixed a real
  bug: **mint was wrongly "continuous" (told you to re-sow every 45 days); it is a
  perennial** (plant once, harvest for years). Correct perennials: mint, curry leaf,
  ivy gourd, drumstick, banana, papaya, lemon, guava, mango, sapota, custard apple,
  pomegranate. Borderline: Malabar spinach (bachali) kept as annual/continuous but
  can persist as a perennial vine in warm Telangana — user judgment.
- **`days_to_maturity` & `spacing_cm`** — corrected against extension/almanac sources
  (well documented, consistent). Examples fixed: spinach 40→30 d & 15→10 cm; radish
  35→28 d & 10→5 cm; carrot spacing 8→6 cm; ginger 240→300 d; garlic 150→180 d;
  colocasia 150→180 d; guava/lemon maturity raised to ~2 yr; banana 300→390 d.
- **`yield_per_plant_kg`** — set to MID-RANGE home-garden values informed by sources;
  inherently variable (2–3× by variety/soil/care), so treat as estimates and tune.
- **`per_person_weekly_g`** — consumption defaults, NOT sourced horticulture; a
  household preference. Override weekly demand per crop in the planner instead.

Sources consulted (June 2026): OSU Extension, UMD Extension, Clemson HGIC, Virginia
Tech pubs, Old Farmer's Almanac, VeggieHarvest; India-specific: agrifarming.in,
agriculture.institute, IndiaAgroNet, allthatgrows.in. A library-integrity unit test
(`tests/test_crop_planner.py`) now validates every entry computes a valid plan.

## Notes
- Still SIMULATE-era / software-only — no hardware dependency. Pure planning aid.
- Consistent with project philosophy: logic first, cheap to fail, additive schema.
- Numbers remain editable: the planner is a starting skeleton; real per-garden yields
  should be logged over seasons to refine these (see roadmap item 6).
