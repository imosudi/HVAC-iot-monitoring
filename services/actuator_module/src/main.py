"""
Main Entry Point for SDV Vehicle Actuator Module Daemon.

Listens for downlink actuation directives from the oneM2M Base CSE platform,
validates commands against the actuator schema contract, and executes them
on the in-cabin ESP32-S3 microcontroller via the serial bus (or closed-loop
emulation mode).
"""

import logging
import os
import signal
import sys
import time

from src.actuator_controller import ActuatorController
from src.downlink_listener import DownlinkListener

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sdv.actuator")


def main() -> None:
    """Executes the vehicle actuator module daemon loop."""
    vehicle_id = os.environ.get("VEHICLE_ID", "vehicle-001")
    base_host = os.environ.get("BASE_CSE_HOST", "localhost")
    onem2m_port = int(os.environ.get("ONEM2M_PORT", "8080"))
    mqtt_port = int(os.environ.get("MOSQUITTO_PORT", "8883"))
    serial_device = os.environ.get("SERIAL_DEVICE", "/dev/ttyACM0")
    baudrate = int(os.environ.get("SERIAL_BAUDRATE", "115200"))
    simulation_fallback = os.environ.get("SIMULATION_FALLBACK", "true").lower() in ("true", "1", "yes")
    poll_interval = float(os.environ.get("POLL_INTERVAL", "2.0"))

    # Certificate resolution
    ca_cert = os.environ.get("CA_CERT", "/certs/ca.crt")
    client_cert = os.environ.get("CLIENT_CERT", "/certs/client_esp32.crt")
    client_key = os.environ.get("CLIENT_KEY", "/certs/client_esp32.key")

    logger.info("================================================================================")
    logger.info("  SDV VEHICLE ACTUATOR DOWNLINK & HARDWARE MODULE (Module 2)")
    logger.info("  Vehicle Identifier:  %s", vehicle_id)
    logger.info("  Base CSE Host:       %s (HTTP: %d, MQTT: %d)", base_host, onem2m_port, mqtt_port)
    logger.info("  Serial Interface:    %s @ %d baud (Fallback Sim: %s)", serial_device, baudrate, simulation_fallback)
    logger.info("================================================================================")

    # Initialise Actuator Controller
    controller = ActuatorController(
        vehicle_id=vehicle_id,
        base_host=base_host,
        http_port=onem2m_port,
        device=serial_device,
        baudrate=baudrate,
        simulation_fallback=simulation_fallback,
    )

    # Initialise Downlink Listener
    listener = DownlinkListener(
        base_host=base_host,
        mqtt_port=mqtt_port,
        http_port=onem2m_port,
        vehicle_id=vehicle_id,
        on_command_callback=controller.apply_directive,
        ca_cert=ca_cert,
        client_cert=client_cert,
        client_key=client_key,
    )

    running = True

    def _shutdown(signum, frame):
        nonlocal running
        logger.info("Received termination signal (%d). Shutting down actuator module...", signum)
        running = False

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Actuator daemon initialised. Listening for downlink directives...")
    try:
        while running:
            # Poll oneM2M commands container periodically to catch REST dispatches
            listener.poll_onem2m_commands()
            time.sleep(poll_interval)
    finally:
        logger.info("Cleaning up actuator subsystem...")
        listener.close()
        controller.close()
        logger.info("Vehicle actuator module stopped cleanly.")


if __name__ == "__main__":
    main()
