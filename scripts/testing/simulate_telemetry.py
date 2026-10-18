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


def build_native_primitive(vehicle_id: str, payload_str: str, req_id: str | None = None) -> dict:
    """Encapsulates telemetry JSON payload into a native oneM2M TS-0010 CREATE primitive."""
    return {
        "op": 1,
        "to": "/id-sdv/sdv-cse/AE_CabinNode_Car01/raw-telemetry",
        "fr": "C_CabinNode_Car01",
        "rqi": req_id or f"req_{int(time.time() * 1000)}",
        "ty": 4,
        "rvi": "3",
        "pc": {
            "m2m:cin": {
                "cnf": "application/json:0",
                "con": payload_str,
            }
        },
    }


def build_argument_parser() -> argparse.ArgumentParser:
    """Constructs the command-line interface argument parser for telemetry simulation."""
    parser = argparse.ArgumentParser(
        description="Publish synthetic vehicular telemetry to Mosquitto MQTT broker."
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MQTT_HOST", os.getenv("GATEWAY_IP", "localhost")),
        help="MQTT broker hostname or IP address"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MQTT_PORT", os.getenv("MOSQUITTO_PORT", "8883"))),
        help="MQTT broker port (8883 for mTLS, 1883 for plain)"
    )
    parser.add_argument("--vehicle-id", default="vehicle_01", help="Vehicle identifier")
    parser.add_argument("--interval", type=float, default=1.0, help="Publish interval in seconds")
    parser.add_argument("--count", type=int, default=0, help="Number of frames to send (0 = infinite)")
    parser.add_argument(
        "--mode",
        choices=["normal", "co2_spike", "delta_t_divergence", "stale", "fault"],
        default="normal",
        help="Simulation operating scenario",
    )
    parser.add_argument(
        "--route",
        choices=["native", "legacy"],
        default="native",
        help="Routing path: 'native' (direct oneM2M TS-0010 MQTT binding) or 'legacy' (Node-RED proxy)",
    )
    parser.add_argument("--ca-cert", default="", help="Path to Root CA certificate")
    parser.add_argument("--client-cert", default="", help="Path to client X.509 certificate")
    parser.add_argument("--client-key", default="", help="Path to client private key")
    return parser


def main():
    parser = build_argument_parser()
    args = parser.parse_args()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"sim_{args.vehicle_id}_{int(time.time())}",
    )

    confirmed_count = 0

    def on_connect(cl, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("Broker connection acknowledged (CONNACK).")
            if args.route == "native":
                resp_topic = "/oneM2M/resp/C_CabinNode_Car01/id-sdv/json"
                cl.subscribe(resp_topic, qos=1)
                logger.info(f"Subscribed to oneM2M response topic: {resp_topic}")
        else:
            logger.error(f"Broker connection failed with reason code: {rc}")

    def on_message(cl, userdata, msg):
        nonlocal confirmed_count
        try:
            resp_dict = json.loads(msg.payload.decode("utf-8"))
            rsc = resp_dict.get("rsc")
            rqi = resp_dict.get("rqi", "unknown")
            cin_rn = resp_dict.get("pc", {}).get("m2m:cin", {}).get("rn", "unknown")
            if rsc == 2001:
                confirmed_count += 1
                logger.info(
                    f"oneM2M IN-CSE Response: RSC {rsc} (CREATED) | rqi={rqi} | cin={cin_rn} (Total Confirmed: {confirmed_count})"
                )
            else:
                logger.warning(f"oneM2M IN-CSE Response: RSC {rsc} | rqi={rqi}")
        except Exception as err:
            logger.debug(f"Failed to parse response payload: {err}")

    client.on_connect = on_connect
    client.on_message = on_message

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

    if args.route == "native":
        topic = "/oneM2M/req/C_CabinNode_Car01/id-sdv/json"
    else:
        topic = f"sdv/{args.vehicle_id}/telemetry"

    logger.info(f"Connecting to broker at {args.host}:{args.port}...")
    try:
        client.connect(args.host, args.port, keepalive=60)
        client.loop_start()
    except Exception as exc:
        logger.error(f"Failed to establish broker connection: {exc}")
        sys.exit(1)

    logger.info(f"Publishing via {args.route.upper()} route to topic '{topic}' under mode '{args.mode}' every {args.interval}s")
    iteration = 0
    try:
        while True:
            payload = generate_payload(args.vehicle_id, args.mode, iteration)
            payload_str = json.dumps(payload)

            if args.route == "native":
                primitive = build_native_primitive(args.vehicle_id, payload_str)
                out_data = json.dumps(primitive)
            else:
                out_data = payload_str

            result = client.publish(topic, out_data, qos=1)
            result.wait_for_publish(timeout=2.0)
            logger.info(f"Published frame #{iteration + 1} ({args.route}) | CO2={payload['scd30'].get('co2_ppm')} ppm")

            iteration += 1
            if args.count > 0 and iteration >= args.count:
                logger.info(f"Completed transmission of {args.count} requested frames.")
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Simulation halted by user.")
    finally:
        if args.route == "native" and iteration > 0:
            drain_deadline = time.time() + 2.0
            while confirmed_count < iteration and time.time() < drain_deadline:
                time.sleep(0.05)
            logger.info(
                f"Ingress Summary: Transmitted={iteration} | Confirmed (RSC 2001)={confirmed_count} | Loss={iteration - confirmed_count}"
            )
        client.loop_stop()
        client.disconnect()
        logger.info("Broker disconnected.")


if __name__ == "__main__":
    main()
