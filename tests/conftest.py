"""Pytest configuration and shared fixtures for unit and integration testing."""

import sys
from pathlib import Path
import pytest

# Ensure services/bridge_ae/src is on the module search path
REPO_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_SRC = REPO_ROOT / "services" / "bridge_ae" / "src"
if str(BRIDGE_SRC) not in sys.path:
    sys.path.insert(0, str(BRIDGE_SRC))


@pytest.fixture
def nominal_telemetry_frame():
    """Provides a valid, calibrated nominal sensor telemetry frame."""
    return {
        "vehicle_id": "vehicle_01",
        "timestamp_unix_s": 1700000000.0,
        "scd30": {
            "co2_ppm": 480.0,
            "temperature_c": 21.8,
            "relative_humidity_pct": 45.0,
            "status": "OK"
        },
        "dht22": {
            "temperature_c": 22.0,
            "relative_humidity_pct": 46.0,
            "status": "OK"
        },
        "actuation": {
            "fan_duty_pct": 25.0,
            "fan_rpm": 980,
            "status": "RUNNING"
        }
    }
