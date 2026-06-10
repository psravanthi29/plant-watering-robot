# Graph Report - .  (2026-06-10)

## Corpus Check
- Corpus is ~17,173 words - fits in a single context window. You may not need a graph.

## Summary
- 156 nodes · 379 edges · 9 communities (7 shown, 2 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.9)
- Token cost: 15,373 input · 2,181 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Flask Routes & Dashboard|Flask Routes & Dashboard]]
- [[_COMMUNITY_Vision Analysis Pipeline|Vision Analysis Pipeline]]
- [[_COMMUNITY_Watering State Machine|Watering State Machine]]
- [[_COMMUNITY_Crop Planning Math|Crop Planning Math]]
- [[_COMMUNITY_Planner Settings & Persistence|Planner Settings & Persistence]]
- [[_COMMUNITY_Project Design Docs|Project Design Docs]]
- [[_COMMUNITY_Care Schedules & Tasks|Care Schedules & Tasks]]
- [[_COMMUNITY_Launch Config|Launch Config]]
- [[_COMMUNITY_Dependencies|Dependencies]]

## God Nodes (most connected - your core abstractions)
1. `crop_from_library()` - 18 edges
2. `compute_crop_plan()` - 16 edges
3. `check_and_water()` - 15 edges
4. `init_planner_db()` - 14 edges
5. `Connection` - 14 edges
6. `_build_planner_view()` - 11 edges
7. `care_schedule()` - 11 edges
8. `sync_tasks()` - 11 edges
9. `generate_sowing_calendar()` - 10 edges
10. `should_water()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `get_vision_logs()` --calls--> `init_vision_db()`  [EXTRACTED]
  app.py → vision_analysis.py
- `check()` --calls--> `check_and_water()`  [EXTRACTED]
  app.py → plant_state.py
- `api_vision_logs()` --calls--> `init_vision_db()`  [EXTRACTED]
  app.py → vision_analysis.py
- `_build_planner_view()` --calls--> `compute_crop_plan()`  [EXTRACTED]
  app.py → crop_planner.py
- `planner_add()` --calls--> `add_crop()`  [EXTRACTED]
  app.py → crop_planner.py

## Import Cycles
- None detected.

## Communities (9 total, 2 thin omitted)

### Community 0 - "Flask Routes & Dashboard"
Cohesion: 0.16
Nodes (23): api_planner_plan(), api_runs(), dashboard(), get_runs(), get_vision_logs(), planner(), planner_add(), planner_care() (+15 more)

### Community 1 - "Vision Analysis Pipeline"
Cohesion: 0.13
Nodes (23): analyze(), api_vision_logs(), progress(), Chronological view of every capture for a zone, with photos + analysis., Send all of a zone's dated photos to Gemini and report the trend over time., zone_timeline(), Client, analyze_images() (+15 more)

### Community 2 - "Watering State Machine"
Cohesion: 0.14
Nodes (20): check(), check_and_water(), init_db(), log_run(), Simulated soil-moisture sensor reading (0-100%)., Simulated solenoid-valve activation, hard-capped at MAX_WATER_SECONDS.      The, One pass of the CHECKING -> (WATERING) -> DONE state machine for a zone., read_moisture() (+12 more)

### Community 3 - "Crop Planning Math"
Cohesion: 0.21
Nodes (20): compute_crop_plan(), crop_from_library(), effective_weekly_demand(), generate_sowing_calendar(), Weekly demand in kg: explicit override if set, else per-person × household., Compute plant count, batch size/cadence, and area for one crop.      Returns a d, Staggered sow events from start_date over horizon_days.      Each event: {sow_da, Across all crops, sow events whose sow_date falls within the next window.      c (+12 more)

### Community 4 - "Planner Settings & Persistence"
Cohesion: 0.21
Nodes (19): _build_planner_view(), Compute everything the planner page needs from the stored crops + settings., get_household_size(), get_plan_start_date(), get_setting(), is_demand_auto(), list_crops(), list_tasks() (+11 more)

### Community 5 - "Project Design Docs"
Cohesion: 0.19
Nodes (17): Plant Watering Robot — Project Context, Image Feedback Loop, Plant Treatment Expansion, Scaling to Terrace Garden, Shopping List (India), Soil Root Robot, Why This Project, Watering decision logic + state machine (SIMULATE-aware).  Run states: IDLE -> C (+9 more)

### Community 6 - "Care Schedules & Tasks"
Cohesion: 0.20
Nodes (18): care_schedule(), date, Post-sowing care schedules — what to do after seeds go into the soil.  Generates, Split a care schedule into (done_or_past, upcoming) relative to today., Build a dated care timeline for one planting of `crop` sown on `sow_date`., split_past_upcoming(), add_crop(), get_task() (+10 more)

## Knowledge Gaps
- **4 isolated node(s):** `version`, `configurations`, `Client`, `Requirements`
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `check_and_water()` connect `Watering State Machine` to `Flask Routes & Dashboard`, `Project Design Docs`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Why does `crop_from_library()` connect `Crop Planning Math` to `Flask Routes & Dashboard`, `Planner Settings & Persistence`, `Care Schedules & Tasks`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Why does `should_water()` connect `Project Design Docs` to `Watering State Machine`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **What connects `version`, `configurations`, `Flask REST API / dashboard for the plant-watering robot (SIMULATE-aware).` to the rest of the system?**
  _40 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Vision Analysis Pipeline` be split into smaller, more focused modules?**
  _Cohesion score 0.12681159420289856 - nodes in this community are weakly interconnected._
- **Should `Watering State Machine` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._