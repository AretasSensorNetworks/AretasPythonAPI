"""Scenario files (YAML) -> a fully-built, deterministic simulation setup.

Example (see samples/*.scenario.yaml):

    name: walkthrough
    building: hotel-small.building.json     # relative to this file
    seed: 42
    epochMs: null          # null -> wall clock at start; fix it for
                           # byte-reproducible record traces
    durationS: 600
    ownerClientId: sim-client
    rf: {pathlossN: 2.8}                    # optional RfParams overrides
    receiver: {batchIntervalMs: 1500}       # optional ReceiverConfig overrides
    receivers: all                          # or a list of integer MACs
    tags:
      - mac: "CC:11:00:00:00:01"
        profile: bc011                      # bc011 | ruuvi_raw2
        tagType: PANIC                      # wire enum: PANIC (= Aretas Assist Button) | PERSONNEL | ASSET
        label: "Pendant 1"
        kind: personnel                     # personnel | asset | static
        start: f0-r01                       # room id or [x, y, floor]
        path: [f0-r03, f1-r02]              # waypoints (rooms or coords)
        speedMps: 1.2
        dwellS: 45
        loop: true
        registered: true                    # false -> discovery-ring test tag
        enabled: true                       # false -> registered-but-disabled
        rtlsTagId: null                     # fabricated from MAC when null
        presses: [{atS: 120, kind: single_click}]
        vanish:  [{atS: 300, forS: 60}]
        battery: {startPct: 95, decayPctPerHour: 0.5}

rtlsTagId fabrication: in bypass/record modes there is no platform to assign
the real server-derived id, so the sim derives a stable positive long from
the MAC — deterministic across runs so golden traces never drift. Runs
against the real ingest (mqtt transport) don't use it at all: the platform
enriches from the actual registry (register_tags.py seeds it).
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .actors import TAG_PROFILES, Press, TagActor, build_knots
from .building import VirtualBuilding
from .receiver import ReceiverConfig
from .rf import RfParams

CARRY_HEIGHT = {"personnel": 1.2, "asset": 1.0, "static": 1.0}


def canonical_mac(mac: str) -> str:
    """Uppercase colon form — the platform's canonical BLE MAC shape."""
    hex_only = mac.strip().upper().replace(":", "").replace("-", "")
    if len(hex_only) != 12 or any(c not in "0123456789ABCDEF" for c in hex_only):
        raise ValueError(f"Bad BLE MAC: {mac!r}")
    return ":".join(hex_only[i:i + 2] for i in range(0, 12, 2))


def fabricate_rtls_tag_id(mac: str) -> int:
    h = hashlib.sha256(canonical_mac(mac).encode()).digest()
    return int.from_bytes(h[:8], "big") & 0x7FFFFFFFFFFFFFFF


@dataclass
class TagSpec:
    """Registry-facing view of a scenario tag (register_tags.py + manifest)."""
    mac: str
    profile: str
    tag_type: str
    label: str
    rtls_tag_id: int
    owner_client_id: str
    registered: bool
    enabled: bool


@dataclass
class Scenario:
    name: str
    path: Path
    seed: int
    epoch_ms: int | None
    duration_ms: int
    owner_client_id: str
    building: VirtualBuilding
    building_path: Path
    actors: list[TagActor]
    specs: list[TagSpec]
    rf_params: RfParams
    receiver_cfg: ReceiverConfig
    receiver_macs: list[int]
    raw: dict = field(repr=False, default_factory=dict)

    def registry(self) -> dict[str, dict]:
        """Canonical MAC -> auth entry, the ingest allowlist shape —
        used by the bypass/record enrichment path."""
        return {s.mac: {"rtlsTagId": s.rtls_tag_id,
                        "ownerClientId": s.owner_client_id,
                        "tagType": s.tag_type, "enabled": s.enabled}
                for s in self.specs if s.registered}


def _resolve_point(building: VirtualBuilding, spec) -> tuple[float, float, int]:
    if isinstance(spec, str):
        room = building.room(spec)
        cx, cy = room.center()
        return (cx, cy, room.floor)
    x, y, floor = spec
    return (float(x), float(y), int(floor))


def load_scenario(path: str | Path) -> Scenario:
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        d = yaml.safe_load(f)

    building_path = (path.parent / d["building"]).resolve()
    building = VirtualBuilding.load(building_path)
    seed = int(d.get("seed", 1))
    duration_ms = int(float(d.get("durationS", 600)) * 1000)
    owner = d.get("ownerClientId", "sim-client")

    rx_sel = d.get("receivers", "all")
    if rx_sel == "all" or rx_sel is None:
        receiver_macs = [r.mac for r in building.receivers]
    else:
        receiver_macs = [int(m) for m in rx_sel]

    actors: list[TagActor] = []
    specs: list[TagSpec] = []
    for i, td in enumerate(d.get("tags", [])):
        mac = canonical_mac(td["mac"])
        profile = TAG_PROFILES[td.get("profile", "bc011")]
        kind = td.get("kind", "personnel")
        carry = CARRY_HEIGHT.get(kind, 1.2)

        start = _resolve_point(building, td.get("start", building.rooms[0].id))
        waypoints = [_resolve_point(building, w) for w in td.get("path", [])]
        knots = build_knots(
            building, start, waypoints,
            speed_mps=float(td.get("speedMps", 1.2 if kind == "personnel" else 0.8)),
            dwell_ms=int(float(td.get("dwellS", 45)) * 1000),
            carry_height_m=carry, duration_ms=duration_ms,
            loop=bool(td.get("loop", False)))

        presses = [Press(int(float(p["atS"]) * 1000), p.get("kind", "single_click"))
                   for p in td.get("presses", [])]
        vanish = [(int(float(v["atS"]) * 1000),
                   int((float(v["atS"]) + float(v["forS"])) * 1000))
                  for v in td.get("vanish", [])]
        batt = td.get("battery") or {}

        # per-tag structural randomness, stable regardless of tag order
        trng = random.Random(int.from_bytes(
            hashlib.sha256(f"{seed}|tag|{mac}".encode()).digest()[:8], "big"))

        rtls_tag_id = int(td["rtlsTagId"]) if td.get("rtlsTagId") else fabricate_rtls_tag_id(mac)
        registered = bool(td.get("registered", True))
        enabled = bool(td.get("enabled", True))
        label = td.get("label", f"Sim tag {i + 1}")
        tag_type = td.get("tagType", "PANIC")

        actors.append(TagActor(
            mac=mac, profile=profile, tag_type=tag_type, label=label,
            rtls_tag_id=rtls_tag_id, owner_client_id=owner,
            carry_height_m=carry, knots=knots, presses=presses,
            vanish_windows=vanish,
            battery_start_pct=(float(batt["startPct"]) if "startPct" in batt else
                               (95.0 if profile.has_battery else None)),
            battery_decay_pct_per_h=float(batt.get("decayPctPerHour", 0.0)),
            baro_offset_pa=trng.uniform(-50.0, 50.0),
            phase_ms=trng.uniform(0, profile.heartbeat_ms)))
        specs.append(TagSpec(mac, profile.name, tag_type, label, rtls_tag_id,
                             owner, registered, enabled))

    return Scenario(
        name=d.get("name", path.stem), path=path, seed=seed,
        epoch_ms=(int(d["epochMs"]) if d.get("epochMs") else None),
        duration_ms=duration_ms, owner_client_id=owner, building=building,
        building_path=building_path, actors=actors, specs=specs,
        rf_params=RfParams.from_dict(d.get("rf") or {}),
        receiver_cfg=ReceiverConfig.from_dict(d.get("receiver") or {}),
        receiver_macs=receiver_macs, raw=d)
