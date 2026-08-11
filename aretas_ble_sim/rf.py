"""RF propagation model — every term the methodology doc says matters.

rssi = P0(tag)                          log-distance @ 1 m reference
     - 10 n log10(d)                    path loss (n ~ 2.8 indoors)
     - walls/slabs along the ray        building.attenuation_db
     + fading(rx, channel, x, y)        stationary per-channel field, ±fading_db
     + o_i                              per-receiver RX-chain bias (what the
                                        platform's self-calibration recovers)
     + N(0, awgn_sigma)                 fast noise

Reception is then a PDR-vs-RSSI Bernoulli draw (BLE adv single-shot PDR
~0.75-0.9 strong-signal, arXiv 2208.04050), with a hard sensitivity floor.

Channel model: a BLE advertising event transmits on channels 37/38/39
sequentially while each scanner dwells on one channel at a time, so the
channel a given receiver hears a given blink on is ~uniform over the three.
The per-channel stationary fading fields (3 sinusoids each, wavelengths
1.5-6 m) reproduce the 5-10 dB position-dependent spread the literature
blames on advertising-channel rotation (arXiv 2006.09099).

Determinism: structural randomness (bias, fading fields) is derived from
sha256(seed, ...) per receiver/channel so it never depends on call order;
per-blink randomness (channel pick, noise, reception) comes from the
engine's single seeded stream.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .building import Receiver, VirtualBuilding
from .geometry import distance3
from .random_stream import make_stream

ADV_CHANNELS = (37, 38, 39)

# ~11.9 Pa per metre near sea level (methodology LF)
PA_PER_M = 11.9
SEA_LEVEL_PA = 101325.0


@dataclass
class RfParams:
    pathloss_n: float = 2.8
    awgn_sigma_db: float = 2.0
    fading_db: float = 5.0             # peak amplitude of the per-channel field
    receiver_bias_sigma_db: float = 3.0
    pdr_max: float = 0.9
    pdr_mid_dbm: float = -88.0         # RSSI where reception probability halves
    pdr_slope_db: float = 4.0
    hard_floor_dbm: float = -100.0
    default_p0_dbm: float = -59.0      # used when a tag profile has no txPowerRef
    baro_noise_pa: float = 3.0         # BMP390-class relative noise
    baro_weather_amp_pa: float = 150.0
    baro_weather_period_h: float = 8.0

    @classmethod
    def from_dict(cls, d: dict) -> "RfParams":
        p = cls()
        mapping = {"pathlossN": "pathloss_n", "awgnSigmaDb": "awgn_sigma_db",
                   "fadingDb": "fading_db", "receiverBiasSigmaDb": "receiver_bias_sigma_db",
                   "pdrMax": "pdr_max", "pdrMidDbm": "pdr_mid_dbm",
                   "pdrSlopeDb": "pdr_slope_db", "hardFloorDbm": "hard_floor_dbm",
                   "defaultP0Dbm": "default_p0_dbm"}
        for k, v in (d or {}).items():
            attr = mapping.get(k, k)
            if hasattr(p, attr):
                setattr(p, attr, float(v))
        return p


class RfModel:

    def __init__(self, building: VirtualBuilding, params: RfParams, seed: int):
        self.building = building
        self.params = params
        self.seed = seed
        self._bias: dict[int, float] = {}
        self._fields: dict[tuple[int, int], list[tuple[float, float, float, float]]] = {}
        self._weather_phase = make_stream(seed, "weather").uniform(0, 2 * math.pi)

    # ------------------------------------------------------- structural draws

    def receiver_bias(self, mac: int) -> float:
        """o_i — stable per receiver; exported in the record-mode manifest so
        self-calibration tests can verify recovery."""
        if mac not in self._bias:
            rng = make_stream(self.seed, "bias", mac)
            self._bias[mac] = rng.gauss(0.0, self.params.receiver_bias_sigma_db)
        return self._bias[mac]

    def _field(self, mac: int, channel: int) -> list[tuple[float, float, float, float]]:
        key = (mac, channel)
        if key not in self._fields:
            rng = make_stream(self.seed, "fade", mac, channel)
            comps = []
            for _ in range(3):
                theta = rng.uniform(0, 2 * math.pi)
                wavelength = rng.uniform(1.5, 6.0)
                phase = rng.uniform(0, 2 * math.pi)
                amp = rng.uniform(0.5, 1.0) * self.params.fading_db / 2.0
                k = 2 * math.pi / wavelength
                comps.append((k * math.cos(theta), k * math.sin(theta), phase, amp))
            self._fields[key] = comps
        return self._fields[key]

    def fading(self, mac: int, channel: int, x: float, y: float) -> float:
        return sum(a * math.sin(kx * x + ky * y + ph)
                   for kx, ky, ph, a in self._field(mac, channel))

    # --------------------------------------------------------------- sampling

    def pdr(self, rssi: float) -> float:
        p = self.params
        if rssi <= p.hard_floor_dbm:
            return 0.0
        return p.pdr_max / (1.0 + math.exp(-(rssi - p.pdr_mid_dbm) / p.pdr_slope_db))

    def mean_rssi(self, tag_pos: tuple[float, float, float], p0_dbm: float,
                  rx: Receiver, channel: int) -> float:
        """Deterministic part (no AWGN): path loss + structure + fading + bias."""
        d = max(distance3(tag_pos, rx.pos()), 0.3)
        pl = p0_dbm - 10.0 * self.params.pathloss_n * math.log10(d)
        att = self.building.attenuation_db(tag_pos, rx.pos())
        return (pl - att
                + self.fading(rx.mac, channel, tag_pos[0], tag_pos[1])
                + self.receiver_bias(rx.mac))

    def sample(self, tag_pos: tuple[float, float, float], p0_dbm: float | None,
               rx: Receiver, rng: random.Random) -> int | None:
        """One blink at one receiver: returns integer RSSI, or None when the
        advert was not received (PDR draw / below sensitivity)."""
        channel = rng.choice(ADV_CHANNELS)
        p0 = p0_dbm if p0_dbm is not None else self.params.default_p0_dbm
        rssi = self.mean_rssi(tag_pos, p0, rx, channel) + rng.gauss(0.0, self.params.awgn_sigma_db)
        if rssi < self.params.hard_floor_dbm:
            return None
        if rng.random() >= self.pdr(rssi):
            return None
        return round(rssi)

    # -------------------------------------------------------------- barometry

    def pressure_pa(self, sim_ms: int, z_m: float, tag_offset_pa: float,
                    rng: random.Random) -> float:
        """Tag barometer reading: altitude term + slow weather swing + the
        per-tag absolute offset (±50 Pa unit spread) + sensor noise. Absolute
        pressure is useless for floor detection — only differentials against
        reference barometers work — which is exactly what this model forces
        any consumer to do."""
        weather = self.params.baro_weather_amp_pa * math.sin(
            2 * math.pi * sim_ms / (self.params.baro_weather_period_h * 3600e3)
            + self._weather_phase)
        return (SEA_LEVEL_PA - PA_PER_M * z_m + weather + tag_offset_pa
                + rng.gauss(0.0, self.params.baro_noise_pa))
