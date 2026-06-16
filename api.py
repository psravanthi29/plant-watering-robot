"""JSON API for the Expo app — zones, crops, crop→zone placement, plan, tasks.

A Flask blueprint mounted at /api by app.py. Every route requires a Supabase JWT
(see auth.require_auth; a no-op until SUPABASE_JWT_SECRET is set). The sensor
ingest route (POST /api/reading) stays in app.py with its own device token.

DB access goes through _conn(), which reads plant_state.DB_PATH at call time so
tests can point it at a temp database.
"""

from flask import Blueprint, jsonify, request

import db
import plant_state
import crop_planner as cp
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
    conn = _conn()
    try:
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
