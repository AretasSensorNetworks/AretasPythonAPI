"""Pin the floor-plan placement geometry — the contract three parties share:
the plan renderer records the px<->m mapping, provision.py places receivers
through it, and the scorer converts world truth into the registered map's
frame (image px / pxPerM, y down) before measuring position error. If any
of the three drifts, positions land in the wrong rooms on the platform's
floor-plan views.
"""

from __future__ import annotations

from aretas_ble_sim.building_gen import generate, render_floorplans
from aretas_ble_sim.provision import plan_px

# the checked-in sample building's recorded mapping (20 px/m, 40 px margin
# over a 19 x 12.4 m footprint)
FP = {"floor": 0, "file": "x.png", "pxPerM": 20, "originPx": [40, 288]}


def test_plan_px_matches_the_sample_mapping():
    # receiver 90000001 sits at (5.0, 2.5) m -> (140, 238) px on the plan
    assert plan_px(FP, 5.0, 2.5) == (140, 238)
    # world +y points up, image +y points down
    assert plan_px(FP, 5.0, 9.9)[1] < plan_px(FP, 5.0, 2.5)[1]


def test_plan_px_never_emits_the_never_placed_sentinel():
    # (0, 0) px means "never placed" to the platform — clamp, don't collide
    fp = {"floor": 0, "file": "x.png", "pxPerM": 20, "originPx": [0, 0]}
    assert plan_px(fp, 0.0, 0.0) == (1, 1)


def test_map_frame_round_trip():
    # a receiver placed via plan_px and read back through the registered
    # map's frame (img_px / pxPerM, zero offsets) must land within one
    # pixel's worth of metres of the scorer's truth conversion
    b = generate(rooms_per_floor=4, floors=1)
    for rx in b.receivers:
        img_x, img_y = plan_px(FP, rx.x, rx.y)
        map_x, map_y = img_x / FP["pxPerM"], img_y / FP["pxPerM"]
        # the scorer-side conversion (score.py _truth_to_map_frame)
        want_x = (FP["originPx"][0] + rx.x * FP["pxPerM"]) / FP["pxPerM"]
        want_y = (FP["originPx"][1] - rx.y * FP["pxPerM"]) / FP["pxPerM"]
        tol = 1.0 / FP["pxPerM"]
        assert abs(map_x - want_x) <= tol
        assert abs(map_y - want_y) <= tol


def test_renderer_mapping_agrees_with_plan_px(tmp_path):
    # the renderer's recorded originPx/pxPerM must put a receiver at the
    # same pixel plan_px computes — the two implementations of the mapping
    b = generate(rooms_per_floor=4, floors=1)
    plans = render_floorplans(b, tmp_path)
    fp = plans[0]
    rx = b.receivers[0]
    img_x, img_y = plan_px(fp, rx.x, rx.y)
    # the renderer draws at origin + int(x*pxPerM) (truncation, not round)
    assert abs(img_x - (fp["originPx"][0] + int(rx.x * fp["pxPerM"]))) <= 1
    assert abs(img_y - (fp["originPx"][1] - int(rx.y * fp["pxPerM"]))) <= 1
