import pytest
from flask import Flask

import db
import plant_state
from api import api as api_blueprint
from crop_planner import init_planner_db
from plant_state import init_db
from zones import init_zones_db
from garden_layout import init_layout_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Blueprint on a throwaway temp sqlite DB — never touches plant.db OR Supabase.

    Force sqlite even if DATABASE_URL is set in the environment, otherwise
    db.connect() would route the file path to live Postgres.
    """
    # Disable auth: clear every env var auth_enabled() looks at (a local .env may
    # set any of them; SUPABASE_PROJECT_URL alone is enough to switch auth on).
    for var in ("SUPABASE_JWT_SECRET", "SUPABASE_PROJECT_URL", "SUPABASE_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(db, "USE_PG", False)
    monkeypatch.setattr(db, "DATABASE_URL", None)
    dbfile = str(tmp_path / "t.db")
    monkeypatch.setattr(plant_state, "DB_PATH", dbfile)
    init_db(dbfile).close()          # runs + sensor_readings tables
    init_planner_db(dbfile).close()
    init_zones_db(dbfile).close()
    init_layout_db(dbfile).close()
    app = Flask(__name__)
    app.register_blueprint(api_blueprint)
    return app.test_client()


def test_zone_crud(client):
    r = client.post("/api/zones", json={"name": "Bed A", "area_m2": 100.0, "sun": "full",
                                        "sensor_key": "zone-1"})
    assert r.status_code == 201
    zid = r.get_json()["id"]

    zones = client.get("/api/zones").get_json()
    assert any(z["name"] == "Bed A" for z in zones)

    client.patch(f"/api/zones/{zid}", json={"moisture_target": 55.0})
    assert client.get(f"/api/zones/{zid}").get_json()["moisture_target"] == 55.0

    assert client.delete(f"/api/zones/{zid}").status_code == 200
    assert client.get(f"/api/zones/{zid}").status_code == 404


def test_zone_requires_name(client):
    assert client.post("/api/zones", json={"area_m2": 5}).status_code == 400


def test_add_and_list_crops(client):
    assert client.post("/api/crops", json={"library_key": "tomato"}).status_code == 201
    crops = client.get("/api/crops").get_json()
    assert len(crops) == 1
    assert crops[0]["water_need"] == "high"
    assert crops[0]["plan"]["plants_needed"] >= 1


def test_add_crop_rejects_unknown_key(client):
    assert client.post("/api/crops", json={"library_key": "dragonfruit"}).status_code == 400


def test_placement_and_apply(client):
    client.post("/api/zones", json={"name": "Bed A", "area_m2": 1000.0, "sun": "full",
                                    "sensor_key": "zone-1"})
    client.post("/api/crops", json={"library_key": "tomato"})  # high water

    placement = client.get("/api/placement").get_json()
    assert placement["assignments"], "tomato should be placeable in a big full-sun bed"
    assert not placement["unplaced"]

    applied = client.post("/api/placement/apply").get_json()
    assert applied["assignments"]

    # the zone now has the crop and a derived moisture target (high -> 60)
    zones = client.get("/api/zones").get_json()
    bed = next(z for z in zones if z["name"] == "Bed A")
    assert "Tomato" in bed["crops"]
    assert bed["moisture_target"] == 60.0


def test_manual_zone_assignment(client):
    r = client.post("/api/zones", json={"name": "Bed A", "area_m2": 50.0, "sun": "full"})
    zid = r.get_json()["id"]
    client.post("/api/crops", json={"library_key": "spinach"})
    crop_id = client.get("/api/crops").get_json()[0]["id"]

    assert client.post(f"/api/crops/{crop_id}/zone", json={"zone_id": zid}).status_code == 200
    bed = client.get(f"/api/zones/{zid}").get_json()
    assert any(c["display"].startswith("Spinach") for c in bed["crops"])


def test_watering_check_logs_a_run(client):
    r = client.post("/api/check", json={"zone": "zone-1"})
    assert r.status_code == 200
    assert r.get_json()["zone"] == "zone-1"
    assert r.get_json()["state"]  # some terminal state string

    runs = client.get("/api/runs").get_json()
    assert len(runs) >= 1
    assert runs[0]["zone"] == "zone-1"


def test_readings_feed_returns_list(client):
    # Empty to start; a logged reading then shows up (incl. unconfigured zones).
    assert client.get("/api/readings").get_json() == []
    conn = db.connect(plant_state.DB_PATH)
    plant_state.log_reading(conn, "wild-zone", 42.0)
    conn.close()
    feed = client.get("/api/readings").get_json()
    assert any(row["zone"] == "wild-zone" and row["value"] == 42.0 for row in feed)


def test_planner_settings_roundtrip(client):
    before = client.get("/api/planner/settings").get_json()
    assert "household_size" in before and "plan_start_date" in before

    assert client.post("/api/planner/settings",
                       json={"household_size": 12}).status_code == 200
    assert client.get("/api/planner/settings").get_json()["household_size"] == 12


def test_set_crop_demand_override(client):
    client.post("/api/crops", json={"library_key": "tomato"})
    crop_id = client.get("/api/crops").get_json()[0]["id"]

    assert client.post(f"/api/crops/{crop_id}/demand",
                       json={"weekly_demand_kg": 3.5}).status_code == 200
    crop = client.get("/api/crops").get_json()[0]
    assert crop["demand_auto"] is False

    # Blank reverts to auto.
    client.post(f"/api/crops/{crop_id}/demand", json={"weekly_demand_kg": None})
    assert client.get("/api/crops").get_json()[0]["demand_auto"] is True


def test_tasks_materialize_and_care_plan(client):
    client.post("/api/crops", json={"library_key": "tomato"})
    tasks = client.get("/api/tasks").get_json()
    assert tasks, "adding a crop + listing tasks should materialize sow tasks"

    care = client.get(f"/api/care/{tasks[0]['id']}").get_json()
    assert care["task"]["display"]
    # A care schedule always has a day-0 'Sown' event among past/upcoming.
    titles = [e["title"] for e in care["past"] + care["upcoming"]]
    assert any("Sown" in t for t in titles)


def test_care_404_for_unknown_task(client):
    assert client.get("/api/care/99999").status_code == 404


def test_feature_crud_and_area(client):
    # A 120x60 cm raised bed → 0.72 m².
    r = client.post("/api/features", json={
        "name": "Bed A", "template": "raised_bed", "kind": "bed", "shape": "rect",
        "width_cm": 120, "length_cm": 60, "x_cm": 10, "y_cm": 20, "sun": "full",
    })
    assert r.status_code == 201
    fid = r.get_json()["id"]

    feats = client.get("/api/features").get_json()
    bed = next(f for f in feats if f["id"] == fid)
    assert bed["area_m2"] == 0.72

    # Move + resize via PATCH.
    client.patch(f"/api/features/{fid}", json={"x_cm": 99, "width_cm": 100})
    bed = next(f for f in client.get("/api/features").get_json() if f["id"] == fid)
    assert bed["x_cm"] == 99 and bed["area_m2"] == 0.6

    assert client.delete(f"/api/features/{fid}").status_code == 200
    assert all(f["id"] != fid for f in client.get("/api/features").get_json())


def test_feature_rejects_bad_shape(client):
    assert client.post("/api/features", json={"shape": "blob"}).status_code == 400


def test_circle_feature_area(client):
    # Ø30 cm pot → π*0.15² ≈ 0.071 m².
    client.post("/api/features", json={
        "name": "Pot", "kind": "container", "shape": "circle",
        "width_cm": 30, "length_cm": 30,
    })
    pot = client.get("/api/features").get_json()[-1]
    assert pot["area_m2"] == 0.071


def test_deleting_zone_detaches_its_features(client):
    zid = client.post("/api/zones", json={"name": "Bed Zone"}).get_json()["id"]
    fid = client.post("/api/features", json={
        "name": "Bed A", "shape": "rect", "width_cm": 100, "length_cm": 100,
        "zone_id": zid,
    }).get_json()["id"]

    client.delete(f"/api/zones/{zid}")
    bed = next(f for f in client.get("/api/features").get_json() if f["id"] == fid)
    assert bed["zone_id"] is None  # feature survives, just unzoned
