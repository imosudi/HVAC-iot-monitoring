"""Unit tests for the four-state empirical Data Health Classifier."""

import pytest
from health_classifier import HealthClassifier, HealthState


class TestHealthClassifier:
    """Test suite evaluating deterministic health state transitions."""

    @pytest.fixture
    def classifier(self):
        return HealthClassifier(max_latency_s=2.5, max_stale_s=10.0, max_delta_t_c=1.5)

    def test_nominal_frame_evaluates_to_fresh(self, classifier, nominal_telemetry_frame):
        sample_time = nominal_telemetry_frame["timestamp_unix_s"]
        eval_time = sample_time + 0.8  # Latency = 0.8s (< 2.5s)

        state, tau_age, delta_t = classifier.evaluate_frame(
            nominal_telemetry_frame, eval_time_unix_s=eval_time
        )

        assert state == HealthState.FRESH
        assert pytest.approx(tau_age, 0.01) == 0.8
        assert pytest.approx(delta_t, 0.01) == 0.2

    def test_latency_exceedance_evaluates_to_stale(self, classifier, nominal_telemetry_frame):
        sample_time = nominal_telemetry_frame["timestamp_unix_s"]
        eval_time = sample_time + 4.2  # Latency = 4.2s (2.5s < tau <= 10.0s)

        state, tau_age, delta_t = classifier.evaluate_frame(
            nominal_telemetry_frame, eval_time_unix_s=eval_time
        )

        assert state == HealthState.STALE
        assert pytest.approx(tau_age, 0.01) == 4.2
        assert pytest.approx(delta_t, 0.01) == 0.2

    def test_sensor_temperature_divergence_evaluates_to_degraded(self, classifier, nominal_telemetry_frame):
        sample_time = nominal_telemetry_frame["timestamp_unix_s"]
        eval_time = sample_time + 1.0

        # Create 2.5 deg C discrepancy (> 1.5 deg C threshold)
        nominal_telemetry_frame["scd30"]["temperature_c"] = 21.0
        nominal_telemetry_frame["dht22"]["temperature_c"] = 23.5

        state, tau_age, delta_t = classifier.evaluate_frame(
            nominal_telemetry_frame, eval_time_unix_s=eval_time
        )

        assert state == HealthState.DEGRADED
        assert pytest.approx(delta_t, 0.01) == 2.5

    def test_extreme_latency_evaluates_to_fault(self, classifier, nominal_telemetry_frame):
        sample_time = nominal_telemetry_frame["timestamp_unix_s"]
        eval_time = sample_time + 15.0  # Latency = 15.0s (> 10.0s max stale)

        state, tau_age, _ = classifier.evaluate_frame(
            nominal_telemetry_frame, eval_time_unix_s=eval_time
        )

        assert state == HealthState.FAULT
        assert tau_age == 15.0

    def test_missing_timestamp_evaluates_to_fault(self, classifier, nominal_telemetry_frame):
        nominal_telemetry_frame["timestamp_unix_s"] = None

        state, tau_age, delta_t = classifier.evaluate_frame(
            nominal_telemetry_frame, eval_time_unix_s=1700000000.0
        )

        assert state == HealthState.FAULT
        assert tau_age == float("inf")
        assert delta_t is None

    def test_null_sensor_readings_evaluate_to_fault(self, classifier, nominal_telemetry_frame):
        nominal_telemetry_frame["scd30"]["co2_ppm"] = None

        state, _, delta_t = classifier.evaluate_frame(
            nominal_telemetry_frame, eval_time_unix_s=1700000001.0
        )

        assert state == HealthState.FAULT
        assert delta_t is None

    def test_out_of_range_co2_evaluates_to_fault(self, classifier, nominal_telemetry_frame):
        nominal_telemetry_frame["scd30"]["co2_ppm"] = 15000.0  # Physical upper limit 10,000 ppm

        state, _, _ = classifier.evaluate_frame(
            nominal_telemetry_frame, eval_time_unix_s=1700000001.0
        )

        assert state == HealthState.FAULT

    def test_humidity_divergence_evaluates_to_degraded(self, classifier, nominal_telemetry_frame):
        sample_time = nominal_telemetry_frame["timestamp_unix_s"]
        eval_time = sample_time + 1.0

        # Inject 15% RH discrepancy (> 10% threshold)
        nominal_telemetry_frame["scd30"]["humidity_pct"] = 45.0
        nominal_telemetry_frame["dht22"]["humidity_pct"] = 62.0

        state, tau_age, delta_t = classifier.evaluate_frame(
            nominal_telemetry_frame, eval_time_unix_s=eval_time
        )

        assert state == HealthState.DEGRADED

    def test_blower_motor_stall_evaluates_to_fault(self, classifier, nominal_telemetry_frame):
        sample_time = nominal_telemetry_frame["timestamp_unix_s"]
        eval_time = sample_time + 1.0

        # Inject stall condition: PWM >= 30% with Tachometer RPM < 100
        nominal_telemetry_frame["actuator_state"] = {
            "pwm_duty_pct": 50,
            "tachometer_rpm": 45,
            "carrier_freq_hz": 25000
        }

        state, tau_age, _ = classifier.evaluate_frame(
            nominal_telemetry_frame, eval_time_unix_s=eval_time
        )

        assert state == HealthState.FAULT

    def test_thermal_derivative_calculation(self, classifier):
        """Verifies calculation of temporal derivative dT_cabin/dt and differential against exterior."""
        # Initial observation establishes baseline
        dt_cabin_1, dt_diff_1 = classifier.compute_thermal_derivative(
            car_id="vehicle_01",
            current_temp_c=21.0,
            timestamp_unix_s=1715000000,
            ext_temp_c=18.0
        )
        assert dt_cabin_1 is None
        assert dt_diff_1 is None

        # Second observation (+1.0°C cabin, +0.5°C exterior over 10 seconds)
        dt_cabin_2, dt_diff_2 = classifier.compute_thermal_derivative(
            car_id="vehicle_01",
            current_temp_c=22.0,
            timestamp_unix_s=1715000010,
            ext_temp_c=18.5
        )
        assert pytest.approx(dt_cabin_2, 0.001) == 0.10  # 1.0°C / 10s = 0.10 °C/s
        assert pytest.approx(dt_diff_2, 0.001) == 0.05   # 0.10 - 0.05 = 0.05 °C/s

        # Third observation cooling (-0.5°C cabin, constant exterior over 10 seconds)
        dt_cabin_3, dt_diff_3 = classifier.compute_thermal_derivative(
            car_id="vehicle_01",
            current_temp_c=21.5,
            timestamp_unix_s=1715000020,
            ext_temp_c=18.5
        )
        assert pytest.approx(dt_cabin_3, 0.001) == -0.05
        assert pytest.approx(dt_diff_3, 0.001) == -0.05

    def test_blower_motor_stall_heuristic_boundaries(self, classifier, nominal_telemetry_frame):
        """Verifies precise boundary transitions for blower motor stall/slip detection."""
        sample_time = nominal_telemetry_frame["timestamp_unix_s"]

        # Boundary A: PWM 29% (< 30% threshold) with 0 RPM is not flagged as blower stall
        nominal_telemetry_frame["actuator_state"] = {"pwm_duty_pct": 29, "tachometer_rpm": 0}
        state, _, _ = classifier.evaluate_frame(nominal_telemetry_frame, eval_time_unix_s=sample_time + 0.5)
        assert state == HealthState.FRESH

        # Boundary B: PWM 30% with 99 RPM (< 100 RPM threshold) flags FAULT
        nominal_telemetry_frame["actuator_state"] = {"pwm_duty_pct": 30, "tachometer_rpm": 99}
        state, _, _ = classifier.evaluate_frame(nominal_telemetry_frame, eval_time_unix_s=sample_time + 0.5)
        assert state == HealthState.FAULT

        # Boundary C: PWM 30% with 100 RPM (threshold met) evaluates to FRESH
        nominal_telemetry_frame["actuator_state"] = {"pwm_duty_pct": 30, "tachometer_rpm": 100}
        state, _, _ = classifier.evaluate_frame(nominal_telemetry_frame, eval_time_unix_s=sample_time + 0.5)
        assert state == HealthState.FRESH


