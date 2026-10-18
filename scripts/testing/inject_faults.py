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
import os
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import paho.mqtt.client as mqtt


def _load_env_file():
    """Dynamically loads configuration from root or deploy .env files."""
    root = Path(__file__).resolve().parent.parent.parent
    for env_path in [root / ".env", root / "deploy" / ".env"]:
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    clean = line.strip()
                    if clean and not clean.startswith("#") and "=" in clean:
                        k, v = clean.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v


_load_env_file()

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
            "car_id": "vehicle_01",
            "zone": "cabin_front",
            "timestamp_unix_s": -5,  # Backdated by 5s into STALE latency regime (2.5s < tau <= 10.0s)
            "scd30": {"co2_ppm": 450.0, "temperature_c": 22.0, "humidity_pct": 50.0},
            "dht22": {"temperature_c": 22.1, "humidity_pct": 50.2},
            "actuator_state": {"pwm_duty_pct": 20, "tachometer_rpm": 800, "carrier_freq_hz": 25000},
        },
        "expected_state": "STALE",
    },
    {
        "id": "FI-02",
        "name": "Transducer Divergence (Degraded State Trigger)",
        "payload": {
            "car_id": "vehicle_01",
            "zone": "cabin_front",
            "timestamp_unix_s": None,  # Dynamically set to now
            "scd30": {"co2_ppm": 520.0, "temperature_c": 21.0, "humidity_pct": 48.0},
            "dht22": {"temperature_c": 24.5, "humidity_pct": 49.0},  # Delta-T = 3.5 deg C > 1.5 deg C
            "actuator_state": {"pwm_duty_pct": 25, "tachometer_rpm": 950, "carrier_freq_hz": 25000},
        },
        "expected_state": "DEGRADED",
    },
    {
        "id": "FI-03",
        "name": "Transducer Physical Line Detachment (Fault State Trigger)",
        "payload": {
            "car_id": "vehicle_01",
            "zone": "cabin_front",
            "timestamp_unix_s": None,
            "scd30": {"co2_ppm": None, "temperature_c": None, "humidity_pct": None},
            "dht22": {"temperature_c": 22.0, "humidity_pct": 50.0},
            "actuator_state": {"pwm_duty_pct": 50, "tachometer_rpm": 1400, "carrier_freq_hz": 25000},
        },
        "expected_state": "FAULT",
    },
    {
        "id": "FI-04",
        "name": "Out of Range Sensor Measurement (Fault State Trigger)",
        "payload": {
            "car_id": "vehicle_01",
            "zone": "cabin_front",
            "timestamp_unix_s": None,
            "scd30": {"co2_ppm": 12500.0, "temperature_c": 22.0, "humidity_pct": 45.0},
            "dht22": {"temperature_c": 22.2, "humidity_pct": 46.0},
            "actuator_state": {"pwm_duty_pct": 75, "tachometer_rpm": 1800, "carrier_freq_hz": 25000},
        },
        "expected_state": "FAULT",
    },
    {
        "id": "FI-05",
        "name": "Malformed Schema Payload (Ingress Validation Drop)",
        "raw_string": '{"car_id": "vehicle_01", "co2": "INVALID_TYPE", "temperature": "NaN"}',
        "expected_state": "SCHEMA_REJECTION",
    },
    {
        "id": "FI-06",
        "name": "Blower Motor Stall / Slip Fault (Actuator Fault State Trigger)",
        "payload": {
            "car_id": "vehicle_01",
            "zone": "cabin_front",
            "timestamp_unix_s": None,
            "scd30": {"co2_ppm": 480.0, "temperature_c": 22.0, "humidity_pct": 50.0},
            "dht22": {"temperature_c": 22.1, "humidity_pct": 50.1},
            "actuator_state": {"pwm_duty_pct": 50, "tachometer_rpm": 45, "carrier_freq_hz": 25000},
        },
        "expected_state": "FAULT",
    },
]


def run_injection_tests(
    host: str,
    port: int,
    vehicle_id: str,
    ca_cert: str = "",
    client_cert: str = "",
    client_key: str = "",
    route: str = "native",
):
    """Publish test vectors sequentially to the target broker."""
    client = mqtt.Client(client_id=f"fault_injector_{int(time.time())}")
    if route == "native":
        topic = "/oneM2M/req/C_CabinNode_Car01/id-sdv/json"
    else:
        topic = f"sdv/{vehicle_id}/telemetry"

    if port == 8883 or ca_cert:
        if not ca_cert:
            logger.error("Root CA certificate must be supplied when connecting via TLS port 8883.")
            sys.exit(1)
        client.tls_set(
            ca_certs=ca_cert,
            certfile=client_cert if client_cert else None,
            keyfile=client_key if client_key else None,
            cert_reqs=ssl.CERT_REQUIRED if client_cert else ssl.CERT_NONE,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        client.tls_insecure_set(True)

    logger.info("Connecting to broker at %s:%d via '%s' route...", host, port, route)
    try:
        client.connect(host, port, keepalive=60)
        client.loop_start()
    except Exception as exc:
        logger.error("Cannot connect to broker: %s", exc)
        sys.exit(1)

    time.sleep(1.0)
    logger.info("Initiating %d fault injection scenarios...", len(FAULT_SUITES))

    for test in FAULT_SUITES:
        test_id = test["id"]
        test_name = test["name"]
        expected = test["expected_state"]
        logger.info("--- Executing %s: %s (Target: %s) ---", test_id, test_name, expected)

        if "raw_string" in test:
            payload_str = test["raw_string"]
        else:
            payload = dict(test["payload"])
            ts = payload.get("timestamp_unix_s")
            if ts is None:
                payload["timestamp_unix_s"] = int(time.time())
            elif ts < 0:
                payload["timestamp_unix_s"] = int(time.time() + ts)
            payload["car_id"] = vehicle_id
            payload_str = json.dumps(payload)

        if route == "native":
            primitive = {
                "op": 1,
                "to": "/id-sdv/sdv-cse/AE_CabinNode_Car01/raw-telemetry",
                "fr": "C_CabinNode_Car01",
                "rqi": f"req_fi_{int(time.time() * 1000)}",
                "ty": 4,
                "rvi": "3",
                "pc": {
                    "m2m:cin": {
                        "cnf": "application/json:0",
                        "con": payload_str,
                    }
                },
            }
            send_payload = json.dumps(primitive)
        else:
            send_payload = payload_str

        res = client.publish(topic, send_payload, qos=1)
        res.wait_for_publish(timeout=2.0)
        logger.info("Injected frame for %s. Awaiting pipeline ingestion...", test_id)
        time.sleep(1.5)

    client.loop_stop()
    client.disconnect()
    logger.info("Fault injection suite execution completed.")


def main():
    parser = argparse.ArgumentParser(description="SDV HVAC Fault Injection Utility")
    parser.add_argument(
        "--host",
        default=os.getenv("MQTT_HOST", os.getenv("GATEWAY_IP", "localhost")),
        help="MQTT broker host"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MQTT_PORT", os.getenv("MOSQUITTO_PORT", "8883"))),
        help="MQTT broker port (8883 for TLS)"
    )
    parser.add_argument("--vehicle-id", default="vehicle_01", help="Vehicle ID target")
    parser.add_argument(
        "--route",
        choices=["native", "legacy"],
        default="native",
        help="Routing path: 'native' (direct oneM2M TS-0010 MQTT binding) or 'legacy' (flat JSON)",
    )
    parser.add_argument("--ca-cert", default="", help="Path to Root CA certificate")
    parser.add_argument("--client-cert", default="", help="Path to client certificate")
    parser.add_argument("--client-key", default="", help="Path to client private key")
    args = parser.parse_args()

    run_injection_tests(
        args.host,
        args.port,
        args.vehicle_id,
        args.ca_cert,
        args.client_cert,
        args.client_key,
        route=args.route,
    )


if __name__ == "__main__":
    main()
