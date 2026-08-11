"""Virtual-building generator: hotel-like corridor + N rooms x M floors.

Emits the building JSON (building.py schema) plus one floor-plan PNG per
floor so the SAME building can later be registered in the platform
(BUILDING_MAP upload + device placements) for visual demos. The PNG <-> world
mapping is recorded in the JSON's floorplans[] entries:

    imgX = originPx[0] + x * pxPerM
    imgY = originPx[1] - y * pxPerM      (world +y points up on the plan)

Layout per floor (west stairwell, central corridor, two room rows):

    +--------+----------------------------------+
    |        |  r05  |  r06  |  r07  |  r08     |   north row
    | stair  +--d--------d-------d-------d------+
    |        |            corridor              |
    |        +--d--------d-------d-------d------+
    |        |  r01  |  r02  |  r03  |  r04     |   south row
    +--------+----------------------------------+

One receiver per room (incl. stairwell) at ceiling mount height + one
mid-corridor receiver per floor — the "sensor in every room" density the
product targets. Deterministic: same args -> byte-identical JSON.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from .building import Floor, NavHint, Receiver, Room, VirtualBuilding, Wall

DOOR_W = 0.9


def _wall_with_gaps(floor: int, y: float, x0: float, x1: float,
                    gap_centers: list[float], db: float) -> list[Wall]:
    """One horizontal wall run split around door openings."""
    walls = []
    cursor = x0
    for gc in sorted(gap_centers):
        g0, g1 = gc - DOOR_W / 2, gc + DOOR_W / 2
        if g0 > cursor:
            walls.append(Wall(floor, cursor, y, g0, y, db))
        cursor = max(cursor, g1)
    if cursor < x1:
        walls.append(Wall(floor, cursor, y, x1, y, db))
    return walls


def generate(rooms_per_floor: int = 8, floors: int = 2, room_w: float = 4.0,
             room_d: float = 5.0, corridor_w: float = 2.4, stair_w: float = 3.0,
             floor_height: float = 3.0, mount_height: float = 2.4,
             wall_db: float = 5.0, ext_wall_db: float = 12.0, slab_db: float = 15.0,
             mac_base: int = 90000000, name: str = "hotel-small") -> VirtualBuilding:

    ncols = math.ceil(rooms_per_floor / 2)
    width = stair_w + ncols * room_w
    cy0, cy1 = room_d, room_d + corridor_w      # corridor y band
    depth = 2 * room_d + corridor_w

    floor_list = [Floor(k, k * floor_height, floor_height) for k in range(floors)]
    rooms: list[Room] = []
    walls: list[Wall] = []
    receivers: list[Receiver] = []
    nav: list[NavHint] = []
    mac = mac_base

    for k in range(floors):
        fz = k * floor_height
        rx_z = fz + mount_height

        # stairwell spans the full depth at the west end, door onto the corridor
        stair = Room(f"f{k}-stair", f"Stairwell F{k + 1}", k, 0, 0, stair_w, depth,
                     door=(stair_w, (cy0 + cy1) / 2))
        rooms.append(stair)

        room_ids = []
        for i in range(rooms_per_floor):
            south = i < ncols
            col = i if south else i - ncols
            x0 = stair_w + col * room_w
            num = i + 1
            rid = f"f{k}-r{num:02d}"
            if south:
                r = Room(rid, f"Room {k + 1}{num:02d}", k, x0, 0, x0 + room_w, cy0,
                         door=(x0 + room_w / 2, cy0))
            else:
                r = Room(rid, f"Room {k + 1}{num:02d}", k, x0, cy1, x0 + room_w, depth,
                         door=(x0 + room_w / 2, cy1))
            rooms.append(r)
            room_ids.append(rid)

        south_rooms = [r for r in rooms if r.floor == k and r.id in room_ids and r.y0 == 0]
        north_rooms = [r for r in rooms if r.floor == k and r.id in room_ids and r.y1 == depth]

        # exterior shell
        walls += [Wall(k, 0, 0, width, 0, ext_wall_db),
                  Wall(k, 0, depth, width, depth, ext_wall_db),
                  Wall(k, 0, 0, 0, depth, ext_wall_db),
                  Wall(k, width, 0, width, depth, ext_wall_db)]

        # stairwell east wall with its corridor door
        sd = stair.door
        walls.append(Wall(k, stair_w, 0, stair_w, sd[1] - DOOR_W / 2, wall_db))
        walls.append(Wall(k, stair_w, sd[1] + DOOR_W / 2, stair_w, depth, wall_db))

        # corridor walls with a door gap per room
        walls += _wall_with_gaps(k, cy0, stair_w, width,
                                 [r.door[0] for r in south_rooms], wall_db)
        walls += _wall_with_gaps(k, cy1, stair_w, width,
                                 [r.door[0] for r in north_rooms], wall_db)

        # partitions between rooms in each row
        for col in range(1, ncols):
            x = stair_w + col * room_w
            walls.append(Wall(k, x, 0, x, cy0, wall_db))
            if any(r.x0 == x or r.x1 == x for r in north_rooms):
                walls.append(Wall(k, x, cy1, x, depth, wall_db))
        # east cap of a short north row (odd room counts)
        if north_rooms and north_rooms[-1].x1 < width:
            x = north_rooms[-1].x1
            walls.append(Wall(k, x, cy1, x, depth, wall_db))

        # one receiver per room, then a mid-corridor unit
        for r in [stair] + south_rooms + north_rooms:
            cx, cy = r.center()
            receivers.append(Receiver(mac, r.id, k, cx, cy, rx_z))
            mac += 1
        receivers.append(Receiver(mac, None, k, (stair_w + width) / 2, (cy0 + cy1) / 2, rx_z))
        mac += 1

        nav.append(NavHint(k, (stair_w, cy0, width, cy1), [f"f{k}-stair"]))

    return VirtualBuilding(name, floor_list, rooms, walls, receivers, nav, slab_db)


# ---------------------------------------------------------------- floor plans

def render_floorplans(b: VirtualBuilding, out_dir: Path, px_per_m: int = 20,
                      margin_px: int = 40) -> list[dict]:
    """One PNG per floor (Pillow — already an API-wrapper dependency)."""
    from PIL import Image, ImageDraw

    max_x = max(r.x1 for r in b.rooms)
    max_y = max(r.y1 for r in b.rooms)
    origin = (margin_px, margin_px + int(max_y * px_per_m))

    def px(x: float, y: float) -> tuple[int, int]:
        return (origin[0] + int(x * px_per_m), origin[1] - int(y * px_per_m))

    plans = []
    for f in b.floors:
        img = Image.new("RGB", (2 * margin_px + int(max_x * px_per_m),
                                2 * margin_px + int(max_y * px_per_m)), "white")
        d = ImageDraw.Draw(img)

        for r in b.rooms:
            if r.floor != f.index:
                continue
            d.rectangle([px(r.x0, r.y1), px(r.x1, r.y0)], fill="#f4f6f8")
            cx, cy = r.center()
            d.text((px(cx, cy)[0], px(cx, cy)[1] + 8), r.name,
                   fill="#8a94a0", anchor="mm")

        for w in b.walls:
            if w.floor != f.index:
                continue
            d.line([px(w.x1, w.y1), px(w.x2, w.y2)],
                   fill="black", width=3 if w.attenuation_db >= 10 else 2)

        for rx in b.receivers:
            if rx.floor != f.index:
                continue
            cx, cy = px(rx.x, rx.y)
            d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill="#d81b30")
            d.text((cx, cy - 12), str(rx.mac), fill="#d81b30", anchor="mm")

        fname = f"{b.name}.f{f.index}.png"
        img.save(out_dir / fname)
        plans.append({"floor": f.index, "file": fname, "pxPerM": px_per_m,
                      "originPx": [origin[0], origin[1]]})
    return plans


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description="Generate a hotel-like virtual building")
    ap.add_argument("--rooms-per-floor", type=int, default=8)
    ap.add_argument("--floors", type=int, default=2)
    ap.add_argument("--room-w", type=float, default=4.0)
    ap.add_argument("--room-d", type=float, default=5.0)
    ap.add_argument("--corridor-w", type=float, default=2.4)
    ap.add_argument("--wall-db", type=float, default=5.0)
    ap.add_argument("--ext-wall-db", type=float, default=12.0)
    ap.add_argument("--slab-db", type=float, default=15.0)
    ap.add_argument("--mount-height", type=float, default=2.4)
    ap.add_argument("--mac-base", type=int, default=90000000,
                    help="first receiver integer MAC (match registered demo devices later)")
    ap.add_argument("--name", default="hotel-small")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    b = generate(rooms_per_floor=args.rooms_per_floor, floors=args.floors,
                 room_w=args.room_w, room_d=args.room_d, corridor_w=args.corridor_w,
                 mount_height=args.mount_height, wall_db=args.wall_db,
                 ext_wall_db=args.ext_wall_db, slab_db=args.slab_db,
                 mac_base=args.mac_base, name=args.name)
    if not args.no_png:
        b.floorplans = render_floorplans(b, out_dir)

    path = out_dir / f"{args.name}.building.json"
    b.save(path)
    print(f"{path}: {len(b.rooms)} rooms, {len(b.receivers)} receivers, "
          f"{len(b.walls)} walls, {len(b.floors)} floors")


if __name__ == "__main__":
    main()
