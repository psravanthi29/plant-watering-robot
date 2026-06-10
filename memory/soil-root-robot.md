---
name: soil-root-robot
description: "Feasibility + design for sensing below-ground soil/root problems (root rot, nematodes, compaction, anaerobic zones) without pulling the plant — insertable probes, minirhizotron borescope, and why a true burrowing \"worm\" robot is research-frontier"
metadata: 
  node_type: memory
  type: project
  originSessionId: 35cf2a60-e45d-4853-a712-a41c0d845e9e
---

# Below-ground sensing — "what's wrong at the roots without digging?"

**Status: forward-looking feasibility study (10 June 2026). NOT a current build target.**
Captured from a design conversation about whether we could build a robot that
"goes into the soil like a worm" to find root/soil problems invisible from the
surface. See also [[plant-treatment-expansion]], [[image-feedback-vision]],
[[scaling-to-terrace-garden]].

---

## The honest split: goal vs. mechanism

The **goal** — diagnose below-ground problems without pulling the plant — is
achievable now with cheap parts.

The **mechanism** the question imagined — an autonomous robot that *burrows
through soil like an earthworm* — is a research-frontier problem (see "Why
true burrowing is hard" below). The right move is to decouple them: get the
diagnostic value through fixed probes + below-ground imaging, and treat the
burrowing robot as an aspirational "someday / fun to follow" project, not a
build target.

---

## What actually goes wrong below the surface (the diagnostic targets)

| Problem | How it's normally found | Below-ground signal we can sense |
|---|---|---|
| **Root rot** (over-watering → anaerobic → fungal/bacterial) | Pull plant, smell/see mushy brown roots | Low redox/ORP + persistently high moisture + (visual via borescope: dark mushy roots). #1 killer — and the most detectable early. |
| **Anaerobic / waterlogged root zone** | Plant declines mysteriously | Redox (ORP) probe, dissolved-oxygen; high moisture that never drops |
| **Root-knot nematodes** | Pull plant, see knobbly galls on roots | Visual via borescope (galls are visible); free-soil counts need a lab |
| **Grubs / root aphids / fungus-gnat larvae** | Dig and find them | Visual via borescope near root zone |
| **Soil compaction / poor aeration** | Penetrometer, hard to push a probe | Insertion-force feedback; low O2; poor water infiltration |
| **Salt / fertilizer buildup (high EC)** | Lab soil test | EC probe at root depth |
| **pH wrong at depth** | Lab soil test | pH probe at root depth |
| **Dry pockets / uneven moisture** | Guesswork | Moisture at multiple depths |
| **Root temperature stress** | Rarely measured | Thermistor at depth |

Takeaway: most of these are caught by a **multi-sensor probe at root depth**
plus a **camera that can see the roots through a buried tube**. Neither needs
locomotion.

---

## The practical path (tiers — fits the "cheap to fail" philosophy)

### Tier 0 — Handheld, basically free, do it now
- **Cheap USB / WiFi borescope endoscope** (~₹500–1,500, 5.5–8 mm, waterproof).
  Push it a few cm into the soil near the root ball, or into a chopstick-made
  channel. Photograph roots/soil.
- **Manual sensor probe**: the same capacitive moisture sensor we already use,
  plus a cheap pH/EC pen, inserted by hand at depth.
- **Feed photos straight into the vision app we already built** — the
  `/analyze` endpoint + Gemini already diagnoses plant images; just point the
  prompt at roots ("what root/soil problems do you see — rot, galls, pests,
  discoloration?"). The progress-timeline feature then tracks roots over weeks.

### Tier 1 — Permanently installed, per zone (the real workhorse)
- **Minirhizotron tube** (this is the key idea): bury a **clear acrylic/
  polycarbonate tube** at an angle next to the plant, once. Slide a borescope
  down it any time to photograph roots growing against the clear wall —
  **without ever disturbing the plant**. This is a real, established
  plant-science technique; the borescope is the hobby version of a commercial
  minirhizotron camera.
- **Multi-sensor probe spike** left in the soil at root depth, reporting to the
  same Pi: moisture + temperature (thermistor) + EC + pH + **redox/ORP**
  (ORP is what catches the over-watered→anaerobic→root-rot cascade early).
- Software reuse: identical to [[plant-treatment-expansion]] — analog sensors →
  MCP3008 ADC → `should_act()` → log. Add a per-zone "root profile" alongside
  the watering profile. Camera reuse: identical to [[image-feedback-vision]].

### Tier 2 — Motorized inspection (the "next step up" already hinted at in CLAUDE.md)
- A small **motorized carriage / winch lowers the borescope down the
  minirhizotron tube** on a schedule (e.g. weekly), auto-capturing a strip of
  root images at known depths and feeding them into the vision timeline.
- This is exactly the "single-axis rail/carriage" idea noted as the natural
  complexity step-up in the original project scope — now with a concrete purpose.
- Still **no burrowing**: the tube is the highway; the camera just rides it.

### Tier 3 — Actual burrowing robot (aspirational / research only)
- Treat as "fun to follow," not a build. See next section for why.

---

## Why true burrowing is hard (so we don't sink months into it)

Soil is not water or air — moving through it is brutal:

1. **Enormous drag/resistance.** Pushing a body through soil means displacing or
   excavating it. Forces scale fast with depth (overburden pressure). Small
   motors can't supply it; big ones need big power.
2. **Spoil problem.** If you excavate, you must move the removed soil *somewhere*
   — earthworms literally eat soil and pass it through their gut. Mechanically
   mimicking that is unsolved at hobby scale.
3. **No localization underground.** No GPS, no radio through soil. You don't know
   where the robot is or which way it's pointing.
4. **Power + tether.** Battery life under load is tiny; a tether limits range and
   tangles.
5. **It destroys what it's inspecting.** A burrower shoves through the very roots
   you're trying to assess — the act of measuring damages the subject.

**What the research frontier looks like (for inspiration, not purchase):**
- **Root-inspired "growing" robots** — extend from the *tip* and add body
  material behind, so the surface doesn't slide against soil (kills friction
  along the length). EU **PLANTOID** project (B. Mazzolai, IIT) and Stanford
  tip-everting "vine robots" (E. Hawkes).
- **RoboClam** (MIT, Winter/Hosoi) — razor-clam-inspired: *fluidizes* the
  surrounding soil/sand to cut drag, then anchors.
- **Sandfish / "swimming in sand"** (D. Goldman, Georgia Tech) — undulatory
  motion through *loose* granular media.

Common thread: they work in **controlled loose substrate (sand/lab soil)**, are
PhD-scale, and don't operate in real rocky, root-filled garden soil. That's the
honest ceiling today.

---

## Hardware notes (if/when Tier 1 happens — none needed now)

- Borescope endoscope (USB or WiFi), 5.5–8 mm, waterproof, with LED ring — cheap.
- Clear acrylic/polycarbonate tube for the minirhizotron (local plastics shop),
  end-capped to keep soil/water out, installed at ~30–45° angle.
- ORP/redox probe + EC probe + pH probe (analog → MCP3008; same bus we already
  have, 7 free channels). ORP is the high-value add for early root-rot warning.
- Thermistor for root-zone temperature (cheap analog).
- Dissolved-oxygen in soil is the one genuinely expensive/finicky sensor —
  redox is a good cheaper proxy; skip DO unless redox proves inadequate.
- Sensors that DON'T exist cheaply: direct nematode/pathogen detection (lab
  extraction + microscopy). We infer those visually (borescope) + indirectly
  (EC/moisture/redox), not with a dedicated sensor.

## Software reuse (everything we've already built carries over)
- Borescope images → existing `/analyze` Gemini pipeline (just retarget the
  prompt at roots) → existing per-zone **progress timeline** for week-over-week
  root tracking. This is a near-zero-code win.
- Root-zone sensors → existing scheduler/state-machine pattern; add a per-zone
  "root profile" (redox/EC/pH/temp targets) next to the watering profile.

## Suggested order of operations (when the time comes)
1. Buy a ₹500–1,500 borescope. Push it near a plant's roots; run the photos
   through the app we already have. Confirm the diagnosis is useful. (Tier 0)
2. Install one minirhizotron tube + a sensor spike on the Phase-1 plant. (Tier 1)
3. Add ORP/redox sensing — the early-warning signal for the most common killer
   (over-watering → root rot). (Tier 1)
4. Only if all that is solid and you want a mechatronics challenge: motorize the
   borescope down the tube on a schedule. (Tier 2)
5. Follow PLANTOID / vine-robot research for fun; revisit Tier 3 only if the
   field matures into something buildable. (Tier 3)
