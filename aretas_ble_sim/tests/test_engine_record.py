"""End-to-end: engine + record transport. Wire validity, enrichment policy,
truth files, and byte-level determinism."""

import json
from pathlib import Path

from pydantic import BaseModel
from typing import List, Optional

from aretas_ble_sim.engine import SimEngine
from aretas_ble_sim.transports import Enricher, NullTransport, RecordTransport


# Mirrors of the platform ingest's wire validation (raw sighting/event shape
# + the enrichment fields) — if the sim drifts from these, ingest drops it.

class SightingWire(BaseModel):
    mac: str
    rssi: int
    ageMs: int = 0
    seq: Optional[int] = None
    frameType: Optional[int] = None
    txPower: Optional[int] = None
    battery: Optional[float] = None
    pressurePa: Optional[float] = None
    # enrichment
    tagId: int
    ownerClientId: str


class BatchWire(BaseModel):
    schemaVersion: int
    receiverMac: int
    batchId: int
    receivedTime: int
    sightings: List[SightingWire]


class EventWire(BaseModel):
    schemaVersion: int
    receiverMac: int
    eventRef: str
    mac: str
    eventType: int
    triggerKind: Optional[str] = None
    firstSeenAgeMs: int = 0
    rssi: Optional[int] = None
    smoothedRssi: Optional[float] = None
    eventCounter: Optional[int] = None
    attempt: Optional[int] = None
    tagId: int
    ownerClientId: str
    receivedTime: int


def run_recorded(scenario, out_dir: Path) -> Path:
    engine = SimEngine(scenario, NullTransport(), epoch_ms=scenario.epoch_ms,
                       speedup=0.0)
    transport = RecordTransport(out_dir, Enricher(scenario.registry()),
                                engine.manifest())
    engine.transport = transport
    engine.run()
    transport.close()
    return out_dir


def read_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def test_record_run(scenario, tmp_path):
    out = run_recorded(scenario, tmp_path / "run1")

    trace = read_jsonl(out / "trace.jsonl")
    truth = read_jsonl(out / "truth.jsonl")
    manifest = json.loads((out / "manifest.json").read_text())

    batches = [r for r in trace if r["kind"] == "sightings"]
    events = [r for r in trace if r["kind"] == "event"]
    assert batches and events

    # every record validates against the wire mirror
    for r in batches:
        BatchWire(**r["data"])
    for r in events:
        EventWire(**r["data"])

    # trace is time-ordered
    ts = [r["t"] for r in trace]
    assert ts == sorted(ts)

    # enrichment policy: the unregistered tag never reaches the trace
    registered = {s.mac for s in scenario.specs if s.registered}
    seen = {s["mac"] for r in batches for s in r["data"]["sightings"]}
    assert seen and seen.issubset(registered)

    # both presses that can burst produce events; the 8 s re-press cannot
    press_events = [r for r in trace if r["kind"] == "event"]
    kinds = {e["data"]["triggerKind"] for e in press_events}
    assert kinds == {"single_click", "double_click"}
    # eventRef is RECEIVER-local: (receiverMac, eventRef) is the unique key;
    # retransmits reuse it with a growing attempt counter
    attempts = {}
    for e in press_events:
        d = e["data"]
        attempts.setdefault((d["receiverMac"], d["eventRef"]), []).append(d["attempt"])
    assert any(len(a) > 1 for a in attempts.values())  # un-acked -> retransmits
    for seq in attempts.values():
        assert seq == sorted(seq) == list(range(1, len(seq) + 1))
    assert len(attempts) >= 2  # >= 1 receiver per press kind

    # truth: continuous per-tag records + the press ground truth
    truth_events = [r for r in truth if r["kind"] == "truthEvent"]
    assert len(truth_events) == 2  # single at 5 s + double at 25 s (8 s dropped)
    macs_in_truth = {r["mac"] for r in truth if r["kind"] == "truth"}
    assert macs_in_truth == {a.mac for a in scenario.actors}
    sample = next(r for r in truth if r["kind"] == "truth")
    for key in ("x", "y", "z", "floor", "nearestReceiverMac", "tagId"):
        assert key in sample

    # ruuvi tag carries seq + battery + pressure on the wire
    ruuvi = [s for r in batches for s in r["data"]["sightings"]
             if s["mac"] == "CC:11:00:00:00:02"]
    assert ruuvi
    assert all(s.get("seq") is not None for s in ruuvi)
    assert all(s.get("pressurePa") is not None for s in ruuvi)

    # manifest carries what downstream tests need
    assert manifest["seed"] == scenario.seed
    assert len(manifest["receiverBiasDb"]) == len(scenario.receiver_macs)
    assert manifest["building"]["rooms"]


def test_deterministic_traces(scenario, tmp_path):
    out1 = run_recorded(scenario, tmp_path / "a")
    out2 = run_recorded(scenario, tmp_path / "b")
    for name in ("trace.jsonl", "truth.jsonl", "manifest.json"):
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes(), name


def test_seed_changes_world(scenario, tmp_path):
    out1 = run_recorded(scenario, tmp_path / "a")
    scenario.seed += 1
    out2 = run_recorded(scenario, tmp_path / "b")
    assert (out1 / "trace.jsonl").read_bytes() != (out2 / "trace.jsonl").read_bytes()
