"""Idempotently register a scenario's tags in the platform tag registry.

Needed before running --transport mqtt against the real ingest: the platform
drops any tag MAC that isn't registered and enabled (unregistered tags land
in the discovery list instead — which is itself a thing to demo). Tags with
`registered: false` in the scenario are deliberately skipped.

The platform requires every tag to have a HOME location (receivers only
accept tags registered to their own site), so registration targets one:
by default the location provision.py names after the building
('BLE Sim — <building>'), or pass --location-id / --location-name.

    python -m aretas_ble_sim.register_tags --scenario aretas_ble_sim/samples/walkthrough.scenario.yaml

A duplicate-MAC response counts as success (already registered). After the
writes, the account's rtlsTagIds are printed — note these differ from the
fabricated ids used by record/rabbitmq modes (the platform assigns its own),
which is fine: each mode is internally consistent.

Full building registration (floor-plan upload + device placements) lives
in provision.py — run that for the complete visual-demo setup (it registers
the tags too, homed at the location it just ensured).
"""

from __future__ import annotations

import argparse
import logging
import sys

import requests

from .scenario import load_scenario

log = logging.getLogger(__name__)


def api_session(config_path: str) -> tuple[str, dict]:
    """(api_url, auth headers) from the repo's config.cfg — shared by the
    provisioning/registration/scoring helpers."""
    from api_config import APIConfig
    from auth import APIAuth

    config = APIConfig(config_path)
    token = APIAuth(config).get_token(refresh_if_expired=True)
    if token is None:
        raise RuntimeError("Could not authenticate against the REST API")
    return config.get_api_url(), {"Authorization": "Bearer " + token}


def register_scenario_tags(api: str, headers: dict, scenario,
                           location_id: str | None = None) -> int:
    """Idempotently create the scenario's registered tags, homed at
    `location_id` (required by current platforms — a tag is only accepted
    by receivers at its home location). Returns the number of failures
    (0 = all present)."""
    failures = 0
    for spec in scenario.specs:
        if not spec.registered:
            log.info("Skipping %s (registered: false — discovery-ring tag)", spec.mac)
            continue
        body = {"macAddress": spec.mac, "tagType": spec.tag_type,
                "label": spec.label, "vendorModel": spec.profile,
                "enabled": spec.enabled, "notes": "aretas_ble_sim",
                "owner": location_id}
        r = requests.post(api + "bletags/create", json=body, headers=headers,
                          timeout=30)
        if r.status_code != 200:
            log.error("%s: HTTP %d %s", spec.mac, r.status_code, r.text[:200])
            failures += 1
            continue
        resp = r.json()
        if resp.get("booleanResponse"):
            log.info("Registered %s (%s)", spec.mac, resp.get("message", ""))
        elif "already" in (resp.get("message") or "").lower() or \
                "duplicate" in (resp.get("message") or "").lower() or \
                "in use" in (resp.get("message") or "").lower():
            log.info("Already registered: %s", spec.mac)
        else:
            log.error("%s: %s", spec.mac, resp.get("message"))
            failures += 1

    # show the platform's authoritative rtlsTagIds — and adopt any
    # pre-existing registrations that predate location scoping (no home
    # yet), so re-provisioning heals them in place
    r = requests.get(api + "bletags/list", headers=headers, timeout=30)
    if r.status_code == 200:
        by_mac = {t["macAddress"]: t for t in r.json()}
        for spec in scenario.specs:
            t = by_mac.get(spec.mac)
            if not t:
                continue
            log.info("%s -> rtlsTagId %s (%s)", spec.mac, t.get("rtlsTagId"),
                     t.get("label"))
            if location_id and not t.get("owner"):
                u = requests.post(api + "bletags/update",
                                  json={**t, "owner": location_id},
                                  headers=headers, timeout=30)
                ok = u.status_code == 200 and u.json().get("booleanResponse")
                if ok:
                    log.info("Assigned home location to existing tag %s", spec.mac)
                else:
                    log.error("Could not assign a home to %s: %s", spec.mac, u.text[:150])
                    failures += 1
    return failures


def resolve_location_id(api: str, headers: dict, location_id: str | None,
                        location_name: str) -> str | None:
    """Find the home location for the scenario's tags. Explicit id wins;
    otherwise look the name up in the account's location view. Returns None
    (with a logged error) when nothing matches — we never CREATE a location
    here, that's provision.py's job."""
    r = requests.get(api + "client/locationview", headers=headers, timeout=60)
    r.raise_for_status()
    for lsv in r.json().get("locationSensorViews", []):
        loc = lsv.get("location", {})
        if location_id and loc.get("id") == location_id:
            return location_id
        if not location_id and loc.get("description") == location_name:
            log.info("Home location: %s (%s)", location_name, loc["id"])
            return loc["id"]
    log.error("No location %s in the account — run provision.py first, or pass "
              "--location-id/--location-name",
              repr(location_id or location_name))
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Register scenario tags via /bletags")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--config", default="config.cfg")
    ap.add_argument("--location-id", default=None,
                    help="home location for the tags (default: resolve --location-name)")
    ap.add_argument("--location-name", default=None,
                    help="resolve the home location by name (default: 'BLE Sim — <building>')")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        api, headers = api_session(args.config)
    except RuntimeError as e:
        log.error("%s", e)
        return 2

    scenario = load_scenario(args.scenario)
    name = args.location_name or f"BLE Sim — {scenario.building.name}"
    location_id = resolve_location_id(api, headers, args.location_id, name)
    if location_id is None:
        return 2
    failures = register_scenario_tags(api, headers, scenario, location_id)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
