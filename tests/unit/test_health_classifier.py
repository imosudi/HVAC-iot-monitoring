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
