"""Empirical Data Health Classifier implementing the four-state deterministic state machine."""

import time
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class HealthState(str, Enum):
    """Categorical states of telemetry data integrity."""
    FRESH = "FRESH"
    STALE = "STALE"
    DEGRADED = "DEGRADED"
    FAULT = "FAULT"


class HealthClassifier:
    """Evaluates telemetry frames against temporal latency and inter-transducer divergence."""

    def __init__(
        self,
        max_latency_s: float = 2.5,
        max_stale_s: float = 10.0,
        max_delta_t_c: float = 1.5,
        max_delta_rh_pct: float = 10.0
    ):
        self.max_latency_s = max_latency_s
        self.max_stale_s = max_stale_s
        self.max_delta_t_c = max_delta_t_c
        self.max_delta_rh_pct = max_delta_rh_pct
        self._previous_observations: Dict[str, Dict[str, Any]] = {}

    def compute_thermal_derivative(
        self,
        car_id: str,
        current_temp_c: float,
        timestamp_unix_s: float,
        ext_temp_c: Optional[float] = None
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Computes temporal temperature derivative (dT_cabin/dt) and differential against exterior (dT_cabin/dt - dT_ext/dt).

        Returns:
            Tuple of (dT_cabin_per_sec, dT_diff_per_sec)
        """
        prev = self._previous_observations.get(car_id)
        dt_cabin_dt = None
        dt_diff_dt = None

        if prev is not None:
            dt_s = timestamp_unix_s - prev["timestamp"]
            if dt_s > 0:
                dt_cabin_dt = (current_temp_c - prev["cabin_temp"]) / dt_s
                if ext_temp_c is not None and prev.get("ext_temp") is not None:
                    dt_ext_dt = (ext_temp_c - prev["ext_temp"]) / dt_s
                    dt_diff_dt = dt_cabin_dt - dt_ext_dt

        self._previous_observations[car_id] = {
            "timestamp": timestamp_unix_s,
            "cabin_temp": current_temp_c,
            "ext_temp": ext_temp_c
        }

        return dt_cabin_dt, dt_diff_dt

    def evaluate_frame(
        self,
        payload: Dict[str, Any],
        eval_time_unix_s: Optional[float] = None
    ) -> Tuple[HealthState, float, Optional[float]]:
        """
        Classifies incoming telemetry payload into deterministic health regime.

        Returns:
            Tuple of (HealthState, tau_age_seconds, delta_t_celsius)
        """
        if eval_time_unix_s is None:
            eval_time_unix_s = time.time()

        sample_time = payload.get("timestamp_unix_s")
        if sample_time is None or not isinstance(sample_time, (int, float)):
            return HealthState.FAULT, float("inf"), None

        tau_age = max(0.0, eval_time_unix_s - float(sample_time))

        scd30 = payload.get("scd30", {})
        dht22 = payload.get("dht22", {})

        t_scd30 = scd30.get("temperature_c") if isinstance(scd30, dict) else None
        t_dht22 = dht22.get("temperature_c") if isinstance(dht22, dict) else None
        co2_val = scd30.get("co2_ppm") if isinstance(scd30, dict) else None

        # Check for unphysical or null readings
        if t_scd30 is None or t_dht22 is None or co2_val is None:
            return HealthState.FAULT, tau_age, None

        # Check physical boundary limits
        if not (-40.0 <= t_scd30 <= 70.0) or not (-40.0 <= t_dht22 <= 80.0) or not (0.0 <= co2_val <= 10000.0):
            return HealthState.FAULT, tau_age, None

        delta_t = abs(float(t_scd30) - float(t_dht22))

        # Check for blower motor stall/slip fault (PWM >= 30% with Tachometer RPM < 100)
        actuator = payload.get("actuator_state", {})
        if isinstance(actuator, dict):
            pwm = actuator.get("pwm_duty_pct")
            rpm = actuator.get("tachometer_rpm")
            if pwm is not None and rpm is not None:
                if float(pwm) >= 30.0 and float(rpm) < 100.0:
                    return HealthState.FAULT, tau_age, delta_t

        # Evaluate piecewise health boundaries
        if tau_age > self.max_stale_s:
            return HealthState.FAULT, tau_age, delta_t

        # Check thermal divergence (Delta T > 1.5°C)
        if delta_t > self.max_delta_t_c:
            return HealthState.DEGRADED, tau_age, delta_t

        # Check relative humidity divergence (Delta RH > 10%)
        rh_scd30 = scd30.get("humidity_pct") if isinstance(scd30, dict) else None
        rh_dht22 = dht22.get("humidity_pct") if isinstance(dht22, dict) else None
        if rh_scd30 is not None and rh_dht22 is not None:
            delta_rh = abs(float(rh_scd30) - float(rh_dht22))
            if delta_rh > self.max_delta_rh_pct:
                return HealthState.DEGRADED, tau_age, delta_t

        if tau_age > self.max_latency_s:
            return HealthState.STALE, tau_age, delta_t

        return HealthState.FRESH, tau_age, delta_t
