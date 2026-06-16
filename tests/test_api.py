import pytest
from flask import Flask

import db
import plant_state
from api import api as api_blueprint
from crop_planner import init_planner_db
from zones import init_zones_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Blueprint on a throwaway temp sqlite DB — never touches plant.db OR Supabase.

    Force sqlite even if DATABASE_URL is set in the environment, otherwise
    db.connect() would route the file path to live Postgres.
    """
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)  # auth disabled
    monkeypatch.setattr(db, "USE_PG", False)
    monkeypatch.setattr(db, "DATABASE_URL", None)
    dbfile = str(tmp_path / "t.db")
    monkeypatch.setattr(plant_state, "DB_PATH", dbfile)
    init_planner_db(dbfile).close()
    init_zones_db(dbfile).close()
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
