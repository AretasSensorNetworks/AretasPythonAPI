"""Blink schedules, motion, and the receiver edge behaviors."""

from aretas_ble_sim.actors import TAG_PROFILES, Blink, Press, TagActor
from aretas_ble_sim.building import Receiver
from aretas_ble_sim.receiver import ReceiverConfig, SimReceiver


def _actor(profile="bc011", presses=None, vanish=None):
    return TagActor(
        mac="CC:11:00:00:00:0A", profile=TAG_PROFILES[profile],
        tag_type="PANIC", label="t", rtls_tag_id=1, owner_client_id="c",
        carry_height_m=1.2, knots=[(0, 1.0, 2.0, 1.2)],
        presses=presses or [], vanish_windows=vanish or [])


def _blink(t_ms, trigger=None, mac="CC:11:00:00:00:0A"):
    return Blink(t_ms=t_ms, mac=mac, frame_type=2, tx_power_ref=-59,
                 trigger_kind=trigger)


def _receiver(cfg=None):
    rx = Receiver(mac=90000001, room_id="r", floor=0, x=0, y=0, z=2.4)
    return SimReceiver(rx, cfg or ReceiverConfig(), stagger_ms=0)


# ------------------------------------------------------------------- actors

def test_heartbeat_cadence():
    a = _actor()
    blinks = a.blink_schedule(10_000)
    assert 8 <= len(blinks) <= 10  # ~1022.5 ms interval
    assert all(b.trigger_kind is None for b in blinks)


def test_press_burst_replaces_heartbeats():
    a = _actor(presses=[Press(2000, "single_click")])
    blinks = a.blink_schedule(20_000)
    burst = [b for b in blinks if b.trigger_kind == "single_click"]
    assert len(burst) == 25  # 400 ms x 10 s
    assert burst[0].t_ms == 2000
    # no heartbeats inside the trigger window
    assert not any(b.trigger_kind is None and 2000 <= b.t_ms < 12000
                   for b in blinks)


def test_mid_window_repress_dropped():
    a = _actor(presses=[Press(2000, "single_click"), Press(5000, "single_click")])
    burst = [b for b in a.blink_schedule(30_000) if b.trigger_kind]
    assert len(burst) == 25  # second press physically impossible


def test_vanish_window_silences_tag():
    a = _actor(vanish=[(3000, 6000)])
    blinks = a.blink_schedule(10_000)
    assert not any(3000 <= b.t_ms < 6000 for b in blinks)
    assert any(b.t_ms >= 6000 for b in blinks)


def test_ruuvi_has_seq_and_battery():
    a = _actor(profile="ruuvi_raw2")
    a.battery_start_pct = 90.0
    blinks = a.blink_schedule(5000)
    assert all(b.seq is not None for b in blinks)
    assert all(b.battery_pct == 90.0 for b in blinks)


def test_position_interpolates():
    a = _actor()
    a.knots = [(0, 0.0, 0.0, 1.2), (1000, 10.0, 0.0, 1.2)]
    assert a.position(500) == (5.0, 0.0, 1.2)
    assert a.position(5000) == (10.0, 0.0, 1.2)


# ----------------------------------------------------------------- receiver

def test_rate_cap_keeps_best_rssi():
    r = _receiver()
    r.add_blink(100, _blink(100), -70)
    r.add_blink(300, _blink(300), -60)   # same 500 ms bucket, stronger
    r.add_blink(700, _blink(700), -80)   # next bucket
    batch = r.take_batch(2000)
    assert [s["rssi"] for s in batch["sightings"]] == [-60, -80]
    assert batch["sightings"][0]["ageMs"] == 2000 - 300


def test_batch_respects_interval():
    r = _receiver()                       # stagger 0: first flush due at once
    r.add_blink(100, _blink(100), -60)
    batch = r.take_batch(200)
    assert batch is not None and batch["batchId"] == 1
    r.add_blink(300, _blink(300), -60)
    assert r.take_batch(500) is None      # interval (1500) not yet elapsed
    batch = r.take_batch(1700)
    assert batch is not None and batch["batchId"] == 2
    assert r.take_batch(3300) is None     # buffer empty: no empty batches


def test_overflow_flush_at_max_batch():
    r = _receiver(ReceiverConfig(max_batch=4))
    for i in range(4):
        mac = f"CC:11:00:00:01:{i:02X}"
        r.add_blink(10 + i, _blink(10 + i, mac=mac), -60)
    batch = r.take_batch(20)              # before the interval, but full
    assert batch is not None and len(batch["sightings"]) == 4


def test_trigger_collapses_burst_to_one_event():
    r = _receiver()
    events = []
    for k in range(25):                   # the full 10 s burst
        ev = r.add_blink(1000 + k * 400, _blink(1000 + k * 400, "single_click"), -60)
        if ev:
            events.append(ev)
    assert len(events) == 1
    ev = events[0]
    assert ev["eventRef"] == "CC:11:00:00:00:0A:1"
    assert ev["eventType"] == 0 and ev["triggerKind"] == "single_click"
    assert ev["attempt"] == 1 and ev["firstSeenAgeMs"] == 0


def test_different_trigger_mid_window_reports():
    r = _receiver()
    e1 = r.add_blink(1000, _blink(1000, "single_click"), -60)
    e2 = r.add_blink(1400, _blink(1400, "double_click"), -60)
    assert e1 and e2 and e1["eventRef"] != e2["eventRef"]
    assert e2["eventType"] == 1


def test_rearm_after_gap_new_event():
    r = _receiver()
    assert r.add_blink(1000, _blink(1000, "single_click"), -60)
    assert r.add_blink(1400, _blink(1400, "single_click"), -60) is None
    # >= 2.5 s trigger gap re-arms
    ev = r.add_blink(4000, _blink(4000, "single_click"), -60)
    assert ev and ev["eventRef"].endswith(":2")


def test_heartbeat_resume_rearms():
    r = _receiver()
    assert r.add_blink(1000, _blink(1000, "single_click"), -60)
    r.add_blink(2400, _blink(2400), -60)  # heartbeat after >= 1.2 s silence
    ev = r.add_blink(2600, _blink(2600, "single_click"), -60)
    assert ev is not None


def test_retransmit_backoff_until_ack():
    r = _receiver()
    ev = r.add_blink(1000, _blink(1000, "single_click"), -60)
    assert r.due_retransmits(1500) == []
    due = r.due_retransmits(3000)         # first backoff: 2 s
    assert len(due) == 1
    assert due[0]["attempt"] == 2
    assert due[0]["firstSeenAgeMs"] == 2000
    assert r.due_retransmits(3500) == []  # next backoff: 4 s
    assert len(r.due_retransmits(7000)) == 1
    assert r.on_ack(ev["eventRef"])       # ack clears the journal
    assert r.due_retransmits(60_000) == []
    assert not r.on_ack(ev["eventRef"])   # idempotent
