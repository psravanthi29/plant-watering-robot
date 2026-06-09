"""Flask REST API / dashboard for the plant-watering robot (SIMULATE-aware)."""

import os
import sqlite3
import tempfile

from flask import Flask, jsonify, render_template_string, request

from plant_state import DB_PATH, check_and_water, init_db
from vision_analysis import analyze_images, init_vision_db, log_analysis, get_recent_analyses

app = Flask(__name__)

PAGE = """
<!doctype html>
<title>Plant Watering Dashboard</title>
<h1>Plant Watering History</h1>
<form action="/check" method="post"><button type="submit">Run check now</button></form>
<table border="1" cellpadding="4">
  <tr>
    <th>Time</th><th>Zone</th><th>Moisture</th>
    <th>State</th><th>Action</th><th>Reason</th>
  </tr>
  {% for r in runs %}
  <tr>
    <td>{{ r['timestamp'] }}</td>
    <td>{{ r['zone'] }}</td>
    <td>{{ r['moisture'] }}</td>
    <td>{{ r['state'] }}</td>
    <td>{{ r['action'] }}</td>
    <td>{{ r['reason'] }}</td>
  </tr>
  {% endfor %}
</table>

<h2>Plant Vision Analysis</h2>
<form action="/analyze" method="post" enctype="multipart/form-data">
  <label>Photos (1-4): <input type="file" name="images" multiple accept="image/*"></label><br>
  <label>Zone: <input type="text" name="zone" value="zone-1"></label><br>
  <label>Plant types (optional): <input type="text" name="plant_types" placeholder="e.g. tomato, basil"></label><br>
  <button type="submit">Analyze photos</button>
</form>
{% if last_analysis %}
<h3>Latest analysis</h3>
<pre style="background:#f4f4f4;padding:8px">{{ last_analysis }}</pre>
{% endif %}

<h3>Vision log</h3>
<table border="1" cellpadding="4">
  <tr><th>Time</th><th>Zone</th><th>Images</th><th>Source</th><th>Analysis</th></tr>
  {% for v in vision_logs %}
  <tr>
    <td>{{ v['timestamp'] }}</td>
    <td>{{ v['zone'] }}</td>
    <td>{{ v['image_count'] }}</td>
    <td>{{ v['source'] }}</td>
    <td><pre style="margin:0;white-space:pre-wrap;max-width:600px">{{ v['analysis'] }}</pre></td>
  </tr>
  {% endfor %}
</table>
"""


def get_runs(limit=50):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


def get_vision_logs(limit=10):
    conn = init_vision_db(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM vision_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


@app.route("/")
def dashboard():
    return render_template_string(
        PAGE, runs=get_runs(), vision_logs=get_vision_logs(), last_analysis=None
    )


@app.route("/api/runs")
def api_runs():
    return jsonify([dict(r) for r in get_runs()])


@app.route("/check", methods=["POST"])
def check():
    state = check_and_water()
    return jsonify({"state": state}), 200


@app.route("/analyze", methods=["POST"])
def analyze():
    files = request.files.getlist("images")
    if not files or len(files) > 4:
        return jsonify({"error": "Supply 1-4 images"}), 400

    zone = request.form.get("zone", "zone-1")
    plant_types = request.form.get("plant_types", "unknown")

    saved = []
    tmp_dir = tempfile.mkdtemp()
    try:
        for f in files:
            dest = os.path.join(tmp_dir, f.filename)
            f.save(dest)
            saved.append(dest)

        result = analyze_images(saved, zone=zone, plant_types=plant_types)

        conn = init_vision_db(DB_PATH)
        log_analysis(conn, zone, len(saved), result["analysis"], source="manual")
        conn.close()
    finally:
        for p in saved:
            try:
                os.remove(p)
            except OSError:
                pass

    if request.accept_mimetypes.best == "application/json":
        return jsonify(result)

    return render_template_string(
        PAGE,
        runs=get_runs(),
        vision_logs=get_vision_logs(),
        last_analysis=result["analysis"],
    )


@app.route("/api/vision-logs")
def api_vision_logs():
    conn = init_vision_db(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM vision_logs ORDER BY id DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    init_db().close()
    init_vision_db().close()
    app.run(debug=True)
