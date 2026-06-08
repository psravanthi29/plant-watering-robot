"""Flask REST API / dashboard for the plant-watering robot (SIMULATE-aware)."""

import sqlite3

from flask import Flask, jsonify, render_template_string

from plant_state import DB_PATH, check_and_water, init_db

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
"""


def get_runs(limit=50):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


@app.route("/")
def dashboard():
    return render_template_string(PAGE, runs=get_runs())


@app.route("/api/runs")
def api_runs():
    return jsonify([dict(r) for r in get_runs()])


@app.route("/check", methods=["POST"])
def check():
    state = check_and_water()
    return jsonify({"state": state}), 200


if __name__ == "__main__":
    init_db().close()
    app.run(debug=True)
