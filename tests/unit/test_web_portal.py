"""Unit tests validating the public-facing Flask web application."""

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
    """Verifies architectural constraints and routing behaviour for the web interface."""

    def test_direct_module_instantiation_without_factory(self):
        """Verifies that the application does not utilise an application factory pattern."""
        assert isinstance(app, Flask)
        assert not hasattr(web_app_module, "create_app"), (
            "Found 'create_app' factory function; architectural constraint requires direct instantiation."
        )

    def test_index_route_returns_http_200(self, client):
        """Verifies that the root path responds with HTTP 200 OK."""
        response = client.get("/")
        assert response.status_code == 200

    def test_index_route_is_blank_devoid_of_ui_ux(self, client):
        """Verifies that the index page is blank, devoid of interactive or styled UI/UX elements."""
        response = client.get("/")
        content = response.data.decode("utf-8")

        # Must not contain styled layout elements or components
        ui_indicators = [
            "<button", "<input", "<form", "<nav", "<table",
            "class=\"card\"", "class=\"btn\"", "dashboard", "sidebar"
        ]
        for indicator in ui_indicators:
            assert indicator not in content.lower(), f"Unexpected UI element found in blank index: {indicator}"

        # Body element must be empty
        assert "<body>\n</body>" in content or "<body></body>" in content

    def test_health_probe_returns_up(self, client):
        """Verifies the service liveness probe endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "UP"
        assert data["service"] == "web_portal"
