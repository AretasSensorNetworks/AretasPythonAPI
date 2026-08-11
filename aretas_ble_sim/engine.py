"""The simulation clock: blinks -> RF fan-out -> receivers -> transports.

Event-driven over a merged, precomputed blink timeline plus a 100 ms service
tick (batch flushes, retransmits, acks, truth records). Sim time is ms from
run start; wire timestamps are epoch_ms + sim_ms.

Pacing: --speedup 1 tracks wall clock (live demos against the real broker),
N accelerates N-fold, 0 = free-run (record/bypass modes). Note that under
acceleration against the REAL ingest the platform stamps receivedTime with
its own wall clock, so ageMs semantics compress — free-running is only
honest for the bypass transports, which stamp sim time. run_sim warns
accordingly.

Determinism: one seeded stream drives all per-blink draws in a fixed order
(tags in scenario order, receivers sorted by MAC); structural draws are
hash-derived in rf.py/scenario.py. Same scenario + seed + epochMs ->
byte-identical golden traces.
"""

from __future__ import annotations

import heapq
import logging
import time
from dataclasses import dataclass, field

from .actors import EVENT_TYPE_MAP
from .random_stream import make_stream
from .receiver import SimReceiver
from .rf import RfModel
from .scenario import Scenario
from .transports import Transport

log = logging.getLogger(__name__)

TICK_MS = 100
TRUTH_INTERVAL_MS = 1000


@dataclass
class SimSummary:
    sim_ms: int = 0
    blinks: int = 0
    receptions: int = 0
    batches: int = 0
    events: int = 0
    retransmits: int = 0
    acks: int = 0
    counters: dict = field(default_factory=dict)


class SimEngine:

    def __init__(self, scenario: Scenario, transport: Transport,
                 epoch_ms: int, speedup: float = 0.0,
                 wall_hooks: list | None = None):
        self.sc = scenario
        self.transport = transport
        self.epoch_ms = epoch_ms
        self.speedup = speedup
        self.wall_hooks = wall_hooks or []   # called (sim_ms, epoch_ms) per tick
        self.rng = make_stream(scenario.seed, "engine")
        self.rf = RfModel(scenario.building, scenario.rf_params, scenario.seed)

        # which receivers heard >=1 registered+enabled tag: the honest
        # denominator for ingest-coverage scoring (a receiver whose only
        # audible tag is unregistered never produces a stored sighting)
        self._registered_macs = {mac for mac, e in scenario.registry().items()
                                 if e.get("enabled")}
        self.receivers_heard_registered: set[int] = set()

        macs = set(scenario.receiver_macs)
        self.receivers: list[SimReceiver] = []
        for rx in scenario.building.receivers:      # already sorted by MAC
            if rx.mac not in macs:
                continue
            stagger = make_stream(scenario.seed, "stagger", rx.mac).randrange(
                scenario.receiver_cfg.batch_interval_ms)
            self.receivers.append(SimReceiver(rx, scenario.receiver_cfg, stagger))
        self._rx_by_mac = {r.rx.mac: r for r in self.receivers}

    # ------------------------------------------------------------------ run

    def run(self) -> SimSummary:
        sc = self.sc
        summary = SimSummary()

        # (t_ms, order, kind, payload) — order keeps heap comparisons off dicts
        heap: list = []
        order = 0
        for actor in sc.actors:
            for blink in actor.blink_schedule(sc.duration_ms):
                heap.append((blink.t_ms, order, "blink", (actor, blink)))
                order += 1
        for t in range(0, sc.duration_ms + TICK_MS, TICK_MS):
            heap.append((t, order, "tick", None))
            order += 1
        heapq.heapify(heap)

        # press ground truth is known upfront — record it before the stream
        for ev in self.truth_events():
            self.transport.record_truth(ev)

        wall_start = time.monotonic()
        next_truth_ms = 0

        while heap:
            t_ms, _, kind, payload = heapq.heappop(heap)
            if t_ms > sc.duration_ms:
                break
            self._pace(wall_start, t_ms)

            if kind == "blink":
                actor, blink = payload
                summary.blinks += 1
                summary.receptions += self._fan_out(t_ms, actor, blink, summary)
            else:
                self._service_tick(t_ms, summary)
                if t_ms >= next_truth_ms:
                    self._emit_truth(t_ms)
                    next_truth_ms = t_ms + TRUTH_INTERVAL_MS
                for hook in self.wall_hooks:
                    hook(t_ms, self.epoch_ms)

        # final flush so short runs don't strand a partial batch
        self._service_tick(sc.duration_ms, summary, force_flush=True)
        summary.sim_ms = sc.duration_ms
        summary.counters = dict(self.transport.counters)
        return summary

    def _pace(self, wall_start: float, sim_ms: int):
        if self.speedup <= 0:
            return
        target = wall_start + (sim_ms / 1000.0) / self.speedup
        delay = target - time.monotonic()
        if delay > 0:
            time.sleep(delay)

    # ------------------------------------------------------------- internals

    def _fan_out(self, t_ms: int, actor, blink, summary: SimSummary) -> int:
        pos = actor.position(t_ms)
        if actor.profile.has_baro:
            blink.pressure_pa = self.rf.pressure_pa(
                t_ms, pos[2], actor.baro_offset_pa, self.rng)

        heard = 0
        for sim_rx in self.receivers:
            rssi = self.rf.sample(pos, blink.tx_power_ref, sim_rx.rx, self.rng)
            if rssi is None:
                continue
            heard += 1
            if blink.mac in self._registered_macs:
                self.receivers_heard_registered.add(sim_rx.rx.mac)
            event = sim_rx.add_blink(t_ms, blink, rssi)
            if event is not None:
                summary.events += 1
                self.transport.publish_event(self.epoch_ms + t_ms, event)
            batch = sim_rx.take_batch(t_ms)   # 64-sighting overflow flush
            if batch is not None:
                summary.batches += 1
                self.transport.publish_batch(self.epoch_ms + t_ms, batch)
        return heard

    def _service_tick(self, t_ms: int, summary: SimSummary, force_flush: bool = False):
        for rx_mac, event_ref in self.transport.poll_acks():
            sim_rx = self._rx_by_mac.get(rx_mac)
            if sim_rx is not None and sim_rx.on_ack(event_ref):
                summary.acks += 1

        for sim_rx in self.receivers:
            if force_flush:
                sim_rx.next_flush_ms = min(sim_rx.next_flush_ms, t_ms)
            batch = sim_rx.take_batch(t_ms)
            if batch is not None:
                summary.batches += 1
                self.transport.publish_batch(self.epoch_ms + t_ms, batch)
            for event in sim_rx.due_retransmits(t_ms):
                summary.retransmits += 1
                self.transport.publish_event(self.epoch_ms + t_ms, event)

    def _emit_truth(self, t_ms: int):
        for actor in self.sc.actors:
            x, y, z = actor.position(t_ms)
            floor = self.sc.building.floor_of_z(z)
            room = self.sc.building.room_at(x, y, floor)
            nearest = self.sc.building.nearest_receiver(x, y, z)
            self.transport.record_truth({
                "t": self.epoch_ms + t_ms, "kind": "truth",
                "mac": actor.mac, "tagId": actor.rtls_tag_id,
                "x": round(x, 3), "y": round(y, 3), "z": round(z, 3),
                "floor": floor, "roomId": room.id if room else None,
                "nearestReceiverMac": nearest.mac,
                "vanished": actor.vanished(t_ms)})

    def truth_at(self, sim_ms: int) -> dict[int, dict]:
        """tagId -> ground truth (the scorer's oracle)."""
        out = {}
        for actor in self.sc.actors:
            x, y, z = actor.position(sim_ms)
            nearest = self.sc.building.nearest_receiver(x, y, z)
            out[actor.rtls_tag_id] = {
                "mac": actor.mac, "x": x, "y": y, "z": z,
                "floor": self.sc.building.floor_of_z(z),
                "nearestReceiverMac": nearest.mac,
                "vanished": actor.vanished(sim_ms)}
        return out

    def truth_events(self) -> list[dict]:
        """Every press that physically produced a burst, with its fix-time
        ground truth — record-mode truthEvent lines + the scorer's oracle."""
        out = []
        for actor in self.sc.actors:
            window = actor.profile.trigger_window_ms
            if window is None:
                continue
            last_end = -1
            for press in sorted(actor.presses, key=lambda p: p.at_ms):
                if press.at_ms < last_end:
                    continue                       # mid-window re-press: no burst
                last_end = press.at_ms + window
                if press.at_ms >= self.sc.duration_ms or actor.vanished(press.at_ms):
                    continue
                x, y, z = actor.position(press.at_ms)
                floor = self.sc.building.floor_of_z(z)
                room = self.sc.building.room_at(x, y, floor)
                nearest = self.sc.building.nearest_receiver(x, y, z)
                out.append({
                    "t": self.epoch_ms + press.at_ms, "kind": "truthEvent",
                    "mac": actor.mac, "tagId": actor.rtls_tag_id,
                    "triggerKind": press.kind,
                    "eventType": EVENT_TYPE_MAP.get(press.kind, 0),
                    "x": round(x, 3), "y": round(y, 3), "z": round(z, 3),
                    "floor": floor, "roomId": room.id if room else None,
                    "nearestReceiverMac": nearest.mac})
        return out

    def manifest(self) -> dict:
        """Everything a golden-trace consumer needs to re-derive expectations."""
        sc = self.sc
        p = sc.rf_params
        return {
            "generator": "aretas_ble_sim",
            "scenario": sc.name,
            "seed": sc.seed,
            "epochMs": self.epoch_ms,
            "durationMs": sc.duration_ms,
            "building": sc.building.to_dict(),
            "rfParams": {
                "pathlossN": p.pathloss_n, "awgnSigmaDb": p.awgn_sigma_db,
                "fadingDb": p.fading_db,
                "receiverBiasSigmaDb": p.receiver_bias_sigma_db,
                "pdrMax": p.pdr_max, "pdrMidDbm": p.pdr_mid_dbm,
                "pdrSlopeDb": p.pdr_slope_db, "hardFloorDbm": p.hard_floor_dbm,
                "defaultP0Dbm": p.default_p0_dbm},
            # the o_i the platform self-calibration must recover (anchored Σo=0)
            "receiverBiasDb": {str(r.rx.mac): round(self.rf.receiver_bias(r.rx.mac), 4)
                               for r in self.receivers},
            "receiverConfig": {
                "batchIntervalMs": sc.receiver_cfg.batch_interval_ms,
                "rateCapMs": sc.receiver_cfg.rate_cap_ms,
                "maxBatch": sc.receiver_cfg.max_batch},
            "tags": [{"mac": s.mac, "profile": s.profile, "tagType": s.tag_type,
                      "label": s.label, "rtlsTagId": s.rtls_tag_id,
                      "ownerClientId": s.owner_client_id,
                      "registered": s.registered, "enabled": s.enabled,
                      "baroOffsetPa": round(a.baro_offset_pa, 2)}
                     for s, a in zip(sc.specs, sc.actors)],
        }
