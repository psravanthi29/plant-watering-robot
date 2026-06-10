"""Flask REST API / dashboard for the plant-watering robot (SIMULATE-aware)."""

import sqlite3
from datetime import date, datetime

from dotenv import load_dotenv
load_dotenv()  # loads GOOGLE_API_KEY (and others) from .env if present

from flask import (
    Flask, jsonify, redirect, render_template_string, request, send_from_directory,
)

from plant_state import DB_PATH, check_and_water, init_db
from vision_analysis import (
    CAPTURES_DIR,
    analyze_images,
    analyze_progress,
    get_zone_sessions,
    init_vision_db,
    log_analysis,
    save_captures,
)
from crop_planner import (
    SEED_LIBRARY,
    add_crop,
    compute_crop_plan,
    crop_from_library,
    get_household_size,
    get_plan_start_date,
    get_task,
    init_planner_db,
    is_demand_auto,
    list_crops,
    list_tasks,
    mark_task_done,
    mark_task_pending,
    remove_crop,
    set_crop_demand,
    set_setting,
    sync_tasks,
)
from crop_care import care_schedule, split_past_upcoming

app = Flask(__name__)

PAGE = """
<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Plant Watering Dashboard</title>
<style>
  body { font-family: sans-serif; max-width: 700px; margin: 0 auto; padding: 12px; }
  h1 { font-size: 1.3em; } h2 { font-size: 1.1em; margin-top: 24px; }
  table { border-collapse: collapse; width: 100%; font-size: 0.85em; }
  th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; }
  th { background: #f0f0f0; }
  .btn { display: inline-block; padding: 10px 18px; margin: 6px 4px; font-size: 1em;
         border: none; border-radius: 6px; cursor: pointer; }
  .btn-green { background: #3a7d44; color: #fff; }
  .btn-blue  { background: #1a6faf; color: #fff; }
  .btn-amber { background: #e07b00; color: #fff; }
  label { display: block; margin: 8px 0 2px; font-size: 0.95em; }
  input[type=text] { width: 100%; padding: 6px; box-sizing: border-box; font-size: 1em; }
  #preview { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
  #preview img { width: 90px; height: 90px; object-fit: cover; border-radius: 6px; border: 1px solid #ccc; }
  .analysis-box { background: #f4f8f4; border-left: 4px solid #3a7d44;
                  padding: 10px 14px; margin-top: 10px; white-space: pre-wrap;
                  font-size: 0.9em; border-radius: 4px; }
  .spinner { display: none; font-size: 0.9em; color: #666; margin-top: 8px; }
</style>

<h1>🌱 Plant Watering Dashboard</h1>
<p>🗓 <a href="/planner">Garden Planner</a> — plan sowing dates, plant counts &amp; spacing for year-round produce</p>
<form action="/check" method="post">
  <button class="btn btn-green" type="submit">💧 Run watering check now</button>
</form>

<h2>Watering History</h2>
<table>
  <tr><th>Time</th><th>Zone</th><th>Moisture</th><th>State</th><th>Action</th><th>Reason</th></tr>
  {% for r in runs %}
  <tr>
    <td>{{ r['timestamp'][:19] }}</td>
    <td>{{ r['zone'] }}</td>
    <td>{{ r['moisture'] }}</td>
    <td>{{ r['state'] }}</td>
    <td>{{ r['action'] }}</td>
    <td>{{ r['reason'] }}</td>
  </tr>
  {% endfor %}
</table>

<h2>📷 Plant Vision Analysis</h2>
<form id="analyzeForm" action="/analyze" method="post" enctype="multipart/form-data">
  <label>Zone</label>
  <input type="text" name="zone" value="zone-1">
  <label>Plant types (optional)</label>
  <input type="text" name="plant_types" placeholder="e.g. tomato, curry leaf, basil">

  <!-- Hidden file input shared by both buttons -->
  <input type="file" id="galleryPicker" name="images" multiple accept="image/*" style="display:none">
  <!-- Camera-direct input: capture="environment" opens rear camera straight away -->
  <input type="file" id="cameraPicker" name="images" accept="image/*" capture="environment" style="display:none">

  <div style="margin-top:10px">
    <button class="btn btn-blue" type="button" onclick="document.getElementById('galleryPicker').click()">
      🖼 Pick from gallery (up to 4)
    </button>
    <button class="btn btn-amber" type="button" onclick="document.getElementById('cameraPicker').click()">
      📸 Take photo now
    </button>
  </div>

  <div id="preview"></div>
  <div class="spinner" id="spinner">⏳ Analyzing… this takes ~10 seconds</div>
  <button class="btn btn-green" type="submit" id="submitBtn" style="display:none">
    🔍 Analyze selected photos
  </button>
</form>

{% if last_analysis %}
<h3>Latest analysis</h3>
<div class="analysis-box">{{ last_analysis }}</div>
{% endif %}

<p style="margin-top:10px">
  📈 <a href="/zone/zone-1">View progress timeline for zone-1</a>
  &nbsp;(track changes over days &amp; run a trend comparison)
</p>

<h2>Vision Log</h2>
<table>
  <tr><th>Time</th><th>Zone</th><th>#</th><th>Source</th><th>Analysis</th></tr>
  {% for v in vision_logs %}
  <tr>
    <td>{{ v['timestamp'][:19] }}</td>
    <td>{{ v['zone'] }}</td>
    <td>{{ v['image_count'] }}</td>
    <td>{{ v['source'] }}</td>
    <td><div style="white-space:pre-wrap;max-width:400px;font-size:0.85em">{{ v['analysis'] }}</div></td>
  </tr>
  {% endfor %}
</table>

<script>
// Merge files from both pickers into a single DataTransfer, show previews
const dt = new DataTransfer();

function onFilesChosen(input) {
  for (const file of input.files) {
    if (dt.items.length >= 4) { alert("Max 4 photos"); break; }
    dt.items.add(file);
  }
  // Sync both inputs to the merged set so FormData sends them all
  document.getElementById('galleryPicker').files = dt.files;
  document.getElementById('cameraPicker').files = dt.files;
  renderPreviews();
}

function renderPreviews() {
  const box = document.getElementById('preview');
  box.innerHTML = '';
  for (const file of dt.files) {
    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    box.appendChild(img);
  }
  document.getElementById('submitBtn').style.display = dt.files.length ? 'inline-block' : 'none';
}

document.getElementById('galleryPicker').addEventListener('change', function(){ onFilesChosen(this); });
document.getElementById('cameraPicker').addEventListener('change', function(){ onFilesChosen(this); });

document.getElementById('analyzeForm').addEventListener('submit', function() {
  document.getElementById('spinner').style.display = 'block';
  document.getElementById('submitBtn').disabled = true;
});
</script>
"""

TIMELINE_PAGE = """
<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ zone }} — Progress Timeline</title>
<style>
  body { font-family: sans-serif; max-width: 700px; margin: 0 auto; padding: 12px; }
  h1 { font-size: 1.3em; } h2 { font-size: 1.05em; }
  a { color: #1a6faf; }
  .btn { display: inline-block; padding: 10px 18px; margin: 6px 0; font-size: 1em;
         border: none; border-radius: 6px; cursor: pointer; }
  .btn-purple { background: #6a4caf; color: #fff; }
  .session { border: 1px solid #ddd; border-radius: 8px; padding: 10px 14px; margin: 12px 0; }
  .session .date { font-weight: bold; color: #3a7d44; }
  .thumbs { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
  .thumbs img { width: 110px; height: 110px; object-fit: cover; border-radius: 6px; border: 1px solid #ccc; }
  .analysis-box { background: #f7f7f7; padding: 8px 12px; white-space: pre-wrap;
                  font-size: 0.88em; border-radius: 4px; }
  .progress-box { background: #f0ecfa; border-left: 4px solid #6a4caf; padding: 12px 16px;
                  white-space: pre-wrap; font-size: 0.92em; border-radius: 4px; margin: 10px 0; }
  .spinner { display: none; color: #666; margin-top: 6px; }
</style>

<p><a href="/">&larr; Back to dashboard</a></p>
<h1>📈 {{ zone }} — Progress over time</h1>

<form action="/progress" method="post" id="progForm">
  <input type="hidden" name="zone" value="{{ zone }}">
  <button class="btn btn-purple" type="submit" id="progBtn">
    🔬 Analyze progress across all dates
  </button>
  <div class="spinner" id="progSpin">⏳ Comparing photos over time… ~15 seconds</div>
</form>

{% if progress %}
<h2>Progress assessment</h2>
<div class="progress-box">{{ progress }}</div>
{% endif %}

<h2>Capture history ({{ sessions|length }} sessions, newest first)</h2>
{% if not sessions %}
<p>No captures yet for this zone. Take some photos from the dashboard first.</p>
{% endif %}
{% for s in sessions %}
<div class="session">
  <div class="date">{{ s.timestamp[:16].replace('T', ' ') }} <span style="color:#999;font-weight:normal">({{ s.source }})</span></div>
  <div class="thumbs">
    {% for p in s.image_paths %}
      <a href="/captures/{{ p.split('captures/')[1] }}" target="_blank">
        <img src="/captures/{{ p.split('captures/')[1] }}" alt="capture">
      </a>
    {% endfor %}
  </div>
  <div class="analysis-box">{{ s.analysis }}</div>
</div>
{% endfor %}

<script>
document.getElementById('progForm').addEventListener('submit', function() {
  document.getElementById('progSpin').style.display = 'block';
  document.getElementById('progBtn').disabled = true;
});
</script>
"""

PLANNER_STYLE = """
<style>
  :root { --green:#3a7d44; --green-soft:#eef5ee; --amber:#e07b00; --blue:#1a6faf; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; max-width: 760px;
         margin: 0 auto; padding: 12px 14px 60px; background: #fcfcfa; color: #222; }
  h1 { font-size: 1.35em; margin: 8px 0 2px; }
  h2 { font-size: 1.05em; margin: 26px 0 8px; display:flex; align-items:center; gap:6px; }
  a { color: var(--blue); text-decoration: none; }
  .topnav { font-size: 0.92em; margin-bottom: 4px; }
  .muted { color: #888; font-size: 0.85em; }
  .btn { display:inline-block; padding: 10px 16px; font-size: 0.98em; border: none;
         border-radius: 8px; cursor: pointer; background: var(--green); color: #fff;
         font-weight: 600; }
  .btn:active { transform: scale(0.98); }
  .btn-ghost { background:#fff; color:#b44; border:1px solid #d99; font-weight:normal;
               padding: 6px 12px; font-size: 0.85em; }
  .btn-amber { background: var(--amber); }
  input[type=text], input[type=number], input[type=date], select {
    padding: 9px 10px; font-size: 1em; border: 1px solid #ccc; border-radius: 8px;
    background: #fff; }
  .card { border: 1px solid #e3e3dd; border-radius: 12px; padding: 14px 16px;
          margin: 10px 0; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
  .task { display:flex; align-items:center; justify-content:space-between; gap:10px;
          flex-wrap:wrap; }
  .task.overdue { border-left: 4px solid var(--amber); }
  .task .when { font-weight: 700; color: var(--green); }
  .task .what { flex: 1 1 200px; }
  .chip { display:inline-block; padding: 1px 9px; border-radius: 10px; font-size: 0.75em;
          background: var(--green-soft); color: var(--green); font-weight: 600; }
  .chip.amber { background:#fdf1e0; color:#b36200; }
  .chip.blue  { background:#e8f1f8; color:#155d92; }
  .cropgrid { display:grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
              gap: 10px; }
  .crop-card h3 { margin: 0 0 4px; font-size: 1em; }
  .crop-card .stats { display:flex; gap:14px; flex-wrap:wrap; font-size:0.88em;
                      margin: 6px 0; }
  .crop-card .stats b { font-size: 1.15em; color: var(--green); display:block; }
  .totals { background: var(--green-soft); border-radius: 12px; padding: 12px 16px;
            margin: 12px 0; font-size: 0.95em; }
  details { margin: 10px 0; }
  details summary { cursor: pointer; font-weight: 600; padding: 10px 4px; }
  .empty { text-align:center; padding: 26px 10px; color:#999; }
  .demand-form { display:flex; gap:6px; align-items:center; margin-top:6px; }
  .demand-form input { width: 92px; }
</style>
"""

PLANNER_PAGE = """
<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Garden Planner</title>
""" + PLANNER_STYLE + """
<div class="topnav"><a href="/">&larr; Dashboard</a></div>
<h1>🗓 Garden Planner</h1>
<p class="muted">Feeding {{ household_size }} people · plan starts {{ start_date }}</p>

<h2>📋 To-do — sow these</h2>
{% if not tasks_pending %}
<div class="card empty">Nothing waiting to be sown.
{% if not rows %}Add your first crop below to get a plan. 👇{% else %}You're all caught up! 🎉{% endif %}</div>
{% endif %}
{% for t in tasks_pending %}
<div class="card task {{ 'overdue' if t.sow_date < today }}">
  <div class="what">
    <span class="when">{{ t.sow_date }}</span>
    {% if t.sow_date < today %}<span class="chip amber">overdue</span>{% endif %}<br>
    Sow <b>{{ t.batch_size }}</b> × <b>{{ t.display }}</b>
  </div>
  <form action="/planner/task/done" method="post" style="margin:0">
    <input type="hidden" name="task_id" value="{{ t.id }}">
    <button class="btn" type="submit">✓ Mark sown</button>
  </form>
</div>
{% endfor %}

{% if tasks_done %}
<h2>🌿 Growing now — tap for care plan</h2>
{% for t in tasks_done %}
<div class="card task">
  <div class="what">
    <b>{{ t.display }}</b> <span class="chip">sown {{ t.done_on }}</span><br>
    <span class="muted">{{ t.batch_size }} plants</span>
  </div>
  <div style="display:flex; gap:8px; align-items:center">
    <a class="btn btn-amber" href="/planner/care/{{ t.id }}">🌿 Care plan</a>
    <form action="/planner/task/undo" method="post" style="margin:0">
      <input type="hidden" name="task_id" value="{{ t.id }}">
      <button class="btn-ghost btn" type="submit" title="Undo">↩</button>
    </form>
  </div>
</div>
{% endfor %}
{% endif %}

<h2>🥬 My crops ({{ rows|length }})</h2>
{% if not rows %}
<div class="card empty">No crops yet — add one below and the planner will work out
how many plants you need and when to sow.</div>
{% else %}
<div class="cropgrid">
  {% for r in rows %}
  <div class="card crop-card">
    <h3>{{ r.crop.display }}
      <span class="chip {{ 'blue' if r.plan.type == 'perennial' }}">
        {{ 'plant once' if r.plan.type == 'perennial' else r.plan.type }}</span>
    </h3>
    <div class="stats">
      <span><b>{{ r.plan.plants_needed }}</b> plants</span>
      <span><b>{{ r.plan.weekly_demand_kg }} kg</b> per week
        <span class="muted">({{ 'auto' if r.demand_auto else 'custom' }})</span></span>
      <span><b>{{ r.plan.area_m2 }} m²</b> area</span>
    </div>
    {% if r.plan.type != 'perennial' %}
    <div class="muted">Sow {{ r.plan.batch_size }} every {{ r.plan.succession_interval_days }} days
    for continuous harvest</div>
    {% endif %}
    <div class="demand-form">
      <form action="/planner/set-demand" method="post" style="display:flex;gap:6px;margin:0">
        <input type="hidden" name="crop_id" value="{{ r.crop.id }}">
        <input type="number" step="0.1" name="weekly_demand_kg"
          {% if r.demand_auto %}placeholder="kg/week"{% else %}value="{{ r.crop.weekly_demand_kg }}"{% endif %}>
        <button class="btn" style="padding:6px 12px;font-size:0.85em" type="submit">set need</button>
      </form>
      <form action="/planner/remove" method="post" style="margin:0 0 0 auto">
        <input type="hidden" name="crop_id" value="{{ r.crop.id }}">
        <button class="btn btn-ghost" type="submit">remove</button>
      </form>
    </div>
  </div>
  {% endfor %}
</div>

<div class="totals">
  <b>Whole garden:</b> {{ total_plants }} plants · ~<b>{{ total_area }} m²</b>
  <div class="muted">Rough footprint at peak — vertical growing &amp; intercropping
  usually fit more. "set need" blank = back to auto.</div>
</div>
{% endif %}

<h2>➕ Add a crop</h2>
<div class="card">
  <form action="/planner/add" method="post" style="display:flex; gap:8px; flex-wrap:wrap">
    <select name="library_key" style="flex:1 1 220px">
      <option value="">— choose a crop —</option>
      {% for key, c in library.items() %}
      <option value="{{ key }}">{{ c.display }} ({{ c.category }})</option>
      {% endfor %}
    </select>
    <button class="btn" type="submit">Add</button>
  </form>
</div>

<details>
  <summary>⚙️ Settings</summary>
  <div class="card">
    <form action="/planner/settings" method="post" style="display:flex; gap:10px; flex-wrap:wrap; align-items:flex-end">
      <label>People to feed<br>
        <input type="number" name="household_size" value="{{ household_size }}" min="1" style="width:90px"></label>
      <label>Plan start date<br>
        <input type="text" name="plan_start_date" value="{{ start_date }}" placeholder="YYYY-MM-DD" style="width:140px"></label>
      <button class="btn" type="submit">Save</button>
    </form>
    <p class="muted" style="margin-top:8px">Changing people-to-feed rescales every crop
    that's on "auto" demand. Crop yields/timings are editable estimates — tune as you learn
    your garden's real numbers.</p>
  </div>
</details>
"""

CARE_PAGE = """
<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Care plan — {{ task.display }}</title>
""" + PLANNER_STYLE + """
<div class="topnav"><a href="/planner">&larr; Planner</a></div>
<h1>🌿 {{ task.display }}</h1>
<p class="muted">{{ task.batch_size }} plants · sown {{ sown_on }}</p>

<h2>📌 Up next</h2>
{% if not upcoming %}
<div class="card empty">No more scheduled care — this planting should be wrapping up.
Check the planner for your next sowing.</div>
{% endif %}
{% for e in upcoming %}
<div class="card {{ 'task overdue' if loop.first }}">
  <span class="when" style="font-weight:700;color:var(--green)">{{ e.date }}</span>
  <span class="muted">(day {{ e.day }})</span>
  {% if loop.first %}<span class="chip amber">next up</span>{% endif %}
  <div style="margin-top:4px"><b>{{ e.title }}</b></div>
  <div style="font-size:0.92em; margin-top:2px">{{ e.note }}</div>
</div>
{% endfor %}

{% if past %}
<details>
  <summary>✅ Earlier steps ({{ past|length }})</summary>
  {% for e in past %}
  <div class="card" style="opacity:0.65">
    <span class="muted">{{ e.date }} (day {{ e.day }})</span>
    <div><b>{{ e.title }}</b></div>
    <div style="font-size:0.9em">{{ e.note }}</div>
  </div>
  {% endfor %}
</details>
{% endif %}
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

    # Persist the photos (so we can review/compare them over days), then analyze.
    file_tuples = [(f.filename or "photo.jpg", f.read()) for f in files]
    saved_paths = save_captures(zone, file_tuples)

    result = analyze_images(saved_paths, zone=zone, plant_types=plant_types)

    conn = init_vision_db(DB_PATH)
    log_analysis(conn, zone, len(saved_paths), result["analysis"],
                 source="manual", image_paths=saved_paths)
    conn.close()

    if request.accept_mimetypes.best == "application/json":
        return jsonify(result)

    return render_template_string(
        PAGE,
        runs=get_runs(),
        vision_logs=get_vision_logs(),
        last_analysis=result["analysis"],
    )


@app.route("/captures/<path:relpath>")
def serve_capture(relpath):
    """Serve a stored plant photo for the timeline/thumbnail views."""
    return send_from_directory(CAPTURES_DIR, relpath)


@app.route("/zone/<zone>")
def zone_timeline(zone):
    """Chronological view of every capture for a zone, with photos + analysis."""
    conn = init_vision_db(DB_PATH)
    sessions = get_zone_sessions(conn, zone)
    conn.close()
    sessions = list(reversed(sessions))  # newest first for display
    return render_template_string(
        TIMELINE_PAGE, zone=zone, sessions=sessions, progress=None
    )


@app.route("/progress", methods=["POST"])
def progress():
    """Send all of a zone's dated photos to Gemini and report the trend over time."""
    zone = request.form.get("zone", "zone-1")
    conn = init_vision_db(DB_PATH)
    sessions = get_zone_sessions(conn, zone)  # oldest first
    try:
        result = analyze_progress(zone, sessions)
        log_analysis(conn, zone, result["images_analyzed"], result["analysis"],
                     source="progress")
        progress_text = result["analysis"]
    except RuntimeError as exc:
        progress_text = str(exc)
    conn.close()

    if request.accept_mimetypes.best == "application/json":
        return jsonify({"zone": zone, "analysis": progress_text})

    return render_template_string(
        TIMELINE_PAGE, zone=zone, sessions=list(reversed(sessions)),
        progress=progress_text
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


# --------------------------------------------------------------------------- #
# Garden planner                                                               #
# --------------------------------------------------------------------------- #

def _build_planner_view(conn):
    """Compute everything the planner page needs from the stored crops + settings."""
    household = get_household_size(conn)
    start = get_plan_start_date(conn)
    crops = list_crops(conn)

    rows = []
    crops_with_plans = []
    total_plants = 0
    total_area = 0.0
    for c in crops:
        plan = compute_crop_plan(c, household)
        rows.append({"crop": c, "plan": plan, "demand_auto": is_demand_auto(c)})
        crops_with_plans.append((c, plan))
        total_plants += plan["plants_needed"]
        total_area += plan["area_m2"]

    # Materialize sow events as trackable tasks, then split by status
    sync_tasks(conn, crops_with_plans, start, within_days=60)
    tasks = list_tasks(conn)
    tasks_pending = [t for t in tasks if t["status"] == "pending"]
    tasks_done = [t for t in tasks if t["status"] == "done"]
    tasks_pending.sort(key=lambda t: t["sow_date"])
    tasks_done.sort(key=lambda t: t["done_on"] or "", reverse=True)

    return {
        "household_size": household,
        "start_date": start.isoformat(),
        "today": date.today().isoformat(),
        "library": SEED_LIBRARY,
        "rows": rows,
        "tasks_pending": tasks_pending,
        "tasks_done": tasks_done,
        "total_plants": total_plants,
        "total_area": round(total_area, 2),
    }


@app.route("/planner")
def planner():
    conn = init_planner_db(DB_PATH)
    view = _build_planner_view(conn)
    conn.close()
    return render_template_string(PLANNER_PAGE, **view)


@app.route("/planner/settings", methods=["POST"])
def planner_settings():
    conn = init_planner_db(DB_PATH)
    hh = request.form.get("household_size", "").strip()
    if hh:
        set_setting(conn, "household_size", int(hh))
    start = request.form.get("plan_start_date", "").strip()
    if start:
        set_setting(conn, "plan_start_date", start)
    conn.close()
    return redirect_to_planner()


@app.route("/planner/add", methods=["POST"])
def planner_add():
    conn = init_planner_db(DB_PATH)
    key = request.form.get("library_key", "").strip()
    if key and key in SEED_LIBRARY:
        demand_raw = request.form.get("weekly_demand_kg", "").strip()
        demand = float(demand_raw) if demand_raw else None
        add_crop(conn, crop_from_library(key, weekly_demand_kg=demand))
    conn.close()
    return redirect_to_planner()


@app.route("/planner/remove", methods=["POST"])
def planner_remove():
    conn = init_planner_db(DB_PATH)
    crop_id = request.form.get("crop_id")
    if crop_id:
        remove_crop(conn, int(crop_id))
    conn.close()
    return redirect_to_planner()


@app.route("/planner/set-demand", methods=["POST"])
def planner_set_demand():
    """Set a per-crop weekly-demand override, or clear it (blank) back to auto."""
    conn = init_planner_db(DB_PATH)
    crop_id = request.form.get("crop_id")
    raw = request.form.get("weekly_demand_kg", "").strip()
    if crop_id:
        set_crop_demand(conn, int(crop_id), float(raw) if raw else None)
    conn.close()
    return redirect_to_planner()


@app.route("/api/planner/plan")
def api_planner_plan():
    conn = init_planner_db(DB_PATH)
    view = _build_planner_view(conn)
    conn.close()
    return jsonify({
        "household_size": view["household_size"],
        "start_date": view["start_date"],
        "total_plants": view["total_plants"],
        "total_area_m2": view["total_area"],
        "crops": [
            {"display": r["crop"]["display"], **r["plan"]} for r in view["rows"]
        ],
        "tasks_pending": view["tasks_pending"],
        "tasks_done": view["tasks_done"],
    })


@app.route("/planner/task/done", methods=["POST"])
def planner_task_done():
    conn = init_planner_db(DB_PATH)
    task_id = request.form.get("task_id")
    if task_id:
        mark_task_done(conn, int(task_id))
    conn.close()
    return redirect_to_planner()


@app.route("/planner/task/undo", methods=["POST"])
def planner_task_undo():
    conn = init_planner_db(DB_PATH)
    task_id = request.form.get("task_id")
    if task_id:
        mark_task_pending(conn, int(task_id))
    conn.close()
    return redirect_to_planner()


@app.route("/planner/care/<int:task_id>")
def planner_care(task_id):
    """Post-sowing care plan for one planting, anchored to the actual sown date."""
    conn = init_planner_db(DB_PATH)
    task = get_task(conn, task_id)
    if not task:
        conn.close()
        return redirect_to_planner()

    # Prefer the crop's saved (possibly user-tuned) row; fall back to the library.
    crop = next((c for c in list_crops(conn) if c["id"] == task["crop_row_id"]), None)
    conn.close()
    if crop is None and task["crop_key"] in SEED_LIBRARY:
        crop = crop_from_library(task["crop_key"])
        crop["key"] = task["crop_key"]
    if crop is None:
        return redirect_to_planner()

    sown_on = task["done_on"] or task["sow_date"]
    sow_d = datetime.strptime(sown_on, "%Y-%m-%d").date()
    events = care_schedule(crop, sow_d)
    past, upcoming = split_past_upcoming(events, date.today())

    return render_template_string(
        CARE_PAGE, task=task, sown_on=sown_on, past=past, upcoming=upcoming
    )


def redirect_to_planner():
    return redirect("/planner")


if __name__ == "__main__":
    init_db().close()
    init_vision_db().close()
    init_planner_db().close()
    # host="0.0.0.0" makes the server reachable from other devices on the same WiFi.
    # Use http://<your-machine-ip>:5000 on your phone.
    app.run(host="0.0.0.0", port=5000, debug=True)
