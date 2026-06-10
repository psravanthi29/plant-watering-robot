"""Plant health analysis via Google Gemini Vision API.

Two usage modes:
- Manual: user uploads photos via the Flask /analyze endpoint for prompt refinement.
- Automated: Pi Camera captures on a schedule; same function, same API call.

Results are logged to the vision_logs table in plant.db (created on first use).
Requires GOOGLE_API_KEY in environment (or .env file).
Get a free key at https://aistudio.google.com/app/apikey
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types

from plant_state import DB_PATH

VISION_MODEL = "gemini-2.5-flash"

# gemini-2.5-flash: fast, capable vision, generous free tier — good default
# gemini-2.5-pro:   slower but more detailed — swap in for deeper diagnosis
# Use `python -c "..."` listing in README/notes to see currently available models.

# Photos are kept here so we can review and compare them over time.
# Layout: captures/<zone>/<YYYY-MM-DD_HHMMSS>/<n>.<ext>
CAPTURES_DIR = "captures"

PATH_SEP = "|"  # how multiple image paths are joined in the DB column

ANALYSIS_PROMPT = """You are analyzing {count} photo(s) of plants in a home/terrace garden.

Zone: {zone}
Plant types (if known): {plant_types}
Most recent soil moisture reading: {moisture_pct}%

Please analyze and report:
1. Overall health: healthy / mild concern / needs attention
2. Any visible issues (yellowing, wilting, spots, leggy growth, pests, root problems, etc.)
3. Likely cause for each issue you see, if identifiable
4. Recommended action (adjust watering, check for pests, add nutrients, repot, etc.)

Be concise. If the plants look healthy say so in one line. Focus on actionable observations."""


def _make_client() -> genai.Client:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. "
            "Get a free key at https://aistudio.google.com/app/apikey "
            "and add it to your .env file as GOOGLE_API_KEY=..."
        )
    return genai.Client(api_key=api_key)


def analyze_images(
    image_paths: list,
    zone: str = "zone-1",
    plant_types: str = "unknown",
    moisture_pct: float | None = None,
    model: str = VISION_MODEL,
) -> dict:
    """Send local images to Gemini Vision for plant health analysis.

    Args:
        image_paths: Paths to local JPEG/PNG files (1-4 recommended).
        zone: Zone identifier passed as context to the model.
        plant_types: Comma-separated plant names, e.g. "tomato, basil".
        moisture_pct: Latest sensor reading, included as context if available.
        model: Gemini model ID. Default is gemini-2.0-flash.

    Returns:
        dict with keys: zone, analysis (text), images_analyzed, timestamp.
    """
    client = _make_client()

    # Build the parts list: images first, then the text prompt
    parts = []
    for path in image_paths:
        raw = Path(path).read_bytes()
        suffix = Path(path).suffix.lower().lstrip(".")
        mime_type = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
        parts.append(types.Part(inline_data=types.Blob(mime_type=mime_type, data=raw)))

    parts.append(
        types.Part(
            text=ANALYSIS_PROMPT.format(
                count=len(image_paths),
                zone=zone,
                plant_types=plant_types,
                moisture_pct=f"{moisture_pct:.1f}" if moisture_pct is not None else "N/A",
            )
        )
    )

    response = client.models.generate_content(
        model=model,
        contents=parts,
    )

    return {
        "zone": zone,
        "analysis": response.text,
        "images_analyzed": len(image_paths),
        "timestamp": datetime.now().isoformat(),
    }


def init_vision_db(path: str = DB_PATH) -> sqlite3.Connection:
    """Create vision_logs table if it doesn't exist (additive — does not touch runs table)."""
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vision_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            zone        TEXT NOT NULL,
            image_count INTEGER,
            source      TEXT,
            analysis    TEXT,
            image_paths TEXT
        )
        """
    )
    # Migrate older DBs that predate the image_paths column.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(vision_logs)").fetchall()]
    if "image_paths" not in cols:
        conn.execute("ALTER TABLE vision_logs ADD COLUMN image_paths TEXT")
    conn.commit()
    return conn


def save_captures(zone: str, files, captures_root: str = CAPTURES_DIR) -> list:
    """Persist uploaded photos to captures/<zone>/<timestamp>/ and return their paths.

    `files` is a list of (original_name, bytes) tuples. Returns a list of
    relative file paths (forward-slash form) suitable for storing in the DB
    and serving over HTTP.
    """
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    safe_zone = zone.replace("/", "_").replace("\\", "_")
    session_dir = Path(captures_root) / safe_zone / stamp
    session_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for i, (name, data) in enumerate(files):
        ext = Path(name).suffix.lower() or ".jpg"
        dest = session_dir / f"{i}{ext}"
        dest.write_bytes(data)
        saved.append(dest.as_posix())
    return saved


def log_analysis(conn: sqlite3.Connection, zone: str, image_count: int,
                 analysis: str, source: str = "manual",
                 image_paths: list | None = None) -> None:
    """Persist a vision analysis result. source is 'manual', 'pi_camera', or 'progress'."""
    paths_str = PATH_SEP.join(image_paths) if image_paths else None
    conn.execute(
        "INSERT INTO vision_logs (timestamp, zone, image_count, source, analysis, image_paths) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), zone, image_count, source, analysis, paths_str),
    )
    conn.commit()


def get_recent_analyses(conn: sqlite3.Connection, limit: int = 20) -> list:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        "SELECT * FROM vision_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


def get_zone_sessions(conn: sqlite3.Connection, zone: str, limit: int = 30) -> list:
    """All single-capture analyses for one zone, oldest first, with image paths parsed.

    Excludes 'progress' rows (those are summaries, not captures). Returns dicts:
    {timestamp, analysis, source, image_paths: [...]}.
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM vision_logs WHERE zone = ? AND source != 'progress' "
        "ORDER BY id ASC LIMIT ?",
        (zone, limit),
    ).fetchall()
    sessions = []
    for r in rows:
        paths = r["image_paths"].split(PATH_SEP) if r["image_paths"] else []
        sessions.append({
            "timestamp": r["timestamp"],
            "analysis": r["analysis"],
            "source": r["source"],
            "image_paths": paths,
        })
    return sessions


PROGRESS_INTRO = """You are reviewing photos of the SAME plant zone ({zone}) captured on
{n} different occasions over time, shown below in chronological order (oldest first)."""

PROGRESS_QUESTION = """Based on the dated photos above, report on how this zone has PROGRESSED over time:

1. Overall trend: improving / stable / declining
2. Specific changes you can see across the dates (new growth, more/less yellowing,
   spread or reduction of spots/pests, wilting trend, etc.)
3. Whether any earlier-flagged issue is getting better or worse
4. What to do next based on the trajectory

Be concise and focus on the CHANGE between dates, not a static description of the latest photo."""


def analyze_progress(zone: str, sessions: list, model: str = VISION_MODEL) -> dict:
    """Send multiple dated capture sessions to Gemini and ask for a trend assessment.

    `sessions` is the output of get_zone_sessions (oldest first). Only sessions
    that still have image files on disk are included.
    """
    client = _make_client()

    parts = [types.Part(text=PROGRESS_INTRO.format(zone=zone, n=len(sessions)))]
    used = 0
    for s in sessions:
        existing = [p for p in s["image_paths"] if Path(p).exists()]
        if not existing:
            continue
        date_label = s["timestamp"][:16].replace("T", " ")
        parts.append(types.Part(text=f"\n--- Photos from {date_label} ---"))
        for p in existing:
            raw = Path(p).read_bytes()
            suffix = Path(p).suffix.lower().lstrip(".")
            mime_type = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
            parts.append(types.Part(inline_data=types.Blob(mime_type=mime_type, data=raw)))
            used += 1

    if used == 0:
        raise RuntimeError(
            "No stored photos found for this zone yet. Capture a few analyses over "
            "different days first, then come back to see the progress comparison."
        )

    parts.append(types.Part(text=PROGRESS_QUESTION))

    response = client.models.generate_content(model=model, contents=parts)

    return {
        "zone": zone,
        "analysis": response.text,
        "images_analyzed": used,
        "timestamp": datetime.now().isoformat(),
    }
