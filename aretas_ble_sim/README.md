# aretas_ble_sim — BLE tag / Assist Button simulator

A hardware-free simulator for the Aretas BLE tag, asset-tracking and Assist
Button subsystem. It simulates **one level upstream of the platform** — raw
RSSI sightings as real receivers would publish them — so the genuine ingest,
localization solver, incident pipeline and UI are all exercised end to end.
One codebase, three jobs:

1. **Live demos** — walk simulated people and assets through a virtual
   building and watch them move on the platform's Live Tracking page and
   floor plans, including Assist Button presses arriving as real incidents.
2. **Scored verification** — run a scenario, then ask the platform what it
   saw and score room accuracy, ingest coverage and assist-request
   detection/latency against thresholds (CI-able, non-zero exit on a miss).
3. **Golden traces** — record mode captures byte-deterministic traces the
   platform's unit tests replay, so unit tests and the end-to-end sim can
   never drift apart.

Everything the simulator creates lives under its own site location in your
account; re-running any step is idempotent and never touches other data.

## Setup

From the repository root (the auth helpers read `config.ini` relative to the
working directory):

```bash
python3 -m venv ~/.venvs/aretas-ble-sim
~/.venvs/aretas-ble-sim/bin/pip install -r requirements.txt   # paho-mqtt >= 2.0
```

`config.ini` needs an `[ARETAS]` section with `API_URL`, `API_USERNAME`,
`API_PASSWORD` for the account that will own the simulated building. MQTT
publishing uses the same account's MQTT credentials (the broker's ACL checks
that the account owns each receiver's MAC — which is why provisioning comes
first).

## Quickstart

```bash
# 1. Provision (idempotent — safe to re-run any time)
python -m aretas_ble_sim.provision \
    --scenario aretas_ble_sim/samples/demo-tour.scenario.yaml --config config.ini

# 2. Run live over MQTT
python -m aretas_ble_sim.run_sim \
    --scenario aretas_ble_sim/samples/demo-tour.scenario.yaml --config config.ini \
    --transport mqtt

# 3. Watch: open the platform's Live Tracking page, pick the sim building,
#    open a floor plan from any live tag card. Allow ~60-90 s after start
#    for the first solves.
```

Provisioning creates, in order: the site location (named after the building,
override with `--location-name` / `--location-id`), one device per simulated
receiver, **the building's floor plans as registered building maps with every
receiver placed on them** (this is what makes tags render as positioned chips
with uncertainty circles instead of presence-only markers — `--skip-placement`
opts out), and the scenario's tags — homed at that location (the platform
requires a home location per tag: receivers only accept tags registered to
their own site, so a tag homed elsewhere won't be heard here). Re-running
also assigns the home to any of the scenario's tags registered before the
platform required one. Newly registered tags enter the ingest allowlist
within about a minute.

## Sample scenarios

| Scenario | Purpose |
|---|---|
| `demo-tour` | The visual demo: four personnel badges on distinct looped cross-floor routes, an Assist pendant being worn on rounds, a parked asset cart. 30 min, wall-clock time, no presses — built to be watched live. |
| `assist-drill` | The incident demo and events-pipeline test: a pendant wearer presses the button (including a mid-window double press the tag physically cannot re-emit — proving server dedupe), plus one unregistered badge to exercise the discovered-tags list. 5 min, deterministic seed. Presses create **real incidents** — acknowledge/resolve them from the UI. |
| `walkthrough` | Golden-trace source (pinned epoch, fixed seed): one walker, one asset. Regression material more than demo. |
| `calibration-burnin` | Positional-diversity traffic for exercising receiver self-calibration. |

Run demos at real time. `--speedup N` exists for impatient testing, but the
solver's room declarations are deliberately hysteretic (they lag transits by
a few seconds to avoid flapping), so accelerated time makes tags look like
they teleport.

## Scored verification

```bash
python -m aretas_ble_sim.run_sim \
    --scenario aretas_ble_sim/samples/assist-drill.scenario.yaml --config config.ini \
    --transport mqtt --score report.json
```

Writes a JSON report and exits non-zero on a threshold miss (defaults in
`score.py`: ingest coverage ≥ 0.9, room accuracy ≥ 0.85, assist-request
detection = 1.0, latency p95 ≤ 15 s). Every section feature-detects its
endpoint and reports `"skipped"` where the server doesn't have it yet, so the
same command works against any server generation. Position error is compared
in the registered floor plan's frame — meaningful only after provisioning has
placed the receivers.

## Transports

| `--transport` | What it does |
|---|---|
| `mqtt` (default for live work) | Publishes real per-receiver `blesightings/{mac}` / `bleevents/{mac}` payloads — indistinguishable from firmware. Also consumes per-receiver command topics, so the retransmit-until-acknowledged event loop is exercised for real. |
| `record` | No network: writes `trace.jsonl` + `truth.jsonl` + `manifest.json` (gzip-able golden traces; the manifest carries the per-receiver bias draws so calibration recovery is testable). Deterministic per seed. |
| `rabbitmq` | Bypasses MQTT and publishes the enriched envelope directly (solver-only development). |
| `null` | Engine dry-run, no output. |

Useful flags: `--duration N` (seconds, overrides the scenario), `--seed`,
`--epoch-ms` (pin time for reproducibility; `epochMs: null` in the scenario =
wall clock, right for live demos), `-v`.

## The virtual building

`building_gen.py` generates a hotel-like building (rooms, corridor,
stairwell, walls with per-segment attenuation, one ceiling receiver per room)
plus one floor-plan PNG per floor, and records the pixel↔metre mapping
(`pxPerM`, `originPx`) in the building JSON so the same building can be
registered in the platform for visual demos:

```bash
python -m aretas_ble_sim.building_gen --rooms-per-floor 8 --floors 2 --name my-hotel
```

The RF model is log-distance path loss with per-wall/per-slab attenuation
along the ray, per-channel stationary fading, receiver bias draws, AWGN and a
reception-probability curve — deterministic for a given seed.

## Writing a scenario

YAML, next to its building file (see `scenario.py`'s docstring for the full
schema):

```yaml
name: my-demo
building: hotel-small.building.json
seed: 11
epochMs: null          # wall clock; set a fixed epoch for reproducible traces
durationS: 1800
tags:
  - mac: "CC:11:00:00:00:31"          # sample MACs are deliberately fake
    profile: bc011                     # bc011 | ruuvi_raw2
    tagType: PANIC                     # wire enum: PANIC (= Aretas Assist Button) | PERSONNEL | ASSET
    label: "Pendant — J. Doe"
    kind: personnel                    # personnel | asset | static
    start: f0-r01
    path: [f0-r04, f1-r02, f0-r01]
    speedMps: 1.2
    dwellS: 60
    loop: true
    presses: [{atS: 120, kind: single_click}]   # Assist Button presses
  - mac: "CC:11:00:00:00:32"
    profile: ruuvi_raw2                # seq + battery + barometer profile
    tagType: ASSET
    label: "Cart 9"
    kind: asset
    start: f1-r04
    battery: {startPct: 90, decayPctPerHour: 0.4}
```

`registered: false` marks a tag that should be *dropped* at ingest and appear
in the platform's discovered-tags list instead — useful for testing
onboarding. Note `tagType: PANIC` is the wire's enum value; the product name
for that category is the **Aretas Assist Button**.

## Tests

```bash
python -m pytest aretas_ble_sim/tests -q
```

Pure and offline — wire-shape mirrors, deterministic-trace, receiver
behavior, placement-geometry pins. No credentials needed.

## Troubleshooting

- **Tags never appear** — provisioning registered them less than a minute
  ago (allowlist refresh), or the account's MQTT credentials don't own the
  receiver MACs (provision first), or the scenario's building was generated
  with `--no-png` so nothing could be placed.
- **Tags stuck "near" a receiver without a position** — receivers are
  unplaced on the server (run provisioning without `--skip-placement`); the
  platform then only knows room-level presence.
- **Chips teleport** — you ran `--speedup`; use real time for demos.
- **`paho-mqtt` import errors on Windows** — the requirement is `>= 2.0`;
  older 1.x installs have a different callback API.
