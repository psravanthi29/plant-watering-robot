# Why we picked the plant-watering robot as the starter project

Context: this came out of a conversation while working on the Solar Panel
Cleaning Robot project (`C:\Claude Projects\Solar\application`). The person
has software knowledge but **no real hands-on hardware experience**, and
wanted a good "first robot" to experiment on before/alongside the harder
solar build.

## Options considered
1. **Line-following / grid-traversal rover** — parked for now (good warm-up,
   but lower direct transfer to the solar project's actual hard problems)
2. **Plant-watering / grow-shelf robot** ← CHOSEN
3. **Mini single-rail rig** (a literal 1-row, 1-rail mini version of the solar
   robot, to de-risk the V-wheel + rack-and-pinion adhesion design at small
   scale)
4. **Desk-organizing / object-sorting robotic arm**

## Why plant-watering won
- **Hardware bill of materials is small, cheap, and forgiving**: one motor or
  pump, one moisture sensor, one relay — all extremely common beginner parts
  with abundant tutorials. No custom machining or tight mechanical tolerances.
- **Failure is safe and cheap.** Worst case of a mistake: a plant gets too
  much/little water. Compare to the mini-rail rig (#3), where a hardware
  mistake means a robot losing grip on a tilted rail mid-air — much higher
  stakes for someone still learning which wire goes where.
- **Directly reuses the Solar project's proven software architecture**:
  - `scheduler.py`'s `should_deploy()` / `is_within_deploy_window()` /
    `battery_ok()` map almost 1:1 onto `should_water()` /
    `is_within_watering_window()` / `moisture_below_threshold()`
  - The Flask + SQLite + simulate-mode pattern (`SIMULATE = True` flag, no
    hardware imports until later) carries over directly
  - This means the *new* learning surface is narrowed to just the hardware
    side — the right way to isolate what's actually being learned
- **Gentle hardware on-ramp**: wiring a relay, reading an analog sensor,
  driving a small pump — these are the "first breadboard project" building
  blocks that make later, harder hardware (the solar robot's rail/motor/
  driver/sensor stack) much less intimidating.

## Why the others were set aside (for now)
- **Line follower (#1)**: parked by request — good general warm-up, but
  doesn't teach anything about gating logic, scheduling, or sensor-driven
  decisions, which are central to the solar project.
- **Mini single-rail rig (#3)**: actually the *highest-leverage* project for
  directly de-risking the solar build (it's a literal mini prototype of the
  hardest part — rail adhesion on tilted surfaces) — but it demands real
  mechanical fabrication skill and has a much less forgiving failure mode.
  **Recommended as the natural next step after this project**, once basic
  wiring/sensor/actuator skills are in hand.
- **Robotic arm (#4)**: stacks two new hard domains at once (multi-joint
  actuation + computer vision/inverse kinematics) — too much simultaneous
  novelty for a first hardware project.

## Suggested progression
Plant-watering robot (this project — learn wiring/sensors/actuators safely)
  → Mini single-rail rig (apply that hardware confidence to the harder
    adhesion/tilt problem)
  → Full Solar Panel Cleaning Robot build
