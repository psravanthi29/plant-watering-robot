# Shopping List — Plant Watering Robot v1 (India sourcing)

Single-zone (one plant) build, Raspberry Pi-based, mirrors the architecture in
`scheduler.py` / `plant_state.py`. Prices are indicative (street prices found
via search, June 2026) — always confirm current price/stock on the product page.
Robu.in, Robokits, and Robocraze are well-known Indian hobbyist-electronics
retailers (similar to SparkFun/Adafruit but India-based, with COD + India-wide
shipping).

**v2 — hose/pipe variant:** this list assumes an always-available pressurized
water line (garden hose / household pipe with a tap), so the build uses a
**solenoid valve** to gate flow instead of a pump drawing from a reservoir.
That removes the pump, reservoir, and tank-level concerns entirely — the
trade-off is that a stuck-open valve can flood rather than just run a
reservoir dry, so the control logic now enforces a hard `MAX_WATER_SECONDS`
cutoff per run (see `scheduler.py`).

| # | Item | Exact spec to look for | Where to buy (link) | Approx price |
|---|---|---|---|---|
| 1 | Raspberry Pi (Zero 2 W recommended) | Raspberry Pi Zero 2 W — quad-core 64-bit, WiFi+BT, with GPIO header (or buy header separately) | [Robu.in – Raspberry Pi Zero 2 W with Header](https://robu.in/product/raspberry-pi-zero-2-w-with-header/) · [Robu.in – Pi Zero 2 W](https://robu.in/product/raspberry-pi-zero-2-w/) | ₹1,800–2,500 |
| 2 | MicroSD card | 16GB+ Class 10 / A1 (e.g. SanDisk Ultra) | Amazon.in / local — any reputable brand, search "16GB microSD class 10" | ₹300–500 |
| 3 | Capacitive soil moisture sensor | **Capacitive** v1.2 or v2.0 (NOT resistive — resistive corrodes within weeks); analog output, 5V | [Robokits – Capacitive Soil Moisture Sensor V1.2 (₹83)](https://robokits.co.in/sensors/water-moisture/capacitive-soil-moisture-sensor-v1.2) · [Robu.in – Soil Sensor category](https://robu.in/product-category/sensor-modules/environment-sensor/soil-sensor/) | ₹80–250 |
| 4 | ADC chip/module (for the analog sensor — Pi has no analog pins) | MCP3008 — 8-channel 10-bit ADC, SPI interface, DIP-16 package | [Robu.in – MCP3008 DIP-16 (₹633)](https://robu.in/product/mcp3008-8-channel-10-bit-a-d-converter-with-spi-interface-ic-dip-16-package/) · [DNA Technology – MCP3008](https://www.dnatechindia.com/MCP3008-10-Bit-ADC.html) | ₹250–650 (DNA Tech / IndiaMART breakout boards run cheaper, ~₹250) |
| 5 | Relay module | 1-channel, 5V, opto-isolated, high/low-level trigger (rated well above the valve coil's draw — gives safety headroom) | [Robu.in – 1-Channel 5V Relay w/ Optocoupler](https://robu.in/product/1-channel-5v-10a-relay-control-board-module-optocoupler/) · [Robu.in – 1Ch 5V High/Low Trigger Relay](https://robu.in/product/1-channel-relay-module-5v-high-and-low-level-trigger-relay-module/) | ₹60–150 |
| 6 | Solenoid valve (gates the hose line) | 12V DC, **normally closed (NC)**, ½" BSP threaded inlet/outlet (matches standard garden-hose/tap fittings) | [Robu.in – 12V DC Solenoid Water Valve, ½" NC](https://robu.in/product/dc12v-plastic-electric-12v-water-solenoid-valve-electric-solenoid-valve-magnetic-nc-water-air-inlet-flow-switch-nc-12/) · [Robocraze – 12V Solenoid Valve ½" NC](https://robocraze.com/products/solenoid-valve-12v) | ₹350–750 |
| 7 | Hose/pipe fittings | ½" hose-to-BSP adapter + thread tape, to connect the existing hose/tap to the valve's threaded ports | Local plumbing/hardware shop — describe as "½ inch tap-to-hose adapter" | ₹50–150 |
| 8 | Outlet tubing | Food-grade silicone or reinforced PVC tube, ID ~8–12mm (matched to the valve outlet), ~1m, to carry water from the valve to the plant | [Robu.in – Silicone/PVC tubing search](https://robu.in/?s=silicone+tube) · Local hardware shop | ₹100–200 |
| 9 | Separate 12V power supply for the valve | 12V/1A adapter (don't power the solenoid coil from the Pi's 5V rail — match the valve's rated coil voltage) | Local electronics shop / Amazon.in — generic 12V 1A adapter | ₹150–300 |
| 10 | Breadboard + jumper wires | MB102 830-point breadboard + 140pc jumper wire kit (M-M, M-F, F-F) | [Robu.in – MB102 Breadboard + 140 Jumper Wires Kit](https://robu.in/product/mb102-830-points-solderless-prototype-breadboard-power-supply-module-140-jumper-wires-arduino-diy-starter-kit/) | ₹250–400 |
| 11 | 1N4007 diode (flyback protection across the valve coil) | 1N4007, 1A 1KV standard recovery diode — buy a small pack of 10–30 | [Robu.in – 1N4007 1W Diode (Pack of 30)](https://robu.in/product/1n4007-1w-diode-pack-of-30/) | ₹20–50 |

**Estimated total: ₹3,200–5,800** (Pi is the dominant cost — if you already have one from the Solar project, this drops to roughly ₹1,400–3,300).

## Notes / things that don't change the list
- These retailers (Robu.in, Robokits, Robocraze, DNA Technology) all ship pan-India and accept COD — good for a first-timer ordering hobby electronics.
- If Robu.in is out of stock on any item, Robocraze, Robokits.co.in, FlyRobo, and Amazon.in are reliable fallbacks carrying near-identical parts — search using the **"exact spec to look for"** column, not the brand name, since many of these are generic modules sold by multiple sellers.
- **Buy the moisture sensor as capacitive, not resistive** — this is the one spec where getting it wrong will cost you a re-order in a few weeks (resistive sensors corrode and give bad readings).
- **Buy the solenoid valve as normally-closed (NC), 12V DC, threaded ½" BSP** — NC means it stays shut on power loss (fails safe, no flooding if the Pi crashes); ½" BSP threading matches standard Indian tap/hose fittings so you won't need odd adapters.
- **Match the relay's switching rating to the valve coil**, not to mains — the valve coil draws well under 1A at 12V, so even the cheapest opto-isolated 5V relay module has plenty of headroom; what matters is that its *trigger side* runs off the Pi's 5V/3.3V logic.
