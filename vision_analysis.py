"""Plant health analysis via Claude Vision API.

Two usage modes:
- Manual: user uploads photos via the Flask /analyze endpoint for prompt refinement.
- Automated: Pi Camera captures on a schedule; same function, same API call.

Results are logged to the vision_logs table in plant.db (created on first use).
"""

import base64
import sqlite3
from datetime import datetime
from pathlib import Path

import anthropic

from plant_state import DB_PATH

VISION_MODEL = "claude-opus-4-8"

# Swap for claude-haiku-4-5 if running frequent automated checks (5x cheaper).
# Opus gives better diagnosis for manual deep-dive sessions.

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


def analyze_images(
    image_paths: list,
    zone: str = "zone-1",
    plant_types: str = "unknown",
    moisture_pct: float | None = None,
    model: str = VISION_MODEL,
) -> dict:
    """Send local images to Claude Vision API for plant health analysis.

    Args:
        image_paths: Paths to local JPEG/PNG files (1-4 recommended).
        zone: Zone identifier passed as context to the model.
        plant_types: Comma-separated plant names, e.g. "tomato, basil".
        moisture_pct: Latest sensor reading, included as context if available.
        model: Claude model ID. Default is Opus for best vision accuracy.

    Returns:
        dict with keys: zone, analysis (text), images_analyzed, timestamp.
    """
    client = anthropic.Anthropic()

    content = []
    for path in image_paths:
        raw = Path(path).read_bytes()
        encoded = base64.standard_b64encode(raw).decode("utf-8")
        suffix = Path(path).suffix.lower().lstrip(".")
        media_type = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": encoded},
        })

    content.append({
        "type": "text",
        "text": ANALYSIS_PROMPT.format(
            count=len(image_paths),
            zone=zone,
            plant_types=plant_types,
            moisture_pct=f"{moisture_pct:.1f}" if moisture_pct is not None else "N/A",
        ),
    })

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
    )

    return {
        "zone": zone,
        "analysis": response.content[0].text,
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
            analysis    TEXT
        )
        """
    )
    conn.commit()
    return conn


def log_analysis(conn: sqlite3.Connection, zone: str, image_count: int,
                 analysis: str, source: str = "manual") -> None:
    """Persist a vision analysis result. source is 'manual' or 'pi_camera'."""
    conn.execute(
        "INSERT INTO vision_logs (timestamp, zone, image_count, source, analysis) "
        "VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), zone, image_count, source, analysis),
    )
    conn.commit()


def get_recent_analyses(conn: sqlite3.Connection, limit: int = 20) -> list:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        "SELECT * FROM vision_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
