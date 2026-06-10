---
name: image-feedback-vision
description: "Camera-based plant health monitoring — Claude Vision API integration, manual photo upload track, Pi Camera automated track, Phase 1 BOM impact"
metadata: 
  node_type: memory
  type: project
  originSessionId: 35cf2a60-e45d-4853-a712-a41c0d845e9e
---

# Image feedback loop — plant health vision analysis

**Status: designed 9 June 2026. Software-only implementation parallel to Phase 1.**
See also [[scaling-to-terrace-garden]], [[plant-treatment-expansion]].

The user wants per-zone camera-based monitoring: capture images → send to Claude
Vision API → receive plant health observations + care suggestions → log/alert on
the Flask dashboard. Key constraint: can start immediately in manual-photo mode,
before any hardware is purchased.

---

## Two parallel tracks

### Track 1 — Manual photos (start now, no hardware needed)
User takes photos of plants on their phone and uploads them via a Flask endpoint.
Claude analyzes and returns health observations. This track lets the user:
- Refine the analysis prompt based on real plant types and real issues
- Build up a labeled library of what "good", "underwatered", "pest damage", etc.
  look like for their specific plants
- Validate the API integration and prompt quality before automating anything

Flask endpoint: `POST /analyze` accepts a multipart upload (1-4 images),
optional fields `zone` and `plant_types`, calls `vision_analysis.analyze_images()`,
logs result to `vision_logs` table, returns JSON.

### Track 2 — Automated Pi Camera (after Phase 1 hardware)
Pi Camera Module captures images on a schedule (e.g. every 4-6 hours, or triggered
after each watering run). Same `analyze_images()` function, same Claude API call.
The scheduler calls it; results land in the same `vision_logs` table and appear on
the dashboard. No code change between manual and automated — just who supplies the
image file path.

---

## Claude Vision API integration

**Module: `vision_analysis.py`**

Model choice:
- `claude-opus-4-8` — best vision accuracy; use for manual deep-diagnosis sessions
  and for the default periodic check until cost becomes a concern
- `claude-haiku-4-5` — ~5× cheaper; appropriate for high-frequency automated polling
  (e.g. every 2-4 hours across 5-10 zones)

Image passing: **base64** (not URL). The Pi captures locally; base64 encodes the
JPEG/PNG bytes and includes them directly in the API payload. URL-based passing
would require hosting images somewhere, which adds unnecessary complexity.

Token cost estimate (for reference):
- Each image ≈ 1,600–4,800 input tokens (depends on resolution and model tier)
- 1-4 images + prompt + response ≈ 10,000-25,000 tokens per call
- At Opus pricing ($5/1M input, $25/1M output): roughly ₹0.10–0.25 per call
- At Haiku pricing ($1/1M input, $5/1M output): roughly ₹0.02–0.05 per call
- Several times per day across one zone is negligible cost in either case

```python
import anthropic, base64
from pathlib import Path

def analyze_images(image_paths, zone="zone-1", plant_types="unknown",
                   moisture_pct=None, model="claude-opus-4-8"):
    client = anthropic.Anthropic()
    content = []
    for path in image_paths:
        data = Path(path).read_bytes()
        encoded = base64.standard_b64encode(data).decode("utf-8")
        suffix = Path(path).suffix.lower().lstrip(".")
        media_type = "image/jpeg" if suffix in ("jpg","jpeg") else f"image/{suffix}"
        content.append({"type": "image",
                         "source": {"type": "base64", "media_type": media_type, "data": encoded}})
    content.append({"type": "text", "text": ANALYSIS_PROMPT.format(...)})
    response = client.messages.create(
        model=model, max_tokens=1024,
        messages=[{"role": "user", "content": content}]
    )
    return {"zone": zone, "analysis": response.content[0].text, ...}
```

---

## Database schema addition

New table `vision_logs` in `plant.db` (created by `vision_analysis.init_vision_db()`):

```sql
CREATE TABLE IF NOT EXISTS vision_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT NOT NULL,
    zone         TEXT NOT NULL,
    image_count  INTEGER,
    source       TEXT,   -- "manual" or "pi_camera"
    analysis     TEXT
);
```

Does not touch the existing `runs` table — fully additive.

---

## Flask additions

- `POST /analyze` — accepts multipart form with `images[]` files + optional `zone`,
  `plant_types` fields. Saves uploaded images to a temp dir, calls
  `analyze_images()`, logs to `vision_logs`, returns JSON analysis.
- `GET /api/vision-logs` — returns last N vision analysis records as JSON.
- Dashboard `GET /` extended with a "Vision Log" section showing recent analyses.

---

## Phase 1 hardware BOM impact

**No required BOM change.** Camera module is optional for Phase 1.

If the user wants to automate Track 2 sooner:
- **Pi Camera Module v2** (~₹1,200–2,000 at Robu.in / Robocraze / Amazon.in)
  - 8 MP Sony IMX219 sensor
  - Connects to Pi Zero 2 W's CSI port (the thin ribbon-cable connector on the board)
  - **IMPORTANT: Requires a special short 15-to-15 pin ribbon cable for Pi Zero** —
    the standard Pi Camera ribbon is too wide/long for the Zero's smaller connector.
    Search for "Pi Zero Camera Cable" or "Pi Zero 2 W CSI ribbon cable" (~₹100-200).
    This cable is easy to overlook and often sold separately from the camera module.
  - v3 module also compatible but ~₹3,000–4,000
- Alternatively: a USB webcam works with Pi Zero 2 W via the micro-USB OTG adapter
  (which is in the iRasptek kit already). Easier to set up (no ribbon cable), lower
  resolution, slightly bulkier. Fine for phase 1 experiments.

Recommendation: start with manual photo uploads (Track 1) in Phase 1. Add camera
hardware in Phase 2 when validating on real plants. The CSI camera gives cleaner
image quality; a USB webcam is a lower-friction starting point.

---

## Suggested order of operations

1. Add `vision_analysis.py` and `/analyze` endpoint to Flask app (software only).
2. User takes phone photos of plants → upload via Flask → refine the prompt.
3. Build a small labeled prompt library ("these are my curry leaf plants in
   direct sun, they tend to get scale insects...") per zone/plant type.
4. After Phase 1 hardware is validated: attach Pi Camera Module v2 (or USB webcam),
   wire periodic capture into the scheduler (or trigger after each watering run).
5. Scale: one camera per zone (group), not one per plant — same zone-grouping logic
   as the drip emitter approach in [[scaling-to-terrace-garden]].
