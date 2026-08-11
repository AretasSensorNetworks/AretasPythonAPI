"""
aretas_ble_sim — a hardware-free simulator for the Aretas BLE tag /
asset-tracking / Assist Button subsystem.

Simulates a building full of Aretas BLE receivers and battery BLE tags at
the RSSI-sighting level: virtual buildings (JSON + generated floor plans),
an indoor RF propagation model, scripted tag actors (walking personnel,
parked assets, assist-button presses), and faithful receiver-side behavior
(sighting batching, trigger-burst collapse, event retransmit-until-ack).
Emissions are real wire payloads — publish them to the live MQTT ingest,
bypass straight into the processing queues, or record deterministic
"golden trace" files for solver regression tests.

Everything is seed-deterministic: the same scenario + seed + epoch produce
byte-identical traces.

Run from the AretasPythonAPI repo root (flat-module repo — auth.py etc.
resolve from there):

    python -m aretas_ble_sim.building_gen --out-dir aretas_ble_sim/samples
    python -m aretas_ble_sim.run_sim --scenario aretas_ble_sim/samples/walkthrough.scenario.yaml
"""

__version__ = "0.1.0"
