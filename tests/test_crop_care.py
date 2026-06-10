from datetime import date, timedelta

from crop_care import CLIMBERS, care_schedule, sowing_params, split_past_upcoming
from crop_planner import (
    SEED_LIBRARY,
    compute_crop_plan,
    crop_from_library,
    get_task,
    init_planner_db,
    list_tasks,
    mark_task_done,
    mark_task_pending,
    sync_tasks,
)

SOWN = date(2026, 6, 10)


def _crop(key):
    c = crop_from_library(key)
    c["key"] = key
    return c


# --- care schedule generation ------------------------------------------------

def test_every_crop_gets_a_nonempty_schedule_starting_with_sowing():
    for key in SEED_LIBRARY:
        events = care_schedule(_crop(key), SOWN)
        assert events, f"{key}: empty schedule"
        assert events[0]["date"] == SOWN, f"{key}: first event must be sowing day"
        titles = " ".join(e["title"] for e in events)
        assert "harvest" in titles.lower(), f"{key}: no harvest event"


def test_transplant_event_only_for_transplanted_crops():
    tomato_titles = [e["title"] for e in care_schedule(_crop("tomato"), SOWN)]
    radish_titles = [e["title"] for e in care_schedule(_crop("radish"), SOWN)]
    assert any("Transplant" in t for t in tomato_titles)
    assert not any("Transplant" in t for t in radish_titles)


def test_climbers_get_trellis_event():
    gourd_titles = [e["title"] for e in care_schedule(_crop("bottle_gourd"), SOWN)]
    spinach_titles = [e["title"] for e in care_schedule(_crop("spinach"), SOWN)]
    assert any("trellis" in t.lower() for t in gourd_titles)
    assert not any("trellis" in t.lower() for t in spinach_titles)


def test_first_harvest_lands_on_days_to_maturity():
    crop = _crop("okra")
    events = care_schedule(crop, SOWN)
    harvest = next(e for e in events if "First harvest" in e["title"])
    assert harvest["date"] == SOWN + timedelta(days=crop["days_to_maturity"])


def test_split_past_upcoming():
    events = care_schedule(_crop("spinach"), SOWN)
    today = SOWN + timedelta(days=10)
    past, upcoming = split_past_upcoming(events, today)
    assert all(e["date"] < today for e in past)
    assert all(e["date"] >= today for e in upcoming)
    assert len(past) + len(upcoming) == len(events)


# --- pre-sowing parameters ----------------------------------------------------

def test_sowing_params_for_every_crop():
    for key in SEED_LIBRARY:
        p = sowing_params(_crop(key))
        assert p["method"] and p["depth"] and p["spacing"], f"{key}: incomplete params"


def test_sowing_params_method_classification():
    assert "transplant" in sowing_params(_crop("tomato"))["method"]      # tray-raised
    assert "hates transplanting" in sowing_params(_crop("carrot"))["method"]
    assert "plant once" in sowing_params(_crop("mango"))["method"]       # perennial
    assert sowing_params(_crop("spinach"))["method"] == "direct sow"


def test_sowing_params_depth_by_seed_size():
    assert sowing_params(_crop("potato"))["depth"] == "8–10 cm"          # tuber
    assert sowing_params(_crop("bottle_gourd"))["depth"] == "2–3 cm"     # large seed
    assert sowing_params(_crop("spinach"))["depth"] == "0.5–1 cm"        # leafy


# --- sowing task lifecycle ----------------------------------------------------

def _setup_conn_with_crop(key="spinach"):
    conn = init_planner_db(":memory:")
    crop = _crop(key)
    from crop_planner import add_crop, list_crops
    add_crop(conn, crop)
    stored = list_crops(conn)[0]
    plan = compute_crop_plan(stored, 10)
    return conn, stored, plan


def test_sync_tasks_creates_pending_tasks_idempotently():
    conn, crop, plan = _setup_conn_with_crop()
    sync_tasks(conn, [(crop, plan)], SOWN, within_days=60)
    first_count = len(list_tasks(conn))
    assert first_count >= 1
    sync_tasks(conn, [(crop, plan)], SOWN, within_days=60)  # re-run: no dupes
    assert len(list_tasks(conn)) == first_count
    assert all(t["status"] == "pending" for t in list_tasks(conn))
    conn.close()


def test_mark_done_and_undo():
    conn, crop, plan = _setup_conn_with_crop()
    sync_tasks(conn, [(crop, plan)], SOWN, within_days=60)
    task = list_tasks(conn)[0]

    mark_task_done(conn, task["id"], done_on=SOWN)
    assert get_task(conn, task["id"])["status"] == "done"
    assert get_task(conn, task["id"])["done_on"] == SOWN.isoformat()

    mark_task_pending(conn, task["id"])
    assert get_task(conn, task["id"])["status"] == "pending"
    assert get_task(conn, task["id"])["done_on"] is None
    conn.close()


def test_removing_crop_clears_pending_but_keeps_done_tasks():
    conn, crop, plan = _setup_conn_with_crop()
    sync_tasks(conn, [(crop, plan)], SOWN, within_days=60)
    tasks = list_tasks(conn)
    mark_task_done(conn, tasks[0]["id"], done_on=SOWN)

    from crop_planner import remove_crop
    remove_crop(conn, crop["id"])
    sync_tasks(conn, [], SOWN, within_days=60)

    remaining = list_tasks(conn)
    assert len(remaining) == 1  # the done one survives as history
    assert remaining[0]["status"] == "done"
    conn.close()
