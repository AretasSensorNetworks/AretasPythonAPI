"""Per-receiver edge emulation: what real receiver firmware does between a
BLE advert and MQTT, reproduced so the simulated wire is indistinguishable
from hardware.

* Rate cap: keep the best-RSSI sighting per tag per 500 ms.
* Batching: flush every 1-2 s (receivers staggered) or at 64 sightings;
  each sighting carries ageMs relative to send time (receivers have no RTC —
  the server stamps true time as receipt minus age).
* Trigger state machine: the first packet of a button/trigger burst emits
  ONE logical event immediately (bypasses batching); repeats of the same
  active trigger are suppressed; a DIFFERENT trigger kind mid-window reports
  immediately; re-arm on a >=2.5 s trigger gap, on heartbeat-frame resume
  after >=3x trigger-interval silence, or on the 12 s failsafe.
  eventRef = mac + a receiver-local monotonic counter.
* Journal + retransmit: events are journaled and retransmitted on
  2,4,8,...,60 s backoff until the cloud's APPLICATION ack (a blecmd
  eventAck message) clears them — attempt/firstSeenAgeMs grow per
  retransmit; duplicates are the server dedupe's problem (by design).

Trigger frames also enter the sighting stream (they are adverts with RSSI —
burst-mode position fixes feed on them).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .actors import EVENT_TYPE_MAP, Blink
from .building import Receiver

RETRANSMIT_BACKOFF_MS = [2000, 4000, 8000, 16000, 32000, 60000]


@dataclass
class ReceiverConfig:
    batch_interval_ms: int = 1500
    rate_cap_ms: int = 500
    max_batch: int = 64
    trigger_rearm_gap_ms: int = 2500
    trigger_failsafe_ms: int = 12000     # BC011 trigger window 10 s + 2 s
    heartbeat_resume_ms: int = 1200      # >= 3 x 400 ms trigger interval

    @classmethod
    def from_dict(cls, d: dict) -> "ReceiverConfig":
        c = cls()
        mapping = {"batchIntervalMs": "batch_interval_ms", "rateCapMs": "rate_cap_ms",
                   "maxBatch": "max_batch"}
        for k, v in (d or {}).items():
            attr = mapping.get(k, k)
            if hasattr(c, attr):
                setattr(c, attr, int(v))
        return c


@dataclass
class _BufferedSighting:
    t_ms: int
    mac: str
    rssi: int
    seq: int | None
    frame_type: int
    tx_power: int | None
    battery: float | None
    pressure_pa: float | None


@dataclass
class _TriggerState:
    kind: str
    start_ms: int
    last_trigger_ms: int
    event_ref: str


@dataclass
class JournalEntry:
    event_ref: str
    mac: str
    event_type: int
    trigger_kind: str
    first_seen_ms: int
    first_rssi: int
    rssi_sum: float = 0.0
    rssi_n: int = 0
    event_counter: int | None = None
    attempts: int = 0
    next_retry_ms: int = 0

    def smoothed(self) -> float:
        return round(self.rssi_sum / max(self.rssi_n, 1), 1)


class SimReceiver:
    """One virtual Aretas receiver. add_blink() may return an immediate event
    payload; batches and retransmits are pulled by the engine's clock."""

    def __init__(self, rx: Receiver, cfg: ReceiverConfig, stagger_ms: int):
        self.rx = rx
        self.cfg = cfg
        self.batch_id = 0
        self.next_flush_ms = stagger_ms  # de-synchronize the fleet's flushes
        self._buffer: dict[tuple[str, int], _BufferedSighting] = {}
        self._trigger: dict[str, _TriggerState] = {}
        self._event_counter = 0          # receiver-local, monotonic
        self.journal: dict[str, JournalEntry] = {}

    # ---------------------------------------------------------------- blinks

    def add_blink(self, t_ms: int, blink: Blink, rssi: int) -> dict | None:
        """Record a received advert. Returns an event wire payload when this
        packet opens a new logical trigger event (the immediate lane)."""
        bucket = t_ms // self.cfg.rate_cap_ms
        key = (blink.mac, bucket)
        cur = self._buffer.get(key)
        if cur is None or rssi > cur.rssi:
            self._buffer[key] = _BufferedSighting(
                t_ms=t_ms, mac=blink.mac, rssi=rssi, seq=blink.seq,
                frame_type=blink.frame_type, tx_power=blink.tx_power_ref,
                battery=blink.battery_pct, pressure_pa=blink.pressure_pa)

        if blink.trigger_kind is not None:
            return self._on_trigger(t_ms, blink, rssi)
        self._on_heartbeat(t_ms, blink.mac)
        return None

    def _on_trigger(self, t_ms: int, blink: Blink, rssi: int) -> dict | None:
        st = self._trigger.get(blink.mac)
        if st is not None and (t_ms - st.last_trigger_ms >= self.cfg.trigger_rearm_gap_ms
                               or t_ms - st.start_ms >= self.cfg.trigger_failsafe_ms):
            self._trigger.pop(blink.mac, None)
            st = None

        if st is not None and st.kind == blink.trigger_kind:
            st.last_trigger_ms = t_ms                 # same active trigger: suppress
            entry = self.journal.get(st.event_ref)
            if entry is not None:
                entry.rssi_sum += rssi
                entry.rssi_n += 1
            return None

        # new logical event (fresh trigger, or a different kind mid-window)
        self._event_counter += 1
        event_ref = f"{blink.mac}:{self._event_counter}"
        self._trigger[blink.mac] = _TriggerState(
            kind=blink.trigger_kind, start_ms=t_ms, last_trigger_ms=t_ms,
            event_ref=event_ref)

        entry = JournalEntry(
            event_ref=event_ref, mac=blink.mac,
            event_type=EVENT_TYPE_MAP.get(blink.trigger_kind, 0),
            trigger_kind=blink.trigger_kind, first_seen_ms=t_ms,
            first_rssi=rssi, rssi_sum=float(rssi), rssi_n=1,
            event_counter=blink.event_counter,
            next_retry_ms=t_ms + RETRANSMIT_BACKOFF_MS[0])
        self.journal[event_ref] = entry
        entry.attempts = 1
        return self._event_payload(entry, t_ms)

    def _on_heartbeat(self, t_ms: int, mac: str):
        st = self._trigger.get(mac)
        if st is not None and t_ms - st.last_trigger_ms >= self.cfg.heartbeat_resume_ms:
            self._trigger.pop(mac, None)              # normal-frame resume re-arm

    # --------------------------------------------------------------- batches

    def take_batch(self, t_ms: int) -> dict | None:
        """Batch payload if one is due (interval elapsed or buffer full)."""
        full = len(self._buffer) >= self.cfg.max_batch
        if t_ms < self.next_flush_ms and not full:
            return None
        while self.next_flush_ms <= t_ms:
            self.next_flush_ms += self.cfg.batch_interval_ms
        if not self._buffer:
            return None

        sightings = []
        for s in sorted(self._buffer.values(), key=lambda b: (b.t_ms, b.mac)):
            rec = {"mac": s.mac, "rssi": s.rssi, "ageMs": max(t_ms - s.t_ms, 0)}
            if s.seq is not None:
                rec["seq"] = s.seq
            if s.frame_type is not None:
                rec["frameType"] = s.frame_type
            if s.tx_power is not None:
                rec["txPower"] = s.tx_power
            if s.battery is not None:
                rec["battery"] = s.battery
            if s.pressure_pa is not None:
                rec["pressurePa"] = round(s.pressure_pa, 1)
            sightings.append(rec)
        self._buffer.clear()
        self.batch_id += 1
        return {"schemaVersion": 1, "receiverMac": self.rx.mac,
                "batchId": self.batch_id, "sightings": sightings}

    # ----------------------------------------------------- events + journal

    def _event_payload(self, e: JournalEntry, now_ms: int) -> dict:
        return {"schemaVersion": 1, "receiverMac": self.rx.mac,
                "eventRef": e.event_ref, "mac": e.mac, "eventType": e.event_type,
                "triggerKind": e.trigger_kind,
                "firstSeenAgeMs": max(now_ms - e.first_seen_ms, 0),
                "rssi": e.first_rssi, "smoothedRssi": e.smoothed(),
                "eventCounter": e.event_counter, "attempt": e.attempts}

    def due_retransmits(self, t_ms: int) -> list[dict]:
        out = []
        for e in sorted(self.journal.values(), key=lambda j: j.event_ref):
            if t_ms >= e.next_retry_ms:
                e.attempts += 1
                backoff = RETRANSMIT_BACKOFF_MS[
                    min(e.attempts - 1, len(RETRANSMIT_BACKOFF_MS) - 1)]
                e.next_retry_ms = t_ms + backoff
                out.append(self._event_payload(e, t_ms))
        return out

    def on_ack(self, event_ref: str) -> bool:
        """Cloud application ack (blecmd eventAck) — closes the journal entry
        exactly like real firmware clears its non-volatile journal."""
        return self.journal.pop(event_ref, None) is not None
