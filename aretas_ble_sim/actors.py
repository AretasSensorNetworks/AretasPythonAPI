"""Tag actors: blink schedules + motion timelines + scenario events.

Tag profiles mirror real commercial beacon behavior:

* bc011 — Blue Charm BC011, iBeacon-only. 1022.5 ms heartbeat; a button
  press bursts the trigger frame every 400 ms for 10 s (~25 packets) and
  the tag physically cannot emit a different trigger mid-window. NO seq
  counter, NO battery/baro in the frame — which is exactly why receivers
  collapse bursts locally and the platform dedupes events by time window.
* ruuvi_raw2 — RuuviTag format 05: has a per-advert measurement sequence
  counter (exact cross-receiver blink association), battery and pressure.
  No button.

Motion is precomputed as a deterministic timeline of (t, x, y, z) knots at
scenario build (waypoints routed through the building's corridor/stair nav),
then position(t) is linear interpolation — no per-tick mutable state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .building import VirtualBuilding

# Frame-type codes on the sighting wire (2 = iBeacon, 5 = RuuviTag RAWv2)
FRAME_IBEACON = 2
FRAME_RUUVI_RAW2 = 5

# triggerKind -> wire eventType (0 PANIC, 1 BUTTON_2/DOUBLE, 2 FALL,
# 3 LOW_BATT). The canonical per-profile map ships with the receiver
# firmware's frame profiles; until then single/long press = eventType 0,
# multi-click = DOUBLE.
EVENT_TYPE_MAP = {
    "single_click": 0,
    "long_press": 0,
    "double_click": 1,
    "triple_click": 1,
}


@dataclass(frozen=True)
class TagProfile:
    name: str
    heartbeat_ms: float
    frame_type: int
    tx_power_ref: int | None
    trigger_interval_ms: float | None = None
    trigger_window_ms: float | None = None
    has_seq: bool = False
    has_battery: bool = False
    has_baro: bool = False
    has_event_counter: bool = False
    trigger_kinds: tuple[str, ...] = ()


TAG_PROFILES: dict[str, TagProfile] = {
    "bc011": TagProfile(
        name="bc011", heartbeat_ms=1022.5, frame_type=FRAME_IBEACON,
        tx_power_ref=-59, trigger_interval_ms=400.0, trigger_window_ms=10000.0,
        trigger_kinds=("single_click", "double_click", "triple_click", "long_press")),
    "ruuvi_raw2": TagProfile(
        name="ruuvi_raw2", heartbeat_ms=1285.0, frame_type=FRAME_RUUVI_RAW2,
        tx_power_ref=-55, has_seq=True, has_battery=True, has_baro=True),
}


@dataclass
class Blink:
    """One advertising event as the tag emits it (before any receiver)."""
    t_ms: int
    mac: str
    frame_type: int
    tx_power_ref: int | None
    trigger_kind: str | None = None      # None = heartbeat frame
    seq: int | None = None
    battery_pct: float | None = None
    pressure_pa: float | None = None     # stamped once per blink by the engine
    event_counter: int | None = None     # future blessed tags only


@dataclass
class Press:
    at_ms: int
    kind: str = "single_click"


@dataclass
class TagActor:
    mac: str                              # canonical AA:BB:CC:DD:EE:FF
    profile: TagProfile
    tag_type: str                         # PANIC | PERSONNEL | ASSET
    label: str
    rtls_tag_id: int
    owner_client_id: str
    carry_height_m: float
    knots: list[tuple[int, float, float, float]]   # (t_ms, x, y, z) sorted
    presses: list[Press] = field(default_factory=list)
    vanish_windows: list[tuple[int, int]] = field(default_factory=list)
    battery_start_pct: float | None = None
    battery_decay_pct_per_h: float = 0.0
    baro_offset_pa: float = 0.0
    phase_ms: float = 0.0                 # heartbeat phase (de-syncs the fleet)

    # ------------------------------------------------------------- position

    def position(self, t_ms: int) -> tuple[float, float, float]:
        k = self.knots
        if t_ms <= k[0][0]:
            return k[0][1:]
        if t_ms >= k[-1][0]:
            return k[-1][1:]
        # knots are few (tens); linear scan is fine and obviously correct
        for i in range(len(k) - 1):
            t0, x0, y0, z0 = k[i]
            t1, x1, y1, z1 = k[i + 1]
            if t0 <= t_ms <= t1:
                if t1 == t0:
                    return (x1, y1, z1)
                f = (t_ms - t0) / (t1 - t0)
                return (x0 + f * (x1 - x0), y0 + f * (y1 - y0), z0 + f * (z1 - z0))
        return k[-1][1:]

    def battery_pct(self, t_ms: int) -> float | None:
        if not self.profile.has_battery or self.battery_start_pct is None:
            return None
        pct = self.battery_start_pct - self.battery_decay_pct_per_h * (t_ms / 3600e3)
        return round(max(pct, 1.0), 1)

    def vanished(self, t_ms: int) -> bool:
        return any(a <= t_ms < b for a, b in self.vanish_windows)

    # -------------------------------------------------------- blink schedule

    def blink_schedule(self, duration_ms: int) -> list[Blink]:
        """The tag's full advertising timeline for the run, precomputed.

        Heartbeats tick at the profile interval from the actor's phase
        offset; a press replaces the heartbeat stream with the trigger burst
        for the trigger window (the BC011 behavior); presses landing inside
        an active window are ignored (the tag can't re-trigger mid-window —
        the receiver/server dedupe design leans on this).
        """
        p = self.profile
        bursts: list[tuple[int, int, str]] = []
        for press in sorted(self.presses, key=lambda e: e.at_ms):
            if p.trigger_window_ms is None:
                continue  # profile has no button
            if bursts and press.at_ms < bursts[-1][1]:
                continue  # mid-window re-press: physically dropped
            bursts.append((press.at_ms, int(press.at_ms + p.trigger_window_ms), press.kind))

        blinks: list[Blink] = []
        seq = 0

        def in_burst(t: float) -> bool:
            return any(b0 <= t < b1 for b0, b1, _ in bursts)

        t = self.phase_ms
        while t < duration_ms:
            if not in_burst(t):
                blinks.append(self._blink(int(t), None, seq))
                seq += 1
            t += p.heartbeat_ms

        for b0, b1, kind in bursts:
            t = float(b0)
            while t < min(b1, duration_ms):
                blinks.append(self._blink(int(t), kind, seq))
                seq += 1
                t += p.trigger_interval_ms

        blinks.sort(key=lambda blk: blk.t_ms)
        # renumber seq in emission order, then drop vanished stretches
        for i, blk in enumerate(blinks):
            if blk.seq is not None:
                blk.seq = i & 0xFFFF
        return [b for b in blinks if not self.vanished(b.t_ms)]

    def _blink(self, t_ms: int, trigger_kind: str | None, seq: int) -> Blink:
        return Blink(
            t_ms=t_ms, mac=self.mac, frame_type=self.profile.frame_type,
            tx_power_ref=self.profile.tx_power_ref, trigger_kind=trigger_kind,
            seq=seq if self.profile.has_seq else None,
            battery_pct=self.battery_pct(t_ms))


# ------------------------------------------------------------ timeline build

def build_knots(building: VirtualBuilding, start: tuple[float, float, int],
                waypoints: list[tuple[float, float, int]], speed_mps: float,
                dwell_ms: int, carry_height_m: float, duration_ms: int,
                loop: bool, climb_mps: float = 0.5) -> list[tuple[int, float, float, float]]:
    """Route start -> each waypoint (dwelling at each), optionally looping,
    into interpolation knots. z = floor z + carry height; floor transitions
    ramp z at climbing speed inside the stairwell."""

    def z_of(floor: int) -> float:
        return building.floor_z(floor) + carry_height_m

    knots: list[tuple[int, float, float, float]] = []
    t = 0.0
    cur = start
    knots.append((0, start[0], start[1], z_of(start[2])))

    targets = list(waypoints)
    if not targets:
        return knots

    guard = 0
    while t < duration_ms and guard < 10000:
        for wp in targets:
            route = building.route(cur, wp)
            for i in range(1, len(route)):
                x0, y0, f0 = route[i - 1]
                x1, y1, f1 = route[i]
                horiz = math.hypot(x1 - x0, y1 - y0)
                climb = abs(z_of(f1) - z_of(f0))
                dt = (horiz / speed_mps + climb / climb_mps) * 1000.0
                t += dt
                knots.append((int(t), x1, y1, z_of(f1)))
                if t >= duration_ms:
                    return knots
            t += dwell_ms
            knots.append((int(t), wp[0], wp[1], z_of(wp[2])))
            cur = wp
            if t >= duration_ms:
                return knots
        if not loop:
            break
        guard += 1
    return knots
