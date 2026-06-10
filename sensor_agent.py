"""Networked sensor agent — reads a soil-moisture sensor and pushes readings
to the watering server's database over HTTP.

This is the "small app" that runs on the sensor node (a Raspberry Pi with the
moisture sensor + ADC, or any networked device). It does ONE job: read the
sensor and POST the value to the central server's /api/reading endpoint. All
storage, dashboards, planning, and watering decisions live in the server — the
agent stays dumb and replaceable.

Run it anywhere on the same network as the server:

    SERVER_URL=http://192.168.68.84:5000 ZONE=tomato python sensor_agent.py

Config via environment:
    SERVER_URL          server base URL (default http://127.0.0.1:5000)
    ZONE                zone this sensor reports for (default zone-1)
    SENSOR_API_TOKEN    must match the server's token if it sets one
    INTERVAL_SECONDS    seconds between readings (default 300)
    SIMULATE            "1" = fake readings (default), "0" = real GPIO/ADC

Hardware reading (SIMULATE=0) is left as a stub — wire your MCP3008/ADC there
when the hardware arrives. Until then SIMULATE=1 proves the whole network path.
"""

import os
import random
import time

import requests

SERVER_URL = os.environ.get("SERVER_URL", "http://127.0.0.1:5000").rstrip("/")
ZONE = os.environ.get("ZONE", "zone-1")
SENSOR_API_TOKEN = os.environ.get("SENSOR_API_TOKEN")
INTERVAL_SECONDS = int(os.environ.get("INTERVAL_SECONDS", "300"))
SIMULATE = os.environ.get("SIMULATE", "1") != "0"


def read_moisture_pct() -> float:
    """Return soil moisture as 0-100%. Replace the SIMULATE=0 branch with a
    real ADC read (e.g. MCP3008 channel → calibrated %) when hardware is wired."""
    if SIMULATE:
        return round(random.uniform(10, 60), 1)
    raise NotImplementedError(
        "Real sensor read not wired yet — read the MCP3008 ADC channel here "
        "and map raw counts to a calibrated 0-100% value."
    )


def push_reading(value: float) -> None:
    payload = {"zone": ZONE, "value": value, "sensor": "moisture", "source": "agent"}
    if SENSOR_API_TOKEN:
        payload["token"] = SENSOR_API_TOKEN
    resp = requests.post(f"{SERVER_URL}/api/reading", json=payload, timeout=10)
    resp.raise_for_status()
    print(f"pushed {value}% for {ZONE} → {resp.json()}")


def main() -> None:
    print(f"sensor_agent: zone={ZONE} server={SERVER_URL} interval={INTERVAL_SECONDS}s "
          f"simulate={SIMULATE}")
    while True:
        try:
            push_reading(read_moisture_pct())
        except Exception as exc:  # keep the loop alive across transient errors
            print(f"reading/push failed: {exc}")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
