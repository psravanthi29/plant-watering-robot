"""Post-sowing care schedules — what to do after seeds go into the soil.

Generates a dated care timeline for one planting (one sowing batch of one crop),
derived from the crop's own parameters in crop_planner.SEED_LIBRARY:
germination check, thinning, transplanting, feeding cadence, trellis/staking,
flowering-time pest watch, and the expected harvest window.

Pure functions (no DB) so the schedule logic is unit-testable. The Flask layer
renders these against a sowing task's actual sown date.
"""

from datetime import date, timedelta

# Crops that climb / vine and need a trellis or stake early.
CLIMBERS = {
    "tomato", "cucumber", "bottle_gourd", "ridge_gourd", "bitter_gourd",
    "snake_gourd", "ash_gourd", "pumpkin", "dosakaya", "ivy_gourd",
    "field_beans", "cowpea", "beans", "malabar_spinach",
}

# Heavy feeders benefit from an extra compost top-dress at flowering.
HEAVY_FEEDERS = {
    "tomato", "brinjal", "chilli", "capsicum", "bottle_gourd", "ridge_gourd",
    "bitter_gourd", "snake_gourd", "ash_gourd", "pumpkin", "cabbage",
    "cauliflower", "banana", "papaya",
}

# Crop-specific extra care notes: key -> list of (day_offset, title, note).
CROP_NOTES = {
    "tomato": [
        (30, "Prune suckers", "Pinch off small shoots growing in the V between the main stem and branches — improves airflow and fruit size."),
        (45, "Watch for leaf curl & borers", "Yellowing/curling leaves can mean leaf-curl virus (remove affected plants); small holes in fruit mean fruit borer — hand-pick or use neem spray."),
    ],
    "chilli": [
        (40, "Watch for thrips & mites", "Curled, crinkled leaves = thrips/mites. Spray neem oil (5 ml/L) in the evening, repeat weekly until clear."),
    ],
    "brinjal": [
        (40, "Watch for shoot & fruit borer", "Wilting shoot tips = borer inside the stem. Snip and destroy affected tips immediately; neem spray as preventive."),
    ],
    "okra": [
        (35, "Pick pods young", "Harvest pods at 7–10 cm, every 2–3 days. Overgrown pods turn woody AND signal the plant to stop producing."),
    ],
    "gongura": [
        (40, "Harvest by pinching tops", "Pinch the top 10–15 cm of each branch — the plant bushes out and gives 3–4 more pickings."),
    ],
    "mint": [
        (45, "Cut back hard regularly", "Harvest by cutting stems near the base every few weeks — prevents flowering and keeps leaves tender. Contain the runners; mint spreads aggressively."),
    ],
    "curry_leaf": [
        (90, "Pinch flower buds", "Remove flower/seed heads on young plants so energy goes into leaf production."),
    ],
    "coriander": [
        (25, "Harvest before bolting", "In Telangana heat, coriander bolts (flowers) fast — harvest whole stems as soon as plants are 15 cm; don't wait."),
    ],
    "banana": [
        (180, "Remove extra suckers", "Keep only 1–2 healthy suckers per clump (one to fruit, one follower); cut the rest at soil level."),
    ],
    "drumstick": [
        (120, "Pinch the growing tip", "When the sapling is ~1 m tall, pinch the top so it branches low — keeps pods within reach on a terrace."),
    ],
}


def care_schedule(crop: dict, sow_date: date) -> list:
    """Build a dated care timeline for one planting of `crop` sown on `sow_date`.

    Returns a list of dicts {date, day, title, note}, sorted by date.
    Works for all three crop types; perennials get establishment-phase events.
    """
    key = crop.get("key", "")
    maturity = int(crop["days_to_maturity"])
    window = int(crop["harvest_window_days"])
    transplant_offset = int(crop.get("seed_to_transplant_days", 0) or 0)
    spacing = int(crop["spacing_cm"])

    events = []

    def add(day, title, note):
        events.append({
            "date": sow_date + timedelta(days=day),
            "day": day,
            "title": title,
            "note": note,
        })

    # Day 0 — sowing instructions
    if crop["type"] == "perennial":
        add(0, "🌱 Plant",
            f"Plant in its permanent spot — it stays for years. Allow {spacing} cm "
            "footprint, dig in compost, water deeply after planting.")
    elif transplant_offset > 0:
        add(0, "🌱 Sow in seed tray",
            "Sow in a seed tray / small cups (2 seeds per cell, thin to the stronger "
            "one). Keep in bright shade, soil just-moist.")
    else:
        add(0, "🌱 Direct sow",
            f"Sow directly where it will grow, ~1–2 cm deep, final spacing {spacing} cm. "
            "Water gently with a fine rose so seeds don't wash out.")

    # Germination check
    add(7, "👀 Germination check",
        "Most seeds should be up by now. Re-sow any gaps. Keep soil consistently "
        "moist (not soggy) until seedlings establish.")

    # Thinning for direct-sown, closely spaced crops
    if transplant_offset == 0 and crop["type"] != "perennial" and spacing <= 30:
        add(14, "✂️ Thin seedlings",
            f"Thin to the strongest seedling every {spacing} cm. Crowded seedlings "
            "stay weak — be ruthless; eat the thinnings if leafy.")

    # Transplant
    if transplant_offset > 0:
        add(transplant_offset, "🪴 Transplant",
            f"Seedlings ready (3–4 true leaves). Transplant at {spacing} cm spacing, "
            "in the evening, water immediately. Shade for 2–3 days if sun is harsh.")

    # Trellis / staking for climbers
    if key in CLIMBERS:
        add(max(transplant_offset + 7, 20), "🪜 Set up trellis/stake",
            "Install the trellis/stake now, before vines sprawl — moving an "
            "established vine damages roots. Train the main shoot up gently.")

    # Feeding cadence: every 3 weeks from day 20 until maturity (cap at 4 events)
    feed_day = max(20, transplant_offset + 10)
    feeds = 0
    while feed_day < maturity and feeds < 4:
        add(feed_day, "🍃 Feed",
            "Top-dress with a handful of compost/vermicompost per plant; or dilute "
            "liquid feed (e.g. fish/seaweed or jeevamrutham). Water in well.")
        feed_day += 21
        feeds += 1

    # Pest watch around flowering (≈60% of the way to maturity)
    pest_day = int(maturity * 0.6)
    add(pest_day, "🐛 Pest & disease watch",
        "Flowering/fruiting attracts pests. Check under leaves twice a week — "
        "aphids, whitefly, caterpillars. Neem oil (5 ml/L) in the evening at first "
        "sign; remove badly affected leaves.")

    if key in HEAVY_FEEDERS:
        add(pest_day, "🍌 Extra feed (heavy feeder)",
            "This crop is a heavy feeder — give an extra compost top-dress now that "
            "flowering has started, plus a potassium boost (wood ash / banana-peel "
            "soak) for fruit set.")

    # Harvest window
    add(maturity, "🧺 First harvest",
        f"First harvest expected around now. Productive for roughly {window} days "
        "after that — harvest regularly to keep production going.")
    if crop["type"] == "continuous":
        add(maturity + window, "🔄 Wind down",
            "This batch is near the end of its productive window — your next "
            "succession batch should be coming into harvest. Pull tired plants, "
            "refresh the soil with compost for the next planting.")

    events.sort(key=lambda e: (e["date"], e["title"]))

    # Crop-specific extras merged in
    for day, title, note in CROP_NOTES.get(key, []):
        events.append({
            "date": sow_date + timedelta(days=day),
            "day": day,
            "title": f"⭐ {title}",
            "note": note,
        })

    events.sort(key=lambda e: e["date"])
    return events


def split_past_upcoming(events: list, today: date) -> tuple:
    """Split a care schedule into (done_or_past, upcoming) relative to today."""
    past = [e for e in events if e["date"] < today]
    upcoming = [e for e in events if e["date"] >= today]
    return past, upcoming
