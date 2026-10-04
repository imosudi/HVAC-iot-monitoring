#!/usr/bin/env python3
"""
Telemetry Simulation Utility for Software-Defined Vehicle (SDV) Cabin Monitoring.

Generates synthetic sensor frames conforming to docs/schemas/telemetry_schema.json
and transmits them over MQTT (with optional mutual TLS 1.3 authentication) to
validate edge gateway ingestion, oneM2M Interworking Proxy Entities, and the
Bridge AE data health state machine.
"""

import argparse
import json
import logging
import ssl
import sys
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("TelemetrySimulator")


def generate_payload(vehicle_id: str, mode: str, iteration: int) -> dict:
    """Generate a structured telemetry payload according to operating mode."""
    now = datetime.now(timezone.utc)

    # Base nominal telemetry values
    co2_ppm = 480.0 + (iteration % 20) * 2.5
    scd30_temp = 21.8 + (iteration % 10) * 0.1
    dht22_temp = 21.9 + (iteration % 8) * 0.1
    scd30_rh = 45.2 + (iteration % 5) * 0.3
    dht22_rh = 44.8 + (iteration % 7) * 0.2
    fan_duty = 25.0
    fan_rpm = 980 + (iteration % 30)

    # Induce specific test conditions based on active mode
    if mode == "co2_spike":
        # Simulate elevated occupancy or exhalation spike (> 800 ppm)
        co2_ppm = 750.0 + (iteration * 45.0)
        if co2_ppm > 1600.0:
            co2_ppm = 1600.0
        logger.info(f"Simulating elevated CO2 condition: {co2_ppm:.1f} ppm")

    elif mode == "delta_t_divergence":
        # Discrepancy between SCD30 and DHT22 exceeding 1.5 deg C threshold
        scd30_temp = 21.5
        dht22_temp = 24.8  # Delta-T = 3.3 deg C -> triggers DEGRADED state
        logger.info(f"Simulating Delta-T divergence: SCD30={scd30_temp} C, DHT22={dht22_temp} C")

    elif mode == "stale":
        # Backdate timestamp by 10 seconds to exceed 2.5 s latency threshold
        now = datetime.fromtimestamp(now.timestamp() - 10.0, tz=timezone.utc)
        logger.info(f"Simulating stale telemetry timestamp: {int(now.timestamp())}")

    elif mode == "fault":
        # Transmit null/invalid values for primary transducer
        logger.info("Simulating transducer fault with null reading")
        return {
            "car_id": vehicle_id,
            "zone": "cabin_front",
            "timestamp_unix_s": int(now.timestamp()),
            "scd30": {
                "co2_ppm": None,
                "temperature_c": None,
                "humidity_pct": None,
            },
            "dht22": {
                "temperature_c": round(dht22_temp, 2),
                "humidity_pct": round(dht22_rh, 1),
            },
            "actuator_state": {
                "pwm_duty_pct": round(fan_duty, 1),
                "tachometer_rpm": int(fan_rpm),
                "carrier_freq_hz": 25000,
            },
        }

    return {
        "car_id": vehicle_id,
        "zone": "cabin_front",
        "timestamp_unix_s": int(now.timestamp()),
        "scd30": {
            "co2_ppm": round(co2_ppm, 1),
            "temperature_c": round(scd30_temp, 2),
            "humidity_pct": round(scd30_rh, 1),
        },
        "dht22": {
            "temperature_c": round(dht22_temp, 2),
            "humidity_pct": round(dht22_rh, 1),
        },
        "actuator_state": {
            "pwm_duty_pct": round(fan_duty, 1),
            "tachometer_rpm": int(fan_rpm),
            "carrier_freq_hz": 25000,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Publish synthetic vehicular telemetry to Mosquitto MQTT broker."
    )
    parser.add_argument("--host", default="localhost", help="MQTT broker hostname or IP address")
    parser.add_argument("--port", type=int, default=8883, help="MQTT broker port (8883 for mTLS, 1883 for plain)")
    parser.add_argument("--vehicle-id", default="vehicle_01", help="Vehicle identifier")
    parser.add_argument("--interval", type=float, default=1.0, help="Publish interval in seconds")
    parser.add_argument("--count", type=int, default=0, help="Number of frames to send (0 = infinite)")
    parser.add_argument(
        "--mode",
        choices=["normal", "co2_spike", "delta_t_divergence", "stale", "fault"],
        default="normal",
        help="Simulation operating scenario",
    )
    parser.add_argument("--ca-cert", default="", help="Path to Root CA certificate")
    parser.add_argument("--client-cert", default="", help="Path to client X.509 certificate")
    parser.add_argument("--client-key", default="", help="Path to client private key")
    args = parser.parse_args()

    client = mqtt.Client(client_id=f"sim_{args.vehicle_id}_{int(time.time())}")

    if args.port == 8883 or args.ca_cert:
        if not args.ca_cert:
            logger.error("Root CA certificate must be supplied when connecting via TLS port 8883.")
            sys.exit(1)
        client.tls_set(
            ca_certs=args.ca_cert,
            certfile=args.client_cert if args.client_cert else None,
            keyfile=args.client_key if args.client_key else None,
            cert_reqs=ssl.CERT_REQUIRED if args.client_cert else ssl.CERT_NONE,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        client.tls_insecure_set(True)

    topic = f"sdv/{args.vehicle_id}/telemetry"
    logger.info(f"Connecting to broker at {args.host}:{args.port}...")
    try:
        client.connect(args.host, args.port, keepalive=60)
        client.loop_start()
    except Exception as exc:
        logger.error(f"Failed to establish broker connection: {exc}")
        sys.exit(1)

    logger.info(f"Publishing to topic '{topic}' under mode '{args.mode}' every {args.interval}s")
    iteration = 0
    try:
        while True:
            payload = generate_payload(args.vehicle_id, args.mode, iteration)
            payload_str = json.dumps(payload)
            result = client.publish(topic, payload_str, qos=1)
            result.wait_for_publish(timeout=2.0)
            logger.info(f"Published frame #{iteration + 1} | CO2={payload['scd30'].get('co2_ppm')} ppm")

            iteration += 1
            if args.count > 0 and iteration >= args.count:
                logger.info(f"Completed transmission of {args.count} requested frames.")
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Simulation halted by user.")
    finally:
        client.loop_stop()
        client.disconnect()
        logger.info("Broker disconnected.")


if __name__ == "__main__":
    main()
