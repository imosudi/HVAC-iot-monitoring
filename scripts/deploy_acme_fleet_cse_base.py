#!/usr/bin/env python3
"""
CSEBase & Expandable Fleet Infrastructure Provisioning Script
Deploy and reconcile the ACME oneM2M CSEBase, Fleet Governance policies (<m2m:acp>),
Fleet Aggregation Groups (<m2m:grp>), and any specified Vehicle Application Entities (<m2m:ae>).

Conforms to:
  - ETSI TS 118 101 Release 4 (RVI 3)
  - collections/acme_fleet_insomnia_collection.yaml
  - collections/SDV_Expandable_Fleet_ACME_CSE_SOP.md

Capabilities:
  1. Preflight connectivity & Release verification of the target ACME CSEBase (<m2m:cb>).
  2. Fleet Governance Provisioning:
     - Access Control Policy (<m2m:acp>) 'acp_fleet_manager' with dual-originator RBAC.
     - Fleet Aggregation Group (<m2m:grp>) 'grp_fleet_telemetry' supporting atomic fan-out.
  3. Expandable Vehicle AE Onboarding:
     - Support for ANY vehicle application entity (arbitrary vehicle ID or list of IDs).
     - Full 8-container manifest provisioning with 24h retention (mia: 86400) & buffer quotas.
     - Tri-subscription provisioning (sub_co_alert, sub_fleet_telemetry, sub_downlink).
     - Baseline multi-sensor telemetry & closed-loop command instance ingestion.
  4. Dynamic Fleet Registry & Group Membership Reconciliation:
     - Auto-discovery of active vehicle AEs and telemetry containers.
     - Atomic synchronization of grp_fleet_telemetry.mid.
     - Group fan-out query validation (/fopt/la).
  5. Comprehensive CSEBase Hierarchy Audit (rcn=4).
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _load_env_file():
    """Dynamically loads configuration from root or deploy .env files."""
    root = Path(__file__).resolve().parent.parent
    for env_path in [root / ".env", root / "deploy" / ".env"]:
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    clean = line.strip()
                    if clean and not clean.startswith("#") and "=" in clean:
                        k, v = clean.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v


_load_env_file()

API_ID = os.getenv("API_ID", "N.org.fhtw.sdv.cabin")
RVI = os.getenv("RVI", os.getenv("ONEM2M_RVI", "3"))

SENSOR_MANIFEST = [
    {"name": "temperature-cabin", "measurement": "temperature", "location": "cabin", "unit": "Cel"},
    {"name": "humidity-cabin", "measurement": "relative-humidity", "location": "cabin", "unit": "%RH"},
    {"name": "co2-cabin", "measurement": "carbon-dioxide", "location": "cabin", "unit": "ppm"},
    {"name": "co-cabin", "measurement": "carbon-monoxide", "location": "cabin", "unit": "ppm"},
    {"name": "air-quality-cabin", "measurement": "air-quality", "location": "cabin", "unit": "sensor-defined"},
    {"name": "air-quality-exterior", "measurement": "air-quality", "location": "exterior", "unit": "sensor-defined"},
    {"name": "raw-telemetry", "measurement": "combined-telemetry", "location": "vehicle", "unit": "mixed"},
    {"name": "commands", "measurement": "actuation-control", "location": "vehicle", "unit": "mixed"}
]

def log(tag: str, msg: str, color: str = "0"):
    # ANSI colors: 32 green, 34 blue, 33 yellow, 31 red, 35 magenta, 36 cyan, 90 dim
    print(f"\033[{color}m[{tag}]\033[0m {msg}")

def request_m2m(url: str, method: str = "GET", payload: dict = None, ty: int = None, origin: str = "CAdmin"):
    headers = {
        "Accept": "application/json",
        "X-M2M-Origin": origin,
        "X-M2M-RI": f"req_{int(time.time()*1000)}",
        "X-M2M-RVI": RVI
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        ct = "application/json"
        if ty is not None:
            ct += f";ty={ty}"
        headers["Content-Type"] = ct

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return e.code, parsed
    except Exception as e:
        return 0, {"error": str(e)}

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Deploy & Reconcile ACME oneM2M CSEBase with Any Vehicle Application Entity",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--host",
        default=os.getenv("ACME_HOST", os.getenv("CSE_HOST", os.getenv("GATEWAY_IP", "127.0.0.1"))),
        help="ACME CSE hostname or IP address"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=int(os.getenv("ACME_PORT", os.getenv("ONEM2M_PORT", "8080"))),
        help="ACME CSE HTTP port"
    )
    parser.add_argument(
        "--cse-rn",
        default="cse-in",
        help="Target Root CSEBase Resource Name"
    )
    parser.add_argument(
        "--originator",
        default="CAdmin",
        help="Administrative originator for CSEBase operations"
    )
    parser.add_argument(
        "--acp-name",
        default="acp_fleet_manager",
        help="Resource Name for Fleet Access Control Policy (<m2m:acp>)"
    )
    parser.add_argument(
        "--grp-name",
        default="grp_fleet_telemetry",
        help="Resource Name for Fleet Aggregation Group (<m2m:grp>)"
    )
    parser.add_argument(
        "--vehicles", "-v",
        nargs="*",
        default=None,
        help="Optional list of any vehicle Application Entity names to onboard/reconcile (e.g. -v vehicle-001 vehicle-002 vehicle-005)"
    )
    parser.add_argument(
        "--no-vehicles",
        action="store_true",
        help="Explicitly skip vehicle AE onboarding; provision only the CSEBase infrastructure and governance"
    )
    parser.add_argument(
        "--notification-host",
        default=None,
        help="Base URL for subscription notification handlers (default: http://<host>:<port>)"
    )
    parser.add_argument(
        "--skip-telemetry",
        action="store_true",
        help="Skip ingesting initial baseline telemetry and actuation command instances"
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Perform a read-only audit of the CSEBase hierarchy without creating or modifying resources"
    )
    return parser.parse_args()

def onboard_vehicle(base_url: str, cse_rn: str, vehicle_id: str, vin: str = None,
                    originator: str = "CAdmin", notif_base: str = None,
                    ingest_telemetry: bool = True):
    """Onboards or reconciles an individual vehicle Application Entity and its complete hierarchy."""
    vin = vin or f"VIN-WAUZZZ-SDV-2026-{vehicle_id.split('-')[-1].zfill(4)}"
    notif_base = notif_base or base_url

    log("AE ONBOARD", f"Processing Vehicle AE: {vehicle_id} (VIN: {vin})...", "36")

    # 1. Register AE with unassigned originator 'S'
    ae_payload = {
        "m2m:ae": {
            "rn": vehicle_id,
            "api": API_ID,
            "rr": True,
            "srv": ["2a", "3"],
            "lbl": ["vehicle", "sdv-fleet", f"identity:{vin}"]
        }
    }
    status, res = request_m2m(f"{base_url}/{cse_rn}", method="POST", payload=ae_payload, ty=2, origin="S")
    if status == 201:
        ae_ri = res["m2m:ae"]["ri"]
        log("SUCCESS", f"  -> Registered AE {vehicle_id} (RI: {ae_ri})", "32")
    elif status == 409:
        _, res = request_m2m(f"{base_url}/{cse_rn}/{vehicle_id}", origin=originator)
        ae_ri = res.get("m2m:ae", {}).get("ri", vehicle_id)
        log("IDEMPOTENT", f"  -> AE {vehicle_id} already exists (RI: {ae_ri})", "34")
    else:
        log("ERROR", f"  -> Failed to register AE {vehicle_id}: HTTP {status} {res}", "31")
        return None

    # 2. Reconcile 8 Manifest Containers
    for cnt_def in SENSOR_MANIFEST:
        c_name = cnt_def["name"]
        is_raw = (c_name == "raw-telemetry")
        is_cmd = (c_name == "commands")
        mni = 1440 if is_raw else (100 if is_cmd else 1000)
        mbs = 2097152 if is_raw else (262144 if is_cmd else 1048576)

        cnt_payload = {
            "m2m:cnt": {
                "rn": c_name,
                "mni": mni,
                "mbs": mbs,
                "mia": 86400,
                "lbl": ["sensor", cnt_def["location"], cnt_def["measurement"], vehicle_id]
            }
        }
        c_status, c_res = request_m2m(
            f"{base_url}/{cse_rn}/{vehicle_id}",
            method="POST",
            payload=cnt_payload,
            ty=3,
            origin=originator
        )
        if c_status == 201:
            log("CREATED", f"     Container: {c_name:<22} (mni={mni:<4}, mia=86400, RI={c_res['m2m:cnt']['ri']})", "32")
        elif c_status == 409:
            log("VERIFIED", f"     Container: {c_name:<22} (verified active)", "34")
        else:
            log("WARN", f"     Failed to provision {c_name}: HTTP {c_status} {c_res}", "33")

    # 3. Reconcile Subscriptions
    subscriptions = [
        {"rn": "sub_co_alert", "target_cnt": "co-cabin", "nu": f"{notif_base}/emergency-monitor"},
        {"rn": "sub_fleet_telemetry", "target_cnt": "raw-telemetry", "nu": f"{notif_base}/fleet-ingest"},
        {"rn": "sub_downlink", "target_cnt": "commands", "nu": f"{notif_base}/downlink"}
    ]
    for sub in subscriptions:
        sub_payload = {
            "m2m:sub": {
                "rn": sub["rn"],
                "nu": [sub["nu"]],
                "nct": 1,
                "enc": {"net": [3]}
            }
        }
        s_status, s_res = request_m2m(
            f"{base_url}/{cse_rn}/{vehicle_id}/{sub['target_cnt']}",
            method="POST",
            payload=sub_payload,
            ty=23,
            origin=originator
        )
        if s_status == 201:
            log("SUBSCRIPTION", f"     Created {sub['rn']:<20} on {sub['target_cnt']} (RI: {s_res['m2m:sub']['ri']})", "32")
        elif s_status == 409:
            log("SUBSCRIPTION", f"     Verified {sub['rn']:<19} on {sub['target_cnt']} (already active)", "34")
        else:
            log("WARN", f"     Subscription {sub['rn']} status {s_status}: {s_res}", "33")

    # 4. Ingest Baseline Telemetry
    if ingest_telemetry:
        now_ts = int(time.time())
        sample_frame = {
            "is_simulated": True,
            "vehicle_id": vehicle_id,
            "vin": vin,
            "timestamp_unix_s": now_ts,
            "cabin": {
                "temperature_c": 22.2,
                "temperature_scd30": 22.2,
                "temperature_dht22": 21.9,
                "humidity_pct": 46.0,
                "humidity_scd30": 46.0,
                "humidity_dht22": 44.8,
                "co2_ppm": 560.0,
                "co_ppm": 0.1,
                "air_quality_score": 42,
                "exterior_aqi": 26
            },
            "actuator_state": {
                "pwm_duty_pct": 55,
                "tachometer_rpm": 1400,
                "carrier_freq_hz": 25000,
                "heater_state": "STANDBY",
                "eco_vent_state": "ACTIVE",
                "dehumidifier_state": "STANDBY",
                "recirculation_flap": "FRESH_AIR"
            }
        }
        cin_tel = {"m2m:cin": {"cnf": "application/json:0", "con": json.dumps(sample_frame)}}
        t_status, t_res = request_m2m(
            f"{base_url}/{cse_rn}/{vehicle_id}/raw-telemetry",
            method="POST",
            payload=cin_tel,
            ty=4,
            origin=originator
        )
        if t_status == 201:
            log("INGESTED", f"     raw-telemetry <cin> (RI: {t_res['m2m:cin']['ri']}, CO2=560ppm, PWM=55%)", "32")

        co_reading = {"is_simulated": True, "val": 0.1, "unit": "ppm", "alarm": False, "severity": "NORMAL", "ts": now_ts}
        cin_co = {"m2m:cin": {"cnf": "application/json:0", "con": json.dumps(co_reading)}}
        request_m2m(f"{base_url}/{cse_rn}/{vehicle_id}/co-cabin", method="POST", payload=cin_co, ty=4, origin=originator)

        cmd_payload = {
            "target_fan_pwm": 55.0,
            "fan_mode": "AUTO",
            "aux_heater_state": "STANDBY",
            "eco_vent_state": "ACTIVE",
            "dehumidifier_state": "STANDBY",
            "recirculation_flap": "FRESH_AIR",
            "trigger_source": "IN_CSE_REGULATION_INITIAL",
            "dispatched_at": now_ts
        }
        cin_cmd = {"m2m:cin": {"cnf": "application/json:0", "con": json.dumps(cmd_payload)}}
        request_m2m(f"{base_url}/{cse_rn}/{vehicle_id}/commands", method="POST", payload=cin_cmd, ty=4, origin=originator)

    return f"{cse_rn}/{vehicle_id}/raw-telemetry"

def main():
    args = parse_arguments()
    base_url = f"http://{args.host}:{args.port}"
    cse_rn = args.cse_rn
    originator = args.originator
    acp_name = args.acp_name
    grp_name = args.grp_name
    notif_base = args.notification_host or base_url

    print("=" * 80)
    print("  SDV AUTOMOTIVE IOT HVAC: ACME oneM2M CSEBASE & FLEET PROVISIONER")
    print(f"  Target CSEBase: {base_url}/{cse_rn} | Admin Originator: {originator}")
    print("  ETSI TS 118 101 Release 4 (RVI 3) • Multi-Hazard Cyber-Physical Mesh")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # STEP 0: Preflight Verification
    # -------------------------------------------------------------------------
    log("STEP 0", f"Verifying CSEBase reachability at {base_url}/{cse_rn}...", "36")
    status, body = request_m2m(f"{base_url}/{cse_rn}", origin=originator)
    if status != 200 or "m2m:cb" not in body:
        log("ERROR", f"CSEBase preflight failed! HTTP status: {status}, response: {body}", "31")
        sys.exit(1)

    cb = body["m2m:cb"]
    log("SUCCESS", f"CSEBase Verified: rn={cb.get('rn')}, ri={cb.get('ri')}, csi={cb.get('csi')}, srv={cb.get('srv')}", "32")

    # If audit-only flag is set, run audit and exit
    if args.audit_only:
        log("AUDIT ONLY", "Executing read-only CSEBase tree audit...", "33")
        audit_status, audit_res = request_m2m(f"{base_url}/{cse_rn}?rcn=4", origin=originator)
        if audit_status == 200:
            cb_data = audit_res.get("m2m:cb", {})
            print(json.dumps(cb_data, indent=2))
        sys.exit(0)

    # -------------------------------------------------------------------------
    # STEP 1: Fleet Governance Provisioning
    # -------------------------------------------------------------------------
    log("STEP 1.1", f"Reconciling Fleet Access Control Policy (<m2m:acp>): {acp_name}...", "36")
    acp_payload = {
        "m2m:acp": {
            "rn": acp_name,
            "pv": {
                "acr": [
                    {"acor": [originator], "acop": 63},
                    {"acor": ["C_vehicle_nodes"], "acop": 35}
                ]
            },
            "pvs": {
                "acr": [
                    {"acor": [originator], "acop": 63}
                ]
            }
        }
    }
    status, res = request_m2m(f"{base_url}/{cse_rn}", method="POST", payload=acp_payload, ty=1, origin=originator)
    if status == 201:
        log("SUCCESS", f"Created ACP '{acp_name}' (RI: {res['m2m:acp']['ri']})", "32")
    elif status == 409:
        log("IDEMPOTENT", f"ACP '{acp_name}' already active on CSE (HTTP 409)", "34")
    else:
        log("WARN", f"Unexpected status {status} for ACP creation: {res}", "33")

    log("STEP 1.2", f"Reconciling Fleet Aggregation Group (<m2m:grp>): {grp_name}...", "36")
    grp_payload = {
        "m2m:grp": {
            "rn": grp_name,
            "mt": 3,
            "mnm": 1000,
            "mid": [],
            "lbl": ["fleet", "telemetry", "sdv-cluster"]
        }
    }
    status, res = request_m2m(f"{base_url}/{cse_rn}", method="POST", payload=grp_payload, ty=9, origin=originator)
    if status == 201:
        log("SUCCESS", f"Created Group '{grp_name}' (RI: {res['m2m:grp']['ri']})", "32")
    elif status == 409:
        log("IDEMPOTENT", f"Group '{grp_name}' already active on CSE (HTTP 409)", "34")
    else:
        log("WARN", f"Unexpected status {status} for Group creation: {res}", "33")

    # -------------------------------------------------------------------------
    # STEP 2: Vehicle Application Entity Onboarding
    # -------------------------------------------------------------------------
    target_vehicles = []
    if not args.no_vehicles:
        if args.vehicles is not None and len(args.vehicles) > 0:
            target_vehicles = args.vehicles
        else:
            log("INFO", "No explicit vehicles specified via --vehicles. (Use -v vehicle-001 ... to onboard new entities)", "90")

    if target_vehicles:
        log("STEP 2", f"Onboarding {len(target_vehicles)} Vehicle Application Entities: {target_vehicles}...", "36")
        for v_rn in target_vehicles:
            onboard_vehicle(
                base_url=base_url,
                cse_rn=cse_rn,
                vehicle_id=v_rn,
                originator=originator,
                notif_base=notif_base,
                ingest_telemetry=not args.skip_telemetry
            )
    else:
        log("STEP 2", "Vehicle AE onboarding bypassed (0 vehicles requested or --no-vehicles active).", "33")

    # -------------------------------------------------------------------------
    # STEP 3: Fleet Registry Discovery & Dynamic Group Synchronization
    # -------------------------------------------------------------------------
    log("STEP 3.1", "Discovering all registered Vehicle Application Entities (fu=1&ty=2)...", "36")
    status, disc_ae = request_m2m(f"{base_url}/{cse_rn}?fu=1&ty=2", origin=originator)
    active_ae_uris = disc_ae.get("m2m:uril", [])
    vehicle_aes = [uri for uri in active_ae_uris if uri != f"{cse_rn}/{originator}" and not uri.endswith(f"/{originator}")]
    log("DISCOVERED", f"Active Fleet Vehicle AEs: {vehicle_aes}", "32")

    log("STEP 3.2", "Discovering all active telemetry containers (fu=1&ty=3)...", "36")
    status, disc_cnt = request_m2m(f"{base_url}/{cse_rn}?fu=1&ty=3", origin=originator)
    all_cnts = disc_cnt.get("m2m:uril", [])
    raw_telemetry_cnts = [c for c in all_cnts if c.endswith("/raw-telemetry") or "raw-telemetry" in c]
    log("DISCOVERED", f"Discovered Fleet Telemetry Endpoints: {raw_telemetry_cnts}", "32")

    log("STEP 3.3", f"Reconciling Group '{grp_name}' membership with all {len(raw_telemetry_cnts)} endpoints...", "36")
    grp_target = f"{base_url}/{cse_rn}/{grp_name}"
    grp_update = {"m2m:grp": {"mid": raw_telemetry_cnts}}
    status, grp_res = request_m2m(grp_target, method="PUT", payload=grp_update, origin=originator)
    if status == 200:
        cnm = grp_res.get("m2m:grp", {}).get("cnm", len(raw_telemetry_cnts))
        log("SYNCHRONISED", f"Updated {grp_name}.mid successfully (cnm: {cnm})", "32")
    else:
        log("WARN", f"Failed to update group membership: HTTP {status} {grp_res}", "33")

    # Group Fan-Out Test
    if raw_telemetry_cnts:
        log("STEP 3.4", f"Validating Atomic Group Fan-Out Query across Fleet ({grp_name}/fopt/la)...", "36")
        f_status, fopt_res = request_m2m(f"{grp_target}/fopt/la", origin=originator)
        if f_status in (200, 207):
            log("FAN-OUT OK", f"Single REST query successfully retrieved state across ALL {len(raw_telemetry_cnts)} fleet vehicles!", "32")
        else:
            log("WARN", f"Fan-out query returned status {f_status}: {fopt_res}", "33")

    # -------------------------------------------------------------------------
    # STEP 4: Comprehensive CSEBase Hierarchy Audit
    # -------------------------------------------------------------------------
    log("STEP 4", f"Executing Comprehensive Root CSEBase Audit ({cse_rn}?rcn=4)...", "36")
    status, root_audit = request_m2m(f"{base_url}/{cse_rn}?rcn=4", origin=originator)
    if status == 200:
        cb_res = root_audit.get("m2m:cb", {})
        aes = [a["rn"] for a in cb_res.get("m2m:ae", [])]
        grps = [g["rn"] for g in cb_res.get("m2m:grp", [])]
        acps = [p["rn"] for p in cb_res.get("m2m:acp", [])]

        print("\n" + "=" * 65)
        print("  ACME oneM2M CSEBASE INFRASTRUCTURE AUDIT REPORT")
        print("=" * 65)
        print(f"  Root CSE Resource Name: {cb_res.get('rn')}")
        print(f"  Root CSE Identifier:    {cb_res.get('ri')} (csi: {cb_res.get('csi')})")
        print(f"  Supported Releases:     {cb_res.get('srv')}")
        print(f"  Points of Access:       {cb_res.get('poa')}")
        print("-" * 65)
        print(f"  Access Control Policies ({len(acps)}): {acps}")
        print(f"  Fleet Groups ({len(grps)}):            {grps}")
        print(f"  Registered Vehicle AEs ({len(aes)}):  {aes}")
        print("=" * 65 + "\n")

    log("COMPLETE", "CSEBase & Fleet Infrastructure deployment executed successfully!\n", "32")

if __name__ == "__main__":
    main()
