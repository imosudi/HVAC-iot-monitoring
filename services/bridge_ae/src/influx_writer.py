"""Client service committing timestamped telemetry metrics to InfluxDB 2.x."""

import logging
from typing import Any, Dict, Optional

try:
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
    INFLUX_CLIENT_INSTALLED = True
except ImportError:
    InfluxDBClient = None
    SYNCHRONOUS = None
    INFLUX_CLIENT_INSTALLED = False

    class WritePrecision:
        NS = "ns"

    class Point:
        def __init__(self, measurement: str):
            self.measurement = measurement
            self.tags = {}
            self.fields = {}
            self._time = None

        def tag(self, k: str, v: Any):
            self.tags[k] = v
            return self

        def field(self, k: str, v: Any):
            self.fields[k] = v
            return self

        def time(self, t: Any, precision: Any = None):
            self._time = t
            return self

try:
    from .config import config
    from .health_classifier import HealthState
except (ImportError, ValueError):
    from config import config
    from health_classifier import HealthState


logger = logging.getLogger(__name__)



class InfluxWriter:
    """Handles point formatting and synchronous writes to InfluxDB."""

    def __init__(self):
        self.client: Optional[InfluxDBClient] = None
        self.write_api = None
        self._initialise_client()

    def _initialise_client(self):
        if not config.influxdb_token:
            logger.warning("InfluxDB token not set. Ingestion will operate in mock mode.")
            return

        try:
            self.client = InfluxDBClient(
                url=config.influxdb_url,
                token=config.influxdb_token,
                org=config.influxdb_org
            )
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            logger.info("Successfully connected to InfluxDB at %s", config.influxdb_url)
        except Exception as exc:
            logger.error("Failed to connect to InfluxDB: %s", exc)

    def write_telemetry(
        self,
        payload: Dict[str, Any],
        health_state: HealthState,
        tau_age: float,
        delta_t: Optional[float]
    ):
        """Converts structured telemetry frame into InfluxDB line-protocol points."""
        if not self.write_api:
            logger.debug("Mock write (no InfluxDB connection): State=%s, tau_age=%.2fs", health_state.value, tau_age)
            return

        car_id = payload.get("car_id", "unknown_vehicle")
        zone = payload.get("zone", "cabin_front")
        timestamp_s = payload.get("timestamp_unix_s", 0)

        point = (
            Point("cabin_environment")
            .tag("car_id", car_id)
            .tag("zone", zone)
            .tag("health_state", health_state.value)
            .field("tau_age_s", float(tau_age))
            .time(int(timestamp_s * 1e9), WritePrecision.NS)
        )

        if delta_t is not None:
            point.field("delta_t_c", float(delta_t))

        # Under FAULT regimes, omit corrupt numerical values to prevent false aggregation
        if health_state != HealthState.FAULT:
            scd30 = payload.get("scd30", {})
            dht22 = payload.get("dht22", {})
            actuator = payload.get("actuator_state", {})

            if isinstance(scd30, dict) and scd30.get("co2_ppm") is not None:
                point.field("co2_ppm", float(scd30["co2_ppm"]))
                point.field("temp_scd30_c", float(scd30["temperature_c"]))
                point.field("humidity_scd30_pct", float(scd30["humidity_pct"]))

            if isinstance(dht22, dict) and dht22.get("temperature_c") is not None:
                point.field("temp_dht22_c", float(dht22["temperature_c"]))
                point.field("humidity_dht22_pct", float(dht22["humidity_pct"]))

            if isinstance(actuator, dict):
                point.field("fan_duty_pct", int(actuator.get("pwm_duty_pct", 0)))
                point.field("fan_rpm", int(actuator.get("tachometer_rpm", 0)))

        try:
            self.write_api.write(bucket=config.influxdb_bucket, org=config.influxdb_org, record=point)
            logger.debug("Committed point to InfluxDB bucket '%s'", config.influxdb_bucket)
        except Exception as exc:
            logger.error("Error writing telemetry to InfluxDB: %s", exc)
