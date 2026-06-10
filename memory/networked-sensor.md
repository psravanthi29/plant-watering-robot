---
name: networked-sensor
description: Networked sensor architecture — a sensor agent pushes readings over HTTP to the server DB; watering logic consumes the latest fresh reading (MOISTURE_SOURCE=db)
metadata: 
  node_type: memory
  type: project
  originSessionId: 35cf2a60-e45d-4853-a712-a41c0d845e9e
---

# Networked sensor push architecture (built 10 June 2026, software)

The sensor does NOT need to live on the same box as the control server. A small
agent reads the sensor and **POSTs readings over the network** to the server's
DB; everything else (dashboard, planner, watering decisions) reads from that one
DB. See also [[garden-planner]], [[scaling-to-terrace-garden]].

## Pieces
- **`sensor_agent.py`** — the "small app". Loops: read moisture → `POST
  {SERVER_URL}/api/reading` with `{zone, value, sensor, token}`. Runs on the Pi
  (or any networked device). SIMULATE=1 fakes readings; SIMULATE=0 = real ADC
  (stub left for MCP3008 wiring). Config via env (SERVER_URL, ZONE,
  SENSOR_API_TOKEN, INTERVAL_SECONDS).
- **`POST /api/reading`** (app.py) — ingests a reading into the `sensor_readings`
  table. Token-gated: if `SENSOR_API_TOKEN` is set in server env it's required
  (header `X-API-Key` or body `token`); unset = open (dev only).
- **`sensor_readings` table** (plant_state.init_db) — additive; id, timestamp,
  zone, sensor, value, source.
- **`plant_state.MOISTURE_SOURCE`** env switch: `simulate` (default, random),
  `db` (consume latest pushed reading — the networked path), `gpio` (future,
  read locally). In `db` mode `read_moisture()` calls `latest_reading()` which
  returns the newest reading **only if fresh** (`READING_MAX_AGE_SECONDS`, default
  3600) — a stale reading = sensor offline = RuntimeError → ERROR state, no water.
- **Dashboard** shows latest moisture per zone; `GET /api/readings[?zone=]` for raw.

## Why this shape
- Decouples sensing from control: the agent stays dumb/replaceable; the server
  owns all data and logic. Multiple sensors (per zone, per the terrace-scaling
  plan) just POST to the same endpoint with different `zone` values.
- Mirrors the eventual reality: the Pi controlling the valve is local hardware,
  but sensors can be distributed; all converge on one DB.
- Staleness guard prevents watering on a dead sensor's last value.

## Tests
tests/test_sensors.py — log/latest roundtrip, most-recent wins, missing→None,
stale→ignored, read_moisture db-mode (hit + offline error), and a full
check_and_water end-to-end driven by a pushed reading. 43 tests pass project-wide.

## Next (when hardware arrives)
- Implement the real ADC read in sensor_agent.read_moisture_pct (MCP3008 → %).
- Set server env MOISTURE_SOURCE=db and SENSOR_API_TOKEN; run sensor_agent.py on
  the Pi (systemd service or the recurring-check timer).
- Optional: push pH/EC/redox the same way (sensor field already generalizes) —
  ties into [[plant-treatment-expansion]] and [[soil-root-robot]].
