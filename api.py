"""JSON API for the Expo app — zones, crops, crop→zone placement, plan, tasks.

A Flask blueprint mounted at /api by app.py. Every route requires a Supabase JWT
(see auth.require_auth; a no-op until SUPABASE_JWT_SECRET is set). The sensor
ingest route (POST /api/reading) stays in app.py with its own device token.

DB access goes through _conn(), which reads plant_state.DB_PATH at call time so
tests can point it at a temp database.
"""

from datetime import date, datetime

from flask import Blueprint, jsonify, request

import db
import plant_state
import crop_planner as cp
import crop_care
import placement as placement_mod
import zones as zones_mod
from auth import require_auth

api = Blueprint("api", __name__, url_prefix="/api")


def _conn():
    return db.connect(plant_state.DB_PATH)


def _crops_with_plans(conn):
    household = cp.get_household_size(conn)
    crops = cp.list_crops(conn)
    return crops, [(c, cp.compute_crop_plan(c, household)) for c in crops]


# --------------------------------------------------------------------------- #
# Library + crops                                                              #
# --------------------------------------------------------------------------- #

@api.get("/library")
@require_auth
def get_library():
    """The seed library for the 'add a crop' picker."""
    return jsonify([
        {"key": k, "display": v["display"], "category": v["category"],
         "type": v["type"], "water_need": cp.crop_water_need({"key": k, **v}),
         "sun_need": cp.crop_sun_need({"key": k, **v})}
        for k, v in cp.SEED_LIBRARY.items()
    ])


@api.get("/crops")
@require_auth
def get_crops():
    conn = _conn()
    try:
        household = cp.get_household_size(conn)
        out = []
        for c in cp.list_crops(conn):
            out.append({
                **c,
                "plan": cp.compute_crop_plan(c, household),
                "water_need": cp.crop_water_need(c),
                "sun_need": cp.crop_sun_need(c),
                "demand_auto": cp.is_demand_auto(c),
            })
        return jsonify(out)
    finally:
        conn.close()


@api.post("/crops")
@require_auth
def add_crop_route():
    data = request.get_json(silent=True) or {}
    key = (data.get("library_key") or "").strip()
    if key not in cp.SEED_LIBRARY:
        return jsonify({"error": "unknown library_key"}), 400
    demand = data.get("weekly_demand_kg")
    conn = _conn()
    try:
        cp.add_crop(conn, cp.crop_from_library(key, weekly_demand_kg=demand))
        return jsonify({"ok": True}), 201
    finally:
        conn.close()


@api.delete("/crops/<int:crop_id>")
@require_auth
def remove_crop_route(crop_id):
    conn = _conn()
    try:
        cp.remove_crop(conn, crop_id)
        return jsonify({"ok": True})
    finally:
        conn.close()


@api.post("/crops/<int:crop_id>/zone")
@require_auth
def assign_zone_route(crop_id):
    """Place a crop in a zone (body {"zone_id": N}); zone_id=null unassigns."""
    data = request.get_json(silent=True) or {}
    conn = _conn()
    try:
        cp.assign_crop_zone(conn, crop_id, data.get("zone_id"))
        return jsonify({"ok": True})
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Zones                                                                        #
# --------------------------------------------------------------------------- #

@api.get("/zones")
@require_auth
def get_zones():
    conn = _conn()
    try:
        out = zones_mod.list_zones(conn)
        for z in out:
            z["recommended_target"] = placement_mod.zone_recommended_target(conn, z["id"])
            z["crops"] = [c["display"] for c in cp.crops_in_zone(conn, z["id"])]
        return jsonify(out)
    finally:
        conn.close()


@api.post("/zones")
@require_auth
def create_zone():
    data = request.get_json(silent=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"error": "name is required"}), 400
    conn = _conn()
    try:
        zid = zones_mod.add_zone(conn, data)
        return jsonify({"ok": True, "id": zid}), 201
    finally:
        conn.close()


@api.get("/zones/<int:zone_id>")
@require_auth
def get_zone_route(zone_id):
    conn = _conn()
    try:
        z = zones_mod.get_zone(conn, zone_id)
        if not z:
            return jsonify({"error": "not found"}), 404
        z["recommended_target"] = placement_mod.zone_recommended_target(conn, zone_id)
        z["crops"] = cp.crops_in_zone(conn, zone_id)
        return jsonify(z)
    finally:
        conn.close()


@api.patch("/zones/<int:zone_id>")
@require_auth
def update_zone_route(zone_id):
    data = request.get_json(silent=True) or {}
    conn = _conn()
    try:
        zones_mod.update_zone(conn, zone_id, data)
        return jsonify({"ok": True})
    finally:
        conn.close()


@api.delete("/zones/<int:zone_id>")
@require_auth
def delete_zone_route(zone_id):
    conn = _conn()
    try:
        zones_mod.remove_zone(conn, zone_id)
        return jsonify({"ok": True})
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Placement (auto-suggest crops → zones)                                       #
# --------------------------------------------------------------------------- #

@api.get("/placement")
@require_auth
def get_placement():
    conn = _conn()
    try:
        _, cwp = _crops_with_plans(conn)
        result = placement_mod.suggest_placement(cwp, zones_mod.list_zones(conn))
        return jsonify(result)
    finally:
        conn.close()


@api.post("/placement/apply")
@require_auth
def apply_placement():
    """Commit the suggested placement: assign crops and set zone moisture targets."""
    conn = _conn()
    try:
        _, cwp = _crops_with_plans(conn)
        result = placement_mod.suggest_placement(cwp, zones_mod.list_zones(conn))
        for a in result["assignments"]:
            if a.get("crop_id") is not None:
                cp.assign_crop_zone(conn, a["crop_id"], a["zone_id"])
        for zid, target in result["zone_targets"].items():
            zones_mod.update_zone(conn, zid, {"moisture_target": target})
        return jsonify(result)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Tasks                                                                        #
# --------------------------------------------------------------------------- #

@api.get("/tasks")
@require_auth
def get_tasks():
    """Materialize sow tasks from the current crops/plan, then list them.

    Mirrors the web planner: sow events become trackable tasks here so the Expo
    'Today' view has something to show (the API never ran sync_tasks before).
    """
    conn = _conn()
    try:
        _, cwp = _crops_with_plans(conn)
        cp.sync_tasks(conn, cwp, cp.get_plan_start_date(conn), within_days=60)
        return jsonify(cp.list_tasks(conn))
    finally:
        conn.close()


@api.post("/tasks/<int:task_id>/done")
@require_auth
def task_done(task_id):
    conn = _conn()
    try:
        cp.mark_task_done(conn, task_id)
        return jsonify({"ok": True})
    finally:
        conn.close()


@api.post("/tasks/<int:task_id>/undo")
@require_auth
def task_undo(task_id):
    conn = _conn()
    try:
        cp.mark_task_pending(conn, task_id)
        return jsonify({"ok": True})
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Per-planting care plan                                                       #
# --------------------------------------------------------------------------- #

@api.get("/care/<int:task_id>")
@require_auth
def get_care(task_id):
    """Dated care schedule for one planting, anchored to its actual sown date."""
    conn = _conn()
    try:
        task = cp.get_task(conn, task_id)
        if not task:
            return jsonify({"error": "not found"}), 404

        # Prefer the crop's saved (possibly user-tuned) row; fall back to library.
        crop = next((c for c in cp.list_crops(conn) if c["id"] == task["crop_row_id"]), None)
        if crop is None and task["crop_key"] in cp.SEED_LIBRARY:
            crop = cp.crop_from_library(task["crop_key"])
            crop["key"] = task["crop_key"]
        if crop is None:
            return jsonify({"error": "crop not found"}), 404

        sown_on = task["done_on"] or task["sow_date"]
        sow_d = datetime.strptime(sown_on, "%Y-%m-%d").date()
        events = crop_care.care_schedule(crop, sow_d)
        past, upcoming = crop_care.split_past_upcoming(events, date.today())

        def ser(e):
            return {"date": e["date"].isoformat(), "day": e["day"],
                    "title": e["title"], "note": e["note"]}

        # The planting's zone keys both the watering log and the photo timeline.
        zone = task["crop_key"] or task["display"].lower().replace(" ", "-")
        return jsonify({
            "task": {"id": task["id"], "display": task["display"],
                     "batch_size": task["batch_size"], "status": task["status"]},
            "sown_on": sown_on,
            "zone": zone,
            "past": [ser(e) for e in past],
            "upcoming": [ser(e) for e in upcoming],
        })
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Per-crop weekly-demand override + planner settings                           #
# --------------------------------------------------------------------------- #

@api.post("/crops/<int:crop_id>/demand")
@require_auth
def set_demand(crop_id):
    """Set a crop's weekly-demand override; null/blank reverts it to auto."""
    data = request.get_json(silent=True) or {}
    raw = data.get("weekly_demand_kg")
    conn = _conn()
    try:
        cp.set_crop_demand(conn, crop_id, float(raw) if raw not in (None, "") else None)
        return jsonify({"ok": True})
    except (TypeError, ValueError):
        return jsonify({"error": "weekly_demand_kg must be a number or null"}), 400
    finally:
        conn.close()


@api.get("/planner/settings")
@require_auth
def get_planner_settings():
    conn = _conn()
    try:
        return jsonify({
            "household_size": cp.get_household_size(conn),
            "plan_start_date": cp.get_plan_start_date(conn).isoformat(),
        })
    finally:
        conn.close()


@api.post("/planner/settings")
@require_auth
def set_planner_settings():
    """Update people-to-feed and/or plan start date (rescales auto-demand crops)."""
    data = request.get_json(silent=True) or {}
    conn = _conn()
    try:
        if data.get("household_size") not in (None, ""):
            cp.set_setting(conn, "household_size", int(data["household_size"]))
        if (data.get("plan_start_date") or "").strip():
            cp.set_setting(conn, "plan_start_date", data["plan_start_date"].strip())
        return jsonify({"ok": True})
    except (TypeError, ValueError):
        return jsonify({"error": "household_size must be an integer"}), 400
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Watering: manual check + history + sensor readings                           #
# --------------------------------------------------------------------------- #

@api.post("/check")
@require_auth
def watering_check():
    """Run one watering-decision pass for a zone now (moisture-gated)."""
    data = request.get_json(silent=True) or {}
    zone = (data.get("zone") or "zone-1")
    # Pass an explicit conn so the run logs to plant_state.DB_PATH as read at call
    # time (the no-conn path re-opens via init_db's default arg, bound at import).
    conn = _conn()
    try:
        state = plant_state.check_and_water(zone=zone, conn=conn)
        return jsonify({"zone": zone, "state": state})
    finally:
        conn.close()


@api.get("/runs")
@require_auth
def get_runs():
    """Recent watering-decision log (newest first)."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT 50"
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@api.get("/readings")
@require_auth
def get_readings():
    """Recent sensor readings (optionally ?zone=), newest first.

    Unlike the per-zone Dashboard cards, this surfaces ALL incoming readings —
    including ones for zone strings not yet tied to a configured zone.
    """
    zone = request.args.get("zone")
    conn = _conn()
    try:
        if zone:
            rows = conn.execute(
                "SELECT * FROM sensor_readings WHERE zone = ? ORDER BY id DESC LIMIT 50",
                (zone,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sensor_readings ORDER BY id DESC LIMIT 50"
            ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Vision: photo analysis, per-zone timeline, progress trend                    #
# --------------------------------------------------------------------------- #

@api.get("/vision/logs")
@require_auth
def vision_logs():
    import vision_analysis  # lazy: keeps google-genai out of the import path for non-vision callers
    conn = vision_analysis.init_vision_db(plant_state.DB_PATH)
    try:
        rows = vision_analysis.get_recent_analyses(conn, limit=50)
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@api.get("/vision/sessions")
@require_auth
def vision_sessions():
    """Per-zone capture history (oldest first): photos + their analyses."""
    import vision_analysis
    zone = request.args.get("zone", "zone-1")
    conn = vision_analysis.init_vision_db(plant_state.DB_PATH)
    try:
        return jsonify({"zone": zone,
                        "sessions": vision_analysis.get_zone_sessions(conn, zone)})
    finally:
        conn.close()


@api.post("/vision/analyze")
@require_auth
def vision_analyze():
    """Upload 1–4 plant photos (multipart 'images') → AI health diagnosis."""
    import vision_analysis
    files = request.files.getlist("images")
    if not files or len(files) > 4:
        return jsonify({"error": "Supply 1-4 images"}), 400
    zone = request.form.get("zone", "zone-1")
    plant_types = request.form.get("plant_types", "unknown")

    file_tuples = [(f.filename or "photo.jpg", f.read()) for f in files]
    saved = vision_analysis.save_captures(zone, file_tuples)
    try:
        result = vision_analysis.analyze_images(saved, zone=zone, plant_types=plant_types)
    except RuntimeError as exc:  # e.g. GOOGLE_API_KEY not set
        return jsonify({"error": str(exc)}), 503

    conn = vision_analysis.init_vision_db(plant_state.DB_PATH)
    try:
        vision_analysis.log_analysis(conn, zone, len(saved), result["analysis"],
                                     source="manual", image_paths=saved)
    finally:
        conn.close()
    return jsonify(result), 201


@api.post("/vision/progress")
@require_auth
def vision_progress():
    """Compare a zone's dated photos and report the trend over time."""
    import vision_analysis
    data = request.get_json(silent=True) or {}
    zone = data.get("zone", "zone-1")
    conn = vision_analysis.init_vision_db(plant_state.DB_PATH)
    try:
        sessions = vision_analysis.get_zone_sessions(conn, zone)
        try:
            result = vision_analysis.analyze_progress(zone, sessions)
        except RuntimeError as exc:  # no stored photos yet, or no API key
            return jsonify({"error": str(exc)}), 400
        vision_analysis.log_analysis(conn, zone, result["images_analyzed"],
                                     result["analysis"], source="progress")
        return jsonify(result)
    finally:
        conn.close()
