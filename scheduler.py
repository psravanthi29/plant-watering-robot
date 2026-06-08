"""Watering-condition gating logic (SIMULATE-aware, mirrors Solar's should_deploy)."""

from datetime import time

# Defaults for the single starting plant/zone.
MOISTURE_THRESHOLD = 30          # below this percentage, soil is considered dry
WATER_WINDOW_START = time(7, 0)  # don't water before 7:00
WATER_WINDOW_END = time(19, 0)   # don't water after 19:00
MAX_WATER_SECONDS = 15           # safety cutoff — longest a single watering is allowed to run


def is_within_watering_window(now, start=WATER_WINDOW_START, end=WATER_WINDOW_END):
    current = now.time()
    return start <= current <= end


def is_soil_dry(moisture_pct, threshold=MOISTURE_THRESHOLD):
    return moisture_pct < threshold


def should_water(moisture_pct, now):
    """Decide whether to water, and why. Returns (decision: bool, reason: str)."""
    if not is_within_watering_window(now):
        return False, "outside watering window"
    if not is_soil_dry(moisture_pct):
        return False, "soil moisture sufficient"
    return True, "soil dry and in window"
