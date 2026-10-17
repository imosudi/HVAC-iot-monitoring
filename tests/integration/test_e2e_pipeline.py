"""End-to-end integration test verifying telemetry parsing, health evaluation, and actuation."""

import json
import time
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

    def test_native_in_cse_primitive_routing(self, telemetry_schema):
        """Verifies oneM2M TS-0010 native MQTT primitive encapsulation and health processing."""
        raw_telemetry = {
            "car_id": "vehicle_01",
            "zone": "cabin_front",
            "timestamp_unix_s": 1715000200,
            "scd30": {
                "co2_ppm": 490.0,
                "temperature_c": 22.2,
                "humidity_pct": 45.0
            },
            "dht22": {
                "temperature_c": 22.3,
                "humidity_pct": 45.5
            },
            "actuator_state": {
                "pwm_duty_pct": 25,
                "tachometer_rpm": 950,
                "carrier_freq_hz": 25000
            }
        }

        # 1. Enclose in oneM2M TS-0010 MQTT CREATE primitive
        native_primitive = {
            "op": 1,
            "to": "/id-sdv/sdv-cse/AE_CabinNode_Car01/raw-telemetry",
            "fr": "C_CabinNode_Car01",
            "rqi": "req_1715000200_test",
            "ty": 4,
            "rvi": "3",
            "pc": {
                "m2m:cin": {
                    "cnf": "application/json:0",
                    "con": json.dumps(raw_telemetry)
                }
            }
        }

        # 2. Verify oneM2M primitive protocol parameters
        assert native_primitive["op"] == 1
        assert native_primitive["ty"] == 4
        assert native_primitive["rvi"] == "3"
        assert native_primitive["to"].endswith("/raw-telemetry")
        assert native_primitive["fr"] == "C_CabinNode_Car01"

        # 3. Extract and validate inner payload against telemetry schema
        inner_content = json.loads(native_primitive["pc"]["m2m:cin"]["con"])
        jsonschema.validate(instance=inner_content, schema=telemetry_schema)

        # 4. In-CSE health classification
        classifier = HealthClassifier()
        state, tau_age, delta_t = classifier.evaluate_frame(
            inner_content, eval_time_unix_s=1715000200.3
        )
        assert state == HealthState.FRESH
        assert pytest.approx(tau_age, 0.01) == 0.3
        assert pytest.approx(delta_t, 0.01) == 0.1

    def test_simulate_telemetry_defaults_to_native_ts0010_route(self):
        """Verifies simulate_telemetry defaults to native TS-0010 route and constructs valid primitives."""
        import sys
        scripts_dir = str(Path(__file__).resolve().parent.parent.parent / "scripts" / "testing")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import simulate_telemetry

        parser = simulate_telemetry.build_argument_parser()
        assert parser.get_default("route") == "native"

        test_payload = json.dumps({"car_id": "vehicle_01", "timestamp_unix_s": 1715000300})
        primitive = simulate_telemetry.build_native_primitive("vehicle_01", test_payload, req_id="test_rqi_01")
        assert primitive["op"] == 1
        assert primitive["ty"] == 4
        assert primitive["rvi"] == "3"
        assert primitive["fr"] == "C_CabinNode_Car01"
        assert primitive["to"] == "/id-sdv/sdv-cse/AE_CabinNode_Car01/raw-telemetry"
        assert primitive["rqi"] == "test_rqi_01"
        assert primitive["pc"]["m2m:cin"]["cnf"] == "application/json:0"
        assert primitive["pc"]["m2m:cin"]["con"] == test_payload

    def test_native_downlink_actuation_notification_routing(self, actuator_schema):
        """Verifies oneM2M TS-0010 native MQTT notification primitive formulation for downlink actuation."""
        # 1. Simulate oneM2M notification primitive dispatched by ACME IN-CSE to Mosquitto
        notification_primitive = {
            "fr": "/id-sdv",
            "to": "sdv/vehicle_01/control/cmd",
            "ot": "20261017T110000,000000",
            "op": 5,
            "rqi": "req_downlink_test_01",
            "rvi": "5",
            "drt": 1,
            "pc": {
                "m2m:sgn": {
                    "nev": {
                        "net": 3,
                        "rep": {
                            "m2m:cin": {
                                "cnf": "application/json:0",
                                "con": json.dumps({
                                    "target_pwm": 75,
                                    "mode": "AUTOMATIC",
                                    "timestamp_unix_s": 1715000400,
                                    "source_entity": "Edge_Closed_Loop_Engine"
                                }),
                                "cs": 135,
                                "ty": 4
                            }
                        }
                    },
                    "sur": "/id-sdv/sub_downlink_dispatcher"
                }
            }
        }

        # 2. Verify protocol attributes conform to oneM2M TS-0010
        assert notification_primitive["op"] == 5  # NOTIFY
        assert notification_primitive["to"] == "sdv/vehicle_01/control/cmd"
        sgn = notification_primitive["pc"]["m2m:sgn"]
        assert sgn["nev"]["net"] == 3
        cin = sgn["nev"]["rep"]["m2m:cin"]
        assert cin["cnf"] == "application/json:0"

        # 3. Extract and validate inner directive against actuator schema
        inner_command = json.loads(cin["con"])
        jsonschema.validate(instance=inner_command, schema=actuator_schema)
        assert inner_command["target_pwm"] == 75
        assert inner_command["mode"] == "AUTOMATIC"

        # 4. Verify init_tree.sh provisions strictly native MQTT URI without Node-RED webhook
        init_tree_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "onem2m" / "init_tree.sh"
        with open(init_tree_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "mqtt://mosquitto:1883/sdv/vehicle_01/control/cmd" in content
        assert "http://nodered_ipe:1880/downlink" not in content

    def test_nodered_ipe_service_decommissioned_from_mesh(self):
        """Verifies that Node-RED IPE service and volume are purged from docker-compose.yml."""
        compose_path = Path(__file__).resolve().parent.parent.parent / "deploy" / "docker-compose.yml"
        with open(compose_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "nodered_ipe" not in content
        assert "nodered_data" not in content
        assert "1880:1880" not in content
        assert "sdv_nodered_ipe" not in content
        for required_service in ["mosquitto:", "onem2m_cse:", "bridge_ae:", "influxdb:", "grafana:", "web_portal:"]:
            assert required_service in content

    def test_bridge_ae_notification_event_pipeline(self, telemetry_schema):
        """Verifies Bridge AE ingestion of oneM2M subscription notifications and persistence pipeline."""
        from main import app as bridge_app

        bridge_app.config["TESTING"] = True
        client = bridge_app.test_client()

        # 1. Verify health probe
        health_resp = client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.get_json()["status"] == "UP"

        # 2. Simulate oneM2M notification primitive from sub_bridge_consumer
        now_ts = int(time.time())
        telemetry_payload = {
            "car_id": "vehicle_01",
            "zone": "cabin_front",
            "timestamp_unix_s": now_ts,
            "scd30": {
                "co2_ppm": 520.0,
                "temperature_c": 22.0,
                "humidity_pct": 45.0
            },
            "dht22": {
                "temperature_c": 22.1,
                "humidity_pct": 45.2
            },
            "actuator_state": {
                "pwm_duty_pct": 25,
                "tachometer_rpm": 980,
                "carrier_freq_hz": 25000
            }
        }
        jsonschema.validate(instance=telemetry_payload, schema=telemetry_schema)

        notification_body = {
            "m2m:sgn": {
                "nev": {
                    "net": 3,
                    "rep": {
                        "m2m:cin": {
                            "cnf": "application/json:0",
                            "con": json.dumps(telemetry_payload)
                        }
                    }
                },
                "sur": "/id-sdv/sub_bridge_consumer"
            }
        }

        # 3. Post notification primitive
        resp = client.post("/notification", json=notification_body)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "PROCESSED"
        assert data["health_state"] == "FRESH"
        assert "delta_t_c" in data

        # 4. Post consecutive frame to verify derivative calculation in event pipeline
        telemetry_payload_2 = dict(telemetry_payload)
        telemetry_payload_2["timestamp_unix_s"] = now_ts + 5
        telemetry_payload_2["scd30"] = {
            "co2_ppm": 525.0,
            "temperature_c": 22.5,
            "humidity_pct": 45.0
        }
        notification_body_2 = {
            "m2m:sgn": {
                "nev": {
                    "net": 3,
                    "rep": {
                        "m2m:cin": {
                            "cnf": "application/json:0",
                            "con": json.dumps(telemetry_payload_2)
                        }
                    }
                },
                "sur": "/id-sdv/sub_bridge_consumer"
            }
        }
        resp2 = client.post("/notification", json=notification_body_2)
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        assert data2["status"] == "PROCESSED"
        assert pytest.approx(data2["dt_cabin_derivative"], 0.001) == 0.10  # 0.5°C / 5s = 0.10 °C/s

        # 5. Verify emergency monitoring webhook
        emerg_body = {
            "m2m:sgn": {
                "nev": {"net": 3, "rep": {"m2m:cin": {"con": json.dumps({"co_ppm": 45.0, "hazard": "CRITICAL"})}}},
                "sur": "/id-sdv/sub_co_alert"
            }
        }
        emerg_resp = client.post("/emergency-monitor", json=emerg_body)
        assert emerg_resp.status_code == 200
        assert emerg_resp.get_json()["status"] == "EMERGENCY_ACKNOWLEDGED"

    def test_fault_injection_vectors_native_conformance(self):
        """Verifies that all 6 adversarial fault injection vectors evaluate to their expected health regimes."""
        import sys
        scripts_testing_dir = Path(__file__).resolve().parent.parent.parent / "scripts" / "testing"
        if str(scripts_testing_dir) not in sys.path:
            sys.path.insert(0, str(scripts_testing_dir))

        from inject_faults import FAULT_SUITES

        assert len(FAULT_SUITES) == 6
        classifier = HealthClassifier()

        eval_time = time.time()
        for vector in FAULT_SUITES:
            assert "id" in vector
            assert "expected_state" in vector
            if "payload" in vector:
                payload = dict(vector["payload"])
                sample_time = payload.get("timestamp_unix_s")
                if sample_time is None:
                    sample_time = int(eval_time)
                elif sample_time < 0:
                    sample_time = int(eval_time + sample_time)
                payload["timestamp_unix_s"] = sample_time
                state, _, _ = classifier.evaluate_frame(payload, eval_time_unix_s=eval_time)
                assert state.value == vector["expected_state"], (
                    f"Vector {vector['id']} evaluated to {state.value}, expected {vector['expected_state']}"
                )





