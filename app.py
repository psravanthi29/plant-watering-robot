"""Flask app for the plant-watering robot.

Two responsibilities:
  1. The JSON API under ``/api/*`` (see api.py — the Expo app's backend), plus the
     device-token sensor-ingest route and capture-image serving.
  2. Serving the exported Expo **web** build (``mobile/dist``) as a single-page app,
     so thotamaali.com *is* the app — web and native share one codebase/API.

The old server-rendered HTML dashboard/planner/vision pages were retired once the
Expo app reached feature parity (their logic lives in api.py + the mobile app now).
"""

import os

from dotenv import load_dotenv
load_dotenv()  # loads GOOGLE_API_KEY (and others) from .env if present

from flask import Flask, abort, jsonify, request, send_from_directory
from flask_cors import CORS

from plant_state import DB_PATH, init_db, log_reading
from zones import init_zones_db
from crop_planner import init_planner_db
from garden_layout import init_layout_db
from vision_analysis import CAPTURES_DIR, init_vision_db
from api import api as api_blueprint

app = Flask(__name__)

# The exported Expo web bundle (`npx expo export -p web` → mobile/dist). Served as
# a SPA below. Committed to the repo so the git-pull deploy delivers it (the EC2
# box has no Node toolchain to build it).
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mobile", "dist")

# Allow cross-origin API calls (e.g. `expo start` web during dev). The production
# web build is same-origin so this isn't needed there; tighten via CORS_ORIGINS.
CORS(app, resources={r"/api/*": {"origins": os.environ.get("CORS_ORIGINS", "*")}})
app.register_blueprint(api_blueprint)

SENSOR_API_TOKEN = os.environ.get("SENSOR_API_TOKEN")  # set in .env for real deployments


@app.route("/api/reading", methods=["POST"])
def api_reading():
    """Ingest a sensor reading pushed over the network by a sensor agent.

    Body (JSON): {"zone": "...", "value": <float>, "sensor": "moisture", "token": "..."}
    Token may also be sent as the X-API-Key header. If SENSOR_API_TOKEN is set in
    the environment, it is required; otherwise (dev) any push is accepted.

    Kept separate from the Supabase-JWT API: a headless sensor can't do an
    interactive login, so it authenticates with the shared device token instead.
    """
    data = request.get_json(silent=True) or {}
    token = request.headers.get("X-API-Key") or data.get("token")
    if SENSOR_API_TOKEN and token != SENSOR_API_TOKEN:
        return jsonify({"error": "unauthorized"}), 401

    zone = data.get("zone")
    value = data.get("value")
    sensor = data.get("sensor", "moisture")
    if zone is None or value is None:
        return jsonify({"error": "zone and value are required"}), 400
    try:
        value = float(value)
    except (TypeError, ValueError):
        return jsonify({"error": "value must be a number"}), 400

    conn = init_db(DB_PATH)
    log_reading(conn, zone, value, sensor=sensor, source=data.get("source", "agent"))
    conn.close()
    return jsonify({"ok": True, "zone": zone, "sensor": sensor, "value": value}), 201


@app.route("/captures/<path:relpath>")
def serve_capture(relpath):
    """Serve a stored plant photo for the vision timeline/thumbnails."""
    return send_from_directory(CAPTURES_DIR, relpath)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_web(path):
    """Serve the exported Expo web app (SPA fallback to index.html).

    `/api/*` and `/captures/*` have their own, more-specific rules and win the
    match; anything else maps to a static file in the web bundle, or index.html.
    """
    # Defined API/capture routes are matched before this catch-all; an UNDEFINED
    # /api or /captures path must 404, not silently return the SPA shell.
    if path.startswith("api/") or path.startswith("captures/"):
        abort(404)
    candidate = os.path.join(WEB_DIR, path)
    if path and os.path.isfile(candidate):
        return send_from_directory(WEB_DIR, path)
    return send_from_directory(WEB_DIR, "index.html")


def _ensure_schema():
    """Create all tables at startup. Runs at import so it also works under a
    WSGI server like gunicorn (which never executes __main__)."""
    init_db().close()
    init_vision_db().close()
    init_planner_db().close()
    init_zones_db().close()
    init_layout_db().close()


_ensure_schema()


if __name__ == "__main__":
    # Local dev. host=0.0.0.0 makes it reachable from other devices on the LAN.
    # In the cloud, gunicorn serves app:app and binds its own port.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
