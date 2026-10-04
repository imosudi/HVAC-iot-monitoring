"""Unit tests validating the public-facing Flask web application and Bootstrap 5 UI."""

import sys
from pathlib import Path
import pytest
from flask import Flask

# Ensure repository root and services/web_portal are on module search path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
WEB_PORTAL_DIR = REPO_ROOT / "services" / "web_portal"
if str(WEB_PORTAL_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_PORTAL_DIR))

import app as web_app_module
from app import app


@pytest.fixture
def client():
    """Provides a test client for the directly instantiated Flask application."""
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


class TestWebPortalApplication:
    """Verifies architectural constraints, routing behaviour, and UI components."""

    def test_direct_module_instantiation_without_factory(self):
        """Verifies that the application does not utilise an application factory pattern."""
        assert isinstance(app, Flask)
        assert not hasattr(web_app_module, "create_app"), (
            "Found 'create_app' factory function; architectural constraint requires direct instantiation."
        )

    def test_index_route_renders_bootstrap5_ui(self, client):
        """Verifies that the root path renders the Stitch-conforming Bootstrap 5 dashboard."""
        response = client.get("/")
        assert response.status_code == 200
        content = response.data.decode("utf-8")

        # Verify key design tokens and Bootstrap 5 components
        assert 'data-bs-theme="dark"' in content
        assert "SDV-MEC" in content
        assert "Space Grotesk" in content
        assert "rounded-0" in content
        assert "SCD30 Carbon Dioxide" in content
        assert "DOWNLINK ACTUATION CONTROLLER" in content

    def test_multipage_routes_render_successfully(self, client):
        """Verifies that all Stitch multipage screens render with HTTP 200 OK."""
        pages = {
            "/architecture": "5-Stage Deterministic Pipeline Topology",
            "/security": "Three-State Data Health Evaluation",
            "/validation": "Three-Tier Empirical Verification"
        }
        for route, expected_text in pages.items():
            response = client.get(route)
            assert response.status_code == 200, f"Route {route} failed with status {response.status_code}"
            assert expected_text in response.data.decode("utf-8"), f"Expected text missing on route {route}"

    def test_health_probe_returns_up(self, client):
        """Verifies the service liveness probe endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "UP"
        assert data["service"] == "web_portal"

    def test_api_telemetry_latest_returns_valid_payload(self, client):
        """Verifies that the telemetry API endpoint serves a schema-compliant frame."""
        response = client.get("/api/telemetry/latest")
        assert response.status_code == 200
        data = response.get_json()
        assert data["car_id"] == "vehicle_01"
        assert "scd30" in data
        assert "co2_ppm" in data["scd30"]
        assert "actuator_state" in data
        assert "health_state" in data

    def test_api_actuator_dispatch_validates_input(self, client):
        """Verifies validation logic on the downlink actuation endpoint."""
        # Valid dispatch
        response = client.post("/api/actuator/dispatch", json={
            "target_pwm": 50,
            "mode": "AUTOMATIC",
            "source_entity": "TestHarness"
        })
        assert response.status_code == 200
        result = response.get_json()
        assert "status" in result

        # Invalid target_pwm out of bounds
        invalid_resp = client.post("/api/actuator/dispatch", json={
            "target_pwm": 150
        })
        assert invalid_resp.status_code == 400
