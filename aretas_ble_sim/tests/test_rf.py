"""RF model: determinism, monotonic attenuation, bias stability, PDR."""

import random

from aretas_ble_sim.rf import RfModel, RfParams


def test_structural_determinism(building):
    m1 = RfModel(building, RfParams(), seed=99)
    m2 = RfModel(building, RfParams(), seed=99)
    rx = building.receivers[0]
    assert m1.receiver_bias(rx.mac) == m2.receiver_bias(rx.mac)
    assert m1.fading(rx.mac, 37, 3.3, 4.4) == m2.fading(rx.mac, 37, 3.3, 4.4)
    m3 = RfModel(building, RfParams(), seed=100)
    assert m1.receiver_bias(rx.mac) != m3.receiver_bias(rx.mac)


def test_channels_fade_differently(building):
    m = RfModel(building, RfParams(), seed=1)
    rx = building.receivers[0]
    vals = {ch: m.fading(rx.mac, ch, 5.0, 5.0) for ch in (37, 38, 39)}
    assert len(set(vals.values())) == 3


def test_distance_and_slabs_reduce_rssi(building):
    m = RfModel(building, RfParams(fading_db=0.0, receiver_bias_sigma_db=0.0),
                seed=5)
    rx = building.receivers[0]
    near = (rx.x + 1.0, rx.y, rx.z - 1.0)
    farther = (rx.x + 1.8, rx.y + 1.5, 1.2)
    other_floor = (rx.x + 1.0, rx.y, rx.z + 3.0)
    assert m.mean_rssi(near, -59, rx, 37) > m.mean_rssi(farther, -59, rx, 37)
    assert (m.mean_rssi(near, -59, rx, 37) - m.mean_rssi(other_floor, -59, rx, 37)
            >= building.slab_attenuation_db)


def test_pdr_curve_monotone(building):
    m = RfModel(building, RfParams(), seed=1)
    assert m.pdr(-60) > m.pdr(-85) > m.pdr(-95)
    assert m.pdr(-120) == 0.0
    assert m.pdr(-60) <= m.params.pdr_max


def test_sample_reproducible(building):
    rx = building.receivers[0]
    pos = (rx.x + 2.0, rx.y + 1.0, 1.2)
    out1 = RfModel(building, RfParams(), 7).sample(pos, -59, rx, random.Random(3))
    out2 = RfModel(building, RfParams(), 7).sample(pos, -59, rx, random.Random(3))
    assert out1 == out2


def test_pressure_tracks_altitude(building):
    m = RfModel(building, RfParams(baro_noise_pa=0.0, baro_weather_amp_pa=0.0),
                seed=1)
    rng = random.Random(1)
    p0 = m.pressure_pa(0, 0.0, 0.0, rng)
    p3 = m.pressure_pa(0, 3.0, 0.0, rng)
    assert abs((p0 - p3) - 3.0 * 11.9) < 0.01
