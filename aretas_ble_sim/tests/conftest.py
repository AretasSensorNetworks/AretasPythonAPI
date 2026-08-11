"""Shared fixtures: a small generated building + a two-tag scenario."""

import pytest

from aretas_ble_sim.building_gen import generate


@pytest.fixture(scope="session")
def building():
    return generate(rooms_per_floor=6, floors=2, name="test-hotel")


SCENARIO_YAML = """
name: test-run
building: {building}
seed: 7
epochMs: 1770000000000
durationS: 40
ownerClientId: test-client
tags:
  - mac: "CC:11:00:00:00:01"
    profile: bc011
    tagType: PANIC
    label: "Pendant"
    kind: personnel
    start: f0-r01
    path: [f0-r04]
    speedMps: 1.2
    dwellS: 10
    presses: [{{atS: 5, kind: single_click}}, {{atS: 8, kind: single_click}},
              {{atS: 25, kind: double_click}}]
  - mac: "CC:11:00:00:00:02"
    profile: ruuvi_raw2
    tagType: ASSET
    label: "Cart"
    kind: asset
    start: f1-r02
    battery: {{startPct: 90, decayPctPerHour: 2}}
    vanish: [{{atS: 30, forS: 5}}]
  - mac: "AA:BB:CC:00:00:01"
    profile: bc011
    tagType: PERSONNEL
    label: "Unregistered badge"
    start: f0-r02
    registered: false
"""


@pytest.fixture()
def scenario(tmp_path, building):
    bpath = tmp_path / "test.building.json"
    building.save(bpath)
    spath = tmp_path / "test.scenario.yaml"
    spath.write_text(SCENARIO_YAML.format(building=bpath.name), encoding="utf-8")

    from aretas_ble_sim.scenario import load_scenario
    return load_scenario(spath)
