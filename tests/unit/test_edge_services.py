"""
Unit tests validating SDV Vehicle Edge Services:
  - Edge Serial Ingress Client (SerialReader & TelemetryPublisher)
  - Actuator Downlink Module (ActuatorController & DownlinkListener)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import jsonschema
import pytest

from services.edge_client.src.serial_reader import SerialReader
from services.edge_client.src.telemetry_publisher import TelemetryPublisher
from services.actuator_module.src.actuator_controller import ActuatorController
from services.actuator_module.src.downlink_listener import DownlinkListener

SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "schemas"


@pytest.fixture
def telemetry_schema():
    with open(SCHEMA_DIR / "telemetry_schema.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def actuator_schema():
    with open(SCHEMA_DIR / "actuator_command_schema.json", "r", encoding="utf-8") as f:
        return json.load(f)


class TestEdgeSerialClient:
    """Validates SerialReader and TelemetryPublisher behaviors."""

    def test_serial_reader_simulation_fallback_generates_schema_compliant_frames(self, telemetry_schema):
        reader = SerialReader(
            car_id="vehicle_01",
            zone="cabin_front",
            device="/dev/nonexistent_serial_device_test",
            simulation_fallback=True,
        )
        assert reader.is_simulated is True

        frame = reader.read_frame()
        assert frame is not None
        assert frame["car_id"] == "vehicle_01"
        assert frame["zone"] == "cabin_front"
        assert "scd30" in frame
        assert "dht22" in frame
        assert "actuator_state" in frame

        # Strict validation against official schema
        jsonschema.validate(instance=frame, schema=telemetry_schema)
        reader.close()

    def test_serial_reader_reads_valid_hardware_serial_line(self, telemetry_schema):
        reader = SerialReader(
            car_id="vehicle_01",
            device="/dev/nonexistent_test",
            simulation_fallback=True,
        )
        mock_serial = MagicMock()
        mock_payload = {
            "car_id": "vehicle_01",
            "zone": "cabin_front",
            "timestamp_unix_s": 1715000000,
            "scd30": {"co2_ppm": 620.0, "temperature_c": 21.5, "humidity_pct": 42.0},
            "dht22": {"temperature_c": 21.4, "humidity_pct": 42.2},
            "actuator_state": {"pwm_duty_pct": 25, "tachometer_rpm": 750, "carrier_freq_hz": 25000},
        }
        mock_serial.readline.return_value = json.dumps(mock_payload).encode("utf-8") + b"\n"
        reader.serial_conn = mock_serial
        reader.is_simulated = False

        frame = reader.read_frame()
        assert frame is not None
        assert frame["scd30"]["co2_ppm"] == 620.0
        jsonschema.validate(instance=frame, schema=telemetry_schema)
        reader.close()

    def test_serial_reader_default_device(self):
        reader = SerialReader(simulation_fallback=True)
        assert reader.requested_device == "/dev/ttyUSB0"
        reader.close()

    def test_telemetry_publisher_native_primitive_formulation(self):
        publisher = TelemetryPublisher(
            base_host="localhost",
            vehicle_id="vehicle-001",
        )
        test_payload = {"car_id": "vehicle-001", "temp": 22.5}
        primitive = publisher.build_native_primitive(test_payload)

        assert primitive["op"] == 1
        assert primitive["to"] == "/id-sdv/sdv-cse/vehicle-001/raw-telemetry"
        assert primitive["fr"] == "C_vehicle-001"
        assert primitive["ty"] == 4
        assert primitive["pc"]["m2m:cin"]["cnf"] == "application/json:0"
        assert json.loads(primitive["pc"]["m2m:cin"]["con"]) == test_payload
        publisher.close()


class TestActuatorModule:
    """Validates ActuatorController and DownlinkListener behaviors."""

    def test_actuator_controller_applies_valid_directive(self):
        controller = ActuatorController(
            vehicle_id="vehicle-001",
            device="/dev/nonexistent_test",
            simulation_fallback=True,
        )
        assert controller.is_simulated is True

        directive = {
            "target_pwm": 80,
            "mode": "AUTOMATIC",
            "timestamp_unix_s": 1715000400,
            "source_entity": "TestRunner",
        }
        feedback = controller.apply_directive(directive)

        assert feedback["target_pwm"] == 80
        assert feedback["fan_mode"] == "AUTOMATIC"
        assert feedback["tachometer_rpm"] > 2000
        assert feedback["carrier_freq_hz"] == 25000
        assert feedback["eco_vent_state"] == "STANDBY"
        assert feedback["recirculation_flap"] == "FRESH_AIR"
        controller.close()

    def test_actuator_controller_default_device(self):
        controller = ActuatorController(simulation_fallback=True)
        assert controller.requested_device == "/dev/ttyUSB0"
        controller.close()

    def test_downlink_listener_processes_onem2m_notification_primitive(self, actuator_schema):
        received_commands = []

        def callback(cmd):
            received_commands.append(cmd)

        listener = DownlinkListener(
            base_host="localhost",
            vehicle_id="vehicle-001",
            on_command_callback=callback,
        )

        inner_command = {
            "target_pwm": 65,
            "mode": "MANUAL_OVERRIDE",
            "timestamp_unix_s": 1715000400,
            "source_entity": "WebPortal",
        }
        # Verify schema validity first
        jsonschema.validate(instance=inner_command, schema=actuator_schema)

        notification_primitive = {
            "op": 5,
            "to": "sdv/vehicle-001/control/cmd",
            "pc": {
                "m2m:sgn": {
                    "nev": {
                        "net": 3,
                        "rep": {
                            "m2m:cin": {
                                "cnf": "application/json:0",
                                "con": json.dumps(inner_command),
                            }
                        }
                    }
                }
            }
        }

        listener._process_raw_payload(json.dumps(notification_primitive))
        assert len(received_commands) == 1
        assert received_commands[0]["target_pwm"] == 65
        assert received_commands[0]["mode"] == "MANUAL_OVERRIDE"
        listener.close()
