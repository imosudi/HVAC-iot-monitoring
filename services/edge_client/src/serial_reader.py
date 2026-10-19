"""
Serial Bus Ingress Interface for ESP32-S3 Micro-ECU.

Ingests real-time cabin environmental telemetry from the physical serial bus
interfacing with in-cabin ESP32-S3 hardware. Provides dynamic hardware port
discovery and an automated fallback simulator for virtual or bench environments.
"""

import glob
import json
import logging
import math
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import serial
except ImportError:
    serial = None

logger = logging.getLogger("sdv.edge_client.serial")


class SerialReader:
    """Reads structured telemetry frames from ESP32-S3 over serial bus or simulation."""

    def __init__(
        self,
        car_id: str = "vehicle_01",
        zone: str = "cabin_front",
        device: str = "/dev/ttyUSB0",
        baudrate: int = 115200,
        simulation_fallback: bool = True,
    ) -> None:
        self.car_id = car_id
        self.zone = zone
        self.requested_device = device
        self.baudrate = baudrate
        self.simulation_fallback = simulation_fallback
        self.serial_conn: Optional[Any] = None
        self.is_simulated = False
        self._iteration = 0
        self._init_connection()

    def _discover_serial_port(self) -> Optional[str]:
        """Discovers available serial device nodes matching USB CDC / UART patterns."""
        if os.path.exists(self.requested_device):
            return self.requested_device

        candidates = (
            glob.glob("/dev/ttyUSB*")
            + glob.glob("/dev/ttyACM*")
            + glob.glob("/dev/serial/by-id/*")
        )
        if candidates:
            return sorted(candidates)[0]
        return None

    def _init_connection(self) -> None:
        """Initialises the serial port or activates simulation fallback."""
        port = self._discover_serial_port()
        if port and serial is not None:
            try:
                self.serial_conn = serial.Serial(
                    port=port,
                    baudrate=self.baudrate,
                    timeout=1.0,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                )
                self.is_simulated = False
                logger.info(
                    "Connected to hardware ESP32-S3 on serial port %s at %d baud",
                    port,
                    self.baudrate,
                )
                return
            except Exception as exc:
                logger.warning(
                    "Failed to open hardware serial port %s (%s). Falling back to simulation: %s",
                    port,
                    exc,
                    self.simulation_fallback,
                )

        if self.simulation_fallback:
            self.is_simulated = True
            self.serial_conn = None
            logger.info(
                "Hardware serial bus not detected. Activated ESP32-S3 synthetic telemetry generator."
            )
        else:
            raise RuntimeError(
                f"Serial device {self.requested_device} unavailable and simulation_fallback=False."
            )

    def read_frame(self) -> Optional[Dict[str, Any]]:
        """Reads a frame from the serial port or synthesises a compliant telemetry record."""
        # Attempt reconnect to hardware if previously in simulation
        if self.is_simulated and serial is not None:
            active_port = self._discover_serial_port()
            if active_port and self._iteration % 10 == 0:
                try:
                    self.serial_conn = serial.Serial(active_port, self.baudrate, timeout=1.0)
                    self.is_simulated = False
                    logger.info("Hot-plugged hardware ESP32-S3 detected on %s. Switched to live serial.", active_port)
                except Exception:
                    pass

        if not self.is_simulated and self.serial_conn is not None:
            try:
                raw_line = self.serial_conn.readline()
                if not raw_line:
                    return None
                line_str = raw_line.decode("utf-8", errors="replace").strip()
                if not line_str or not (line_str.startswith("{") and line_str.endswith("}")):
                    return None
                data = json.loads(line_str)
                # Enforce car_id and timestamp integrity
                if "car_id" not in data:
                    data["car_id"] = self.car_id
                if "zone" not in data:
                    data["zone"] = self.zone
                if "timestamp_unix_s" not in data:
                    data["timestamp_unix_s"] = int(time.time())
                return data
            except Exception as exc:
                logger.warning("Serial read error: %s. Re-evaluating bus connection.", exc)
                self.serial_conn = None
                self.is_simulated = True
                return None

        # Simulation fallback generation conforming to telemetry_schema.json
        self._iteration += 1
        now_ts = int(time.time())
        co2_base = 650.0 + 150.0 * math.sin(self._iteration / 10.0) + random.uniform(-15.0, 15.0)
        t_base = 22.0 + 1.5 * math.sin(self._iteration / 25.0) + random.uniform(-0.2, 0.2)
        rh_base = 45.0 + 3.0 * math.cos(self._iteration / 20.0) + random.uniform(-0.5, 0.5)

        # Actuator state calculation
        pwm = 25
        if co2_base > 1200.0:
            pwm = 100
        elif co2_base > 800.0:
            pwm = 75
        elif t_base < 19.0:
            pwm = 0

        rpm = int(pwm * 30 + random.uniform(-20, 20)) if pwm > 0 else 0

        # Normalise car_id for strict schema pattern conformity (^vehicle_[0-9]{2,}$)
        norm_car_id = self.car_id.replace("-", "_")
        if not norm_car_id.startswith("vehicle_"):
            norm_car_id = f"vehicle_{norm_car_id}"

        return {
            "car_id": norm_car_id,
            "zone": self.zone,
            "timestamp_unix_s": now_ts,
            "scd30": {
                "co2_ppm": round(max(400.0, min(10000.0, co2_base)), 1),
                "temperature_c": round(t_base, 2),
                "humidity_pct": round(max(0.0, min(100.0, rh_base)), 1),
            },
            "dht22": {
                "temperature_c": round(t_base + random.uniform(-0.3, 0.3), 2),
                "humidity_pct": round(max(0.0, min(100.0, rh_base - 0.5 + random.uniform(-0.4, 0.4))), 1),
            },
            "actuator_state": {
                "pwm_duty_pct": pwm,
                "tachometer_rpm": max(0, rpm),
                "carrier_freq_hz": 25000,
            },
        }

    def close(self) -> None:
        """Closes active serial connection."""
        if self.serial_conn is not None:
            try:
                self.serial_conn.close()
            except Exception:
                pass
            self.serial_conn = None
