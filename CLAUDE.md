# Plant Watering Robot — Project Context

## What this project is
A beginner-friendly robotics starter project: an automated plant-watering /
grow-shelf system. Chosen as a low-stakes "first hardware project" for someone
with software experience but **no hands-on hardware experience** — see
`memory/why-this-project.md` for the reasoning behind picking this over
alternatives (a window-cleaning robot, a mini single-rail rig, a robotic arm).

This project is also a deliberate warm-up for a separate, harder project:
the Solar Panel Cleaning Robot (`C:\Claude Projects\Solar\application`).
Lessons learned here (wiring sensors/actuators, scheduler/gating logic,
simulate-then-deploy workflow) are meant to carry over directly.

## Current build stage
Stage 0: planning / software-first. No hardware purchased yet.
Plan is to build and fully validate the control logic in SIMULATE mode before
wiring any real components — same philosophy as the Solar project.

## The idea (starting scope — refine as we go)
- One or more potted plants / a small grow-shelf
- A soil-moisture sensor per plant (or per zone)
- A small water pump (or solenoid valve) gated by a relay
- Optional: a single-axis rail/carriage to move a sensor+nozzle across multiple
  plants (this is the natural "next step up" in complexity — start without it)
- Decide and water based on: moisture reading, time-of-day window, and
  (later) a "tank/reservoir level OK" check — directly analogous to the solar
  project's `battery_ok()` / `is_within_deploy_window()` / `should_deploy()`

## Tech stack (proposed — mirrors the Solar project's proven pattern)
- Python 3.10+
- Flask (REST API / simple dashboard)
- SQLite (watering run log)
- Raspberry Pi (or even just an Arduino to start, if we want to go simpler) +
  relay module + moisture sensor(s) + small pump
- Keep hardware simulation and real hardware behind a flag: SIMULATE = True
  (do not import hardware-specific libraries until we're actually wiring up)

## Project structure (build toward this — mirrors Solar's layout)
plant_watering/
├── CLAUDE.md
├── requirements.txt
├── plant_state.py      ← watering decision logic + state machine (SIMULATE-aware)
├── scheduler.py        ← watering-condition gating logic (should_water, etc.)
├── app.py              ← Flask REST API / dashboard
├── plant.db            ← SQLite run log (auto-created)
└── tests/              ← unit tests for the gating/decision logic

## Key rules (carried over from the Solar project's proven approach)
- Build and test the *logic* in simulation first — no hardware imports
  (pyserial, RPi.GPIO, etc.) until we're actually at the wiring stage
- Run states: IDLE → CHECKING ⇄ WATERING → DONE (ERROR on fault, e.g. sensor
  reads out of range or reservoir empty)
- Always log plant/zone, moisture reading, action taken, and timestamp to SQLite
- State must survive a crash — last decision/action saved to DB after every step
- Keep it cheap and safe to fail: this is explicitly the project where mistakes
  should cost nothing more than a soggy plant, not a damaged robot

## Decisions locked in (resolved 8 June 2026)
- **Zones: ONE.** Single plant / single zone for v1+. Multi-zone is an explicit
  "v3 stretch goal" — not a current requirement, and the schema/scheduler should
  stay easy to extend to it later (the `zone` column already exists in `runs`)
  rather than be redesigned for it now.
- **Pi-only — no Arduino split.** The Solar project's Pi+Arduino split exists
  because it juggles multiple sensors/actuators across a moving rig. This build
  has exactly one sensor and one actuator (solenoid valve via relay), which is
  comfortably within a single Raspberry Pi's GPIO/SPI capability — adding an
  Arduino would be pure complexity tax with no benefit here. Keep it simple;
  this simplicity is itself one of the "lessons that carry over" to Solar
  (i.e., recognizing when a split is *not* needed).
- **"Done" for v1/v2 means:** with `SIMULATE = True`, the system reliably
  waters one (simulated) plant on a schedule — gated by moisture threshold,
  time-of-day window, and `MAX_WATER_SECONDS` — with every decision logged to
  `plant.db`, visible on the Flask dashboard, and covered by passing tests.
  That bar is now MET in software. "Done" for the *hardware* phase additionally
  means: the same logic running unmodified (`SIMULATE = False`) against real
  GPIO/ADC/relay/valve hardware, watering a real plant for at least one full
  real-world day without manual intervention or a flood/dry-run incident.

## Next steps (as of 8 June 2026)
1. Strengthen tests around `plant_state.py`'s state machine and
   `MAX_WATER_SECONDS` edge cases; run a longer multi-day simulated scenario.
2. Wire up a recurring scheduled check (timer-driven `check_and_water()` call)
   so the system behaves like it would in deployment, still in SIMULATE mode.
3. Walk the Hardware Purchase List, re-confirm current prices/stock on the
   linked India retailers, and place the Stage 1 hardware order.
4. Once hardware arrives: follow `Hardware_Assembly_Guide.docx` Stage 0 onward,
   flip `SIMULATE = False`, and validate against the "hardware done" bar above.
