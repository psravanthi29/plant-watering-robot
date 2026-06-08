# Future scaling plan — from one plant to a terrace garden (~50 tubs/pots/structures)

**Status: forward-looking reference only — NOT a current build target.**
This captures a design conversation (8 June 2026) about how the v1/v2 single-zone
architecture would extend to the user's actual terrace garden — roughly **50
tubs/grow-bags/pots plus some larger cemented planting structures**, with
**varying watering needs** across plant types. Written down now so that:
1. We don't accidentally make a Phase-1 purchasing or design choice that would
   block this path later, and
2. Future-us doesn't have to re-derive this reasoning from scratch.

Nothing here changes the current Phase 1 plan (`Hardware_Purchase_List.docx`,
`Hardware_Assembly_Guide.docx`, `shopping-list-india.md`, `scheduler.py` /
`plant_state.py`). Phase 1 remains: prove out ONE zone, in SIMULATE mode first,
then on real hardware. Everything below is what comes *after* that's solid.

---

## The key realization: zones group plants, they don't count them

The naive read of "one valve gates one independently-controlled water line" is
"50 plants → 50 valves." That's wrong, and would make a terrace-garden build
needlessly expensive and complex. Real drip-irrigation systems — including
ordinary home kits — routinely run 30–100+ plants from **4–10 valves total**.
The trick is a layer of indirection: **a "zone" is a group of plants with
similar watering needs, not an individual plant.**

Concretely, the ~50 units would be sorted into a handful of zones such as:
- "Thirsty leafy veg in tubs/grow-bags"
- "Succulents / cacti / low-water plants"
- "The big cemented structures" (likely needs higher-flow valves and longer
  runs — probably its own zone or zones by exposure)
- "Shaded / balcony-edge pots"
- ...however the actual plant mix and layout naturally clusters

Each zone gets **one valve** and **one schedule/threshold profile**. Plants
within a zone share that schedule but can still receive *different amounts* of
water via passive plumbing (next section) — so "different watering needs"
is handled WITHOUT one valve per plant.

## How the fan-out works (replaces "more valves" with cheap passive plumbing)

1. **One valve → one drip manifold/header line** for that zone.
2. **The header line splits into many drip lines**, each ending at an
   **adjustable drip emitter or dripper stake** at an individual pot.
3. Emitters are passive, cheap (a few rupees each), and individually tunable
   (e.g. 2 L/hr vs. 4 L/hr) — so within a zone, a thirstier tub gets a
   higher-flow emitter and a succulent gets a trickle, with no electronics
   of its own. The valve's *open-duration* sets the zone's overall dose; the
   *emitter sizing* fine-tunes each plant's individual share of that dose.

So "different watering needs" is resolved at **two levels**:
- **Coarse** — which zone a plant is grouped into (drives scheduling/threshold/
  duration in software)
- **Fine** — which drip emitter it's fitted with (a one-time passive plumbing
  choice, tuned by hand, no code or electronics involved)

## Sensors don't need to be 1:1 with plants either

A sensible pattern: **one "representative" sensor per zone**, placed in
whichever pot in that zone tends to dry fastest (a conservative proxy for the
whole zone), or 2–3 sensors per zone for more confidence/redundancy.

With ~6–8 zones, that's roughly 6–24 sensors total — comfortably within a
**single MCP3008's 8 analog channels**, and if more are ever needed, the
MCP3008 is on an SPI bus so a second chip can be chained without redesigning
anything.

## How this would change the hardware list (later, not now)

| Item | Phase 1 (now) | Terrace-scale (later) |
|---|---|---|
| Solenoid valves | 1 | ~1 per zone (think 5–10 total for ~50 plants, NOT 50). The zones feeding the big cemented structures may want larger-bore (¾"/1") valves for higher flow vs. ½" for tub clusters — a per-zone sizing decision. |
| Relay module | 1-channel (~₹60–150) | Swap for ONE multi-channel relay board (4-/8-/16-channel) sized to the eventual zone count — a single inexpensive board, not a pile of 1-channel ones. The 1-channel board bought now isn't wasted (spare/backup/reusable elsewhere). |
| Moisture sensors | 1 (capacitive) | ~1 per zone (representative placement), maybe 2–3 for key zones — NOT 50. |
| Drip manifolds, emitters, stakes, header/distribution tubing | none yet | **This is where most of the actual terrace-scale BUDGET goes** — generic, passive, cheap, locally-sourced irrigation-shop items (not specialty electronics). Expect this, not the electronics, to dominate cost at full scale. |
| 12V supply | 1 (1A) | Likely still adequate — a sensible multi-zone design opens **one zone's valve at a time** (sequential watering), so peak coil draw stays low even with many zones. Re-evaluate only if a future design intentionally runs zones concurrently. |
| Raspberry Pi, ADC, breadboard | 1 each | Unchanged — the same Pi can run the whole terrace; the ADC has headroom to spare. |

**Net: nothing in the Phase 1 purchase list is wasted or wrong for this future.**
Phase 1 hardware literally becomes "zone 1" of the eventual system.

## How this would change the software (later, contained, already anticipated)

The `runs` table already has a **`zone` column**, and `check_and_water(zone=...)`
already threads a zone identifier through the whole pipeline (see
`plant_state.py` / `CLAUDE.md` "Decisions locked in"). Scaling to many zones
with different needs would mean evolving the current global constants
(`MOISTURE_THRESHOLD`, `WATER_WINDOW_START/END`, `MAX_WATER_SECONDS`) into a
small **per-zone profile**, e.g.:

```python
ZONE_PROFILES = {
    "leafy-tubs":       {"threshold": 40, "window": (time(6,30), time(9,0)),  "max_seconds": 90,  "valve_gpio": 17, "sensor_ch": 0},
    "succulents":       {"threshold": 20, "window": (time(7,0),  time(8,0)),  "max_seconds": 20,  "valve_gpio": 27, "sensor_ch": 1},
    "cemented-beds":    {"threshold": 35, "window": (time(6,0),  time(8,30)), "max_seconds": 180, "valve_gpio": 22, "sensor_ch": 2},
    # ...
}
```

...and the scheduler loop would iterate zones (likely sequentially, one valve
open at a time — see the power-supply note above), running the same
`should_water()` → `run_valve()` → `log_run()` flow per zone that already
exists. This is a contained, well-scoped extension of the current design —
not a rewrite — precisely because `zone` was already built into the schema
and function signatures from the start.

## Suggested order of operations (when the time comes)
1. Get Phase 1 (one zone, real hardware) running reliably for the "hardware
   done" bar in `CLAUDE.md` (a full real-world day, no incidents).
2. Walk the terrace and group the ~50 units into zones by *actual* observed
   watering behavior (not guesswork) — this is also the point to decide
   valve bore sizes per zone based on real flow/pressure needs.
3. Size and buy the multi-channel relay board, additional valves (per zone,
   not per plant), drip manifold + emitters, and additional sensors.
4. Extend `scheduler.py`/`plant_state.py` to the `ZONE_PROFILES` pattern above,
   testing each new zone in SIMULATE mode before wiring it to real hardware —
   same simulate-then-deploy discipline as Phase 1.
5. Roll out zone by zone rather than all at once — keeps the blast radius of
   any mistake small (consistent with the "cheap to fail" philosophy that
   made this a good first hardware project to begin with).
