#!/usr/bin/env python3
"""
Adversarial Fault Injection Tool for SDV HVAC Monitoring Pipeline.

Executes automated fault-injection test cases against the edge gateway,
verifying deterministic degradation and fail-safe transitions across
the cyber-physical boundary without uncaught runtime exceptions.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("FaultInjector")


FAULT_SUITES = [
    {
        "id": "FI-01",
        "name": "Timestamp Latency Exceedance (Stale State Trigger)",
        "payload": {
            "vehicle_id": "vehicle_01",
            "timestamp": "2026-01-01T00:00:00.000000Z",  # Extensively in past
            "measurements": {
                "scd30": {"co2_ppm": 450.0, "temperature_c": 22.0, "relative_humidity_pct": 50.0, "status": "OK"},
                "dht22": {"temperature_c": 22.1, "relative_humidity_pct": 50.2, "status": "OK"}
            },
            "actuation_feedback": {"fan_duty_pct": 20.0, "fan_rpm": 800, "status": "RUNNING"}
        },
        "expected_state": "STALE"
    },
    {
        "id": "FI-02",
        "name": "Transducer Divergence (Degraded State Trigger)",
        "payload": {
            "vehicle_id": "vehicle_01",
            "timestamp": None,  # Will be replaced with current UTC
            "measurements": {
                "scd30": {"co2_ppm": 520.0, "temperature_c": 21.0, "relative_humidity_pct": 48.0, "status": "OK"},
                "dht22": {"temperature_c": 24.2, "relative_humidity_pct": 49.0, "status": "OK"}  # Delta-T = 3.2 C
            },
            "actuation_feedback": {"fan_duty_pct": 25.0, "fan_rpm": 950, "status": "RUNNING"}
        },
        "expected_state": "DEGRADED"
    },
    {
        "id": "FI-03",
        "name": "Transducer Physical Line Detachment (Fault State Trigger)",
        "payload": {
            "vehicle_id": "vehicle_01",
            "timestamp": None,
            "measurements": {
                "scd30": {"co2_ppm": None, "temperature_c": None, "relative_humidity_pct": None, "status": "DISCONNECTED"},
                "dht22": {"temperature_c": 22.0, "relative_humidity_pct": 50.0, "status": "OK"}
            },
            "actuation_feedback": {"fan_duty_pct": 50.0, "fan_rpm": 1400, "status": "FAILSAFE_ENGAGED"}
        },
        "expected_state": "FAULT"
    },
    {
        "id": "FI-04",
        "name": "Blower Rotor Stall Detection (Actuation Feedback Divergence)",
        "payload": {
            "vehicle_id": "vehicle_01",
            "timestamp": None,
            "measurements": {
                "scd30": {"co2_ppm": 950.0, "temperature_c": 22.0, "relative_humidity_pct": 45.0, "status": "OK"},
                "dht22": {"temperature_c": 22.2, "relative_humidity_pct": 46.0, "status": "OK"}
            },
            "actuation_feedback": {"fan_duty_pct": 75.0, "fan_rpm": 0, "status": "STALL_DETECTED"}  # Commanded 75% but 0 RPM
        },
        "expected_state": "ACTUATION_FAULT"
    },
    {
        "id": "FI-05",
        "name": "Malformed Schema Payload (Ingress Validation Drop)",
        "raw_string": '{"vehicle_id": "vehicle_01", "co2": "INVALID_TYPE", "temperature": "NaN"}',
        "expected_state": "SCHEMA_REJECTION"
    }
]


def run_injection_tests(host: str, port: int, vehicle_id: str):
    """Publish test vectors sequentially to the target broker."""
    client = mqtt.Client(client_id=f"fault_injector_{int(time.time())}")
    topic = f"sdv/{vehicle_id}/telemetry"

    logger.info(f"Connecting to broker at {host}:{port} for fault injection suite...")
    try:
        client.connect(host, port, keepalive=60)
        client.loop_start()
    except Exception as exc:
        logger.error(f"Cannot connect to broker: {exc}")
        sys.exit(1)

    time.sleep(1.0)
    logger.info(f"Initiating {len(FAULT_SUITES)} fault injection scenarios...")

    for test in FAULT_SUITES:
        test_id = test["id"]
        test_name = test["name"]
        expected = test["expected_state"]
        logger.info(f"--- Executing {test_id}: {test_name} (Target: {expected}) ---")

        if "raw_string" in test:
            payload_str = test["raw_string"]
        else:
            payload = test["payload"]
            if payload.get("timestamp") is None:
                payload["timestamp"] = datetime.now(timezone.utc).isoformat()
            payload["vehicle_id"] = vehicle_id
            payload_str = json.dumps(payload)

        res = client.publish(topic, payload_str, qos=1)
        res.wait_for_publish(timeout=2.0)
        logger.info(f"Injected frame for {test_id}. Awaiting pipeline ingestion...")
        time.sleep(2.0)

    client.loop_stop()
    client.disconnect()
    logger.info("Fault injection suite execution completed.")


def main():
    parser = argparse.ArgumentParser(description="SDV HVAC Fault Injection Utility")
    parser.add_argument("--host", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port (plain or TLS)")
    parser.add_argument("--vehicle-id", default="vehicle_01", help="Vehicle ID target")
    args = parser.parse_args()

    run_injection_tests(args.host, args.port, args.vehicle_id)


if __name__ == "__main__":
    main()
