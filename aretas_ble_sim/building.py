"""Virtual building: the checked-in JSON world the simulator runs in.

File schema (schemaVersion 1, camelCase like every Aretas wire shape):

{
  "schemaVersion": 1,
  "name": "hotel-small",
  "slabAttenuationDb": 15.0,
  "floors":    [{"index": 0, "z": 0.0, "height": 3.0}],
  "rooms":     [{"id": "f0-r01", "name": "Room 101", "floor": 0,
                 "x0": 0, "y0": 0, "x1": 4, "y1": 5,
                 "door": {"x": 2.0, "y": 5.0}}],
  "walls":     [{"floor": 0, "x1": 0, "y1": 0, "x2": 4, "y2": 0,
                 "attenuationDb": 5.0}],
  "receivers": [{"mac": 90000001, "roomId": "f0-r01", "floor": 0,
                 "x": 2.0, "y": 2.5, "z": 2.4}],
  "nav":       [{"floor": 0, "corridor": {"x0": 0, "y0": 5, "x1": 40, "y1": 7},
                 "stairRoomIds": ["f0-stair"]}],
  "floorplans":[{"floor": 0, "file": "hotel-small.f0.png",
                 "pxPerM": 20, "originPx": [40, 40]}]
}

The same building can be registered in the platform for visual demos: the
floorplan PNG becomes a building-map upload and the receiver (x, y) map to
imgMapX/Y via pxPerM/originPx — the mapping data lives here so that later
tooling never needs a schema change.

Receiver macs are the Aretas integer MACs the MQTT topics are keyed on
(topics are always {prefix}/{integer-receiver-mac}). Coordinates are metres,
world frame, z absolute (floor z + mount height).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from .geometry import point_in_rect, segments_intersect


@dataclass
class Floor:
    index: int
    z: float
    height: float


@dataclass
class Room:
    id: str
    name: str
    floor: int
    x0: float
    y0: float
    x1: float
    y1: float
    door: tuple[float, float] | None = None

    def center(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2.0, (self.y0 + self.y1) / 2.0)

    def contains(self, x: float, y: float) -> bool:
        return point_in_rect(x, y, self.x0, self.y0, self.x1, self.y1)


@dataclass
class Wall:
    floor: int
    x1: float
    y1: float
    x2: float
    y2: float
    attenuation_db: float


@dataclass
class Receiver:
    mac: int
    room_id: str | None
    floor: int
    x: float
    y: float
    z: float

    def pos(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class NavHint:
    floor: int
    corridor: tuple[float, float, float, float]  # x0, y0, x1, y1
    stair_room_ids: list[str] = field(default_factory=list)


class VirtualBuilding:

    def __init__(self, name: str, floors: list[Floor], rooms: list[Room],
                 walls: list[Wall], receivers: list[Receiver],
                 nav: list[NavHint], slab_attenuation_db: float = 15.0,
                 floorplans: list[dict] | None = None):
        self.name = name
        self.floors = sorted(floors, key=lambda f: f.index)
        self.rooms = rooms
        self.walls = walls
        self.receivers = sorted(receivers, key=lambda r: r.mac)
        self.nav = nav
        self.slab_attenuation_db = slab_attenuation_db
        self.floorplans = floorplans or []
        self._rooms_by_id = {r.id: r for r in rooms}
        self._walls_by_floor: dict[int, list[Wall]] = {}
        for w in walls:
            self._walls_by_floor.setdefault(w.floor, []).append(w)
        self._nav_by_floor = {n.floor: n for n in nav}

    # ------------------------------------------------------------------ I/O

    @classmethod
    def load(cls, path: str | Path) -> "VirtualBuilding":
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("schemaVersion") != 1:
            raise ValueError("Unsupported building schemaVersion: %r" % d.get("schemaVersion"))
        floors = [Floor(f["index"], f["z"], f["height"]) for f in d["floors"]]
        rooms = [Room(r["id"], r.get("name", r["id"]), r["floor"],
                      r["x0"], r["y0"], r["x1"], r["y1"],
                      (r["door"]["x"], r["door"]["y"]) if r.get("door") else None)
                 for r in d["rooms"]]
        walls = [Wall(w["floor"], w["x1"], w["y1"], w["x2"], w["y2"], w["attenuationDb"])
                 for w in d["walls"]]
        receivers = [Receiver(int(r["mac"]), r.get("roomId"), r["floor"],
                              r["x"], r["y"], r["z"])
                     for r in d["receivers"]]
        nav = [NavHint(n["floor"],
                       (n["corridor"]["x0"], n["corridor"]["y0"],
                        n["corridor"]["x1"], n["corridor"]["y1"]),
                       n.get("stairRoomIds", []))
               for n in d.get("nav", [])]
        return cls(d.get("name", Path(path).stem), floors, rooms, walls, receivers,
                   nav, d.get("slabAttenuationDb", 15.0), d.get("floorplans"))

    def to_dict(self) -> dict:
        return {
            "schemaVersion": 1,
            "name": self.name,
            "slabAttenuationDb": self.slab_attenuation_db,
            "floors": [{"index": f.index, "z": f.z, "height": f.height} for f in self.floors],
            "rooms": [{"id": r.id, "name": r.name, "floor": r.floor,
                       "x0": r.x0, "y0": r.y0, "x1": r.x1, "y1": r.y1,
                       **({"door": {"x": r.door[0], "y": r.door[1]}} if r.door else {})}
                      for r in self.rooms],
            "walls": [{"floor": w.floor, "x1": w.x1, "y1": w.y1, "x2": w.x2, "y2": w.y2,
                       "attenuationDb": w.attenuation_db} for w in self.walls],
            "receivers": [{"mac": r.mac, "roomId": r.room_id, "floor": r.floor,
                           "x": r.x, "y": r.y, "z": r.z} for r in self.receivers],
            "nav": [{"floor": n.floor,
                     "corridor": {"x0": n.corridor[0], "y0": n.corridor[1],
                                  "x1": n.corridor[2], "y1": n.corridor[3]},
                     "stairRoomIds": n.stair_room_ids} for n in self.nav],
            "floorplans": self.floorplans,
        }

    def save(self, path: str | Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
            f.write("\n")

    # --------------------------------------------------------------- queries

    def room(self, room_id: str) -> Room:
        return self._rooms_by_id[room_id]

    def floor_of_z(self, z: float) -> int:
        """Floor index whose slab-to-slab band contains z (clamped)."""
        best = self.floors[0].index
        for f in self.floors:
            if z >= f.z - 1e-9:
                best = f.index
        return best

    def floor_z(self, index: int) -> float:
        for f in self.floors:
            if f.index == index:
                return f.z
        raise KeyError(index)

    def room_at(self, x: float, y: float, floor: int) -> Room | None:
        for r in self.rooms:
            if r.floor == floor and r.contains(x, y):
                return r
        return None

    def nearest_receiver(self, x: float, y: float, z: float) -> Receiver:
        """Geometric ground truth for the room answer (receiver-Voronoi:
        the methodology's state space — nearest unit ≡ room)."""
        return min(self.receivers,
                   key=lambda r: (r.x - x) ** 2 + (r.y - y) ** 2 + (r.z - z) ** 2)

    # ------------------------------------------------------------ RF support

    def wall_db(self, p1: tuple[float, float], p2: tuple[float, float], floor: int) -> float:
        """Sum of wall attenuations crossed by the 2D ray p1->p2 on a floor."""
        total = 0.0
        for w in self._walls_by_floor.get(floor, []):
            if segments_intersect(p1, p2, (w.x1, w.y1), (w.x2, w.y2)):
                total += w.attenuation_db
        return total

    def attenuation_db(self, a: tuple[float, float, float],
                       b: tuple[float, float, float]) -> float:
        """Structural attenuation between two 3D points: walls along the
        horizontal projection + slabs between floors. Cross-floor wall
        crossings are approximated as the mean of both floors' counts —
        the slab term dominates there anyway (10–20 dB per slab)."""
        fa, fb = self.floor_of_z(a[2]), self.floor_of_z(b[2])
        p1, p2 = (a[0], a[1]), (b[0], b[1])
        if fa == fb:
            return self.wall_db(p1, p2, fa)
        slabs = abs(fa - fb)
        walls = (self.wall_db(p1, p2, fa) + self.wall_db(p1, p2, fb)) / 2.0
        return slabs * self.slab_attenuation_db + walls

    # ------------------------------------------------------------ navigation

    def route(self, a: tuple[float, float, int],
              b: tuple[float, float, int]) -> list[tuple[float, float, int]]:
        """Plausible walking waypoints from a to b (x, y, floor). Uses the
        generator's corridor/stair nav hints; falls back to a straight line
        when a floor has none (hand-authored buildings without hints)."""
        ax, ay, af = a
        bx, by, bf = b
        if af == bf:
            return self._route_floor(ax, ay, bx, by, af)

        stair_a = self._stair_room(af)
        stair_b = self._stair_room(bf)
        if stair_a is None or stair_b is None:
            return [a, b]  # no stair hints — teleport-ish climb

        route = self._route_floor(ax, ay, *stair_a.center(), af)
        # vertical transition happens inside the stairwell footprint
        route.append((*stair_b.center(), bf))
        route += self._route_floor(*stair_b.center(), bx, by, bf)[1:]
        return route

    def _stair_room(self, floor: int) -> Room | None:
        hint = self._nav_by_floor.get(floor)
        if hint is None:
            return None
        for rid in hint.stair_room_ids:
            r = self._rooms_by_id.get(rid)
            if r is not None:
                return r
        return None

    def _route_floor(self, ax: float, ay: float, bx: float, by: float,
                     floor: int) -> list[tuple[float, float, int]]:
        hint = self._nav_by_floor.get(floor)
        if hint is None:
            return [(ax, ay, floor), (bx, by, floor)]

        cx0, cy0, cx1, cy1 = hint.corridor
        cy_mid = (cy0 + cy1) / 2.0

        def in_corridor(x: float, y: float) -> bool:
            return point_in_rect(x, y, cx0, cy0, cx1, cy1)

        def corridor_point(x: float) -> tuple[float, float, int]:
            return (min(max(x, cx0), cx1), cy_mid, floor)

        pts: list[tuple[float, float, int]] = [(ax, ay, floor)]
        room_a = self.room_at(ax, ay, floor)
        room_b = self.room_at(bx, by, floor)

        if room_a is not None and room_a is room_b:
            pts.append((bx, by, floor))
            return pts

        if not in_corridor(ax, ay) and room_a is not None and room_a.door:
            pts.append((*room_a.door, floor))
            pts.append(corridor_point(room_a.door[0]))
        if not in_corridor(bx, by) and room_b is not None and room_b.door:
            pts.append(corridor_point(room_b.door[0]))
            pts.append((*room_b.door, floor))
        pts.append((bx, by, floor))
        return pts
