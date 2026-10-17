#!/usr/bin/env python3
"""
Software-Defined Vehicle (SDV) Cabin Monitoring - FHTW-AIOT Research Cluster
Automated Environment & Vanilla oneM2M Base CSE Validation & Verification Suite

Conforms to:
  - ETSI TS 118 101 Release 4 Functional Architecture
  - oneM2M TS-0004 Core Protocol Specification
  - oneM2M TS-0010 MQTT Protocol Binding
  - Insomnia Collection 1: SDV_Fleet_01_Environment_Base_CSE
  - Insomnia Collection 4: SDV_Fleet_04_Environment_CSEBase_Validation_Verification
  - SOP-SDV-ONEM2M-001 / FHTW-SDV-ARCH-005
"""

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Terminal ANSI colours
GREEN = "\033[92m"
BLUE = "\033[94m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def load_env_file(filepath: Path) -> Dict[str, str]:
    """Loads environment key-values from deploy/.env file."""
    env_vars: Dict[str, str] = {}
    if not filepath.exists():
        return env_vars
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            clean = line.strip()
            if clean and not clean.startswith("#") and "=" in clean:
                k, v = clean.split("=", 1)
                env_vars[k.strip()] = v.strip().strip("'\"")
    return env_vars


class BaseCSEValidator:
    """Automated validator and verifier for the environment and vanilla Base CSE."""

    def __init__(self):
        self.root_dir = Path(__file__).resolve().parent.parent.parent
        self.env_file = self.root_dir / "deploy" / ".env"
        self.env = load_env_file(self.env_file)

        # Config resolution
        self.cse_host = os.getenv("CSE_HOST", "localhost")
        self.cse_port = int(self.env.get("ONEM2M_PORT", os.getenv("CSE_PORT", "8080")))
        self.cse_name = self.env.get("ONEM2M_CSE_NAME", os.getenv("CSE_NAME", "sdv-cse"))
        self.cse_id = self.env.get("ONEM2M_CSE_ID", os.getenv("CSE_ID", "id-sdv"))
        self.originator = self.env.get("ONEM2M_ADMIN_ORIGIN", os.getenv("ORIGIN", "CAdmin"))
        self.rvi = self.env.get("ONEM2M_RVI", os.getenv("RVI", "3"))
        self.base_url = f"http://{self.cse_host}:{self.cse_port}/{self.cse_name}"

        self.mqtt_port = int(self.env.get("MOSQUITTO_PORT", "1883"))
        self.mqtt_mtls_port = 8883

        self.results: List[Tuple[str, str, bool, str]] = []

    def _execute_request(
        self,
        method: str,
        path_or_url: str,
        originator: Optional[str] = None,
        headers_extra: Optional[Dict[str, str]] = None
    ) -> Tuple[int, Dict[str, str], Any, float]:
        """Issues an HTTP request to the oneM2M CSE."""
        if path_or_url.startswith("http"):
            url = path_or_url
        elif path_or_url.startswith("?"):
            url = f"{self.base_url}{path_or_url}"
        elif not path_or_url or path_or_url.strip() == "":
            url = self.base_url
        else:
            url = f"{self.base_url}/{path_or_url.lstrip('/')}"

        origin = originator or self.originator
        req_id = f"val_{int(time.time() * 1000)}"

        headers = {
            "X-M2M-Origin": origin,
            "X-M2M-RI": req_id,
            "X-M2M-RVI": self.rvi,
            "Accept": "application/json"
        }
        if headers_extra:
            headers.update(headers_extra)

        req = urllib.request.Request(url, headers=headers, method=method)
        t_start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                elapsed = (time.perf_counter() - t_start) * 1000.0
                resp_headers = dict(resp.headers)
                body_bytes = resp.read()
                try:
                    parsed = json.loads(body_bytes.decode("utf-8"))
                except Exception:
                    parsed = body_bytes.decode("utf-8", errors="replace")
                return resp.status, resp_headers, parsed, elapsed
        except urllib.error.HTTPError as http_err:
            elapsed = (time.perf_counter() - t_start) * 1000.0
            resp_headers = dict(http_err.headers)
            body_bytes = http_err.read()
            try:
                parsed = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                parsed = body_bytes.decode("utf-8", errors="replace")
            return http_err.code, resp_headers, parsed, elapsed
        except Exception as exc:
            elapsed = (time.perf_counter() - t_start) * 1000.0
            return 0, {}, {"error": str(exc)}, elapsed

    def test_environment_variables(self) -> bool:
        """Verifies presence and sanity of mandatory environment variables."""
        test_name = "01_ENV_CONFIG"
        desc = "Validate deploy/.env parameters"
        missing = []
        required = ["ONEM2M_CSE_ID", "ONEM2M_CSE_NAME", "ONEM2M_PORT", "ONEM2M_ADMIN_ORIGIN"]
        for key in required:
            val = self.env.get(key)
            if not val or val.strip() == "":
                missing.append(key)

        if missing:
            self.results.append((test_name, desc, False, f"Missing required env keys: {', '.join(missing)}"))
            return False

        detail = f"CSE_ID={self.cse_id}, CSE_NAME={self.cse_name}, PORT={self.cse_port}, ORIGIN={self.originator}"
        self.results.append((test_name, desc, True, detail))
        return True

    def test_csebase_reachability(self) -> bool:
        """Verifies root CSEBase endpoint reachability over HTTP (Collection 1 - Req 0.1)."""
        test_name = "02_CSE_REACHABLE"
        desc = f"GET {self.base_url} (HTTP 200 & RSC 2000)"
        status, headers, body, latency = self._execute_request("GET", "")

        if status != 200:
            self.results.append((test_name, desc, False, f"HTTP {status} (latency {latency:.1f}ms)"))
            return False

        rsc = headers.get("X-M2M-RSC", "")
        if rsc and rsc != "2000":
            self.results.append((test_name, desc, False, f"HTTP 200 but RSC is {rsc} (expected 2000)"))
            return False

        self.results.append((test_name, desc, True, f"HTTP 200 OK, RSC {rsc or '2000'} ({latency:.1f}ms)"))
        return True

    def test_csebase_semantic_attributes(self) -> bool:
        """Verifies <m2m:cb> resource attributes, type, CSE-ID, and release versions."""
        test_name = "03_CSE_SEMANTICS"
        desc = "Verify <m2m:cb> resource representation"
        status, _, body, latency = self._execute_request("GET", "")

        if status != 200 or not isinstance(body, dict) or "m2m:cb" not in body:
            self.results.append((test_name, desc, False, "Response does not contain 'm2m:cb' representation"))
            return False

        cb = body["m2m:cb"]
        rn = cb.get("rn")
        ty = cb.get("ty")
        csi = cb.get("csi", "")
        srv = cb.get("srv", [])

        errors = []
        if ty != 5:
            errors.append(f"ty={ty} (expected 5)")
        if rn != self.cse_name:
            errors.append(f"rn={rn} (expected {self.cse_name})")
        if not any(cand in csi for cand in [self.cse_id, "id-sdv"]):
            errors.append(f"csi={csi} (expected {self.cse_id} or id-sdv)")
        if not any(v in ("2a", "3", "4", "5") for v in srv):
            errors.append(f"srv={srv} (expected oneM2M Release 4 / srv >= 2a)")

        if errors:
            self.results.append((test_name, desc, False, "; ".join(errors)))
            return False

        detail = f"ty={ty} (CSEBase), rn={rn}, csi={csi}, srv={srv}"
        self.results.append((test_name, desc, True, detail))
        return True

    def test_strict_absence_of_application_entities(self) -> bool:
        """Verifies strictly zero Application Entities (e.g. NO AE_CabinNode_Car01) in vanilla base."""
        test_name = "04_VANILLA_NO_AE"
        desc = "Strict absence of Application Entities (<m2m:ae>, ty=2)"
        status, _, body, latency = self._execute_request("GET", "?fu=1&ty=2")

        if status != 200 or not isinstance(body, dict):
            self.results.append((test_name, desc, False, f"Discovery request failed (HTTP {status})"))
            return False

        uril = body.get("m2m:uril", [])
        # Filter out administrative originator CAdmin
        vehicular_aes = [uri for uri in uril if not uri.endswith("/CAdmin") and not uri.endswith(f"/{self.originator}")]

        if vehicular_aes:
            self.results.append((
                test_name,
                desc,
                False,
                f"Found {len(vehicular_aes)} non-vanilla AE(s): {', '.join(vehicular_aes)}"
            ))
            return False

        self.results.append((test_name, desc, True, f"Verified 0 vehicular Application Entities in CSEBase ({latency:.1f}ms)"))
        return True

    def test_baseline_governance_entities(self) -> bool:
        """Verifies baseline Access Control Policy (acp_fleet_manager) and group (grp_fleet_telemetry)."""
        test_name = "05_GOVERNANCE"
        desc = "Verify acp_fleet_manager and grp_fleet_telemetry"

        # Check ACP
        status_acp, _, body_acp, _ = self._execute_request("GET", "acp_fleet_manager")
        has_acp = status_acp == 200 and isinstance(body_acp, dict) and "m2m:acp" in body_acp

        # Check Group
        status_grp, _, body_grp, _ = self._execute_request("GET", "grp_fleet_telemetry")
        has_grp = status_grp == 200 and isinstance(body_grp, dict) and "m2m:grp" in body_grp

        if not has_acp or not has_grp:
            details = []
            if not has_acp:
                details.append(f"acp_fleet_manager missing (HTTP {status_acp})")
            if not has_grp:
                details.append(f"grp_fleet_telemetry missing (HTTP {status_grp})")
            self.results.append((test_name, desc, False, "; ".join(details)))
            return False

        grp_mid = body_grp["m2m:grp"].get("mid", [])
        detail = f"acp_fleet_manager present (ty=1); grp_fleet_telemetry present (ty=9, {len(grp_mid)} members)"
        self.results.append((test_name, desc, True, detail))
        return True

    def test_mqtt_binding_ports(self) -> bool:
        """Verifies native In-CSE MQTT protocol binding ports (1883 internal mesh, 8883 mTLS)."""
        test_name = "06_MQTT_TRANSPORT"
        desc = "Native oneM2M TS-0010 MQTT protocol ports"
        ports = [("Internal Mesh (Port 1883)", 1883), ("Mutual TLS 1.3 (Port 8883)", 8883)]
        active = []
        failed = []

        for label, port in ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            try:
                res = sock.connect_ex((self.cse_host, port))
                if res == 0:
                    active.append(f"{label}: OPEN")
                else:
                    failed.append(f"{label}: CLOSED (code {res})")
            except Exception as e:
                failed.append(f"{label}: ERROR ({e})")
            finally:
                sock.close()

        if failed:
            self.results.append((test_name, desc, False, "; ".join(failed)))
            return False

        self.results.append((test_name, desc, True, "; ".join(active)))
        return True

    def run_all(self) -> bool:
        """Executes all verification checks and prints an audit report."""
        print(f"\n{BOLD}{BLUE}================================================================================{RESET}")
        print(f"{BOLD}{BLUE}  SDV AUTOMOTIVE IOT: LEAN BASE CSE VALIDATION & VERIFICATION SUITE{RESET}")
        print(f"{BLUE}  Standard Conformance: ETSI TS 118 101 Rel 4 / oneM2M TS-0004 & TS-0010{RESET}")
        print(f"{BLUE}  Target: {self.base_url} | Originator: {self.originator} | Mode: Vanilla Base CSE{RESET}")
        print(f"{BOLD}{BLUE}================================================================================{RESET}\n")

        self.test_environment_variables()
        self.test_csebase_reachability()
        self.test_csebase_semantic_attributes()
        self.test_strict_absence_of_application_entities()
        self.test_baseline_governance_entities()
        self.test_mqtt_binding_ports()

        all_passed = True
        print(f"{BOLD}{'STATUS':<8} | {'TEST IDENTIFIER':<20} | {'DESCRIPTION & AUDIT DETAILS':<48}{RESET}")
        print("-" * 80)
        for t_id, desc, passed, detail in self.results:
            if passed:
                status_badge = f"{GREEN}{BOLD}PASS{RESET}"
            else:
                status_badge = f"{RED}{BOLD}FAIL{RESET}"
                all_passed = False
            print(f"{status_badge:<17} | {BOLD}{t_id:<20}{RESET} | {desc}")
            print(f"         | {'':<20} | {CYAN}-> {detail}{RESET}")

        print("-" * 80)
        passed_count = sum(1 for _, _, p, _ in self.results if p)
        total_count = len(self.results)
        score_pct = (passed_count / total_count) * 100.0

        if all_passed:
            print(f"\n{GREEN}{BOLD}[SUCCESS] 100% COMPLIANT: Vanilla Base CSE Verified! ({passed_count}/{total_count} Passed - {score_pct:.1f}%){RESET}")
            print(f"{GREEN}The Base CSE is running with environment variables and zero Application Entities.{RESET}\n")
            return True
        else:
            print(f"\n{RED}{BOLD}[FAILURE] Base CSE Verification Failed ({passed_count}/{total_count} Passed - {score_pct:.1f}%){RESET}\n")
            return False


if __name__ == "__main__":
    validator = BaseCSEValidator()
    success = validator.run_all()
    sys.exit(0 if success else 1)
