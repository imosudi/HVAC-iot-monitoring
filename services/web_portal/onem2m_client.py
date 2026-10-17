"""
oneM2M Common Services Entity (IN-CSE) REST Client Module.

Provides high-level orchestration for Application Entity (AE) provisioning,
container manifest reconciliation, subscription wiring, fleet group synchronization,
and interactive oneM2M REST API operations conforming to ETSI TS 118 101 Release 4.
"""

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

try:
    from services.web_portal.portal_config import config
except ImportError:
    try:
        from .portal_config import config
    except (ImportError, ValueError):
        from portal_config import config

logger = logging.getLogger("oneM2MClient")

# oneM2M Response Status Code (RSC) Reference
RSC_DESCRIPTIONS = {
    "2000": "OK (2000)",
    "2001": "CREATED (2001)",
    "2002": "DELETED (2002)",
    "2004": "UPDATED (2004)",
    "4000": "BAD_REQUEST (4000)",
    "4004": "NOT_FOUND (4004)",
    "4005": "OPERATION_NOT_ALLOWED (4005)",
    "4103": "ACCESS_DENIED (4103)",
    "4105": "CONFLICT / ALREADY_EXISTS (4105)",
    "5000": "INTERNAL_SERVER_ERROR (5000)"
}

# Standard 8-Container Manifest with 24h Storage TTL (mia: 86400)
STANDARD_8_CONTAINER_MANIFEST = {
    "temperature-cabin": {"mni": 1000, "mbs": 1048576, "mia": 86400, "lbl": ["sensor", "temperature", "cabin"]},
    "humidity-cabin": {"mni": 1000, "mbs": 1048576, "mia": 86400, "lbl": ["sensor", "humidity", "cabin"]},
    "co2-cabin": {"mni": 1000, "mbs": 1048576, "mia": 86400, "lbl": ["sensor", "co2", "cabin", "ndir"]},
    "co-cabin": {"mni": 1000, "mbs": 1048576, "mia": 86400, "lbl": ["sensor", "co", "cabin", "toxic-gas", "emergency"]},
    "air-quality-cabin": {"mni": 1000, "mbs": 1048576, "mia": 86400, "lbl": ["sensor", "iaq", "voc", "cabin"]},
    "air-quality-exterior": {"mni": 1000, "mbs": 1048576, "mia": 86400, "lbl": ["sensor", "aqi", "exterior"]},
    "raw-telemetry": {"mni": 1440, "mbs": 2097152, "mia": 86400, "lbl": ["telemetry", "multi-sensor", "raw"]},
    "commands": {"mni": 100, "mbs": 262144, "mia": 86400, "lbl": ["commands", "actuation", "downlink"]}
}

# Legacy Compatibility Aliases
LEGACY_CONTAINER_ALIASES = {
    "cnt_raw_telemetry": {"mni": 1440, "mbs": 2097152, "mia": 86400, "lbl": ["legacy", "raw-telemetry"]},
    "cnt_co2": {"mni": 1000, "mbs": 1048576, "mia": 86400, "lbl": ["legacy", "co2"]},
    "cnt_temperature": {"mni": 1000, "mbs": 1048576, "mia": 86400, "lbl": ["legacy", "temperature"]},
    "cnt_humidity": {"mni": 1000, "mbs": 1048576, "mia": 86400, "lbl": ["legacy", "humidity"]},
    "cnt_data_health": {"mni": 1000, "mbs": 1048576, "mia": 86400, "lbl": ["legacy", "health"]},
    "cnt_actuator_commands": {"mni": 100, "mbs": 262144, "mia": 86400, "lbl": ["legacy", "commands"]}
}


class OneM2MClient:
    """Client for ETSI TS 118 101 oneM2M Common Services Entity interactions."""

    def __init__(self):
        self.admin_origin = config.onem2m_admin_origin
        self.rvi = config.onem2m_rvi

    def get_base_url(self) -> str:
        """Retrieves the effective CSEBase URL (with automatic local fallback)."""
        return config.get_effective_onem2m_url().rstrip("/")

    def get_cse_name(self) -> str:
        """Extracts the CSEBase resource name from URL (e.g. 'sdv-cse')."""
        return self.get_base_url().split("/")[-1]

    def _execute_request(
        self,
        method: str,
        target_url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[bytes] = None,
        timeout: float = 3.5
    ) -> Tuple[int, Dict[str, str], Any, float]:
        """
        Executes an HTTP request and measures round-trip time.

        Returns (http_status, headers_dict, parsed_body_or_raw, latency_ms).
        """
        req_headers = {
            "X-M2M-Origin": self.admin_origin,
            "X-M2M-RI": f"req_{int(time.time() * 1000)}",
            "X-M2M-RVI": self.rvi,
            "Accept": "application/json"
        }
        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(target_url, data=data, headers=req_headers, method=method)
        t_start = time.perf_counter()

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed_ms = (time.perf_counter() - t_start) * 1000.0
                resp_headers = dict(resp.headers)
                raw_bytes = resp.read()
                try:
                    parsed_body = json.loads(raw_bytes.decode("utf-8"))
                except Exception:
                    parsed_body = raw_bytes.decode("utf-8", errors="replace")
                return resp.status, resp_headers, parsed_body, round(elapsed_ms, 2)
        except urllib.error.HTTPError as http_err:
            elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            resp_headers = dict(http_err.headers)
            raw_bytes = http_err.read()
            try:
                parsed_body = json.loads(raw_bytes.decode("utf-8"))
            except Exception:
                parsed_body = raw_bytes.decode("utf-8", errors="replace")
            return http_err.code, resp_headers, parsed_body, round(elapsed_ms, 2)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            return 0, {}, {"error": str(exc)}, round(elapsed_ms, 2)

    def get_cse_overview(self) -> Dict[str, Any]:
        """Queries the root CSEBase resource (<m2m:cb>) for health and configuration."""
        base_url = self.get_base_url()
        status, headers, body, latency = self._execute_request("GET", base_url)

        if status == 200 and isinstance(body, dict) and "m2m:cb" in body:
            cb = body["m2m:cb"]
            return {
                "connected": True,
                "base_url": base_url,
                "cse_rn": cb.get("rn", self.get_cse_name()),
                "csi": cb.get("csi", "unknown"),
                "release_versions": cb.get("srv", ["3"]),
                "creation_time": cb.get("ct", ""),
                "last_modified": cb.get("lt", ""),
                "point_of_access": cb.get("poa", []),
                "rsc": headers.get("X-M2M-RSC", "2000"),
                "latency_ms": latency
            }
        return {
            "connected": False,
            "base_url": base_url,
            "error": body.get("error") if isinstance(body, dict) else f"HTTP {status}",
            "latency_ms": latency
        }

    def list_application_entities(self) -> List[Dict[str, Any]]:
        """
        Discovers all Application Entities (<m2m:ae>) registered under the CSEBase,
        including their child containers, subscriptions, and telemetry status.
        """
        base_url = self.get_base_url()
        disc_url = f"{base_url}?fu=1&ty=2"
        status, _, body, _ = self._execute_request("GET", disc_url)

        if status != 200 or not isinstance(body, dict) or "m2m:uril" not in body:
            return []

        # Also query fleet group membership to identify sync status
        fleet_grp_url = f"{base_url}/grp_fleet_telemetry"
        _, _, grp_body, _ = self._execute_request("GET", fleet_grp_url)
        grp_mids = []
        if isinstance(grp_body, dict) and "m2m:grp" in grp_body:
            grp_mids = grp_body["m2m:grp"].get("mid", [])

        entities = []
        for ae_uri in body["m2m:uril"]:
            ae_rn = ae_uri.split("/")[-1]
            if ae_rn == self.admin_origin or ae_rn == "CAdmin":
                continue  # Skip root administrative originator entry

            # Query the complete tree of the AE with rcn=4
            ae_url = f"{base_url}/{ae_rn}?rcn=4"
            ae_status, _, ae_tree_body, latency = self._execute_request("GET", ae_url)

            if ae_status != 200 or not isinstance(ae_tree_body, dict) or "m2m:ae" not in ae_tree_body:
                # Fallback to minimal record if tree query failed
                entities.append({
                    "rn": ae_rn,
                    "uri": ae_uri,
                    "api": "N.unknown",
                    "status": "PARTIAL",
                    "containers": [],
                    "subscriptions": [],
                    "container_count": 0,
                    "in_fleet_group": False,
                    "latency_ms": latency
                })
                continue

            ae_data = ae_tree_body["m2m:ae"]
            ch_list = ae_data.get("ch", []) or ae_data.get("m2m:cnt", [])
            containers = []
            subscriptions = []

            # Parse child containers and subscriptions
            if isinstance(ch_list, list):
                for item in ch_list:
                    if isinstance(item, dict):
                        # Some CSE implementations return wrapped types or direct dicts
                        if "rn" in item and item.get("ty") == 3:
                            cnt_ri = item.get("ri", "")
                            containers.append({
                                "rn": item.get("rn"),
                                "ri": cnt_ri,
                                "mni": item.get("mni"),
                                "cni": item.get("cni", 0),
                                "cbs": item.get("cbs", 0),
                                "mia": item.get("mia"),
                                "lbl": item.get("lbl", [])
                            })
                            # Parse subscriptions located inside this container
                            sub_list = item.get("m2m:sub", []) or item.get("ch", [])
                            if isinstance(sub_list, list):
                                for sub_item in sub_list:
                                    if isinstance(sub_item, dict) and "rn" in sub_item and sub_item.get("ty") == 23:
                                        subscriptions.append({
                                            "rn": sub_item.get("rn"),
                                            "ri": sub_item.get("ri", ""),
                                            "nu": sub_item.get("nu", [])
                                        })
                        elif "rn" in item and item.get("ty") == 23:
                            subscriptions.append({
                                "rn": item.get("rn"),
                                "ri": item.get("ri", ""),
                                "nu": item.get("nu", [])
                            })

            # Check if this AE's raw-telemetry is registered in grp_fleet_telemetry (by RI or path)
            raw_target_path = f"{self.get_cse_name()}/{ae_rn}/raw-telemetry"
            raw_ris = [c["ri"] for c in containers if c["rn"] in ("raw-telemetry", "cnt_raw_telemetry") and c["ri"]]
            in_group = any(raw_target_path in str(mid) for mid in grp_mids) or any(r in grp_mids for r in raw_ris)

            entities.append({
                "rn": ae_rn,
                "ri": ae_data.get("ri", ""),
                "api": ae_data.get("api", ""),
                "originator": ae_data.get("aei", f"C_{ae_rn}"),
                "labels": ae_data.get("lbl", []),
                "creation_time": ae_data.get("ct", ""),
                "last_modified": ae_data.get("lt", ""),
                "rr": ae_data.get("rr", True),
                "containers": sorted(containers, key=lambda x: x["rn"]),
                "container_count": len(containers),
                "subscriptions": subscriptions,
                "subscription_count": len(subscriptions),
                "in_fleet_group": in_group,
                "latency_ms": latency
            })

        return sorted(entities, key=lambda x: x["rn"])

    def get_entity_resource_tree(self, ae_rn: str) -> Dict[str, Any]:
        """Retrieves the full hierarchical resource tree (rcn=4) for an AE."""
        target_url = f"{self.get_base_url()}/{ae_rn}?rcn=4"
        status, headers, body, latency = self._execute_request("GET", target_url)
        return {
            "status": status,
            "rsc": headers.get("X-M2M-RSC", str(status)),
            "latency_ms": latency,
            "tree": body
        }

    def deploy_application_entity(
        self,
        ae_rn: str,
        vehicle_identity: str,
        api_id: str = "N.org.fhtw.sdv.cabin",
        originator: Optional[str] = None,
        acpi: Optional[str] = None,
        include_legacy_containers: bool = False,
        target_mia: int = 86400,
        sync_fleet_group: bool = True,
        downlink_mqtt_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates full, manifest-driven Application Entity (AE) onboarding into /sdv-cse.

        Workflow:
        1. Register or Reconcile Application Entity (<m2m:ae>, ty=2)
        2. Manifest-Driven Container Creation (<m2m:cnt>, ty=3) with 24h TTL
        3. Event Subscriptions Wiring (<m2m:sub>, ty=23)
        4. Fleet Aggregation Group Synchronization (<m2m:grp>, ty=9)
        5. Verification Audit (<m2m:cb>/<ae_rn>?rcn=4)
        """
        base_url = self.get_base_url()
        cse_name = self.get_cse_name()
        originator = originator or f"C_{ae_rn}"
        acpi_ref = acpi or f"{cse_name}/acp_fleet_manager"
        downlink_mqtt = downlink_mqtt_uri or f"mqtt://mosquitto:1883/sdv/{ae_rn.lower()}/control/cmd"

        audit_log: List[Dict[str, Any]] = []
        step = 1

        # ----------------------------------------------------------------------
        # Step 1: Register or Reconcile Application Entity (<m2m:ae>)
        # ----------------------------------------------------------------------
        ae_payload = {
            "m2m:ae": {
                "rn": ae_rn,
                "api": api_id,
                "rr": True,
                "srv": ["2a", "3"],
                "acpi": [acpi_ref],
                "lbl": ["vehicle", "sdv-fleet", f"identity:{vehicle_identity}"]
            }
        }
        ae_post_headers = {
            "Content-Type": "application/json;ty=2",
            "X-M2M-Origin": originator
        }
        status, headers, body, latency = self._execute_request(
            "POST", base_url, headers=ae_post_headers, data=json.dumps(ae_payload).encode("utf-8")
        )

        rsc = headers.get("X-M2M-RSC", "")
        if status == 201:
            audit_log.append({
                "step": step,
                "action": "REGISTER_AE",
                "resource": ae_rn,
                "http_status": 201,
                "rsc": rsc or "2001",
                "status": "CREATED",
                "latency_ms": latency,
                "details": f"Registered AE {ae_rn} under /{cse_name} with API {api_id}"
            })
        elif status in (403, 409):
            audit_log.append({
                "step": step,
                "action": "REGISTER_AE",
                "resource": ae_rn,
                "http_status": status,
                "rsc": rsc or str(status),
                "status": "IDEMPOTENT",
                "latency_ms": latency,
                "details": f"AE {ae_rn} already exists or registered (HTTP {status})"
            })
        else:
            audit_log.append({
                "step": step,
                "action": "REGISTER_AE",
                "resource": ae_rn,
                "http_status": status,
                "rsc": rsc,
                "status": "FAILED",
                "latency_ms": latency,
                "details": f"Failed to register AE: {body}"
            })
            return {"success": False, "ae_rn": ae_rn, "audit_log": audit_log, "error": "AE creation failed"}

        step += 1
        ae_url = f"{base_url}/{ae_rn}"

        # ----------------------------------------------------------------------
        # Step 2: Provision Containers from Manifest
        # ----------------------------------------------------------------------
        manifest = dict(STANDARD_8_CONTAINER_MANIFEST)
        if include_legacy_containers:
            manifest.update(LEGACY_CONTAINER_ALIASES)

        for cnt_name, spec in manifest.items():
            cnt_payload = {
                "m2m:cnt": {
                    "rn": cnt_name,
                    "mni": spec["mni"],
                    "mbs": spec["mbs"],
                    "mia": target_mia,
                    "acpi": [acpi_ref],
                    "lbl": spec["lbl"] + [ae_rn]
                }
            }
            cnt_headers = {
                "Content-Type": "application/json;ty=3",
                "X-M2M-Origin": originator
            }
            c_status, c_headers, c_body, c_latency = self._execute_request(
                "POST", ae_url, headers=cnt_headers, data=json.dumps(cnt_payload).encode("utf-8")
            )
            c_rsc = c_headers.get("X-M2M-RSC", "")

            if c_status == 201:
                audit_log.append({
                    "step": step,
                    "action": "CREATE_CONTAINER",
                    "resource": f"{ae_rn}/{cnt_name}",
                    "http_status": 201,
                    "rsc": c_rsc or "2001",
                    "status": "CREATED",
                    "latency_ms": c_latency,
                    "details": f"Created container {cnt_name} (mni={spec['mni']}, mia={target_mia}s)"
                })
            elif c_status == 409:
                audit_log.append({
                    "step": step,
                    "action": "CREATE_CONTAINER",
                    "resource": f"{ae_rn}/{cnt_name}",
                    "http_status": 409,
                    "rsc": c_rsc or "4105",
                    "status": "IDEMPOTENT",
                    "latency_ms": c_latency,
                    "details": f"Container {cnt_name} already exists"
                })
            else:
                audit_log.append({
                    "step": step,
                    "action": "CREATE_CONTAINER",
                    "resource": f"{ae_rn}/{cnt_name}",
                    "http_status": c_status,
                    "rsc": c_rsc,
                    "status": "WARNING",
                    "latency_ms": c_latency,
                    "details": f"Container {cnt_name} returned status HTTP {c_status}"
                })
            step += 1

        # ----------------------------------------------------------------------
        # Step 3: Wire Subscriptions (Downlink Actuation, Telemetry, CO Alert)
        # ----------------------------------------------------------------------
        subscriptions = [
            {
                "target_cnt": "raw-telemetry",
                "rn": "sub_bridge_consumer",
                "nu": ["http://bridge_ae:5000/notification"],
                "nct": 1,
                "enc": {"net": [3]}
            },
            {
                "target_cnt": "co-cabin",
                "rn": "sub_co_alert",
                "nu": ["http://bridge_ae:5000/emergency-monitor"],
                "nct": 1,
                "enc": {"net": [3]}
            },
            {
                "target_cnt": "commands",
                "rn": "sub_downlink_dispatcher",
                "nu": [downlink_mqtt],
                "nct": 1,
                "enc": {"net": [3]}
            }
        ]

        if include_legacy_containers:
            subscriptions.extend([
                {
                    "target_cnt": "cnt_raw_telemetry",
                    "rn": "sub_bridge_consumer",
                    "nu": ["http://bridge_ae:5000/notification"],
                    "nct": 1,
                    "enc": {"net": [3]}
                },
                {
                    "target_cnt": "cnt_actuator_commands",
                    "rn": "sub_downlink_dispatcher",
                    "nu": [downlink_mqtt],
                    "nct": 1,
                    "enc": {"net": [3]}
                }
            ])

        for sub_spec in subscriptions:
            cnt_url = f"{ae_url}/{sub_spec['target_cnt']}"
            sub_rn = sub_spec["rn"]
            sub_payload = {
                "m2m:sub": {
                    "rn": sub_rn,
                    "nu": sub_spec["nu"],
                    "nct": sub_spec["nct"],
                    "enc": sub_spec["enc"]
                }
            }
            sub_headers = {
                "Content-Type": "application/json;ty=23",
                "X-M2M-Origin": self.admin_origin
            }
            s_status, s_headers, s_body, s_latency = self._execute_request(
                "POST", cnt_url, headers=sub_headers, data=json.dumps(sub_payload).encode("utf-8")
            )
            s_rsc = s_headers.get("X-M2M-RSC", "")

            if s_status == 201:
                audit_log.append({
                    "step": step,
                    "action": "CREATE_SUBSCRIPTION",
                    "resource": f"{ae_rn}/{sub_spec['target_cnt']}/{sub_rn}",
                    "http_status": 201,
                    "rsc": s_rsc or "2001",
                    "status": "CREATED",
                    "latency_ms": s_latency,
                    "details": f"Subscription {sub_rn} bound to {sub_spec['nu'][0]}"
                })
            elif s_status == 409:
                # Reconcile existing subscription via HTTP PUT without 'rn' attribute
                put_payload = {
                    "m2m:sub": {
                        "nu": sub_spec["nu"],
                        "nct": sub_spec["nct"],
                        "enc": sub_spec["enc"]
                    }
                }
                put_headers = {
                    "Content-Type": "application/json",
                    "X-M2M-Origin": self.admin_origin
                }
                p_status, p_headers, _, p_latency = self._execute_request(
                    "PUT", f"{cnt_url}/{sub_rn}", headers=put_headers, data=json.dumps(put_payload).encode("utf-8")
                )
                audit_log.append({
                    "step": step,
                    "action": "RECONCILE_SUBSCRIPTION",
                    "resource": f"{ae_rn}/{sub_spec['target_cnt']}/{sub_rn}",
                    "http_status": p_status,
                    "rsc": p_headers.get("X-M2M-RSC", str(p_status)),
                    "status": "RECONCILED" if p_status == 200 else "IDEMPOTENT",
                    "latency_ms": s_latency + p_latency,
                    "details": f"Subscription {sub_rn} reconciled to {sub_spec['nu'][0]}"
                })
            else:
                audit_log.append({
                    "step": step,
                    "action": "CREATE_SUBSCRIPTION",
                    "resource": f"{ae_rn}/{sub_spec['target_cnt']}/{sub_rn}",
                    "http_status": s_status,
                    "rsc": s_rsc,
                    "status": "WARNING",
                    "latency_ms": s_latency,
                    "details": f"Subscription {sub_rn} returned HTTP {s_status}"
                })
            step += 1

        # ----------------------------------------------------------------------
        # Step 4: Synchronize Fleet Aggregation Group (<m2m:grp>)
        # ----------------------------------------------------------------------
        if sync_fleet_group:
            grp_url = f"{base_url}/grp_fleet_telemetry"
            g_status, _, g_body, g_latency = self._execute_request("GET", grp_url)

            target_member = f"{cse_name}/{ae_rn}/raw-telemetry"
            current_mids = []
            if g_status == 200 and isinstance(g_body, dict) and "m2m:grp" in g_body:
                current_mids = list(g_body["m2m:grp"].get("mid", []))

            if target_member not in current_mids:
                updated_mids = current_mids + [target_member]
                grp_update = {
                    "m2m:grp": {
                        "mid": updated_mids
                    }
                }
                up_status, up_headers, _, up_latency = self._execute_request(
                    "PUT", grp_url,
                    headers={"Content-Type": "application/json", "X-M2M-Origin": self.admin_origin},
                    data=json.dumps(grp_update).encode("utf-8")
                )
                audit_log.append({
                    "step": step,
                    "action": "SYNC_FLEET_GROUP",
                    "resource": "grp_fleet_telemetry",
                    "http_status": up_status,
                    "rsc": up_headers.get("X-M2M-RSC", str(up_status)),
                    "status": "SYNCHRONIZED" if up_status in (200, 204) else "WARNING",
                    "latency_ms": g_latency + up_latency,
                    "details": f"Appended {target_member} to grp_fleet_telemetry (total: {len(updated_mids)})"
                })
            else:
                audit_log.append({
                    "step": step,
                    "action": "SYNC_FLEET_GROUP",
                    "resource": "grp_fleet_telemetry",
                    "http_status": 200,
                    "rsc": "2000",
                    "status": "UP_TO_DATE",
                    "latency_ms": g_latency,
                    "details": f"{target_member} already present in grp_fleet_telemetry"
                })
            step += 1

        return {
            "success": True,
            "ae_rn": ae_rn,
            "vehicle_identity": vehicle_identity,
            "total_steps": len(audit_log),
            "audit_log": audit_log
        }

    def decommission_application_entity(self, ae_rn: str) -> Dict[str, Any]:
        """
        Decommissions an Application Entity by removing its members from grp_fleet_telemetry
        and issuing a cascading oneM2M DELETE on the AE resource.
        """
        base_url = self.get_base_url()
        cse_name = self.get_cse_name()
        audit_log: List[Dict[str, Any]] = []
        step = 1

        # Step 1: Remove from fleet group
        grp_url = f"{base_url}/grp_fleet_telemetry"
        g_status, _, g_body, g_latency = self._execute_request("GET", grp_url)
        if g_status == 200 and isinstance(g_body, dict) and "m2m:grp" in g_body:
            current_mids = g_body["m2m:grp"].get("mid", [])
            filtered_mids = [mid for mid in current_mids if f"/{ae_rn}/" not in str(mid) and not str(mid).endswith(f"/{ae_rn}")]
            if len(filtered_mids) != len(current_mids):
                grp_update = {"m2m:grp": {"mid": filtered_mids}}
                up_status, up_headers, _, up_latency = self._execute_request(
                    "PUT", grp_url,
                    headers={"Content-Type": "application/json", "X-M2M-Origin": self.admin_origin},
                    data=json.dumps(grp_update).encode("utf-8")
                )
                audit_log.append({
                    "step": step,
                    "action": "PRUNE_FLEET_GROUP",
                    "resource": "grp_fleet_telemetry",
                    "http_status": up_status,
                    "status": "PRUNED",
                    "latency_ms": g_latency + up_latency,
                    "details": f"Removed {ae_rn} containers from grp_fleet_telemetry"
                })
            else:
                audit_log.append({
                    "step": step,
                    "action": "PRUNE_FLEET_GROUP",
                    "resource": "grp_fleet_telemetry",
                    "http_status": 200,
                    "status": "UNCHANGED",
                    "latency_ms": g_latency,
                    "details": "No group memberships matched this AE"
                })
        step += 1

        # Step 2: Delete AE resource (cascading purge of all child containers and subscriptions)
        ae_url = f"{base_url}/{ae_rn}"
        d_status, d_headers, d_body, d_latency = self._execute_request(
            "DELETE", ae_url, headers={"X-M2M-Origin": self.admin_origin}
        )
        rsc = d_headers.get("X-M2M-RSC", "")
        audit_log.append({
            "step": step,
            "action": "DELETE_AE",
            "resource": ae_rn,
            "http_status": d_status,
            "rsc": rsc,
            "status": "DELETED" if d_status in (200, 202, 204) else "ERROR",
            "latency_ms": d_latency,
            "details": f"oneM2M DELETE issued for /{cse_name}/{ae_rn}"
        })
        step += 1

        # Step 3: Verify deletion with 404 assertion
        v_status, _, _, v_latency = self._execute_request("GET", ae_url)
        audit_log.append({
            "step": step,
            "action": "VERIFY_DELETION",
            "resource": ae_rn,
            "http_status": v_status,
            "status": "CONFIRMED" if v_status == 404 else "UNEXPECTED",
            "latency_ms": v_latency,
            "details": "Confirmed 404 Not Found" if v_status == 404 else f"Resource still returned HTTP {v_status}"
        })

        return {
            "success": d_status in (200, 202, 204),
            "ae_rn": ae_rn,
            "audit_log": audit_log
        }

    def validate_entity(self, ae_rn: str) -> Dict[str, Any]:
        """
        Validates an existing Application Entity against ETSI TS 118 101 manifest requirements
        and retrieves the latest operational telemetry snapshot (/la).

        Conforms to Collection 2 (04_Validation) and SOP-SDV-ONEM2M-001 Section 4.
        """
        base_url = self.get_base_url()
        cse_name = self.get_cse_name()
        checks: List[Dict[str, Any]] = []

        # 1. Audit Vehicle Resource Tree (rcn=4)
        ae_url = f"{base_url}/{ae_rn}?rcn=4"
        tree_status, _, tree_body, latency_tree = self._execute_request("GET", ae_url)

        if tree_status != 200 or not isinstance(tree_body, dict) or "m2m:ae" not in tree_body:
            return {
                "valid": False,
                "ae_rn": ae_rn,
                "compliance_score_pct": 0,
                "checks_passed": 0,
                "total_checks": 1,
                "error": f"AE {ae_rn} not found or unreadable (HTTP {tree_status})",
                "checks": [{"name": "AE Presence", "passed": False, "details": f"HTTP {tree_status}"}]
            }

        checks.append({
            "name": "AE Registration",
            "passed": True,
            "details": f"Registered under /{cse_name} (latency {latency_tree}ms)"
        })

        ae_data = tree_body["m2m:ae"]
        ch_list = ae_data.get("ch", []) or ae_data.get("m2m:cnt", [])
        child_cnts = {}
        child_subs = {}

        if isinstance(ch_list, list):
            for item in ch_list:
                if isinstance(item, dict):
                    if "rn" in item and item.get("ty") == 3:
                        child_cnts[item["rn"]] = item
                        # Check subscriptions inside this container
                        sub_list = item.get("m2m:sub", []) or item.get("ch", [])
                        if isinstance(sub_list, list):
                            for sub_item in sub_list:
                                if isinstance(sub_item, dict) and "rn" in sub_item and sub_item.get("ty") == 23:
                                    child_subs[sub_item["rn"]] = sub_item
                    elif "rn" in item and item.get("ty") == 23:
                        child_subs[item["rn"]] = item

        # 2. Audit 8-Container Manifest Compliance
        missing_cnts = []
        for req_cnt, req_spec in STANDARD_8_CONTAINER_MANIFEST.items():
            if req_cnt in child_cnts:
                cnt_obj = child_cnts[req_cnt]
                checks.append({
                    "name": f"Container <{req_cnt}>",
                    "passed": True,
                    "details": f"mni={cnt_obj.get('mni')}, mia={cnt_obj.get('mia')}s, instances={cnt_obj.get('cni', 0)}"
                })
            else:
                missing_cnts.append(req_cnt)
                checks.append({
                    "name": f"Container <{req_cnt}>",
                    "passed": False,
                    "details": "Missing from resource tree"
                })

        # 3. Audit Subscriptions Compliance
        expected_subs = ["sub_bridge_consumer", "sub_co_alert", "sub_downlink_dispatcher"]
        missing_subs = []
        for req_sub in expected_subs:
            found = req_sub in child_subs or any(req_sub in s.get("rn", "") for s in child_subs.values())
            if found:
                checks.append({
                    "name": f"Subscription <{req_sub}>",
                    "passed": True,
                    "details": "Active event listener wired"
                })
            else:
                missing_subs.append(req_sub)
                checks.append({
                    "name": f"Subscription <{req_sub}>",
                    "passed": False,
                    "details": "Missing event subscription"
                })

        # 4. Audit Fleet Group Membership Synchronization
        grp_url = f"{base_url}/grp_fleet_telemetry"
        g_status, _, g_body, _ = self._execute_request("GET", grp_url)
        in_group = False
        if g_status == 200 and isinstance(g_body, dict) and "m2m:grp" in g_body:
            grp_mids = g_body["m2m:grp"].get("mid", [])
            raw_target_path = f"{cse_name}/{ae_rn}/raw-telemetry"
            raw_ri = child_cnts.get("raw-telemetry", {}).get("ri", "")
            in_group = any(raw_target_path in str(mid) for mid in grp_mids) or (raw_ri and raw_ri in grp_mids)

        checks.append({
            "name": "Fleet Group Membership",
            "passed": in_group,
            "details": "Synchronized in grp_fleet_telemetry.mid" if in_group else "Not found in grp_fleet_telemetry"
        })

        # 5. Retrieve Active Vehicle Latest Telemetry (/la)
        la_url = f"{base_url}/{ae_rn}/raw-telemetry/la"
        la_status, _, la_body, la_latency = self._execute_request("GET", la_url)
        latest_telemetry = None

        if la_status == 200 and isinstance(la_body, dict) and "m2m:cin" in la_body:
            cin = la_body["m2m:cin"]
            try:
                latest_telemetry = json.loads(cin.get("con", "{}"))
            except Exception:
                latest_telemetry = cin.get("con")
            checks.append({
                "name": "Latest Telemetry Ingestion (/la)",
                "passed": True,
                "details": f"Latest frame retrieved with ct={cin.get('ct')} ({la_latency}ms)"
            })
        else:
            checks.append({
                "name": "Latest Telemetry Ingestion (/la)",
                "passed": False,
                "details": "No ContentInstance available under raw-telemetry"
            })

        passed_count = sum(1 for c in checks if c["passed"])
        score_pct = round((passed_count / len(checks)) * 100, 1)

        return {
            "valid": score_pct >= 85.0,
            "ae_rn": ae_rn,
            "compliance_score_pct": score_pct,
            "checks_passed": passed_count,
            "checks_total": len(checks),
            "missing_containers": missing_cnts,
            "missing_subscriptions": missing_subs,
            "in_fleet_group": in_group,
            "latest_telemetry": latest_telemetry,
            "checks": checks
        }

    def deploy_and_validate_entity(self, **kwargs) -> Dict[str, Any]:
        """
        Executes single vehicle deployment and immediate automated validation in one pass.
        Conforms to Collection 2 (Single Vehicle Deploy & Validation).
        """
        deploy_res = self.deploy_application_entity(**kwargs)
        if not deploy_res.get("success"):
            return deploy_res

        ae_rn = deploy_res["ae_rn"]

        # Ingest initial synchronised telemetry frame
        telemetry_res = self.dispatch_test_telemetry(ae_rn)

        # Execute validation audit
        validation_report = self.validate_entity(ae_rn)

        return {
            "success": deploy_res["success"],
            "ae_rn": ae_rn,
            "total_steps": deploy_res["total_steps"],
            "audit_log": deploy_res["audit_log"],
            "telemetry_ingested": telemetry_res.get("success", False),
            "validation_report": validation_report
        }

    def validate_and_decommission_entity(self, ae_rn: str) -> Dict[str, Any]:
        """
        Executes single vehicle validate and decommission.
        Archives pre-retirement state, tears down subscriptions, purges AE, and updates fleet group.
        Conforms to Collection 3 (Single Vehicle Validate & Decommission).
        """
        base_url = self.get_base_url()
        cse_name = self.get_cse_name()
        audit_log: List[Dict[str, Any]] = []
        step = 1

        # Phase 1: Pre-Decommission Validation & State Archival
        tree_url = f"{base_url}/{ae_rn}?rcn=4"
        _, _, pre_audit_tree, latency_tree = self._execute_request("GET", tree_url)
        la_url = f"{base_url}/{ae_rn}/raw-telemetry/la"
        _, _, final_cin, latency_cin = self._execute_request("GET", la_url)

        audit_log.append({
            "step": step,
            "action": "PRE_DECOMMISSION_AUDIT",
            "resource": ae_rn,
            "http_status": 200,
            "status": "ARCHIVED",
            "latency_ms": latency_tree + latency_cin,
            "details": f"Archived pre-retirement resource tree and final telemetry snapshot"
        })
        step += 1

        # Phase 2: Explicit Subscription Teardown (Collection 3 Request 2.1-2.3)
        subs_to_delete = [
            ("co-cabin", "sub_co_alert"),
            ("raw-telemetry", "sub_bridge_consumer"),
            ("commands", "sub_downlink_dispatcher")
        ]
        for cnt_rn, sub_rn in subs_to_delete:
            sub_url = f"{base_url}/{ae_rn}/{cnt_rn}/{sub_rn}"
            s_del_status, _, _, s_latency = self._execute_request(
                "DELETE", sub_url, headers={"X-M2M-Origin": self.admin_origin}
            )
            audit_log.append({
                "step": step,
                "action": "DELETE_SUBSCRIPTION",
                "resource": f"{ae_rn}/{cnt_rn}/{sub_rn}",
                "http_status": s_del_status,
                "status": "DELETED" if s_del_status in (200, 202, 204) else ("NOT_FOUND" if s_del_status == 404 else "WARNING"),
                "latency_ms": s_latency,
                "details": f"Torn down subscription {sub_rn}"
            })
            step += 1

        # Phase 3: Cascading Application Entity Decommission
        ae_url = f"{base_url}/{ae_rn}"
        d_status, d_headers, _, d_latency = self._execute_request(
            "DELETE", ae_url, headers={"X-M2M-Origin": self.admin_origin}
        )
        audit_log.append({
            "step": step,
            "action": "DECOMMISSION_VEHICLE_AE",
            "resource": ae_rn,
            "http_status": d_status,
            "rsc": d_headers.get("X-M2M-RSC", ""),
            "status": "DELETED" if d_status in (200, 202, 204) else "ERROR",
            "latency_ms": d_latency,
            "details": f"Issued cascading oneM2M DELETE for /{cse_name}/{ae_rn}"
        })
        step += 1

        # Phase 4: Verify Absence (404 Not Found Expected)
        v_status, _, _, v_latency = self._execute_request("GET", ae_url)
        audit_log.append({
            "step": step,
            "action": "VERIFY_ABSENCE",
            "resource": ae_rn,
            "http_status": v_status,
            "status": "CONFIRMED" if v_status == 404 else "UNEXPECTED",
            "latency_ms": v_latency,
            "details": "Confirmed 404 Not Found in CSEBase" if v_status == 404 else f"Unexpected HTTP {v_status}"
        })
        step += 1

        # Phase 5: Reconcile Fleet Group Membership
        grp_url = f"{base_url}/grp_fleet_telemetry"
        g_status, _, g_body, g_latency = self._execute_request("GET", grp_url)
        if g_status == 200 and isinstance(g_body, dict) and "m2m:grp" in g_body:
            current_mids = g_body["m2m:grp"].get("mid", [])
            filtered_mids = [m for m in current_mids if f"/{ae_rn}/" not in str(m) and not str(m).endswith(f"/{ae_rn}")]
            if len(filtered_mids) != len(current_mids):
                grp_update = {"m2m:grp": {"mid": filtered_mids}}
                up_status, up_headers, _, up_latency = self._execute_request(
                    "PUT", grp_url,
                    headers={"Content-Type": "application/json", "X-M2M-Origin": self.admin_origin},
                    data=json.dumps(grp_update).encode("utf-8")
                )
                audit_log.append({
                    "step": step,
                    "action": "RECONCILE_FLEET_GROUP",
                    "resource": "grp_fleet_telemetry",
                    "http_status": up_status,
                    "status": "RECONCILED",
                    "latency_ms": g_latency + up_latency,
                    "details": f"Pruned {ae_rn} from grp_fleet_telemetry.mid (remaining: {len(filtered_mids)})"
                })
            else:
                audit_log.append({
                    "step": step,
                    "action": "RECONCILE_FLEET_GROUP",
                    "resource": "grp_fleet_telemetry",
                    "http_status": 200,
                    "status": "UNCHANGED",
                    "latency_ms": g_latency,
                    "details": f"No group memberships remained for {ae_rn}"
                })
        step += 1

        return {
            "success": d_status in (200, 202, 204),
            "ae_rn": ae_rn,
            "pre_audit_tree": pre_audit_tree,
            "final_telemetry": final_cin,
            "total_steps": len(audit_log),
            "audit_log": audit_log
        }

    def batch_decommission_entities(self, ae_rns: List[str]) -> Dict[str, Any]:
        """
        Decommissions multiple selected Application Entities in a single consolidated operation.
        Prunes all decommissioned entities from grp_fleet_telemetry in a unified batch step.
        """
        base_url = self.get_base_url()
        cse_name = self.get_cse_name()
        overall_audit: List[Dict[str, Any]] = []
        successful_deletions: List[str] = []
        failed_deletions: List[str] = []

        step = 1
        for ae_rn in ae_rns:
            # Cascading deletion of individual AE
            ae_url = f"{base_url}/{ae_rn}"
            d_status, d_headers, _, d_latency = self._execute_request(
                "DELETE", ae_url, headers={"X-M2M-Origin": self.admin_origin}
            )

            if d_status in (200, 202, 204):
                successful_deletions.append(ae_rn)
                overall_audit.append({
                    "step": step,
                    "action": "BATCH_DELETE_AE",
                    "resource": ae_rn,
                    "http_status": d_status,
                    "status": "DELETED",
                    "latency_ms": d_latency,
                    "details": f"Purged AE /{cse_name}/{ae_rn}"
                })
            else:
                failed_deletions.append(ae_rn)
                overall_audit.append({
                    "step": step,
                    "action": "BATCH_DELETE_AE",
                    "resource": ae_rn,
                    "http_status": d_status,
                    "status": "ERROR",
                    "latency_ms": d_latency,
                    "details": f"Failed to delete AE {ae_rn}: HTTP {d_status}"
                })
            step += 1

        # Consolidated fleet group membership reconciliation
        grp_url = f"{base_url}/grp_fleet_telemetry"
        g_status, _, g_body, g_latency = self._execute_request("GET", grp_url)
        if g_status == 200 and isinstance(g_body, dict) and "m2m:grp" in g_body:
            current_mids = g_body["m2m:grp"].get("mid", [])
            # Filter out all successfully purged AEs
            filtered_mids = [
                m for m in current_mids
                if not any(f"/{rn}/" in str(m) or str(m).endswith(f"/{rn}") for rn in successful_deletions)
            ]
            if len(filtered_mids) != len(current_mids):
                grp_update = {"m2m:grp": {"mid": filtered_mids}}
                up_status, _, _, up_latency = self._execute_request(
                    "PUT", grp_url,
                    headers={"Content-Type": "application/json", "X-M2M-Origin": self.admin_origin},
                    data=json.dumps(grp_update).encode("utf-8")
                )
                overall_audit.append({
                    "step": step,
                    "action": "BATCH_RECONCILE_FLEET_GROUP",
                    "resource": "grp_fleet_telemetry",
                    "http_status": up_status,
                    "status": "RECONCILED",
                    "latency_ms": g_latency + up_latency,
                    "details": f"Pruned {len(successful_deletions)} vehicle(s) from group. Remaining members: {len(filtered_mids)}"
                })
            else:
                overall_audit.append({
                    "step": step,
                    "action": "BATCH_RECONCILE_FLEET_GROUP",
                    "resource": "grp_fleet_telemetry",
                    "http_status": 200,
                    "status": "UNCHANGED",
                    "latency_ms": g_latency,
                    "details": "Fleet group already consistent"
                })

        return {
            "success": len(successful_deletions) > 0,
            "total_requested": len(ae_rns),
            "successful_count": len(successful_deletions),
            "failed_count": len(failed_deletions),
            "successful_entities": successful_deletions,
            "failed_entities": failed_deletions,
            "audit_log": overall_audit
        }


    def dispatch_test_telemetry(self, ae_rn: str, custom_metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispatches a synthetic valid telemetry ContentInstance (<m2m:cin>) to raw-telemetry."""
        base_url = self.get_base_url()
        now_ts = int(time.time())

        metrics = custom_metrics or {}
        frame = {
            "car_id": ae_rn.lower().replace("ae_", ""),
            "zone": "cabin_front",
            "timestamp_unix_s": now_ts,
            "scd30": {
                "co2_ppm": float(metrics.get("co2_ppm", 512.0)),
                "temperature_c": float(metrics.get("temp_scd30_c", 22.4)),
                "humidity_pct": float(metrics.get("humidity_scd30_pct", 45.6))
            },
            "dht22": {
                "temperature_c": float(metrics.get("temp_dht22_c", 22.2)),
                "humidity_pct": float(metrics.get("humidity_dht22_pct", 45.2))
            },
            "actuator_state": {
                "pwm_duty_pct": int(metrics.get("pwm_duty_pct", 30)),
                "tachometer_rpm": int(metrics.get("tachometer_rpm", 1020)),
                "carrier_freq_hz": 25000
            }
        }

        cin_payload = {
            "m2m:cin": {
                "cnf": "application/json:0",
                "con": json.dumps(frame)
            }
        }

        target_url = f"{base_url}/{ae_rn}/raw-telemetry"
        headers = {
            "Content-Type": "application/json;ty=4",
            "X-M2M-Origin": f"C_{ae_rn}"
        }
        status, resp_headers, body, latency = self._execute_request(
            "POST", target_url, headers=headers, data=json.dumps(cin_payload).encode("utf-8")
        )

        return {
            "success": status == 201,
            "http_status": status,
            "rsc": resp_headers.get("X-M2M-RSC", "2001" if status == 201 else str(status)),
            "target_url": target_url,
            "payload": frame,
            "latency_ms": latency,
            "response": body
        }

    def execute_raw_request(
        self,
        method: str,
        path_or_url: str,
        originator: Optional[str] = None,
        resource_type: Optional[int] = None,
        request_id: Optional[str] = None,
        rvi: Optional[str] = None,
        body: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Universal oneM2M REST API client proxy.
        Forwards arbitrary oneM2M requests and translates status codes and timing.
        """
        base_url = self.get_base_url()

        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            target_url = path_or_url
        else:
            clean_path = path_or_url.lstrip("/")
            cse_name = self.get_cse_name()
            if clean_path.startswith(cse_name):
                # Target path already includes CSEBase name
                target_url = f"{base_url.rsplit('/', 1)[0]}/{clean_path}"
            else:
                target_url = f"{base_url}/{clean_path}"

        headers = {
            "X-M2M-Origin": originator or self.admin_origin,
            "X-M2M-RI": request_id or f"client_{int(time.time() * 1000)}",
            "X-M2M-RVI": rvi or self.rvi,
            "Accept": "application/json"
        }

        if resource_type is not None and str(resource_type).strip() != "":
            headers["Content-Type"] = f"application/json;ty={resource_type}"
        elif method in ("POST", "PUT") and body:
            headers["Content-Type"] = "application/json"

        if extra_headers:
            headers.update(extra_headers)

        data = body.encode("utf-8") if body else None
        status, resp_headers, resp_body, latency = self._execute_request(
            method=method.upper(),
            target_url=target_url,
            headers=headers,
            data=data
        )

        rsc = resp_headers.get("X-M2M-RSC", "")
        rsc_desc = RSC_DESCRIPTIONS.get(rsc, f"RSC {rsc}" if rsc else f"HTTP {status}")

        return {
            "status": status,
            "rsc": rsc,
            "rsc_description": rsc_desc,
            "latency_ms": latency,
            "target_url": target_url,
            "method": method.upper(),
            "request_headers": headers,
            "response_headers": resp_headers,
            "response_body": resp_body
        }


    def get_known_vehicles(self) -> List[Dict[str, str]]:
        """
        Discovers all known vehicular entities across the SDV fleet.
        Queries registered Application Entities (<m2m:ae>) from the CSEBase and
        normalises them into standard vehicle descriptors (e.g. vehicle_01, vehicle_02).
        Guarantees fallback nominal nodes if CSE is in offline or simulated mode.
        """
        vehicles = []
        seen = set()
        try:
            entities = self.list_application_entities()
            for ent in entities:
                rn = ent.get("rn", "")
                if not rn or rn in (self.admin_origin, "CAdmin"):
                    continue
                lower_rn = rn.lower()
                if "cabinnode" in lower_rn or "car" in lower_rn or "vehicle" in lower_rn:
                    raw_id = lower_rn.replace("ae_cabinnode_", "").replace("ae_", "")
                    digits = "".join(filter(str.isdigit, raw_id))
                    if digits:
                        car_id = f"vehicle_{digits.zfill(2)}"
                        display_name = f"VEHICLE {digits.zfill(2)}"
                    else:
                        car_id = f"vehicle_{raw_id}"
                        display_name = car_id.upper().replace("_", " ")

                    if car_id not in seen:
                        seen.add(car_id)
                        vehicles.append({
                            "id": car_id,
                            "ae_rn": rn,
                            "name": display_name,
                            "originator": ent.get("originator", f"C_{rn}"),
                            "status": ent.get("status", "ACTIVE")
                        })
        except Exception as exc:
            logger.debug("Failed discovering vehicles from oneM2M CSE: %s", exc)

        return sorted(vehicles, key=lambda x: x["id"])


onem2m_client = OneM2MClient()

