"""Run a scenario. From the AretasPythonAPI repo root:

    # golden trace / free-run (default transport: record)
    python -m aretas_ble_sim.run_sim --scenario aretas_ble_sim/samples/walkthrough.scenario.yaml

    # live against the real MQTT ingest (tags must be registered — see
    # register_tags.py — and the account must own the receiver MACs)
    python -m aretas_ble_sim.run_sim --scenario ... --transport mqtt --config config.cfg

    # processing-side bypass straight into RabbitMQ (enriched payloads)
    python -m aretas_ble_sim.run_sim --scenario ... --transport rabbitmq --config config.cfg

    # assertion mode (CI): score against the platform, JSON report, exit code
    python -m aretas_ble_sim.run_sim --scenario ... --transport mqtt --score report.json

config.cfg keys (this repo's config.ini/config.cfg conventions):
[MQTT] mqtt_broker, mqtt_port, mqtt_username, mqtt_password
[RABBITMQ] rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password
[ARETAS] API_URL, API_USERNAME, API_PASSWORD           (scoring + registration)
"""

from __future__ import annotations

import argparse
import configparser
import json
import logging
import sys
import time
from pathlib import Path

from .engine import SimEngine
from .scenario import load_scenario
from .transports import (Enricher, MqttTransport, MultiTransport, NullTransport,
                         RabbitTransport, RecordTransport, Transport)

log = logging.getLogger("aretas_ble_sim")


def build_transport(args, scenario, manifest: dict) -> Transport:
    enricher = Enricher(scenario.registry())
    transports: list[Transport] = []

    if args.transport == "mqtt" or args.transport == "rabbitmq":
        cfg = configparser.ConfigParser()
        if not cfg.read(args.config):
            sys.exit(f"Cannot read config file: {args.config}")

    if args.transport == "mqtt":
        transports.append(MqttTransport(
            host=cfg.get("MQTT", "mqtt_broker"),
            port=cfg.getint("MQTT", "mqtt_port"),
            username=cfg.get("MQTT", "mqtt_username"),
            password=cfg.get("MQTT", "mqtt_password"),
            receiver_macs=scenario.receiver_macs))
    elif args.transport == "rabbitmq":
        transports.append(RabbitTransport(
            host=cfg.get("RABBITMQ", "rabbitmq_host"),
            port=cfg.getint("RABBITMQ", "rabbitmq_port"),
            username=cfg.get("RABBITMQ", "rabbitmq_username"),
            password=cfg.get("RABBITMQ", "rabbitmq_password"),
            enricher=enricher))
    elif args.transport == "null":
        transports.append(NullTransport())

    if args.transport == "record" or args.record_dir:
        out = Path(args.record_dir or f"ble-sim-out/{scenario.name}")
        transports.append(RecordTransport(out, enricher, manifest))
        log.info("Recording golden trace to %s", out)

    return transports[0] if len(transports) == 1 else MultiTransport(transports)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Aretas BLE tag simulator")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--transport", choices=["record", "mqtt", "rabbitmq", "null"],
                    default="record")
    ap.add_argument("--record-dir", default=None,
                    help="also record a golden trace (implied by --transport record)")
    ap.add_argument("--config", default="config.cfg",
                    help="broker/API credentials")
    ap.add_argument("--speedup", type=float, default=None,
                    help="time acceleration; 0 = free-run (default: 1 for mqtt, else 0)")
    ap.add_argument("--seed", type=int, default=None, help="override scenario seed")
    ap.add_argument("--duration", type=float, default=None,
                    help="override scenario durationS")
    ap.add_argument("--epoch-ms", type=int, default=None,
                    help="override wire-time origin (fix for reproducible traces)")
    ap.add_argument("--score", default=None, metavar="REPORT_JSON",
                    help="assertion mode: score against the platform REST API")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    scenario = load_scenario(args.scenario)
    if args.seed is not None:
        scenario.seed = args.seed
    if args.duration is not None:
        scenario.duration_ms = int(args.duration * 1000)

    speedup = args.speedup
    if speedup is None:
        speedup = 1.0 if args.transport == "mqtt" else 0.0
    if args.transport == "mqtt" and speedup != 1.0:
        log.warning("speedup=%s against the real ingest: the platform stamps "
                    "receipt time with its own wall clock, so accelerated "
                    "ageMs semantics compress", speedup)

    epoch_ms = args.epoch_ms if args.epoch_ms is not None else scenario.epoch_ms
    if epoch_ms is None:
        epoch_ms = int(time.time() * 1000)

    # engine is built first so the manifest can include the receiver biases
    engine = SimEngine(scenario, NullTransport(), epoch_ms, speedup)
    transport = build_transport(args, scenario, engine.manifest())
    engine.transport = transport

    scorer = None
    if args.score:
        from .score import Scorer
        scorer = Scorer(args.config, scenario, engine, args.score)
        scorer.start()
        engine.wall_hooks.append(scorer.on_tick)

    log.info("Scenario '%s': %d tags, %d receivers, %ds sim, seed %d, "
             "transport %s, speedup %s", scenario.name, len(scenario.actors),
             len(scenario.receiver_macs), scenario.duration_ms // 1000,
             scenario.seed, args.transport, speedup)

    try:
        summary = engine.run()
    finally:
        transport.close()

    log.info("Done: %d blinks -> %d receptions; %d batches, %d events "
             "(+%d retransmits), %d acks; transport counters %s",
             summary.blinks, summary.receptions, summary.batches,
             summary.events, summary.retransmits, summary.acks,
             summary.counters)

    if scorer is not None:
        report = scorer.finish()
        print(json.dumps(report, indent=2))
        return 0 if report["pass"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
