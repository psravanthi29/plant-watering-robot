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
Software is well past Stage 0. The control logic, Flask API, garden planner, and
vision features are built and deployed to the cloud; the frontend is being rebuilt
as an Expo app; some hardware is wired. See **"Where we are now"** below for the
live snapshot and **"Resume here (next session)"** for the immediate open decision.

## Where we are now (18 June 2026)
A fast-moving snapshot for whoever picks this up next. Memory files in `MEMORY.md`
hold the detail; verify against current code before treating any of this as fact.

- **Backend (built, deployed):** Flask + `db.py` (SQLite local / Supabase Postgres in
  cloud) on **Render free tier**, domain **thotamaali.com** (Cloudflare → Render).
  JSON API under `/api/*` with Supabase-JWT auth. 72 tests pass. Every push to `main`
  auto-redeploys Render.
- **Zone integration (Phases 1–2 built):** first-class `zones` table bridges the garden
  planner and the watering hardware; `placement.py` auto-suggests crop→zone grouping by
  water need. See `memory/zone-integration.md`.
- **Frontend rebuild (Phases 3–4 built, in `mobile/`):** Expo (React Native + web, one
  codebase). Login + Garden dashboard + Setup (zones CRUD) + Planner (crops, auto-placement,
  override). Typecheck-clean; **not yet verified live** (blocked by server latency below).
  Phases 5–6 pending: auth polish, then Flask serves the Expo web build so thotamaali.com
  *becomes* this app (web == mobile, one codebase) and the old HTML pages retire.
- **Hardware:** ESP32 + capacitive moisture sensor wired & calibrated (DRY≈2620/WET≈930,
  GPIO34), relay + 12V valve electronics done, firmware POSTs readings to the cloud.
  Paused pending female spade connectors (valve) + plumbing. See `memory/networked-sensor.md`.

## Resume here (next session)
**Cloud hosting is SOLVED (18 June 2026).** Migrated Render → **AWS EC2 t4g.micro in
ap-south-1 (Mumbai)**, co-located with the Supabase project → DB latency **~2.2s → ~7ms**.
`https://thotamaali.com` now serves from the EC2 box (Elastic IP `65.2.199.137`, nginx +
gunicorn, Let's Encrypt TLS). Deploy = SSH to box + `bash deploy/deploy.sh`. Full detail
in `memory/deployment-hosting.md` and `deploy/README.md`.

**Immediate next steps:**
1. ✅ DONE — Expo app verified end-to-end against the fast backend (Setup zones, Planner
   crops + placement).
2. ✅ DONE — Render service suspended/deleted; keep-alive GitHub Action disabled; `deploy.sh`
   run to pick up the restored DB liveness check.
3. **Frontend roadmap:** Phase 5 (auth verify-email screen) ✅ done. Web↔mobile feature
   parity (watering ops, planner depth/settings, vision read-only) ✅ built + deployed.
   In-app photo capture: **deferred** (do it as a proper flow later). **Phase 6 (Flask
   serves the Expo web build, old HTML pages retired) is BUILT — needs deploy + live check.**
   `app.py` is now API + static-SPA only; web bundle committed at `mobile/dist/` (rebuild
   with `cd mobile && npm run build:web`). See `memory/zone-integration.md`.

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

## Future enhancements (forward-looking — NOT current build targets)
These are captured ideas, not committed work. Each has a full design write-up in
project memory (see `MEMORY.md` index). Build a purchase list for any of them only
*if and when* we actually start it — don't pre-buy.

1. **Image feedback loop** *(software already built)* — per-zone plant photos →
   Gemini Vision → health diagnosis, with a per-zone progress timeline that
   compares photos over days. Live in `app.py` / `vision_analysis.py`. Optional
   future hardware: Pi Camera or USB webcam for automated capture.
   See `memory/image-feedback-vision.md`.
2. **Terrace-garden scaling** — extend the single zone to ~50 plants via ~5–10
   zones (drip manifolds + emitters), not 50 valves. Schema/scheduler already
   zone-aware. See `memory/scaling-to-terrace-garden.md`.
3. **Plant treatment (pH/EC/nutrient dosing)** — peristaltic pumps + analog
   pH/EC sensors on the spare ADC channels + multi-channel relay; multi-step
   treatment state machine. See `memory/plant-treatment-expansion.md`.
4. **Below-ground / root sensing** — diagnose root rot, nematodes, anaerobic
   zones, compaction *without pulling the plant*, via a buried clear
   minirhizotron tube + borescope (feeds the existing vision timeline) and a
   root-depth sensor probe (moisture/temp/EC/pH/**redox**). A true burrowing
   "worm" robot is research-frontier and explicitly out of scope. Purchase list
   to be built later if/when we start. See `memory/soil-root-robot.md`.
