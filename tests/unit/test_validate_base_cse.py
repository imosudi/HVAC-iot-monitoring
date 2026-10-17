"""
Unit Tests for oneM2M Base CSE Automated Validation Suite
Verifies BaseCSEValidator configuration loading, request construction,
and compliance evaluation logic.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add scripts directory to path for import
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts" / "testing"))

from validate_base_cse import BaseCSEValidator, load_env_file


class TestBaseCSEValidator:
    """Validates BaseCSEValidator methods and verification logic."""

    def test_load_env_file(self, tmp_path):
        """Verifies environment file parsing handles comments, quotes, and whitespace."""
        env_content = """
        # Comment line
        ONEM2M_CSE_ID=id-sdv
        ONEM2M_CSE_NAME="sdv-cse"
        ONEM2M_PORT='8080'
        EMPTY_LINE=
        """
        env_file = tmp_path / ".env"
        env_file.write_text(env_content)

        parsed = load_env_file(env_file)
        assert parsed.get("ONEM2M_CSE_ID") == "id-sdv"
        assert parsed.get("ONEM2M_CSE_NAME") == "sdv-cse"
        assert parsed.get("ONEM2M_PORT") == "8080"
        assert parsed.get("EMPTY_LINE") == ""

    def test_environment_variables_verification_pass(self):
        """Verifies test_environment_variables succeeds when required keys are set."""
        validator = BaseCSEValidator()
        validator.env = {
            "ONEM2M_CSE_ID": "id-sdv",
            "ONEM2M_CSE_NAME": "sdv-cse",
            "ONEM2M_PORT": "8080",
            "ONEM2M_ADMIN_ORIGIN": "CAdmin",
        }
        validator.cse_id = "id-sdv"
        validator.cse_name = "sdv-cse"
        validator.cse_port = 8080
        validator.originator = "CAdmin"

        assert validator.test_environment_variables() is True
        assert len(validator.results) > 0
        assert validator.results[-1][2] is True

    def test_environment_variables_verification_missing_keys(self):
        """Verifies test_environment_variables fails cleanly when mandatory keys are missing."""
        validator = BaseCSEValidator()
        validator.env = {"ONEM2M_CSE_ID": "id-sdv"}

        assert validator.test_environment_variables() is False
        assert len(validator.results) > 0
        assert validator.results[-1][2] is False
        assert "Missing required env keys" in validator.results[-1][3]

    def test_csebase_semantic_attributes_pass(self):
        """Verifies test_csebase_semantic_attributes passes with valid <m2m:cb>."""
        validator = BaseCSEValidator()
        mock_cb_resp = {
            "m2m:cb": {
                "rn": "sdv-cse",
                "ty": 5,
                "csi": "/id-sdv",
                "srv": ["2a", "3", "4", "5"],
            }
        }
        with patch.object(validator, "_execute_request", return_value=(200, {}, mock_cb_resp, 1.2)):
            assert validator.test_csebase_semantic_attributes() is True

    def test_csebase_semantic_attributes_fails_on_wrong_type(self):
        """Verifies test_csebase_semantic_attributes catches invalid resource type."""
        validator = BaseCSEValidator()
        mock_cb_resp = {
            "m2m:cb": {
                "rn": "sdv-cse",
                "ty": 2,  # Invalid: 2 is AE, not CSEBase (5)
                "csi": "/id-sdv",
                "srv": ["3"],
            }
        }
        with patch.object(validator, "_execute_request", return_value=(200, {}, mock_cb_resp, 1.0)):
            assert validator.test_csebase_semantic_attributes() is False
            assert "ty=2 (expected 5)" in validator.results[-1][3]

    def test_strict_absence_of_application_entities_passes_when_clean(self):
        """Verifies discovery asserting strictly zero vehicular AEs."""
        validator = BaseCSEValidator()
        # Admin CAdmin is allowed; no vehicular AE present
        mock_disc_resp = {
            "m2m:uril": ["sdv-cse/CAdmin"]
        }
        with patch.object(validator, "_execute_request", return_value=(200, {}, mock_disc_resp, 2.0)):
            assert validator.test_strict_absence_of_application_entities() is True

    def test_strict_absence_of_application_entities_detects_rogue_ae(self):
        """Verifies discovery fails if an AE (e.g. AE_CabinNode_Car01) is present."""
        validator = BaseCSEValidator()
        mock_disc_resp = {
            "m2m:uril": ["sdv-cse/CAdmin", "sdv-cse/AE_CabinNode_Car01"]
        }
        with patch.object(validator, "_execute_request", return_value=(200, {}, mock_disc_resp, 2.0)):
            assert validator.test_strict_absence_of_application_entities() is False
            assert "AE_CabinNode_Car01" in validator.results[-1][3]
