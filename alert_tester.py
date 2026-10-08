"""End-to-end alert tester: prove that the platform's alerting pipeline fires.

    python alert_tester.py --config config.ini
    python alert_tester.py --config config.ini --type 181 --normal 450 --threshold 1000 --exceed 1500
    python alert_tester.py --config config.ini --duration-trigger 120000 --interval 60
    python alert_tester.py --config config.ini --report report-alert-test.json

The script behaves like a real device that misbehaves for a few minutes:

1. creates a throwaway site location (or uses --location-id) and a simulated device
   with a random, obviously fake MAC,
2. creates an alert on that device: a ceiling threshold on one sensor type, with
   notifications disabled (maxNumAlerts=0) unless --email is given,
3. waits until the ingest accepts the new MAC (the platform refreshes its list of
   known devices every few minutes) and until the alert engine has picked up the
   new alert,
4. sends a few readings at a normal level, at a device-like cadence (--interval,
   default 60 s), then readings above the threshold, then normal readings again,
5. after every exceeding reading polls BOTH the persistent alert log
   (alertlog/listbyid) and the recent-history cache (alerthistory/list) for an
   incident on the simulated MAC, then waits for the return-to-normal reading to
   close it (isActive=False / rtnTimestamp set),
6. prints a report (and writes it as JSON with --report), and — pass, fail or
   Ctrl-C — removes the alert, the alert's log records (unless --keep-history),
   the device and the site location it created.

Exit codes: 0 = the alert fired AND returned to normal, 1 = the alert did not fire
or did not resolve, 2 = setup problem (credentials, out-of-range values, create failed).

Timing: the whole run normally takes 6-12 minutes, most of it waiting for the
platform's periodic device-list refresh and for readings paced at --interval.
Readings are sent with the current time as their timestamp, and the alert
incident's timestamp is the timestamp of the reading that opened it.

Hold time (--duration-trigger, ms): the condition must persist that long before the
incident opens. The tester sends enough exceeding readings to cover it
(ceil(hold / interval) + 1) and reports if the incident opened sooner than the hold
time allows. The platform tolerates about 5 s of slack on the hold, so a hold of
5000 ms or less fires on the first exceeding reading.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
import signal
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

from api_config import APIConfig
from auth import APIAuth
from aretas_client import APIClient
from alert_service import AlertService
from alert_history_service import AlertHistoryService
from alert_log_service import AlertLogService
from device_service import DeviceService
from entities import Alert, AlertLogRecord
from sensor_data_ingest import SensorDataIngest
from sensor_type_info import APISensorTypeInfo
from site_location_service import SiteLocationService
from utils import Utils

log = logging.getLogger("alert_tester")

POLL_INTERVAL_S = 5.0
AUTHMAC_POLL_S = 10.0
FAKE_MAC_MIN = 900_000_000_000
FAKE_MAC_MAX = 999_999_999_999
HOLD_SLACK_MS = 5000  # the engine treats the hold as met within this much of the configured duration


class SetupError(Exception):
    """Raised when the test cannot even be set up (bad credentials, create failures, bad values)."""


@dataclass
class TesterOptions:
    sensor_type: int = 181
    normal_value: float = 450.0
    threshold: float = 1000.0
    exceed_value: float = 1500.0
    interval_s: float = 60.0
    normal_count: int = 3
    exceed_count: int = 2
    duration_trigger_ms: int = 0
    location_id: Optional[str] = None
    timezone: str = "UTC"
    email: Optional[str] = None
    auth_wait_s: float = 420.0
    cache_wait_s: float = 75.0
    fire_timeout_s: float = 180.0
    rtn_timeout_s: float = 180.0
    keep_history: bool = False


@dataclass
class Report:
    started_at_ms: int = 0
    finished_at_ms: int = 0
    outcome: str = "NOT_RUN"           # PASS | FAIL | SETUP_ERROR | INTERRUPTED
    mac: Optional[int] = None
    location_id: Optional[str] = None
    location_created: bool = False
    device_id: Optional[str] = None
    alert_id: Optional[str] = None
    sensor_type: Optional[int] = None
    sensor_type_label: Optional[str] = None
    readings_sent: list = field(default_factory=list)   # {phase, timestamp, value, accepted, message}
    authorized_after_s: Optional[float] = None
    fired: bool = False
    fired_record: Optional[dict] = None
    fire_latency_s: Optional[float] = None               # from the reading that opened it to detection
    fired_before_hold: bool = False
    live_cache_seen: bool = False
    resolved: bool = False
    resolved_record: Optional[dict] = None
    rtn_latency_s: Optional[float] = None
    cleanup: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    def note(self, msg: str):
        log.info(msg)
        self.notes.append(msg)


class AlertTester:
    """Drives one complete create → ingest → verify → clean up cycle."""

    def __init__(self, config: APIConfig, opts: TesterOptions):
        self.opts = opts
        self.auth = APIAuth(config)
        self.client = APIClient(self.auth)
        self.alerts = AlertService(self.auth)
        self.history = AlertHistoryService(self.auth)
        self.alert_log = AlertLogService(self.auth)
        self.devices = DeviceService(self.auth)
        self.sites = SiteLocationService(self.auth)
        self.ingest = SensorDataIngest(self.auth)
        self.report = Report()

        self._client_id: Optional[str] = None
        self._location: Optional[dict] = None
        self._device: Optional[dict] = None
        self._alert: Optional[Alert] = None
        self._alert_saved_at: Optional[float] = None
        self._incident_open = False

    # ------------------------------------------------------------------ setup

    def setup(self):
        rpt = self.report
        rpt.started_at_ms = Utils.now_ms()

        if self.auth.get_token(refresh_if_expired=True) is None:
            raise SetupError("Could not authenticate against the API (check API_URL / credentials)")

        self._validate_values()

        view = self.client.get_client_location_view(invalidate_cache=True)
        if view is None or not view.id:
            raise SetupError("Could not load the account's location view")
        self._client_id = view.id
        known_macs = {int(m) for m in (view.allMacs or [])}
        log.info("Account %s: %d locations, %d known MACs", view.id, len(view.locationSensorViews), len(known_macs))

        self._location = self._ensure_location(view)
        rpt.location_id = self._location['id']

        self._device = self._create_device(known_macs)
        rpt.mac = int(self._device['mac'])
        rpt.device_id = self._device.get('id')

        self._alert = self._create_alert()
        rpt.alert_id = self._alert.id
        self._alert_saved_at = time.monotonic()

    def _validate_values(self):
        o = self.opts
        if not (o.normal_value <= o.threshold < o.exceed_value):
            raise SetupError("Need normal <= threshold < exceed (got normal={}, threshold={}, exceed={})".format(
                o.normal_value, o.threshold, o.exceed_value))
        if o.interval_s < 1:
            raise SetupError("--interval must be at least 1 second")

        info = APISensorTypeInfo(self.auth).get_sensor_type_metadata(o.sensor_type)
        self.report.sensor_type = o.sensor_type
        if info is None:
            self.report.note("Sensor type {} has no metadata on this server; range not validated".format(o.sensor_type))
            return
        self.report.sensor_type_label = "{} ({})".format(info.get('label', '?'), info.get('units', ''))
        log.info("Sensor type %d = %s", o.sensor_type, self.report.sensor_type_label)
        hint = info.get('rangeHint') or {}
        lo, hi = hint.get('min'), hint.get('max')
        if lo is not None and hi is not None:
            for name, v in (("normal", o.normal_value), ("exceed", o.exceed_value)):
                if not (float(lo) <= v <= float(hi)):
                    raise SetupError("{} value {} is outside the ingest range [{}, {}] for type {} — "
                                     "the platform would silently reject it".format(name, v, lo, hi, o.sensor_type))

    def _ensure_location(self, view) -> dict:
        if self.opts.location_id:
            for lsv in view.locationSensorViews:
                if lsv.location.id == self.opts.location_id:
                    log.info("Using existing location '%s' (%s)", lsv.location.description, lsv.location.id)
                    return {'id': lsv.location.id, 'owner': lsv.location.owner,
                            'description': lsv.location.description,
                            'lat': lsv.location.lat, 'lon': lsv.location.lon}
            raise SetupError("Location {} is not in this account".format(self.opts.location_id))

        name = "Alert tester {}".format(time.strftime("%Y-%m-%d %H:%M:%S"))
        body = SiteLocationService.build(owner=self._client_id, description=name, lat=0.0, lon=0.0,
                                         timezone=self.opts.timezone)
        result = self.sites.create(body)
        if not result.get_boolean_response():
            raise SetupError("Site location create failed: {}".format(result.get_message()))
        location = self.sites.find_by_description(self._client_id, name)
        if location is None:
            raise SetupError("Created site location '{}' but could not find it afterwards".format(name))
        self.report.location_created = True
        self.report.note("Created site location '{}' ({})".format(name, location['id']))
        return location

    def _create_device(self, known_macs: set) -> dict:
        for _ in range(5):
            mac = random.randint(FAKE_MAC_MIN, FAKE_MAC_MAX)
            if mac in known_macs:
                continue
            body = DeviceService.build(owner=self._location['id'], mac=mac,
                                       description="Alert tester simulated device",
                                       lat=self._location.get('lat') or 0.0, lon=self._location.get('lon') or 0.0)
            result = self.devices.create(body)
            if result.get_boolean_response():
                device = self.devices.find_by_mac(self._location['id'], mac)
                if device is None:
                    raise SetupError("Created device {} but could not find it afterwards".format(mac))
                self.report.note("Created simulated device MAC {} ({})".format(mac, device.get('id')))
                return device
            msg = result.get_message() or ""
            if "MAC" in msg.upper():
                log.warning("MAC %d rejected (%s) — trying another", mac, msg)
                continue
            raise SetupError("Device create failed: {}".format(msg))
        raise SetupError("Could not find a free MAC after 5 attempts")

    def _create_alert(self) -> Alert:
        o = self.opts
        name = "alert-tester-{}".format(uuid.uuid4().hex[:12])
        notify = o.email is not None
        alert = Alert(
            id="",
            owner=self._client_id,
            name=name,
            description="Temporary alert created by alert_tester.py — safe to delete",
            sensorType=o.sensor_type,
            sensorMacs=str(self._device['mac']),
            thresholdA=float(o.threshold),
            thresholdAType=True,               # ceiling: fire when data > threshold
            thresholdB=float(o.threshold),     # B mirrors A so the time-windowed override can't change the verdict
            thresholdBType=True,
            thresholdBStartTime=-1.0,
            thresholdBEndTime=-1.0,
            durationTrigger=int(o.duration_trigger_ms),
            alertFrequency=60,
            maxNumAlerts=1 if notify else 0,   # 0 = never send a notification; the incident is still recorded
            alertTriggerTTL=3600,
            alertEmails=o.email or "",
            alertSMSes="",
            disabled=False,
        )
        result = self.alerts.save(alert)
        if not result.get_boolean_response():
            raise SetupError("Alert save failed: {}".format(result.get_message()))

        for saved in self.alerts.list() or []:
            if saved.name == name:
                self.report.note("Created alert '{}' ({}) threshold > {} on type {}, hold {} ms, notifications {}".format(
                    name, saved.id, o.threshold, o.sensor_type, o.duration_trigger_ms,
                    "to " + o.email if notify else "off"))
                return saved
        raise SetupError("Saved alert '{}' but it did not appear in alert/list".format(name))

    # ---------------------------------------------------------------- sending

    def _send(self, phase: str, value: float) -> bool:
        ts = Utils.now_ms()
        datum = {'mac': self._device['mac'], 'type': self.opts.sensor_type, 'data': value, 'timestamp': ts}
        result = self.ingest.send_datum_ws(datum, overwritetimestamp=False)
        accepted = bool(result.get_boolean_response())
        self.report.readings_sent.append({'phase': phase, 'timestamp': ts, 'value': value,
                                          'accepted': accepted, 'message': result.get_message()})
        log.info("[%s] sent %.2f @ %d -> %s%s", phase, value, ts, "accepted" if accepted else "REJECTED",
                 "" if accepted else " ({})".format(result.get_message()))
        return accepted

    def _wait_for_authorization(self):
        """Poll the ingest with a normal reading until the platform knows the new MAC.
        The reading that gets accepted counts as the first normal reading."""
        deadline = time.monotonic() + self.opts.auth_wait_s
        t0 = time.monotonic()
        log.info("Waiting for the ingest to accept MAC %d (device list refreshes every few minutes, up to %.0f s)...",
                 self._device['mac'], self.opts.auth_wait_s)
        while True:
            if self._send("normal", self.opts.normal_value):
                self.report.authorized_after_s = round(time.monotonic() - t0, 1)
                self.report.note("Ingest accepted the new MAC after {} s".format(self.report.authorized_after_s))
                return
            last = self.report.readings_sent[-1]['message'] or ""
            if "range" in last.lower() or "type not allowed" in last.lower():
                raise SetupError("Ingest rejected the normal value: {}".format(last))
            if time.monotonic() >= deadline:
                raise SetupError("Ingest never accepted MAC {} within {} s (last reply: {})".format(
                    self._device['mac'], self.opts.auth_wait_s, last))
            time.sleep(AUTHMAC_POLL_S)

    def _sleep_until(self, t_mono: float):
        remaining = t_mono - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)

    # ---------------------------------------------------------------- checking

    def _log_records(self) -> list[AlertLogRecord]:
        start = self.report.started_at_ms - 60_000
        end = Utils.now_ms() + 60_000
        records = self.alert_log.list_by_alert_id(self._alert.id, start, end, limit=1000) or []
        return [r for r in records if int(r.mac) == int(self._device['mac'])]

    def _live_records(self) -> list:
        records = self.history.list_alert_history([self._alert.id], show_dismissed=True) or []
        return [r for r in records if int(r.mac) == int(self._device['mac'])]

    def _check_fired(self) -> bool:
        live = self._live_records()
        if live:
            self.report.live_cache_seen = True
        records = self._log_records()
        if records:
            rec = records[-1]
            self.report.fired = True
            self.report.fired_record = rec.model_dump()
            self._incident_open = bool(rec.isActive)
            return True
        return False

    def _check_resolved(self) -> bool:
        records = self._log_records()
        for rec in records:
            if not rec.isActive and rec.rtnTimestamp > 0:
                self.report.resolved = True
                self.report.resolved_record = rec.model_dump()
                self._incident_open = False
                return True
        live = self._live_records()
        if live and all(getattr(r, 'isResolved', False) for r in live) and not any(r.isActive for r in records):
            # cache says resolved and the log has no open incident (rtnTimestamp may lag)
            self.report.resolved = True
            self.report.resolved_record = records[-1].model_dump() if records else None
            self._incident_open = False
            return True
        return False

    def _poll(self, check, deadline_mono: float) -> bool:
        while True:
            if check():
                return True
            if time.monotonic() >= deadline_mono:
                return False
            time.sleep(min(POLL_INTERVAL_S, max(0.0, deadline_mono - time.monotonic())))

    # -------------------------------------------------------------------- run

    def run(self) -> int:
        o = self.opts
        rpt = self.report
        interval = o.interval_s

        self._wait_for_authorization()

        # the rest of the normal readings, paced like a device
        next_send = time.monotonic() + interval
        for _ in range(max(0, o.normal_count - 1)):
            self._sleep_until(next_send)
            self._send("normal", o.normal_value)
            next_send += interval

        # the alert engine reloads its alert list periodically — don't exceed before it has ours
        earliest_exceed = self._alert_saved_at + o.cache_wait_s
        if earliest_exceed > next_send:
            rpt.note("Holding {:.0f} s more so the alert engine has reloaded the new alert".format(
                earliest_exceed - time.monotonic()))
            next_send = earliest_exceed

        # exceed: enough readings to cover the hold time
        interval_ms = interval * 1000.0
        needed = max(o.exceed_count, int(math.ceil(o.duration_trigger_ms / interval_ms)) + 1)
        rpt.note("Sending {} exceeding reading(s) of {} every {:.0f} s (threshold {}, hold {} ms)".format(
            needed, o.exceed_value, interval, o.threshold, o.duration_trigger_ms))
        first_exceed_ts: Optional[int] = None
        sent = 0
        while sent < needed and not rpt.fired:
            self._sleep_until(next_send)
            self._send("exceed", o.exceed_value)
            sent += 1
            sent_ts = rpt.readings_sent[-1]['timestamp']
            first_exceed_ts = first_exceed_ts or sent_ts
            next_send += interval
            # poll until the next reading is due (or the fire timeout after the last one)
            until = next_send if sent < needed else time.monotonic() + o.fire_timeout_s
            if self._poll(self._check_fired, until):
                rpt.fire_latency_s = round((Utils.now_ms() - rpt.fired_record['timestamp']) / 1000.0, 1)
                opened_after_ms = rpt.fired_record['timestamp'] - first_exceed_ts
                rpt.note("ALERT FIRED: eventId {} opened at {} ({} ms after the first exceeding reading, "
                         "detected {} s after the opening reading){}".format(
                             rpt.fired_record['eventId'], rpt.fired_record['timestamp'], opened_after_ms,
                             rpt.fire_latency_s, "; also visible in the recent-history cache" if rpt.live_cache_seen else ""))
                if o.duration_trigger_ms > HOLD_SLACK_MS and opened_after_ms < o.duration_trigger_ms - HOLD_SLACK_MS:
                    rpt.fired_before_hold = True
                    rpt.note("WARNING: the incident opened {} ms after the first exceeding reading, sooner than the "
                             "{} ms hold time allows".format(opened_after_ms, o.duration_trigger_ms))

        if not rpt.fired:
            rpt.note("ALERT DID NOT FIRE: {} exceeding readings sent, no incident within {:.0f} s of the last one".format(
                sent, o.fire_timeout_s))
            # still send a normal reading so any stopwatch the engine armed is cleared
            self._sleep_until(next_send)
            self._send("normal", o.normal_value)
            return 1

        # return to normal
        rtn_deadline = time.monotonic() + o.rtn_timeout_s
        self._sleep_until(next_send)
        self._send("normal", o.normal_value)
        rtn_sent_ts = rpt.readings_sent[-1]['timestamp']
        next_send += interval
        while not self._poll(self._check_resolved, min(next_send, rtn_deadline)):
            if time.monotonic() >= rtn_deadline:
                break
            self._sleep_until(next_send)
            self._send("normal", o.normal_value)
            next_send += interval

        if rpt.resolved:
            rpt.rtn_latency_s = round((Utils.now_ms() - rtn_sent_ts) / 1000.0, 1)
            rec = rpt.resolved_record or {}
            rpt.note("RETURNED TO NORMAL: eventId {} resolved, rtnTimestamp {} (detected {} s after the normal reading)".format(
                rec.get('eventId'), rec.get('rtnTimestamp'), rpt.rtn_latency_s))
            return 0

        rpt.note("INCIDENT DID NOT RESOLVE within {:.0f} s of the first normal reading".format(o.rtn_timeout_s))
        return 1

    # ---------------------------------------------------------------- cleanup

    def cleanup(self):
        """Remove everything the run created. Each step is attempted even if an earlier one fails."""
        steps = self.report.cleanup

        if self._alert is not None and self._device is not None and self._incident_open:
            # never leave an open incident behind: send a normal reading and give the engine a moment
            log.info("Incident still open — sending a return-to-normal reading before removing the alert")
            try:
                self._send("cleanup-rtn", self.opts.normal_value)
                self._poll(self._check_resolved, time.monotonic() + 90.0)
            except Exception as e:  # noqa: BLE001 — cleanup must keep going
                log.warning("Return-to-normal during cleanup failed: %s", e)
            steps['incident_closed'] = not self._incident_open

        if self._alert is not None:
            if not self.opts.keep_history:
                purged = self.alert_log.purge(self._alert.id, 0)
                steps['alert_log_purged'] = purged
                log.info("Purged %s alert log record(s)", purged)
            result = self.alerts.remove(self._alert)
            steps['alert_removed'] = bool(result.get_boolean_response())
            log.info("Removed alert %s: %s", self._alert.id, result)

        if self._device is not None:
            device = self._device
            if not device.get('id'):
                device = self.devices.find_by_mac(self._location['id'], self._device['mac']) or device
            result = self.devices.remove(device)
            steps['device_removed'] = bool(result.get_boolean_response())
            log.info("Removed device %s: %s", device.get('mac'), result)

        if self._location is not None and self.report.location_created:
            result = self.sites.delete(self._location)
            steps['location_removed'] = bool(result.get_boolean_response())
            log.info("Removed site location %s: %s", self._location['id'], result)

        try:
            self.client.get_client_location_view(invalidate_cache=True)
        except Exception:  # noqa: BLE001
            pass

    # ----------------------------------------------------------------- report

    def print_report(self):
        rpt = self.report
        print("\n=== Alert tester report: {} ===".format(rpt.outcome))
        print("  sensor type : {} {}".format(rpt.sensor_type, rpt.sensor_type_label or ""))
        print("  MAC         : {}".format(rpt.mac))
        print("  alert id    : {}".format(rpt.alert_id))
        print("  readings    : {} sent, {} accepted".format(
            len(rpt.readings_sent), sum(1 for r in rpt.readings_sent if r['accepted'])))
        print("  authorized  : after {} s".format(rpt.authorized_after_s))
        print("  fired       : {}{}".format("yes" if rpt.fired else "NO",
                                            " (eventId {})".format(rpt.fired_record['eventId']) if rpt.fired_record else ""))
        if rpt.fired:
            print("  fire detect : {} s after the opening reading".format(rpt.fire_latency_s))
            print("  live cache  : {}".format("seen" if rpt.live_cache_seen else "not seen"))
        print("  resolved    : {}".format("yes" if rpt.resolved else "NO"))
        if rpt.resolved:
            print("  rtn detect  : {} s after the normal reading".format(rpt.rtn_latency_s))
        if rpt.fired_before_hold:
            print("  WARNING     : incident opened before the hold time elapsed")
        print("  cleanup     : {}".format(rpt.cleanup or "nothing to clean up"))
        print("  elapsed     : {:.0f} s".format((rpt.finished_at_ms - rpt.started_at_ms) / 1000.0))
        print()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create a simulated device + alert, drive readings through it, "
                                            "verify the alert fires and resolves, then clean up.")
    p.add_argument("--config", default="config.ini", help="API config INI (default: config.ini)")
    p.add_argument("--type", type=int, default=181, dest="sensor_type", help="sensor type to alert on (default 181 = CO2 ppm)")
    p.add_argument("--normal", type=float, default=450.0, help="normal reading value (default 450)")
    p.add_argument("--threshold", type=float, default=1000.0, help="alert ceiling threshold (default 1000)")
    p.add_argument("--exceed", type=float, default=1500.0, help="exceeding reading value (default 1500)")
    p.add_argument("--interval", type=float, default=60.0, help="seconds between readings (default 60)")
    p.add_argument("--normal-count", type=int, default=3, help="normal readings before exceeding (default 3)")
    p.add_argument("--exceed-count", type=int, default=2,
                   help="minimum exceeding readings to send; raised automatically to cover the hold time (default 2)")
    p.add_argument("--duration-trigger", type=int, default=0, dest="duration_trigger_ms",
                   help="alert hold time in ms the condition must persist before firing (default 0)")
    p.add_argument("--location-id", default=None, help="put the device in this existing location instead of a throwaway one")
    p.add_argument("--timezone", default="UTC", help="timezone of the throwaway location (default UTC)")
    p.add_argument("--email", default=None,
                   help="also send ONE real notification email to this address (default: notifications off)")
    p.add_argument("--auth-wait", type=float, default=420.0, dest="auth_wait_s",
                   help="max seconds to wait for the ingest to accept the new MAC (default 420)")
    p.add_argument("--cache-wait", type=float, default=75.0, dest="cache_wait_s",
                   help="min seconds between creating the alert and the first exceeding reading (default 75)")
    p.add_argument("--fire-timeout", type=float, default=180.0, dest="fire_timeout_s",
                   help="seconds to wait for the incident after the last exceeding reading (default 180)")
    p.add_argument("--rtn-timeout", type=float, default=180.0, dest="rtn_timeout_s",
                   help="seconds to wait for the incident to resolve (default 180)")
    p.add_argument("--keep-history", action="store_true", help="leave the alert's log records in place after the run")
    p.add_argument("--report", default=None, help="write the JSON report to this path (e.g. report-alert-test.json)")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
    if not args.verbose:
        logging.getLogger("sensor_data_ingest").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    opts = TesterOptions(
        sensor_type=args.sensor_type, normal_value=args.normal, threshold=args.threshold, exceed_value=args.exceed,
        interval_s=args.interval, normal_count=args.normal_count, exceed_count=args.exceed_count,
        duration_trigger_ms=args.duration_trigger_ms, location_id=args.location_id, timezone=args.timezone,
        email=args.email, auth_wait_s=args.auth_wait_s, cache_wait_s=args.cache_wait_s,
        fire_timeout_s=args.fire_timeout_s, rtn_timeout_s=args.rtn_timeout_s, keep_history=args.keep_history,
    )

    try:
        config = APIConfig(args.config)
    except KeyError as e:
        log.error("Config %s is missing the [ARETAS] section / key %s", args.config, e)
        return 2

    tester = AlertTester(config, opts)

    def _on_term(signum, frame):  # make SIGTERM behave like Ctrl-C so cleanup runs
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, _on_term)

    code = 2
    try:
        tester.setup()
        code = tester.run()
        tester.report.outcome = "PASS" if code == 0 else "FAIL"
    except SetupError as e:
        log.error("Setup error: %s", e)
        tester.report.outcome = "SETUP_ERROR"
        tester.report.notes.append(str(e))
        code = 2
    except KeyboardInterrupt:
        log.warning("Interrupted — cleaning up")
        tester.report.outcome = "INTERRUPTED"
        code = 130
    except Exception as e:  # noqa: BLE001 — report it, but still clean up
        log.exception("Unexpected error: %s", e)
        tester.report.outcome = "ERROR"
        tester.report.notes.append(repr(e))
        code = 2
    finally:
        try:
            tester.cleanup()
        except KeyboardInterrupt:
            log.error("Interrupted again during cleanup — some objects may remain (see report)")
        except Exception as e:  # noqa: BLE001
            log.exception("Cleanup error: %s", e)
        tester.report.finished_at_ms = Utils.now_ms()
        tester.print_report()
        if args.report:
            with open(args.report, "w", encoding="utf-8") as fh:
                json.dump(asdict(tester.report), fh, indent=2)
            log.info("Report written to %s", args.report)

    return code


if __name__ == "__main__":
    sys.exit(main())
