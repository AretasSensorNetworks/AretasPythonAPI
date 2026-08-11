"""One-command platform setup for a scenario: location + receiver devices +
tags, all via REST, all idempotent.

    python -m aretas_ble_sim.provision --scenario aretas_ble_sim/samples/assist-drill.scenario.yaml --config config.cfg

Why this exists: publishing to blesightings/{mac} requires the MQTT account
to OWN device {mac} (the broker ACL checks topic-mac ownership), so the
virtual building's receivers must exist as devices in the account before a
--transport mqtt run works. This script makes the whole setup reproducible:

1. ensures a site location named after the building (override with
   --location-name, or target an existing one with --location-id),
2. ensures a device per scenario receiver MAC (existing MACs anywhere in
   the account are left untouched and reported),
3. registers the building's floor plans as building maps and PLACES this
   location's receivers on them (--skip-placement to opt out) — this is
   what makes tags render as positioned chips on the platform's floor-plan
   views instead of presence-only markers,
4. registers the scenario's tags (register_tags logic, same idempotency).

Re-running is safe — it converges to the same state and changes nothing
that already matches.

Placement notes: the building JSON's floorplans[] carries the px<->m
mapping (pxPerM, originPx — world +y points UP the plan, image +y points
down). The registered map's frame is "image metres": actualWidth/Height =
image px / pxPerM with zero X/Y offsets, so a solved position in that
frame is simply imgPx / pxPerM with y increasing DOWN the image. offsetZ
is set to the floor's base z so per-floor receiver heights come out right.
One building map is registered per floor, matched idempotently by file
name; devices the account already holds at OTHER locations are never
placed or moved.
"""

from __future__ import annotations

import argparse
import logging
import sys

import requests

from .register_tags import api_session, register_scenario_tags
from .scenario import load_scenario

log = logging.getLogger(__name__)


def _location_view(api: str, headers: dict, invalidate: bool = False) -> dict:
    params = {"invalidateCache": "true"} if invalidate else {}
    r = requests.get(api + "client/locationview", headers=headers,
                     params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def ensure_location(api: str, headers: dict, view: dict, name: str,
                    lat: float, lon: float) -> dict:
    """Find a location by exact description, creating it if absent.
    Returns the location object."""
    for lsv in view.get("locationSensorViews", []):
        if lsv["location"].get("description") == name:
            log.info("Location exists: %s (%s)", name, lsv["location"]["id"])
            return lsv["location"]

    body = {"id": None, "owner": view["id"], "description": name,
            "streetAddress": "", "city": "", "state": "", "country": "",
            "zipCode": "", "timezone": "", "lat": lat, "lon": lon}
    r = requests.post(api + "sitelocation/create", json=body, headers=headers,
                      timeout=30)
    r.raise_for_status()
    resp = r.json()
    if not resp.get("booleanResponse"):
        raise RuntimeError(f"Location create failed: {resp.get('message')}")
    log.info("Created location: %s", name)

    view = _location_view(api, headers, invalidate=True)
    for lsv in view.get("locationSensorViews", []):
        if lsv["location"].get("description") == name:
            return lsv["location"]
    raise RuntimeError("Created location did not appear in the location view")


def ensure_receivers(api: str, headers: dict, view: dict, location: dict,
                     scenario) -> int:
    """Create a device per scenario receiver MAC that the account doesn't
    already own. Returns the number of failures."""
    owned: dict[int, str] = {}
    for lsv in view.get("locationSensorViews", []):
        for s in lsv.get("sensorList", []):
            owned[int(s["mac"])] = lsv["location"].get("description", "?")

    rooms = {rx.mac: rx.room_id for rx in scenario.building.receivers}
    failures = 0
    for mac in scenario.receiver_macs:
        if mac in owned:
            log.info("Device %d exists (in '%s') — leaving it alone", mac, owned[mac])
            continue
        room = rooms.get(mac)
        body = {
            "id": None, "owner": location["id"],
            "description": f"BLE sim receiver {room or mac}",
            "mac": mac,
            "lat": location.get("lat", 0.0), "lon": location.get("lon", 0.0),
            "areaType": 0, "notifyIfDown": False,
            "downInterval": 24 * 3600 * 1000, "isSharedPublic": False,
            "buildingMapId": "", "imgMapX": -1, "imgMapY": -1,
            "areaUsageHints": {"floorArea": 0, "ceilingHeight": 0,
                               "hasPeople": 0, "occupantCountHint": 0,
                               "hasOpeningWindows": 0},
        }
        r = requests.post(api + "sensorlocation/create", json=body,
                          headers=headers, timeout=30)
        if r.status_code != 200:
            log.error("Device %d: HTTP %d %s", mac, r.status_code, r.text[:200])
            failures += 1
            continue
        resp = r.json()
        if resp.get("booleanResponse"):
            log.info("Created device %d (%s)", mac, body["description"])
        else:
            log.error("Device %d: %s", mac, resp.get("message"))
            failures += 1
    return failures


# ---------------------------------------------------------------- placement

def plan_px(fp: dict, x: float, y: float) -> tuple[int, int]:
    """World metres -> native image px via a floorplans[] entry (world +y
    points up, image +y points down). (0, 0) is the platform's never-placed
    sentinel, so coordinates clamp to 1."""
    img_x = max(1, int(round(fp["originPx"][0] + x * fp["pxPerM"])))
    img_y = max(1, int(round(fp["originPx"][1] - y * fp["pxPerM"])))
    return img_x, img_y


def ensure_building_maps(api: str, headers: dict, location: dict,
                         scenario) -> tuple[dict[int, dict], int]:
    """Register one building map per floor plan, idempotent by file name.
    Returns ({floor index -> map doc}, failure count)."""
    plans = scenario.building.floorplans or []
    maps_by_floor: dict[int, dict] = {}
    if not plans:
        log.info("Building JSON has no floorplans[] — skipping map "
                 "registration (regenerate the building without --no-png)")
        return maps_by_floor, 0

    floor_z = {f.index: f.z for f in scenario.building.floors}

    def _list_maps() -> dict[str, dict]:
        r = requests.get(api + "buildingmaps/list",
                         params={"locationId": location["id"]},
                         headers=headers, timeout=30)
        r.raise_for_status()
        return {m.get("name"): m for m in (r.json() or [])}

    existing = _list_maps()
    failures = 0
    created = False
    for fp in plans:
        floor = fp["floor"]
        if fp["file"] in existing:
            log.info("Building map exists: %s — leaving it alone", fp["file"])
            maps_by_floor[floor] = existing[fp["file"]]
            continue

        png = scenario.building_path.parent / fp["file"]
        if not png.is_file():
            log.error("Floor plan %s not found next to the building JSON", png)
            failures += 1
            continue

        from PIL import Image  # already an API-wrapper dependency
        with Image.open(png) as img:
            width_px, height_px = img.size

        with open(png, "rb") as fh:
            r = requests.post(api + "file/upload", headers=headers,
                              files={"file": (fp["file"], fh, "image/png")},
                              data={"type": "BUILDING_MAP",
                                    "locationId": location["id"]},
                              timeout=60)
        if r.status_code != 200 or not r.json().get("booleanResponse"):
            log.error("Floor plan upload failed for %s: HTTP %d %s",
                      fp["file"], r.status_code, r.text[:200])
            failures += 1
            continue

        px_per_m = fp["pxPerM"]
        body = {
            "id": None, "owner": location["id"], "ownerClientId": None,
            "name": fp["file"],   # must match the uploaded file name exactly
            "description": f"{scenario.building.name} — floor {floor}",
            "mimeType": "image/png",
            "computedWidth": width_px, "computedHeight": height_px,
            # the map frame is "image metres": full image extent over the
            # scale, no X/Y offsets; Z offset = the floor's base height so
            # receiver mount heights resolve per floor
            "actualWidth": width_px / px_per_m,
            "actualHeight": height_px / px_per_m,
            "actualDepth": 0,
            "offsetX": 0, "offsetY": 0, "offsetZ": floor_z.get(floor, 0.0),
        }
        r = requests.post(api + "buildingmaps/create", json=body,
                          headers=headers, timeout=30)
        if r.status_code != 200 or not r.json().get("booleanResponse"):
            log.error("Building map create failed for %s: %s", fp["file"],
                      r.text[:200])
            failures += 1
            continue
        log.info("Registered building map %s (%dx%d px, %.1fx%.1f m)",
                 fp["file"], width_px, height_px,
                 body["actualWidth"], body["actualHeight"])
        created = True

    if created:
        existing = _list_maps()
        for fp in plans:
            if fp["file"] in existing:
                maps_by_floor.setdefault(fp["floor"], existing[fp["file"]])
    return maps_by_floor, failures


def place_receivers(api: str, headers: dict, location: dict, scenario,
                    maps_by_floor: dict[int, dict]) -> int:
    """Write buildingMapId/imgMapX/imgMapY onto THIS location's receiver
    devices from the building's px<->m mapping. Read-modify-write against
    the full device docs so nothing else on them changes; receivers owned
    by other locations are reported and left alone. Returns failures."""
    if not maps_by_floor:
        return 0

    r = requests.get(api + "sensorlocation/list",
                     params={"id": location["id"]}, headers=headers,
                     timeout=30)
    r.raise_for_status()
    by_mac = {int(d["mac"]): d for d in (r.json() or [])}
    plans_by_floor = {fp["floor"]: fp for fp in scenario.building.floorplans}

    failures = 0
    placed = skipped = 0
    for rx in scenario.building.receivers:
        doc = by_mac.get(rx.mac)
        if doc is None:
            log.info("Receiver %d is not a device at '%s' — not placing it",
                     rx.mac, location.get("description"))
            continue
        fp = plans_by_floor.get(rx.floor)
        map_doc = maps_by_floor.get(rx.floor)
        if fp is None or map_doc is None:
            log.warning("No registered floor plan for floor %d — receiver %d "
                        "stays unplaced", rx.floor, rx.mac)
            continue

        img_x, img_y = plan_px(fp, rx.x, rx.y)

        if (doc.get("buildingMapId") == map_doc["id"]
                and doc.get("imgMapX") == img_x and doc.get("imgMapY") == img_y):
            skipped += 1
            continue

        body = {**doc, "buildingMapId": map_doc["id"],
                "imgMapX": img_x, "imgMapY": img_y}
        r = requests.post(api + "sensorlocation/update", json=body,
                          headers=headers, timeout=30)
        if r.status_code != 200 or not r.json().get("booleanResponse"):
            log.error("Placement update failed for %d: HTTP %d %s", rx.mac,
                      r.status_code, r.text[:200])
            failures += 1
            continue
        placed += 1
        log.info("Placed receiver %d at (%d, %d) px on %s", rx.mac, img_x,
                 img_y, map_doc.get("name"))

    if skipped:
        log.info("%d receiver placement(s) already correct", skipped)
    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Provision a scenario's location, receiver devices and tags via REST")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--config", default="config.cfg")
    ap.add_argument("--location-name", default=None,
                    help="site location to hold the receivers (default: 'BLE Sim — <building>')")
    ap.add_argument("--location-id", default=None,
                    help="use this existing location id instead of ensure-by-name")
    ap.add_argument("--lat", type=float, default=0.0)
    ap.add_argument("--lon", type=float, default=0.0)
    ap.add_argument("--skip-placement", action="store_true",
                    help="don't register floor plans or place receivers "
                         "(ingest-only setups; positions degrade to "
                         "presence-only)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        api, headers = api_session(args.config)
    except RuntimeError as e:
        log.error("%s", e)
        return 2

    scenario = load_scenario(args.scenario)
    view = _location_view(api, headers, invalidate=True)

    if args.location_id:
        location = None
        for lsv in view.get("locationSensorViews", []):
            if lsv["location"]["id"] == args.location_id:
                location = lsv["location"]
                break
        if location is None:
            log.error("Location id %s not found in the account", args.location_id)
            return 2
    else:
        name = args.location_name or f"BLE Sim — {scenario.building.name}"
        location = ensure_location(api, headers, view, name, args.lat, args.lon)
        view = _location_view(api, headers, invalidate=True)

    dev_failures = ensure_receivers(api, headers, view, location, scenario)

    place_failures = 0
    if args.skip_placement:
        log.info("Skipping floor-plan registration and receiver placement")
    else:
        maps_by_floor, place_failures = ensure_building_maps(
            api, headers, location, scenario)
        place_failures += place_receivers(
            api, headers, location, scenario, maps_by_floor)

    tag_failures = register_scenario_tags(api, headers, scenario)

    log.info("Provisioning done: %d receiver failures, %d placement "
             "failures, %d tag failures (location '%s')", dev_failures,
             place_failures, tag_failures, location.get("description"))
    return 1 if (dev_failures or place_failures or tag_failures) else 0


if __name__ == "__main__":
    sys.exit(main())
