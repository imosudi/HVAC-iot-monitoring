"""Unit tests validating JSON Schema contracts for telemetry and actuator commands."""

import json
from pathlib import Path
import jsonschema
import pytest

SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "schemas"
TELEMETRY_SCHEMA_PATH = SCHEMA_DIR / "telemetry_schema.json"
ACTUATOR_SCHEMA_PATH = SCHEMA_DIR / "actuator_command_schema.json"


@pytest.fixture(scope="module")
def telemetry_schema():
    with open(TELEMETRY_SCHEMA_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture(scope="module")
def actuator_schema():
    with open(ACTUATOR_SCHEMA_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


class TestJsonSchemaContracts:
    """Validates structural constraints and boundary checks across payload schemas."""

    def test_valid_telemetry_payload_passes(self, telemetry_schema):
        valid_payload = {
            "car_id": "vehicle_01",
            "zone": "cabin_front",
            "timestamp_unix_s": 1715000000,
            "scd30": {
                "co2_ppm": 650.5,
                "temperature_c": 22.4,
                "humidity_pct": 48.2
            },
            "dht22": {
                "temperature_c": 22.1,
                "humidity_pct": 49.0
            },
            "actuator_state": {
                "pwm_duty_pct": 35,
                "tachometer_rpm": 1250,
                "carrier_freq_hz": 25000
            }
        }
        jsonschema.validate(instance=valid_payload, schema=telemetry_schema)

    def test_invalid_car_id_fails_telemetry_schema(self, telemetry_schema):
        payload = {
            "car_id": "invalid-car-name",  # Violates ^vehicle_[0-9]{2,}$
            "zone": "cabin_front",
            "timestamp_unix_s": 1715000000,
            "scd30": {"co2_ppm": 450.0, "temperature_c": 21.0, "humidity_pct": 50.0},
            "dht22": {"temperature_c": 21.2, "humidity_pct": 50.1},
            "actuator_state": {"pwm_duty_pct": 0, "tachometer_rpm": 0, "carrier_freq_hz": 25000}
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=payload, schema=telemetry_schema)

    def test_carrier_frequency_must_be_25khz(self, telemetry_schema):
        payload = {
            "car_id": "vehicle_01",
            "zone": "cabin_front",
            "timestamp_unix_s": 1715000000,
            "scd30": {"co2_ppm": 450.0, "temperature_c": 21.0, "humidity_pct": 50.0},
            "dht22": {"temperature_c": 21.2, "humidity_pct": 50.1},
            "actuator_state": {"pwm_duty_pct": 50, "tachometer_rpm": 1500, "carrier_freq_hz": 10000}  # Not 25 kHz
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=payload, schema=telemetry_schema)

    def test_valid_actuator_command_passes(self, actuator_schema):
        valid_cmd = {
            "target_pwm": 75,
            "mode": "AUTOMATIC",
            "timestamp_unix_s": 1715000100,
            "source_entity": "oneM2M_IN_CSE"
        }
        jsonschema.validate(instance=valid_cmd, schema=actuator_schema)

    def test_invalid_actuator_duty_cycle_fails(self, actuator_schema):
        invalid_cmd = {
            "target_pwm": 150,  # Max 100
            "mode": "MANUAL_OVERRIDE",
            "timestamp_unix_s": 1715000100
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=invalid_cmd, schema=actuator_schema)

    def test_invalid_actuator_mode_fails(self, actuator_schema):
        invalid_cmd = {
            "target_pwm": 50,
            "mode": "UNSUPPORTED_MODE",
            "timestamp_unix_s": 1715000100
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=invalid_cmd, schema=actuator_schema)
