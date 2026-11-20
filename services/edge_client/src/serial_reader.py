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

CO2_ALERT_PPM = 800.0
TEMPERATURE_MIN_C = 18.0
TEMPERATURE_MAX_C = 30.0
HUMIDITY_MIN_PCT = 30.0
HUMIDITY_MAX_PCT = 60.0


def evaluate_scd30_alerts(co2_ppm: float, temperature_c: float, humidity_pct: float) -> Dict[str, bool]:
    """Return threshold alert flags for unified SCD30 measurements."""
    return {
        "co2": co2_ppm >= CO2_ALERT_PPM,
        "temperature": not (TEMPERATURE_MIN_C <= temperature_c <= TEMPERATURE_MAX_C),
        "humidity": not (HUMIDITY_MIN_PCT <= humidity_pct <= HUMIDITY_MAX_PCT),
    }


def _extract_finite_float(mapping: Dict[str, Any], key: str, alias: str) -> float:
    val = mapping.get(key, mapping.get(alias))
    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
        raise ValueError(f"Invalid or missing SCD30 measurement: {key}")
    return float(val)


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
                return self.normalize_serial_payload(data)
            except Exception as exc:
                logger.warning("Serial read error: %s. Re-evaluating bus connection.", exc)
                self.serial_conn = None
                self.is_simulated = True
                return None

        # Simulation fallback generation conforming to scd30_only telemetry_schema.json
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

        norm_car_id = self.car_id if self.car_id.startswith("vehicle") else f"vehicle_{self.car_id}"
        co2_val = round(max(400.0, min(10000.0, co2_base)), 1)
        temp_val = round(t_base, 2)
        rh_val = round(max(0.0, min(100.0, rh_base)), 1)

        return {
            "car_id": norm_car_id,
            "zone": self.zone,
            "timestamp_unix_s": now_ts,
            "sensor_profile": "scd30_only",
            "scd30": {
                "co2_ppm": co2_val,
                "temperature_c": temp_val,
                "humidity_pct": rh_val,
            },
            "alerts": evaluate_scd30_alerts(co2_val, temp_val, rh_val),
            "actuator_state": {
                "pwm_duty_pct": pwm,
                "tachometer_rpm": max(0, rpm),
                "carrier_freq_hz": 25000,
            },
        }

    def normalize_serial_payload(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validates and normalises an incoming ESP32-S3 serial JSON frame."""
        if not isinstance(data, dict):
            return None

        if data.get("type") == "error":
            logger.warning("ESP32-S3 reported sensor error: %s", data.get("message", "unknown"))
            return None

        raw_scd30 = data.get("scd30")
        src = raw_scd30 if isinstance(raw_scd30, dict) else data
        try:
            co2_ppm = _extract_finite_float(src, "co2_ppm", "co2")
            temp_c = _extract_finite_float(src, "temperature_c", "temp")
            rh_pct = _extract_finite_float(src, "humidity_pct", "hum")
        except ValueError as exc:
            logger.warning("Dropping malformed SCD30 frame: %s", exc)
            return None

        if not (0.0 <= co2_ppm <= 10000.0 and -40.0 <= temp_c <= 70.0 and 0.0 <= rh_pct <= 100.0):
            logger.warning("Dropping out-of-bounds SCD30 frame: co2=%.1f t=%.2f rh=%.1f", co2_ppm, temp_c, rh_pct)
            return None

        norm: Dict[str, Any] = {
            "car_id": data.get("car_id", self.car_id),
            "zone": data.get("zone", self.zone),
            "timestamp_unix_s": data.get("timestamp_unix_s", int(time.time())),
            "sensor_profile": data.get("sensor_profile", "scd30_dht22" if "dht22" in data else "scd30_only"),
            "scd30": {
                "co2_ppm": round(co2_ppm, 1),
                "temperature_c": round(temp_c, 2),
                "humidity_pct": round(rh_pct, 2),
            },
            "alerts": data.get("alerts") or evaluate_scd30_alerts(co2_ppm, temp_c, rh_pct),
        }
        if "dht22" in data:
            norm["dht22"] = data["dht22"]
        if "actuator_state" in data:
            norm["actuator_state"] = data["actuator_state"]
        return norm

    def close(self) -> None:
        """Closes active serial connection."""
        if self.serial_conn is not None:
            try:
                self.serial_conn.close()
            except Exception:
                pass
            self.serial_conn = None
