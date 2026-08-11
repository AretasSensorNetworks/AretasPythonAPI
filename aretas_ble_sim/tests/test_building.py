"""Building geometry, generator layout, RF attenuation, navigation."""

import json

from aretas_ble_sim.building import VirtualBuilding
from aretas_ble_sim.geometry import segments_intersect


def test_segment_intersection_basics():
    assert segments_intersect((0, 0), (2, 2), (0, 2), (2, 0))
    assert not segments_intersect((0, 0), (1, 0), (0, 1), (1, 1))
    # touching an endpoint counts (grazing a wall end)
    assert segments_intersect((0, 0), (2, 0), (1, 0), (1, 1))


def test_generator_layout(building):
    # 6 rooms + stairwell per floor, 2 floors
    assert len(building.rooms) == 14
    # one receiver per room + one corridor unit per floor
    assert len(building.receivers) == 16
    macs = [r.mac for r in building.receivers]
    assert len(set(macs)) == len(macs)
    for rx in building.receivers:
        if rx.room_id:
            assert building.room(rx.room_id).contains(rx.x, rx.y)


def test_round_trip_json(building, tmp_path):
    p = tmp_path / "b.json"
    building.save(p)
    again = VirtualBuilding.load(p)
    assert json.dumps(again.to_dict(), sort_keys=True) == \
           json.dumps(building.to_dict(), sort_keys=True)


def test_room_lookup_and_nearest(building):
    room = building.room("f0-r01")
    cx, cy = room.center()
    assert building.room_at(cx, cy, 0) is room
    nearest = building.nearest_receiver(cx, cy, 1.2)
    assert nearest.room_id == "f0-r01"


def test_wall_attenuation_shapes_rf(building):
    r1 = building.room("f0-r01")
    r2 = building.room("f0-r02")
    a = (*r1.center(), 1.2)
    b = (*r2.center(), 1.2)
    same_room = building.attenuation_db(a, (a[0] + 0.5, a[1], 1.2))
    adjacent = building.attenuation_db(a, b)
    assert same_room == 0.0
    assert adjacent >= 5.0  # at least one partition crossed


def test_slab_attenuation(building):
    a = (*building.room("f0-r01").center(), 1.2)
    b = (*building.room("f1-r01").center(), 4.2)
    assert building.attenuation_db(a, b) >= building.slab_attenuation_db


def test_route_uses_corridor(building):
    r1 = building.room("f0-r01")
    r4 = building.room("f0-r04")
    route = building.route((*r1.center(), 0), (*r4.center(), 0))
    assert len(route) > 2  # not a straight wall-piercing line
    cx0, cy0, cx1, cy1 = building._nav_by_floor[0].corridor
    assert any(cx0 <= x <= cx1 and cy0 <= y <= cy1 for x, y, _ in route)


def test_route_cross_floor_via_stairs(building):
    r1 = building.room("f0-r01")
    r2 = building.room("f1-r02")
    route = building.route((*r1.center(), 0), (*r2.center(), 1))
    floors = [f for _, _, f in route]
    assert 0 in floors and 1 in floors
    stair = building.room("f0-stair")
    assert any(stair.contains(x, y) for x, y, f in route if f == 0)
