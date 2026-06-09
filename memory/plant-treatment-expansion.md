# Future expansion — plant treatment (pH, EC, nutrient dosing)

**Status: forward-looking reference only — NOT a current build target.**
Captured from a design conversation (9 June 2026) about extending the
system beyond moisture-based watering to active plant treatment: pH
adjustment, EC/nutrient monitoring, and automated liquid dosing.
Phase 1 remains moisture-check + watering only.

---

## What "plant treatment" means here

- **pH testing**: measure soil/water pH, dose pH-up or pH-down solution
  to bring it into the target range for the plant type
- **EC (electrical conductivity)**: proxy for total dissolved nutrient
  concentration — "how rich is the water/soil solution overall"
- **Nutrient dosing**: dispense liquid nutrient solutions (N-rich,
  P-rich, K-rich, micronutrient mix, etc.) in calibrated quantities
- **NPK sensing**: direct macronutrient sensing — possible but harder
  (see Practical challenges below)
- **Alerts without auto-action**: for readings that need human judgment
  (e.g. a suspected NPK imbalance), the Pi measures and alerts; the user
  decides whether to intervene manually

---

## What scales cleanly from the current setup

| Component | Current (Phase 1) | Treatment expansion |
|---|---|---|
| ADC channels | 1 used / 8 available | +pH sensor (analog) +EC sensor (analog) → 3/8 used. MCP3008 has plenty of headroom |
| Pi GPIO | Enough for 1 relay | Enough for 8-channel relay board + RS485 adapter if needed |
| Flask / SQLite / scheduler | Unchanged | Same pattern: `read_X()` → `should_act()` → `run_Y()` → `log_run()` |
| Zone-based ZONE_PROFILES | Moisture/window/max_seconds | Extend to include pH target range, EC target range, dose limits per pump |
| MAX_dose safety cutoff | MAX_WATER_SECONDS for valve | max_dose_ml per pump per run — same concept, prevents over-dosing |
| SIMULATE mode | Full simulation | Each pump/sensor gets a simulated read/actuate function; validate full treatment sequence before connecting real pumps |

---

## What specifically needs to be added

### Hardware additions (not needed for Phase 1)

1. **Multi-channel relay board** (4- or 8-channel, ~₹200–500)
   Replace the 1-channel board. Each treatment pump needs its own channel:
   channel 1 = water valve, channel 2 = pH-up pump, channel 3 = pH-down
   pump, channels 4–6 = nutrient pumps A/B/C.
   *Note: buying a 4-channel board during Phase 1 is a cheap future-proof
   upgrade — see Hardware_Purchase_List_sourced_Jun2026_v2.docx.*

2. **Peristaltic pumps** (~₹500–2,000 each, 5V or 12V)
   One per treatment liquid. Dispense at a known ml/min rate → dosing is
   time-based: `dose_seconds = dose_ml / rate_ml_per_min * 60`.
   Small individual reservoirs (glass/plastic bottles with dip tubes) for
   each solution: pH-up, pH-down, nutrient-A, nutrient-B, micronutrient mix.

3. **Analog pH sensor** (~₹600–2,000, e.g. DFRobot pH sensor v2)
   Analog output → direct MCP3008 ADC channel. Standard SPI read, same as
   moisture sensor. **Requires regular 2-point calibration** (see Practical
   challenges).

4. **EC (conductivity) sensor** (~₹500–2,000)
   Analog or digital (I2C). Use as the primary nutrient-level proxy rather
   than trying to measure N/P/K individually.

5. **RS485-to-UART adapter** (~₹150–200) — only if using an NPK sensor
   with RS485 output (optional, see NPK note below).

### Software additions (not needed for Phase 1)

1. **Sequential multi-step treatment flow** — the current state machine
   is single-step (check → water/skip → done). Treatment requires sequenced
   steps with waiting between them:
   ```
   IDLE → SENSING_pH → STEP_pH_CORRECT → WAITING(10–30 min)
        → SENSING_pH_RECHECK → STEP_DOSE_NUTRIENTS → DONE
   ```
   Can't measure pH and dose nutrients simultaneously (precipitation risk).
   This is the main architectural expansion — a new multi-step state machine
   layer on top of the existing scheduler, not a rewrite.

2. **Per-zone treatment profiles** — extend ZONE_PROFILES to include:
   ```python
   "leafy-tubs": {
       "moisture_threshold": 40,
       "ph_target": (6.0, 7.0),   # acceptable range
       "ec_target": (1.2, 2.4),   # mS/cm
       "ph_up_pump": "pump-2",
       "ph_down_pump": "pump-3",
       "nutrient_pump": "pump-4",
       "max_dose_ml": 5.0,        # hard safety limit per run
       ...
   }
   ```

3. **pH-change-rate sanity check** — if pH moved more than N units in
   a single run, stop and alert rather than continuing to dose. Guards
   against miscalibrated sensor or pump fault causing runaway dosing.

---

## NPK sensing — practical note

Direct NPK sensors exist at hobbyist price points (~₹2,000–8,000 with
RS485 output) but are **notoriously unreliable** — high cross-sensitivity
between N/P/K channels, drift quickly, hard to validate readings.

The **recommended practical approach** for a first treatment build:
- Use **EC sensor** as the proxy for overall nutrient level ("the tank
  is depleted" vs "nutrient-rich enough")
- Dose nutrients on a **schedule + pH feedback loop** rather than
  trying to sense individual N/P/K
- Run manual NPK test kits (~₹500 for a simple kit) periodically as a
  sanity check, not as an automated trigger
- Revisit digital NPK sensing only if/when the EC proxy proves inadequate

---

## Practical challenges — flag before committing to automated pH dosing

1. **pH sensor calibration drift** — the single biggest maintenance
   overhead. Analog pH electrodes drift within days–weeks and require
   regular 2-point calibration with pH 4.0 and 7.0 buffer solutions.
   A mis-calibrated sensor dosing pH-up/down unsupervised can seriously
   harm plants. Mitigations:
   - Build in a calibration-reminder alert (e.g. every 14 days)
   - Implement a pH-change-rate sanity check in software
   - Start with sensor-triggered alert + human doses before enabling
     full auto-dosing

2. **Dosing sequence matters** — pH correction must happen before
   nutrient dosing (not simultaneously) with a wait period between.
   The multi-step state machine (above) is the correct implementation.

3. **Peristaltic pump accuracy degradation** — tubing stretches with
   use; recalibrate ml/min rate periodically (monthly is typical).

4. **Reservoir monitoring** — liquid reservoirs will empty; consider
   adding float switches (~₹50 each) or a simple weight/load cell to
   detect near-empty, triggering an alert before the pump runs dry.

---

## Suggested order of operations (when the time comes)

1. Complete Phase 1 (moisture + watering, real hardware, reliable for
   1 full day per CLAUDE.md "done" bar).
2. Expand to terrace-wide zones first (see scaling-to-terrace-garden.md)
   — multi-zone watering with the same moisture-only logic.
3. Add pH monitoring in read-only/alert mode first (no dosing yet) —
   validates sensor + calibration workflow without automation risk.
4. Add auto pH-correction once confident in sensor reliability and
   calibration routine.
5. Add nutrient dosing last — most complex sequencing, highest stakes
   if something goes wrong.
