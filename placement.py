"""Suggest which zone each crop should go in (auto-suggest; user can override).

The hard constraint comes from the hardware: one zone = one sensor + one valve, so
every crop in a zone is watered together. Therefore:
  * crops sharing a zone must have the SAME water need (high/medium/low), and
  * the zone must give enough sun and have enough free area.

Strategy: greedy, largest-area crop first, into the tightest-fitting compatible
zone. A zone "commits" to the water need of the first crop placed in it; only
crops with that same need may join it afterwards. Crops that don't fit anywhere
are returned as ``unplaced`` with a human-readable reason.

Pure functions (no DB) except zone_recommended_target(), which reads the crops
currently assigned to a zone so the watering side can derive its moisture target.
"""

import crop_planner
from zones import SUN_LEVELS


def _sun_ok(crop_sun: str, zone_sun) -> bool:
    return SUN_LEVELS.get(zone_sun, 0) >= SUN_LEVELS.get(crop_sun, 2)


def _need_from_target(target) -> str | None:
    """Map a zone's manual moisture_target % back to the nearest need band."""
    if target in (None, "", 0, 0.0):
        return None
    return min(crop_planner.WATER_TARGET,
               key=lambda need: abs(crop_planner.WATER_TARGET[need] - float(target)))


def suggest_placement(crops_with_plans: list, zones: list) -> dict:
    """Suggest a crop→zone assignment.

    crops_with_plans: list of (crop_dict, plan_dict); plan_dict has ``area_m2``.
    zones: list of zone dicts (id, name, area_m2, sun, moisture_target, ...).

    Returns:
      {
        "assignments": [{crop_key, display, zone_id, zone_name, area_m2, water_need}],
        "unplaced":    [{crop_key, display, area_m2, water_need, reason}],
        "zone_targets": {zone_id: recommended_moisture_target_pct},  # from placed crops
      }
    """
    remaining = {z["id"]: float(z.get("area_m2") or 0.0) for z in zones}
    # A zone commits to one water need; seed from any manual moisture_target.
    committed = {z["id"]: _need_from_target(z.get("moisture_target")) for z in zones}
    by_id = {z["id"]: z for z in zones}

    # Largest-area crops first → better packing, fewer orphans.
    items = sorted(crops_with_plans, key=lambda cp: float(cp[1].get("area_m2") or 0.0),
                   reverse=True)

    assignments, unplaced = [], []
    for crop, plan in items:
        need = crop_planner.crop_water_need(crop)
        sun = crop_planner.crop_sun_need(crop)
        area = float(plan.get("area_m2") or 0.0)

        candidates = [
            z for z in zones
            if committed[z["id"]] in (None, need)      # same water profile
            and _sun_ok(sun, z.get("sun"))             # enough sun
            and remaining[z["id"]] >= area             # room left
        ]
        if not candidates:
            unplaced.append({
                "crop_key": crop.get("key"),
                "display": crop.get("display"),
                "area_m2": round(area, 2),
                "water_need": need,
                "reason": _why_unplaced(crop, plan, zones, remaining, committed, need, sun, area),
            })
            continue

        # Prefer zones already matching this need, then the tightest fit.
        candidates.sort(key=lambda z: (
            0 if committed[z["id"]] == need else 1,
            remaining[z["id"]],
        ))
        chosen = candidates[0]
        remaining[chosen["id"]] -= area
        committed[chosen["id"]] = need
        assignments.append({
            "crop_key": crop.get("key"),
            "display": crop.get("display"),
            "zone_id": chosen["id"],
            "zone_name": chosen.get("name"),
            "area_m2": round(area, 2),
            "water_need": need,
        })

    # Recommended target per zone = the (thirstiest) need committed to it.
    zone_targets = {}
    for zid, need in committed.items():
        if need is not None:
            zone_targets[zid] = crop_planner.WATER_TARGET[need]

    return {"assignments": assignments, "unplaced": unplaced, "zone_targets": zone_targets}


def _why_unplaced(crop, plan, zones, remaining, committed, need, sun, area) -> str:
    """Best-effort explanation for why no zone took this crop."""
    if not zones:
        return "no zones defined yet — add your beds/containers in Setup."
    sun_ok = [z for z in zones if _sun_ok(sun, z.get("sun"))]
    if not sun_ok:
        return f"needs {sun} sun; no zone provides it."
    water_ok = [z for z in sun_ok if committed[z["id"]] in (None, need)]
    if not water_ok:
        return (f"every suitable zone is already committed to a different water "
                f"profile (this crop needs {need} water).")
    return (f"not enough free area — needs {round(area, 2)} m², "
            f"most free is {round(max(remaining[z['id']] for z in water_ok), 2)} m².")


def zone_recommended_target(conn, zone_id: int) -> float | None:
    """Moisture target % derived from the crops currently in a zone.

    Uses the thirstiest crop in the zone (so nothing is under-watered). Returns
    None if the zone has no crops — caller falls back to a manual/zone default.
    """
    crops = crop_planner.crops_in_zone(conn, zone_id)
    if not crops:
        return None
    needs = [crop_planner.crop_water_need(c) for c in crops]
    thirstiest = max(needs, key=lambda n: crop_planner.WATER_RANK.get(n, 1))
    return crop_planner.WATER_TARGET[thirstiest]
