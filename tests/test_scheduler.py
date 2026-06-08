from datetime import datetime

from scheduler import should_water, is_within_watering_window, is_soil_dry

MORNING = datetime(2026, 6, 7, 9, 0)
NIGHT = datetime(2026, 6, 7, 22, 0)


def test_waters_when_dry_and_in_window():
    decision, reason = should_water(moisture_pct=20, now=MORNING)
    assert decision is True
    assert "dry" in reason


def test_skips_when_soil_already_moist():
    decision, reason = should_water(moisture_pct=50, now=MORNING)
    assert decision is False
    assert "moisture" in reason


def test_skips_outside_watering_window():
    decision, reason = should_water(moisture_pct=20, now=NIGHT)
    assert decision is False
    assert "window" in reason


def test_helpers():
    assert is_within_watering_window(MORNING) is True
    assert is_within_watering_window(NIGHT) is False
    assert is_soil_dry(20) is True
    assert is_soil_dry(50) is False
