"""Idempotently register a scenario's tags in the platform tag registry.

Needed before running --transport mqtt against the real ingest: the platform
drops any tag MAC that isn't registered and enabled (unregistered tags land
in the discovery list instead — which is itself a thing to demo). Tags with
`registered: false` in the scenario are deliberately skipped.

    python -m aretas_ble_sim.register_tags --scenario aretas_ble_sim/samples/walkthrough.scenario.yaml

A duplicate-MAC response counts as success (already registered). After the
writes, the account's rtlsTagIds are printed — note these differ from the
fabricated ids used by record/rabbitmq modes (the platform assigns its own),
which is fine: each mode is internally consistent.

Full building registration (floor-plan upload + device placements) lives
in provision.py — run that for the complete visual-demo setup.
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


def register_scenario_tags(api: str, headers: dict, scenario) -> int:
    """Idempotently create the scenario's registered tags. Returns the
    number of failures (0 = all present)."""
    failures = 0
    for spec in scenario.specs:
        if not spec.registered:
            log.info("Skipping %s (registered: false — discovery-ring tag)", spec.mac)
            continue
        body = {"macAddress": spec.mac, "tagType": spec.tag_type,
                "label": spec.label, "vendorModel": spec.profile,
                "enabled": spec.enabled, "notes": "aretas_ble_sim"}
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

    # show the platform's authoritative rtlsTagIds
    r = requests.get(api + "bletags/list", headers=headers, timeout=30)
    if r.status_code == 200:
        by_mac = {t["macAddress"]: t for t in r.json()}
        for spec in scenario.specs:
            t = by_mac.get(spec.mac)
            if t:
                log.info("%s -> rtlsTagId %s (%s)", spec.mac, t.get("rtlsTagId"),
                         t.get("label"))
    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Register scenario tags via /bletags")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--config", default="config.cfg")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        api, headers = api_session(args.config)
    except RuntimeError as e:
        log.error("%s", e)
        return 2
    failures = register_scenario_tags(api, headers, load_scenario(args.scenario))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
