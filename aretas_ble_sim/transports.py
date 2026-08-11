"""Emission transports: where the simulated receivers' messages go.

* MqttTransport   — the REAL thing: publishes raw firmware-wire payloads to
                    blesightings/{rxMac} / bleevents/{rxMac} on the broker,
                    indistinguishable from hardware; subscribes each
                    receiver's blecmd/{rxMac} so cloud app-acks close the
                    simulated event journals.
* RabbitTransport — processing-side bypass: publishes the ENRICHED shape
                    (what the platform's ingest service forwards) straight to
                    the processing exchanges. No broker/auth/allowlist
                    needed; mirrors the ingest drop policy so the stream is
                    identical.
* RecordTransport — golden traces: enriched batches/events + ground truth +
                    manifest as JSONL/JSON, for solver regression fixtures —
                    exported here so unit tests and the end-to-end sim can
                    never drift apart.
* NullTransport   — dry runs (counts only).
* MultiTransport  — fan-out (e.g. mqtt + record in one run).

Enrichment (Rabbit/Record) mirrors the ingest service exactly: unknown tag
MACs are dropped, registered-but-disabled dropped, forwarded sightings gain
tagId + ownerClientId, the batch gains receivedTime (= sim wall time;
receivers have no RTC, ageMs is relative to send).
"""

from __future__ import annotations

import json
import logging
import queue
from pathlib import Path

log = logging.getLogger(__name__)


class Transport:
    """Base: counts everything, delivers nothing."""

    def __init__(self):
        self.counters = {"batches": 0, "events": 0, "dropped_unknown": 0,
                         "dropped_disabled": 0}

    def publish_batch(self, t_ms: int, payload: dict):
        self.counters["batches"] += 1

    def publish_event(self, t_ms: int, payload: dict):
        self.counters["events"] += 1

    def publish_status(self, rx_mac: int, online: bool):
        pass

    def record_truth(self, record: dict):
        pass

    def poll_acks(self) -> list[tuple[int, str]]:
        """(receiverMac, eventRef) app-acks received since the last poll."""
        return []

    def close(self):
        pass


class NullTransport(Transport):
    pass


class MultiTransport(Transport):

    def __init__(self, transports: list[Transport]):
        super().__init__()
        self.transports = transports

    def publish_batch(self, t_ms, payload):
        super().publish_batch(t_ms, payload)
        for t in self.transports:
            t.publish_batch(t_ms, payload)

    def publish_event(self, t_ms, payload):
        super().publish_event(t_ms, payload)
        for t in self.transports:
            t.publish_event(t_ms, payload)

    def publish_status(self, rx_mac, online):
        for t in self.transports:
            t.publish_status(rx_mac, online)

    def record_truth(self, record):
        for t in self.transports:
            t.record_truth(record)

    def poll_acks(self):
        acks = []
        for t in self.transports:
            acks += t.poll_acks()
        return acks

    def close(self):
        for t in self.transports:
            t.close()


# --------------------------------------------------------------- enrichment

class Enricher:
    """The ingest service's allowlist policy, replicated for bypass modes.
    registry: canonical MAC -> {rtlsTagId, ownerClientId, enabled}."""

    def __init__(self, registry: dict[str, dict]):
        self.registry = registry

    def enrich_batch(self, t_ms: int, payload: dict, counters: dict) -> dict | None:
        forwarded = []
        for s in payload["sightings"]:
            entry = self.registry.get(s["mac"])
            if entry is None:
                counters["dropped_unknown"] += 1
                continue
            if not entry.get("enabled", False):
                counters["dropped_disabled"] += 1
                continue
            enriched = dict(s)
            enriched["tagId"] = entry["rtlsTagId"]
            enriched["ownerClientId"] = entry["ownerClientId"]
            forwarded.append(enriched)
        if not forwarded:
            return None
        return {"schemaVersion": 1, "receiverMac": payload["receiverMac"],
                "batchId": payload["batchId"], "receivedTime": t_ms,
                "sightings": forwarded}

    def enrich_event(self, t_ms: int, payload: dict, counters: dict) -> dict | None:
        entry = self.registry.get(payload["mac"])
        if entry is None:
            counters["dropped_unknown"] += 1
            return None
        if not entry.get("enabled", False):
            counters["dropped_disabled"] += 1
            return None
        out = dict(payload)
        out["tagId"] = entry["rtlsTagId"]
        out["ownerClientId"] = entry["ownerClientId"]
        out["receivedTime"] = t_ms
        return out


# ------------------------------------------------------------------- record

class RecordTransport(Transport):
    """Golden-trace export. Files in out_dir:

    trace.jsonl    {"t", "kind": "sightings"|"event", "data": <enriched>}
    truth.jsonl    {"t", "kind": "truth"|"truthEvent", ...ground truth}
    manifest.json  seed, epoch, rf params, receiver biases (o_i!), building,
                   tag registry — everything a downstream test needs to
                   re-derive expectations (self-calibration recovery
                   included).
    """

    def __init__(self, out_dir: str | Path, enricher: Enricher, manifest: dict):
        super().__init__()
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.enricher = enricher
        with open(self.out_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
            f.write("\n")
        self._trace = open(self.out_dir / "trace.jsonl", "w", encoding="utf-8")
        self._truth = open(self.out_dir / "truth.jsonl", "w", encoding="utf-8")

    def _line(self, fh, obj: dict):
        fh.write(json.dumps(obj, sort_keys=True) + "\n")

    def publish_batch(self, t_ms, payload):
        enriched = self.enricher.enrich_batch(t_ms, payload, self.counters)
        if enriched is not None:
            super().publish_batch(t_ms, payload)
            self._line(self._trace, {"t": t_ms, "kind": "sightings", "data": enriched})

    def publish_event(self, t_ms, payload):
        enriched = self.enricher.enrich_event(t_ms, payload, self.counters)
        if enriched is not None:
            super().publish_event(t_ms, payload)
            self._line(self._trace, {"t": t_ms, "kind": "event", "data": enriched})

    def record_truth(self, record):
        self._line(self._truth, record)

    def close(self):
        self._trace.close()
        self._truth.close()


# --------------------------------------------------------------------- MQTT

class MqttTransport(Transport):
    """Publishes the raw firmware wire to the MQTT ingest.

    One connection carries every simulated receiver (payload-identical to a
    per-device connection). The account must own the receiver MACs — the
    broker ACL authorizes per {prefix}/{mac} topic — so blecmd is subscribed
    per receiver, never as a wildcard.
    """

    def __init__(self, host: str, port: int, username: str, password: str,
                 receiver_macs: list[int], client_id: str = "aretas-ble-sim"):
        super().__init__()
        import paho.mqtt.client as mqtt

        if not hasattr(mqtt, "CallbackAPIVersion"):
            raise RuntimeError(
                "paho-mqtt >= 2.0 is required (found an older 1.x install): "
                "pip install -U 'paho-mqtt>=2.0'")

        self.receiver_macs = receiver_macs
        self._acks: queue.Queue = queue.Queue()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=client_id)
        self.client.username_pw_set(username, password)
        if port == 8883:
            # matches the monitors' convention (self-signed chain in the fleet)
            self.client.tls_set()
            self.client.tls_insecure_set(True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.connect(host, port, 60)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        log.info("MQTT connected: %s", reason_code)
        subs = [(f"blecmd/{mac}", 1) for mac in self.receiver_macs]
        if subs:
            client.subscribe(subs)
        for mac in self.receiver_macs:
            self.publish_status(mac, True)

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            if data.get("kind") == "eventAck" and "eventRef" in data:
                rx_mac = int(msg.topic.split("/")[1])
                self._acks.put((rx_mac, str(data["eventRef"])))
        except (ValueError, IndexError, UnicodeDecodeError):
            log.warning("Unparseable blecmd message on %s", msg.topic)

    def publish_batch(self, t_ms, payload):
        super().publish_batch(t_ms, payload)
        self.client.publish(f"blesightings/{payload['receiverMac']}",
                            json.dumps(payload), qos=1)

    def publish_event(self, t_ms, payload):
        super().publish_event(t_ms, payload)
        self.client.publish(f"bleevents/{payload['receiverMac']}",
                            json.dumps(payload), qos=1)

    def publish_status(self, rx_mac, online):
        status = {"state": "online" if online else "offline",
                  "fw": "aretas-ble-sim", "buffered": 0, "allowlistVer": -1}
        self.client.publish(f"blestatus/{rx_mac}", json.dumps(status),
                            qos=1, retain=True)

    def poll_acks(self):
        acks = []
        try:
            while True:
                acks.append(self._acks.get_nowait())
        except queue.Empty:
            pass
        return acks

    def close(self):
        for mac in self.receiver_macs:
            self.publish_status(mac, False)
        self.client.loop_stop()
        self.client.disconnect()


# ----------------------------------------------------------------- RabbitMQ

class RabbitTransport(Transport):
    """Ingest bypass for solver-only development: enriched payloads straight
    to the processing exchanges (idempotent declares, matching the platform's
    own topology provisioning)."""

    def __init__(self, host: str, port: int, username: str, password: str,
                 enricher: Enricher, sightings_exchange: str = "ble-sightings",
                 events_exchange: str = "ble-events"):
        super().__init__()
        import pika

        self._pika = pika
        self.enricher = enricher
        self.sightings_exchange = sightings_exchange
        self.events_exchange = events_exchange
        credentials = pika.PlainCredentials(username, password)
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=host, port=port, credentials=credentials, heartbeat=60))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange=sightings_exchange,
                                      exchange_type="fanout", durable=True)
        self.channel.exchange_declare(exchange=events_exchange,
                                      exchange_type="fanout", durable=True)

    def publish_batch(self, t_ms, payload):
        enriched = self.enricher.enrich_batch(t_ms, payload, self.counters)
        if enriched is None:
            return
        super().publish_batch(t_ms, payload)
        self.channel.basic_publish(exchange=self.sightings_exchange,
                                   routing_key="", body=json.dumps(enriched))

    def publish_event(self, t_ms, payload):
        enriched = self.enricher.enrich_event(t_ms, payload, self.counters)
        if enriched is None:
            return
        super().publish_event(t_ms, payload)
        self.channel.basic_publish(
            exchange=self.events_exchange, routing_key="",
            body=json.dumps(enriched),
            properties=self._pika.BasicProperties(delivery_mode=2))

    def close(self):
        try:
            self.connection.close()
        except Exception:
            pass
