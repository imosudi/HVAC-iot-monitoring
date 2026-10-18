"""
Main Entry Point for SDV Vehicle Edge Serial Client Daemon.

Continuously reads sensor frames from the in-cabin ESP32-S3 microcontroller
via the physical serial bus (or simulation fallback), validates them against
the telemetry JSON schema, and securely publishes them to the Base CSE.
"""

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

import jsonschema

from src.serial_reader import SerialReader
from src.telemetry_publisher import TelemetryPublisher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sdv.edge_client")


def _find_schema_path() -> Path:
    """Finds telemetry_schema.json in container path or workspace path."""
    candidates = [
        Path("/app/schemas/telemetry_schema.json"),
        Path(__file__).resolve().parent.parent / "schemas" / "telemetry_schema.json",
        Path(__file__).resolve().parent.parent.parent.parent / "docs" / "schemas" / "telemetry_schema.json",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return candidates[0]


def main() -> None:
    """Executes the edge serial client daemon loop."""
    vehicle_id = os.environ.get("VEHICLE_ID", "vehicle-001")
    base_host = os.environ.get("BASE_CSE_HOST", "localhost")
    onem2m_port = int(os.environ.get("ONEM2M_PORT", "8080"))
    mqtt_port = int(os.environ.get("MOSQUITTO_PORT", "8883"))
    serial_device = os.environ.get("SERIAL_DEVICE", "/dev/ttyACM0")
    baudrate = int(os.environ.get("SERIAL_BAUDRATE", "115200"))
    simulation_fallback = os.environ.get("SIMULATION_FALLBACK", "true").lower() in ("true", "1", "yes")
    interval = float(os.environ.get("TELEMETRY_INTERVAL", "1.0"))

    # Certificate resolution
    ca_cert = os.environ.get("CA_CERT", "/certs/ca.crt")
    client_cert = os.environ.get("CLIENT_CERT", "/certs/client_esp32.crt")
    client_key = os.environ.get("CLIENT_KEY", "/certs/client_esp32.key")

    logger.info("================================================================================")
    logger.info("  SDV VEHICLE EDGE SERIAL INGRESS DAEMON (Module 2)")
    logger.info("  Vehicle Identifier:  %s", vehicle_id)
    logger.info("  Base CSE Host:       %s (HTTP: %d, MQTT: %d)", base_host, onem2m_port, mqtt_port)
    logger.info("  Serial Interface:    %s @ %d baud (Fallback Sim: %s)", serial_device, baudrate, simulation_fallback)
    logger.info("================================================================================")

    # Load validation schema
    schema_path = _find_schema_path()
    schema = {}
    if schema_path.is_file():
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        logger.info("Loaded telemetry validation schema from %s", schema_path)
    else:
        logger.warning("Telemetry schema not found at %s. Proceeding without strict schema validation.", schema_path)

    # Initialise serial reader and publisher
    reader = SerialReader(
        car_id=vehicle_id,
        zone="cabin_front",
        device=serial_device,
        baudrate=baudrate,
        simulation_fallback=simulation_fallback,
    )

    publisher = TelemetryPublisher(
        base_host=base_host,
        mqtt_port=mqtt_port,
        http_port=onem2m_port,
        vehicle_id=vehicle_id,
        ca_cert=ca_cert,
        client_cert=client_cert,
        client_key=client_key,
    )

    running = True

    def _shutdown(signum, frame):
        nonlocal running
        logger.info("Received termination signal (%d). Shutting down daemon...", signum)
        running = False

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    frame_count = 0
    try:
        while running:
            frame = reader.read_frame()
            if frame is not None:
                # Validate against schema
                if schema:
                    try:
                        jsonschema.validate(instance=frame, schema=schema)
                    except jsonschema.ValidationError as val_err:
                        logger.warning("Telemetry frame schema violation: %s", val_err.message)

                published = publisher.publish(frame)
                frame_count += 1
                co2_val = frame.get("scd30", {}).get("co2_ppm", 0)
                temp_val = frame.get("scd30", {}).get("temperature_c", 0)
                pwm_val = frame.get("actuator_state", {}).get("pwm_duty_pct", 0)
                tacho_val = frame.get("actuator_state", {}).get("tachometer_rpm", 0)

                status_tag = "DELIVERED" if published else "QUEUED/OFFLINE"
                logger.info(
                    "Frame #%d [%s] -> CO2: %s ppm | Temp: %s °C | PWM: %s%% | Tacho: %s RPM",
                    frame_count,
                    status_tag,
                    co2_val,
                    temp_val,
                    pwm_val,
                    tacho_val,
                )

            time.sleep(interval)
    finally:
        logger.info("Cleaning up connections...")
        reader.close()
        publisher.close()
        logger.info("Edge serial client daemon stopped cleanly.")


if __name__ == "__main__":
    main()
