"""Assertion-mode scoring (CI-able): did the platform see what we simulated?

Every section FEATURE-DETECTS its endpoint — a 404 marks the section
"skipped" (never a failure) and stops further polling, so the same command
works against any server generation. Ingest-level scoring needs only
`blereceivers/coverage` (lastSighting / sightingsPerMin); when the live
tag-state and event endpoints are available, the room-accuracy and
assist-request-latency sections light up with no changes here.

Report shape (JSON, non-zero exit on a scored-threshold miss):

{
  "pass": true,
  "thresholds": {...},
  "ingest": {"receiversHeard": 18, "receiversExpected": 19, ...},
  "rtls":   {"skipped": "endpoint not available (404)"} | {...scores},
  "events": {"skipped": "endpoint not available (404)"} | {...scores}
}

Uses the repo's APIConfig/APIAuth (run from the AretasPythonAPI root).
"""

from __future__ import annotations

import json
import logging
import statistics
import time

import requests

log = logging.getLogger(__name__)

DEFAULT_THRESHOLDS = {
    "ingestCoverageMin": 0.9,     # fraction of sim receivers the platform heard
    "roomAccuracyMin": 0.85,      # only enforced when live tag state responds
    "assistDetectionMin": 1.0,    # only enforced when the events endpoint responds
    "assistLatencyP95MaxS": 15.0, # the product's end-to-end latency budget
}

POLL_INTERVAL_S = 5.0


class Scorer:

    def __init__(self, config_path: str, scenario, engine, report_path: str,
                 thresholds: dict | None = None):
        # repo-root flat modules (auth.py / api_config.py) — import here so the
        # sim core never needs API credentials
        from api_config import APIConfig
        from auth import APIAuth

        config = APIConfig(config_path)
        auth = APIAuth(config)
        token = auth.get_token(refresh_if_expired=True)
        if token is None:
            raise RuntimeError("Could not authenticate against the REST API for scoring")
        self.api_url = config.get_api_url()
        self.headers = {"Authorization": "Bearer " + token}

        self.scenario = scenario
        self.engine = engine
        self.report_path = report_path
        self.thresholds = dict(DEFAULT_THRESHOLDS, **(thresholds or {}))

        self.started_ms = 0
        self.coverage_before: dict[int, dict] = {}
        self.live_available: bool | None = None   # None = untested (feature-detect)
        self.room_samples: list[bool] = []
        self.pos_errors_m: list[float] = []
        self._last_poll_wall = 0.0

        # Live-mode identity/time bridges. Against the real ingest the
        # platform speaks ITS OWN tag ids (the registry's rtlsTagId, stamped
        # by the monitor) and wall-clock timestamps, while the engine's
        # truth uses seed-derived sim ids and the scenario's pinned epoch —
        # these maps translate between the two worlds. Empty maps degrade to
        # identity (bypass/record modes, where the fabricated ids ARE the
        # wire ids).
        self.sim_to_platform: dict[int, int] = {}
        self.platform_to_sim: dict[int, int] = {}
        # first/last (wall_ms, sim_ms) tick pair -> empirical wall<->sim slope
        self._sim_anchor_first: tuple[float, int] | None = None
        self._sim_anchor_last: tuple[float, int] | None = None

        # When receivers are PLACED on registered floor plans (provision.py's
        # placement step), solved positions come back in the building-map
        # frame: image metres, origin at the image's top-left, y increasing
        # DOWN the image. Truth is world metres with y up — convert through
        # the building's floorplans[] mapping so position error compares
        # like with like. No floor plans = presence-only install; positions
        # then aren't meaningful and the raw comparison stays as-is.
        self._plans_by_floor: dict[int, dict] = {
            fp["floor"]: fp for fp in (scenario.building.floorplans or [])}

    # ------------------------------------------------------------------ REST

    def _get(self, path: str, params: dict | None = None):
        r = requests.get(self.api_url + path, params=params or {},
                         headers=self.headers, timeout=30)
        if r.status_code == 404:
            return None                      # feature-detect: not deployed
        r.raise_for_status()
        return r.json() if r.content else []

    def _coverage(self) -> dict[int, dict]:
        items = self._get("blereceivers/coverage")
        if items is None:
            return {}
        return {int(i["mac"]): i for i in items}

    # ------------------------------------------------------------- lifecycle

    def start(self):
        self.started_ms = int(time.time() * 1000)
        try:
            self.coverage_before = self._coverage()
        except requests.RequestException as e:
            log.warning("Coverage snapshot failed (%s) — ingest scoring degraded", e)

        # learn the platform's tag ids for the scenario macs (the ids the
        # monitor stamps onto every forwarded record)
        try:
            tags = self._get("bletags/list") or []
            by_mac = {t.get("macAddress"): int(t["rtlsTagId"])
                      for t in tags if t.get("rtlsTagId")}
            for s in self.scenario.specs:
                pid = by_mac.get(s.mac)
                if pid is not None and pid != s.rtls_tag_id:
                    self.sim_to_platform[s.rtls_tag_id] = pid
                    self.platform_to_sim[pid] = s.rtls_tag_id
            if self.sim_to_platform:
                log.info("Scoring with %d platform tag id(s) mapped from the registry",
                         len(self.sim_to_platform))
        except requests.RequestException as e:
            log.warning("bletags/list failed (%s) — scoring with sim tag ids", e)

    def on_tick(self, sim_ms: int, epoch_ms: int):
        """Engine wall hook: poll live tag state while the scenario runs.
        Feature-detected — one 404 disables further polling."""
        # anchor the wall<->sim mapping on every tick, BEFORE any gate —
        # the events section needs it even when live tag state is absent
        now_ms = time.time() * 1000
        if self._sim_anchor_first is None:
            self._sim_anchor_first = (now_ms, sim_ms)
        self._sim_anchor_last = (now_ms, sim_ms)

        if self.live_available is False:
            return
        now = time.monotonic()
        if now - self._last_poll_wall < POLL_INTERVAL_S:
            return
        self._last_poll_wall = now

        try:
            states = self._get("bletagstate/live")
        except requests.RequestException as e:
            log.warning("bletagstate/live poll failed: %s", e)
            return
        if states is None:
            self.live_available = False
            log.info("bletagstate/live 404 — live tag state not available on this server, rtls scoring skipped")
            return
        self.live_available = True

        truth = self.engine.truth_at(sim_ms)
        for st in states:
            pid = int(st.get("tagId", -1))
            t = truth.get(self.platform_to_sim.get(pid, pid))
            if t is None or t["vanished"]:
                continue
            nearest = st.get("nearestReceiverMac")
            if nearest is not None:
                self.room_samples.append(int(nearest) == t["nearestReceiverMac"])
            if st.get("x") is not None and st.get("y") is not None:
                tx, ty = self._truth_to_map_frame(t)
                dx, dy = st["x"] - tx, st["y"] - ty
                self.pos_errors_m.append((dx * dx + dy * dy) ** 0.5)

    def _truth_to_map_frame(self, t: dict) -> tuple[float, float]:
        """World-metre truth -> the registered floor plan's map frame
        (image px / pxPerM, y down). Identity when the tag's floor has no
        floor plan — matching the platform, which then has no frame either."""
        fp = self._plans_by_floor.get(t.get("floor"))
        if fp is None:
            return t["x"], t["y"]
        img_x = fp["originPx"][0] + t["x"] * fp["pxPerM"]
        img_y = fp["originPx"][1] - t["y"] * fp["pxPerM"]
        return img_x / fp["pxPerM"], img_y / fp["pxPerM"]

    # --------------------------------------------------------------- scoring

    def finish(self) -> dict:
        th = self.thresholds
        report = {"scenario": self.scenario.name,
                  "startedMs": self.started_ms,
                  "finishedMs": int(time.time() * 1000),
                  "thresholds": th}
        failures: list[str] = []

        report["ingest"] = self._score_ingest(failures)
        report["discovery"] = self._score_discovery(failures)
        report["rtls"] = self._score_rtls(failures)
        report["events"] = self._score_events(failures)

        report["failures"] = failures
        report["pass"] = not failures
        with open(self.report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            f.write("\n")
        return report

    def _score_ingest(self, failures: list[str]) -> dict:
        # the tail of the run is still in flight at finish time (receiver
        # batch cadence + monitor + store worker) — when the first poll is
        # short, settle briefly and re-poll before calling it a miss
        known = unknown = audible = heard = []
        frac = 0.0
        for attempt in range(3):
            try:
                after = self._coverage()
            except requests.RequestException as e:
                failures.append(f"coverage query failed: {e}")
                return {"error": str(e)}
            if not after:
                failures.append("blereceivers/coverage unavailable — are the BLE registry endpoints available on this server?")
                return {"skipped": "endpoint not available (404)"}

            known = [m for m in self.scenario.receiver_macs if m in after]
            unknown = [m for m in self.scenario.receiver_macs if m not in after]

            # only receivers that actually heard a REGISTERED tag can produce a
            # stored sighting — the sim's RF ground truth is the denominator
            # (unregistered-tag sightings are correctly dropped at ingest, and a
            # receiver out of RF range of every registered tag stays silent)
            audible = [m for m in known if m in self.engine.receivers_heard_registered]
            # margin: stored timestamps are receivedTime - ageMs, so a
            # sighting heard in the run's first seconds can stamp slightly
            # BEFORE started_ms (receiver batch interval + clock skew)
            floor_ms = self.started_ms - 15000
            heard = [m for m in audible
                     if (after[m].get("lastSighting") or 0) >= floor_ms]
            frac = len(heard) / len(audible) if audible else 0.0

            if not audible or frac >= self.thresholds["ingestCoverageMin"] or attempt == 2:
                break
            log.info("ingest coverage %.2f below threshold — settling 5 s for late batches", frac)
            time.sleep(5.0)
        result = {"receiversExpected": len(self.scenario.receiver_macs),
                  "receiversKnownToPlatform": len(known),
                  "receiversUnknownToPlatform": unknown,
                  "receiversAudible": len(audible),
                  "receiversHeard": len(heard),
                  "coverageFraction": round(frac, 3)}
        if not known:
            failures.append("none of the scenario's receiver MACs exist in the "
                            "account — run provision.py first")
        elif not audible:
            failures.append("no receiver was in RF range of a registered tag — "
                            "check the scenario's tag/receiver layout")
        elif frac < self.thresholds["ingestCoverageMin"]:
            failures.append(f"ingest coverage {frac:.2f} < "
                            f"{self.thresholds['ingestCoverageMin']} "
                            f"(heard {len(heard)}/{len(audible)} audible receivers)")
        return result

    def _score_discovery(self, failures: list[str]) -> dict:
        """Scenario tags marked registered:false must surface in the
        discovered-tags list (they were deliberately dropped at ingest)."""
        expected = [s.mac for s in self.scenario.specs if not s.registered]
        if not expected:
            return {"skipped": "scenario has no unregistered tags"}
        try:
            r = requests.get(self.api_url + "bletags/discovered",
                             headers=self.headers, timeout=30)
        except requests.RequestException as e:
            failures.append(f"discovered query failed: {e}")
            return {"error": str(e)}
        if r.status_code == 404:
            return {"skipped": "endpoint not available (404)"}
        if r.status_code == 401:
            return {"skipped": "account cannot read discovered tags (401 — needs canWrite)"}
        r.raise_for_status()
        seen = {d.get("mac") for d in (r.json() or [])}
        missing = [m for m in expected if m not in seen]
        result = {"expected": expected, "found": len(expected) - len(missing),
                  "missing": missing}
        if missing:
            failures.append(f"unregistered tag(s) never reached the discovered "
                            f"list: {missing}")
        return result

    def _score_rtls(self, failures: list[str]) -> dict:
        if not self.live_available:
            return {"skipped": "endpoint not available (404)"}
        if not self.room_samples:
            # the endpoint ships (and returns []) before the solver does —
            # empty-throughout means "no solver yet", not a failure
            return {"skipped": "endpoint live but returned no tag states "
                               "(solver not running yet)"}
        acc = sum(self.room_samples) / len(self.room_samples)
        result = {"samples": len(self.room_samples),
                  "roomAccuracy": round(acc, 3),
                  "meanPositionErrorM": round(statistics.fmean(self.pos_errors_m), 2)
                  if self.pos_errors_m else None}
        if acc < self.thresholds["roomAccuracyMin"]:
            failures.append(f"room accuracy {acc:.2f} < "
                            f"{self.thresholds['roomAccuracyMin']}")
        return result

    def _wall_of(self, truth_t_ms: int) -> float:
        """Map a truth timestamp (scenario epoch base) onto the wall clock.
        Live incidents are stamped with real receipt time, so matching them
        against the oracle needs this bridge. The slope comes from the tick
        anchors (robust to any --speedup); fallback = run start + sim
        elapsed."""
        sim_ms = truth_t_ms - self.engine.epoch_ms
        a, b = self._sim_anchor_first, self._sim_anchor_last
        if a and b and b[1] > a[1]:
            slope = (b[0] - a[0]) / (b[1] - a[1])
            return a[0] + (sim_ms - a[1]) * slope
        speedup = getattr(self.engine, "speedup", 0) or 1.0
        return self.started_ms + sim_ms / speedup

    def _score_events(self, failures: list[str]) -> dict:
        truth_events = self.engine.truth_events()
        if not truth_events:
            return {"skipped": "scenario has no presses"}
        try:
            items = self._get("bleevents/list",
                              {"begin": self.started_ms,
                               "end": int(time.time() * 1000) + 60000})
        except requests.RequestException as e:
            failures.append(f"bleevents/list query failed: {e}")
            return {"error": str(e)}
        if items is None:
            return {"skipped": "endpoint not available (404)"}

        latencies: list[float] = []
        missed = []
        for ev in truth_events:
            # the platform's id + wall clock for this press
            pid = self.sim_to_platform.get(ev["tagId"], ev["tagId"])
            expected_wall = self._wall_of(ev["t"])
            match = None
            for it in items:
                it_t = int(it.get("timestamp", it.get("timestmp", 0)))
                if (int(it.get("tagId", -1)) == pid
                        and int(it.get("eventType", -1)) == ev["eventType"]
                        and abs(it_t - expected_wall) < 30000):
                    match = it
                    break
            if match is None:
                missed.append({"mac": ev["mac"], "t": ev["t"],
                               "expectedWallT": int(expected_wall)})
            else:
                # detection latency = press -> first receiver report landing
                # (detail.reports carry the monitor's receipt stamps); the
                # row timestamp is the derived press time itself, so it only
                # measures press-time accuracy — use it as the fallback
                reports = (match.get("detail") or {}).get("reports") or []
                arrivals = [r.get("receivedTime") for r in reports if r.get("receivedTime")]
                observed = min(arrivals) if arrivals else int(
                    match.get("timestamp", match.get("timestmp", 0)))
                latencies.append((observed - expected_wall) / 1000.0)

        detection = 1.0 - len(missed) / len(truth_events)
        result = {"pressed": len(truth_events),
                  "detected": len(truth_events) - len(missed),
                  "detectionRate": round(detection, 3), "missed": missed}
        if latencies:
            latencies.sort()
            p95 = latencies[max(int(0.95 * len(latencies)) - 1, 0)]
            result["latencyP50S"] = round(statistics.median(latencies), 2)
            result["latencyP95S"] = round(p95, 2)
            if p95 > self.thresholds["assistLatencyP95MaxS"]:
                failures.append(f"assist-request latency p95 {p95:.1f}s > "
                                f"{self.thresholds['assistLatencyP95MaxS']}s")
        if detection < self.thresholds["assistDetectionMin"]:
            failures.append(f"assist-request detection {detection:.2f} < "
                            f"{self.thresholds['assistDetectionMin']}")
        return result
