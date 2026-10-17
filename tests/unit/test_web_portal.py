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
        """Verifies that the root path renders the FH Technikum Wien branded Bootstrap 5 dashboard."""
        response = client.get("/")
        assert response.status_code == 200
        content = response.data.decode("utf-8")

        # Verify key design tokens and Bootstrap 5 components
        assert 'data-bs-theme="light"' in content
        assert "FH Technikum Wien" in content
        assert "Roboto" in content
        assert "SCD30 Carbon Dioxide" in content
        assert "DOWNLINK ACTUATION CONTROLLER" in content

    def test_multipage_routes_render_successfully(self, client):
        """Verifies that core operational views render HTTP 200 OK and pruned documentation pages return 404."""
        # Operational dashboards
        assert client.get("/").status_code == 200
        assert client.get("/entities").status_code == 200

        # Pruned documentation pages migrated to /foundational_document/
        for route in ["/architecture", "/security", "/validation"]:
            response = client.get(route)
            assert response.status_code == 404, f"Expected 404 for migrated documentation route {route}"

    def test_health_probe_returns_up(self, client):
        """Verifies the service liveness probe endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "UP"
        assert data["service"] == "web_portal"

    def test_api_telemetry_latest_returns_valid_payload(self, client):
        """Verifies that the telemetry API endpoint serves a schema-compliant frame with multi-vehicle support."""
        # Default nominal vehicle
        response = client.get("/api/telemetry/latest")
        assert response.status_code == 200
        data = response.get_json()
        assert data["car_id"] == "vehicle_01"
        assert "scd30" in data
        assert "co2_ppm" in data["scd30"]
        assert "actuator_state" in data
        assert "health_state" in data

        # Explicit vehicle selection across fleet
        v2_resp = client.get("/api/telemetry/latest?car_id=vehicle_02")
        assert v2_resp.status_code == 200
        v2_data = v2_resp.get_json()
        assert v2_data["car_id"] == "vehicle_02"
        assert "scd30" in v2_data

    def test_api_vehicles_endpoint(self, client):
        """Verifies that the fleet vehicles discovery endpoint returns registered vehicles structure."""
        response = client.get("/api/vehicles")
        assert response.status_code == 200
        data = response.get_json()
        assert "vehicles" in data
        assert "count" in data
        assert isinstance(data["vehicles"], list)

    def test_api_actuator_dispatch_validates_input(self, client):
        """Verifies validation logic on the downlink actuation endpoint with dynamic vehicle targeting."""
        # Valid dispatch for default vehicle
        response = client.post("/api/actuator/dispatch", json={
            "target_pwm": 50,
            "mode": "AUTOMATIC",
            "source_entity": "TestHarness"
        })
        assert response.status_code == 200
        result = response.get_json()
        assert "status" in result
        assert result["car_id"] == "vehicle_01"

        # Valid dispatch targeting vehicle_02 in fleet
        v2_resp = client.post("/api/actuator/dispatch", json={
            "car_id": "vehicle_02",
            "target_pwm": 75,
            "mode": "PURGE_75",
            "source_entity": "TestHarness"
        })
        assert v2_resp.status_code == 200
        v2_res = v2_resp.get_json()
        assert v2_res["car_id"] == "vehicle_02"
        assert v2_res["target_ae"] == "AE_CabinNode_Car02"

        # Invalid target_pwm out of bounds
        invalid_resp = client.post("/api/actuator/dispatch", json={
            "target_pwm": 150
        })
        assert invalid_resp.status_code == 400

    def test_entities_route_renders_successfully(self, client):
        """Verifies that the /entities Application Entity management view renders successfully."""
        response = client.get("/entities")
        assert response.status_code == 200
        content = response.data.decode("utf-8")
        assert "oneM2M Entity Provisioner" in content
        assert "Single Vehicle Deployment" in content
        assert "Interactive oneM2M REST API Client Workbench" in content
        assert "APPLICATION ENTITIES &amp; API CLIENT" in content

    def test_api_onem2m_status_endpoint(self, client):
        """Verifies the oneM2M CSE status probe endpoint."""
        response = client.get("/api/onem2m/status")
        assert response.status_code == 200
        data = response.get_json()
        assert "base_url" in data
        assert "connected" in data

    def test_api_onem2m_entities_endpoint(self, client):
        """Verifies that the entities list endpoint returns registered AEs."""
        response = client.get("/api/onem2m/entities")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "SUCCESS"
        assert isinstance(data["entities"], list)

    def test_api_onem2m_deploy_validates_input(self, client):
        """Verifies validation on the AE deployment endpoint."""
        # Missing ae_rn
        response = client.post("/api/onem2m/deploy", json={})
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_api_onem2m_request_proxy_endpoint(self, client):
        """Verifies the generic oneM2M REST API client proxy endpoint."""
        # Missing path
        bad_response = client.post("/api/onem2m/request", json={})
        assert bad_response.status_code == 400

        # Valid GET request proxy
        response = client.post("/api/onem2m/request", json={
            "method": "GET",
            "path": "sdv-cse"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert "status" in data
        assert "latency_ms" in data
        assert "target_url" in data

    def test_api_onem2m_validate_endpoint(self, client):
        """Verifies the single vehicle validation endpoint against an existing or non-existent entity."""
        # Non-existent vehicle
        resp_404 = client.get("/api/onem2m/entities/NonExistent_Vehicle_999/validate")
        assert resp_404.status_code == 200
        data_404 = resp_404.get_json()
        assert data_404["valid"] is False
        assert "checks" in data_404

        # Existing vehicle AE_CabinNode_Car01
        resp = client.get("/api/onem2m/entities/AE_CabinNode_Car01/validate")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "compliance_score_pct" in data
        assert "checks" in data
        assert "checks_passed" in data

    def test_api_onem2m_deploy_and_validate_validates_input(self, client):
        """Verifies input validation on the deploy-and-validate endpoint."""
        response = client.post("/api/onem2m/deploy-and-validate", json={})
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_api_onem2m_batch_decommission_validates_input(self, client):
        """Verifies validation on batch decommissioning with empty or missing list."""
        # Empty payload
        resp_empty = client.post("/api/onem2m/batch-decommission", json={})
        assert resp_empty.status_code == 400

        # Empty list
        resp_empty_list = client.post("/api/onem2m/batch-decommission", json={"ae_rns": []})
        assert resp_empty_list.status_code == 400

