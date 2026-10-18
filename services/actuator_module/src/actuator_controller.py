"""
Actuator Controller for SDV Cabin HVAC and Multi-LED Actuators.

Executes validated downlink actuation directives (PWM blower duty cycle,
ventilation regimes, and auxiliary heating) across the physical serial bus
to the ESP32-S3 micro-ECU, or modulates simulated closed-loop feedback.
"""

import glob
import json
import logging
import os
import random
import time
from typing import Any, Dict, Optional
import urllib.error
import urllib.request

try:
    import serial
except ImportError:
    serial = None

logger = logging.getLogger("sdv.actuator.controller")


class ActuatorController:
    """Manages physical and logical state of in-cabin actuators."""

    def __init__(
        self,
        vehicle_id: str = "vehicle-001",
        base_host: str = "localhost",
        http_port: int = 8080,
        device: str = "/dev/ttyACM0",
        baudrate: int = 115200,
        simulation_fallback: bool = True,
    ) -> None:
        self.vehicle_id = vehicle_id
        self.base_host = base_host
        self.http_port = http_port
        self.requested_device = device
        self.baudrate = baudrate
        self.simulation_fallback = simulation_fallback

        self.serial_conn: Optional[Any] = None
        self.is_simulated = False

        # Actuator State Machine Variables
        self.target_pwm: int = 25
        self.mode: str = "AUTOMATIC"
        self.tachometer_rpm: int = 750
        self.carrier_freq_hz: int = 25000
        self.aux_heater_state: str = "STANDBY"
        self.eco_vent_state: str = "ACTIVE"
        self.dehumidifier_state: str = "STANDBY"
        self.recirculation_flap: str = "FRESH_AIR"
        self.last_updated: float = time.time()

        self._init_serial()

    def _discover_serial_port(self) -> Optional[str]:
        """Discovers available serial device nodes matching USB CDC / UART patterns."""
        if os.path.exists(self.requested_device):
            return self.requested_device

        candidates = (
            glob.glob("/dev/serial/by-id/*")
            + glob.glob("/dev/ttyACM*")
            + glob.glob("/dev/ttyUSB*")
        )
        if candidates:
            return sorted(candidates)[0]
        return None

    def _init_serial(self) -> None:
        """Connects to the hardware serial port or initiates simulation mode."""
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
                logger.info("Actuator controller connected to ESP32-S3 on %s", port)
                return
            except Exception as exc:
                logger.warning(
                    "Actuator serial connection failed on %s (%s). Fallback: %s",
                    port,
                    exc,
                    self.simulation_fallback,
                )

        if self.simulation_fallback:
            self.is_simulated = True
            self.serial_conn = None
            logger.info("Physical actuator serial bus absent. Operating in closed-loop emulation mode.")
        else:
            raise RuntimeError(f"Serial port {self.requested_device} unavailable and fallback disabled.")

    def apply_directive(self, directive: Dict[str, Any]) -> Dict[str, Any]:
        """Validates, applies, and dispatches an actuation directive."""
        target_pwm = int(directive.get("target_pwm", directive.get("target_fan_pwm", self.target_pwm)))
        target_pwm = max(0, min(100, target_pwm))
        mode = directive.get("mode", self.mode)
        source = directive.get("source_entity", "BaseCSE_Downlink")

        self.target_pwm = target_pwm
        self.mode = mode
        self.last_updated = time.time()

        # Update dependent actuator states per control heuristics
        if target_pwm > 50:
            self.eco_vent_state = "STANDBY"
            self.recirculation_flap = "FRESH_AIR"
        else:
            self.eco_vent_state = "ACTIVE"

        # Calculate closed-loop tachometer feedback
        if target_pwm == 0:
            self.tachometer_rpm = 0
        else:
            jitter = random.randint(-15, 15)
            self.tachometer_rpm = max(100, target_pwm * 30 + jitter)

        # Dispatch across physical serial bus if available
        if not self.is_simulated and self.serial_conn is not None:
            try:
                cmd_line = f"CMD:PWM={self.target_pwm},MODE={self.mode}\n"
                self.serial_conn.write(cmd_line.encode("utf-8"))
                self.serial_conn.flush()
                logger.info("Dispatched hardware serial directive to ESP32-S3: %s", cmd_line.strip())
            except Exception as exc:
                logger.warning("Failed to dispatch command across serial: %s", exc)
                self.is_simulated = True
        else:
            logger.info(
                "Emulated Actuation -> PWM: %d%% | Mode: %s | Tacho: %d RPM | Flap: %s | Source: %s",
                self.target_pwm,
                self.mode,
                self.tachometer_rpm,
                self.recirculation_flap,
                source,
            )

        feedback_state = self.get_state()
        self._publish_feedback_to_base_cse(feedback_state)
        return feedback_state

    def get_state(self) -> Dict[str, Any]:
        """Returns the current state dictionary of the actuator subsystem."""
        return {
            "vehicle_id": self.vehicle_id,
            "target_fan_pwm": float(self.target_pwm),
            "target_pwm": self.target_pwm,
            "fan_mode": self.mode,
            "tachometer_rpm": self.tachometer_rpm,
            "carrier_freq_hz": self.carrier_freq_hz,
            "aux_heater_state": self.aux_heater_state,
            "eco_vent_state": self.eco_vent_state,
            "dehumidifier_state": self.dehumidifier_state,
            "recirculation_flap": self.recirculation_flap,
            "updated_at": int(self.last_updated),
        }

    def _publish_feedback_to_base_cse(self, state: Dict[str, Any]) -> None:
        """Publishes acknowledged state back to Base CSE oneM2M commands container."""
        try:
            url = f"http://{self.base_host}:{self.http_port}/sdv-cse/{self.vehicle_id}/commands"
            headers = {
                "X-M2M-Origin": f"C_{self.vehicle_id}",
                "X-M2M-RI": f"act_ack_{int(time.time() * 1000)}",
                "X-M2M-RVI": "3",
                "Content-Type": "application/json;ty=4",
            }
            body = {
                "m2m:cin": {
                    "cnf": "application/json:0",
                    "con": json.dumps(state),
                }
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=1.5):
                pass
        except Exception:
            pass

    def close(self) -> None:
        """Safely closes serial resources."""
        if self.serial_conn is not None:
            try:
                self.serial_conn.close()
            except Exception:
                pass
            self.serial_conn = None
