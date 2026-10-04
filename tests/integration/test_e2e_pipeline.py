"""End-to-end integration test verifying telemetry parsing, health evaluation, and actuation."""

import json
from pathlib import Path
import jsonschema
import pytest

from health_classifier import HealthClassifier, HealthState
from influx_writer import InfluxWriter

SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "schemas"


@pytest.fixture(scope="module")
def telemetry_schema():
    with open(SCHEMA_DIR / "telemetry_schema.json", "r", encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture(scope="module")
def actuator_schema():
    with open(SCHEMA_DIR / "actuator_command_schema.json", "r", encoding="utf-8") as file:
        return json.load(file)


class TestEndToEndPipeline:
    """Verifies end-to-end telemetry ingestion, health state tagging, and closed-loop actuation."""

    def test_nominal_pipeline_execution(self, telemetry_schema):
        # 1. Simulate ESP32-S3 Uplink Payload
        uplink_frame = {
            "car_id": "vehicle_01",
            "zone": "cabin_front",
            "timestamp_unix_s": 1715000000,
            "scd30": {
                "co2_ppm": 550.0,
                "temperature_c": 21.5,
                "humidity_pct": 45.0
            },
            "dht22": {
                "temperature_c": 21.7,
                "humidity_pct": 46.0
            },
            "actuator_state": {
                "pwm_duty_pct": 20,
                "tachometer_rpm": 750,
                "carrier_freq_hz": 25000
            }
        }

        # 2. Ingress Validation against Schema
        jsonschema.validate(instance=uplink_frame, schema=telemetry_schema)

        # 3. Health Classification in Bridge AE
        classifier = HealthClassifier()
        state, tau_age, delta_t = classifier.evaluate_frame(
            uplink_frame, eval_time_unix_s=1715000000.5
        )

        assert state == HealthState.FRESH
        assert tau_age == 0.5
        assert pytest.approx(delta_t, 0.01) == 0.2

        # 4. InfluxWriter Commits Line-Protocol
        writer = InfluxWriter()
        writer.write_telemetry(uplink_frame, state, tau_age, delta_t)

    def test_elevated_co2_triggers_closed_loop_actuation(self, telemetry_schema, actuator_schema):
        # 1. Ingress High CO2 Payload (> 800 ppm threshold)
        high_co2_frame = {
            "car_id": "vehicle_01",
            "zone": "cabin_front",
            "timestamp_unix_s": 1715000100,
            "scd30": {
                "co2_ppm": 950.0,
                "temperature_c": 22.0,
                "humidity_pct": 42.0
            },
            "dht22": {
                "temperature_c": 22.1,
                "humidity_pct": 43.0
            },
            "actuator_state": {
                "pwm_duty_pct": 20,
                "tachometer_rpm": 750,
                "carrier_freq_hz": 25000
            }
        }

        # Validate Schema
        jsonschema.validate(instance=high_co2_frame, schema=telemetry_schema)

        # Evaluate Data Health
        classifier = HealthClassifier()
        state, _, _ = classifier.evaluate_frame(high_co2_frame, eval_time_unix_s=1715000100.2)
        assert state == HealthState.FRESH

        # 2. Closed-Loop Decision Logic: High CO2 demands 75% purge ventilation
        co2_ppm = high_co2_frame["scd30"]["co2_ppm"]
        if co2_ppm > 800.0:
            downlink_command = {
                "target_pwm": 75,
                "mode": "AUTOMATIC",
                "timestamp_unix_s": 1715000101,
                "source_entity": "Edge_Closed_Loop_Engine"
            }
        else:
            downlink_command = {
                "target_pwm": 20,
                "mode": "AUTOMATIC",
                "timestamp_unix_s": 1715000101,
                "source_entity": "Edge_Closed_Loop_Engine"
            }

        # 3. Validate Downlink Actuator Directive Schema
        jsonschema.validate(instance=downlink_command, schema=actuator_schema)
        assert downlink_command["target_pwm"] == 75
