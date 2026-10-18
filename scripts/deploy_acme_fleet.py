#!/usr/bin/env python3
"""
Deployment Automation Script: Deploy SDV Expandable Fleet to ACME oneM2M CSE
Executes the full oneM2M provisioning, governance, container reconciliation,
subscription, telemetry ingestion, and fleet fan-out validation against ACME CSE.

Conforms to:
  - collections/acme_fleet_insomnia_collection.yaml
  - collections/SDV_Expandable_Fleet_ACME_CSE_SOP.md
  - ETSI TS 118 101 Release 4 (RVI 3)
"""

import urllib.request
import urllib.error
import json
import time
import sys
import os
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

CSE_HOST = os.getenv("ACME_HOST", os.getenv("CSE_HOST", os.getenv("GATEWAY_IP", "127.0.0.1")))
CSE_PORT = os.getenv("ACME_PORT", os.getenv("ONEM2M_PORT", "8080"))
BASE_URL = os.getenv("BASE_URL", f"http://{CSE_HOST}:{CSE_PORT}").rstrip("/")
CSE_RN = os.getenv("CSE_RN", os.getenv("ONEM2M_CSE_NAME", "cse-in"))
ORIGINATOR = os.getenv("ORIGINATOR", os.getenv("ONEM2M_ADMIN_ORIGIN", "CAdmin"))
RVI = os.getenv("RVI", os.getenv("ONEM2M_RVI", "3"))
API_ID = os.getenv("API_ID", "N.org.fhtw.sdv.cabin")

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

def log(tag, msg, color="0"):
    # ANSI colors: 32 green, 34 blue, 33 yellow, 31 red, 35 magenta, 36 cyan
    print(f"\033[{color}m[{tag}]\033[0m {msg}")

def request_m2m(url, method="GET", payload=None, ty=None, origin=ORIGINATOR):
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

def main():
    print("=" * 80)
    print("  SDV AUTOMOTIVE IOT HVAC: ACME oneM2M CSE FLEET DEPLOYMENT RUNNER")
    print("  ETSI TS 118 101 Release 4 (RVI 3) • Multi-Hazard Cyber-Physical Mesh")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # STEP 0: Preflight Verification
    # -------------------------------------------------------------------------
    log("STEP 0.1", f"Verifying CSEBase connection to {BASE_URL}/{CSE_RN}...", "36")
    status, body = request_m2m(f"{BASE_URL}/{CSE_RN}")
    if status != 200 or "m2m:cb" not in body:
        log("ERROR", f"Preflight failed! HTTP status: {status}, body: {body}", "31")
        sys.exit(1)
    
    cb = body["m2m:cb"]
    log("SUCCESS", f"CSEBase Verified: rn={cb.get('rn')}, ri={cb.get('ri')}, csi={cb.get('csi')}, srv={cb.get('srv')}", "32")

    # -------------------------------------------------------------------------
    # STEP 1: Fleet Governance
    # -------------------------------------------------------------------------
    log("STEP 1.1", "Reconciling Fleet Access Control Policy: acp_fleet_manager...", "36")
    acp_payload = {
        "m2m:acp": {
            "rn": "acp_fleet_manager",
            "pv": {
                "acr": [
                    {"acor": [ORIGINATOR], "acop": 63},
                    {"acor": ["C_vehicle_nodes"], "acop": 35}
                ]
            },
            "pvs": {
                "acr": [
                    {"acor": [ORIGINATOR], "acop": 63}
                ]
            }
        }
    }
    status, res = request_m2m(f"{BASE_URL}/{CSE_RN}", method="POST", payload=acp_payload, ty=1)
    if status == 201:
        log("SUCCESS", f"Created acp_fleet_manager (RI: {res['m2m:acp']['ri']})", "32")
    elif status == 409:
        log("IDEMPOTENT", "acp_fleet_manager already exists on CSE (HTTP 409)", "33")
    else:
        log("WARN", f"Unexpected status {status} for ACP creation: {res}", "33")

    log("STEP 1.2", "Reconciling Fleet Aggregation Group: grp_fleet_telemetry...", "36")
    grp_payload = {
        "m2m:grp": {
            "rn": "grp_fleet_telemetry",
            "mt": 3,
            "mnm": 1000,
            "mid": [],
            "lbl": ["fleet", "telemetry", "sdv-cluster"]
        }
    }
    status, res = request_m2m(f"{BASE_URL}/{CSE_RN}", method="POST", payload=grp_payload, ty=9)
    if status == 201:
        log("SUCCESS", f"Created grp_fleet_telemetry (RI: {res['m2m:grp']['ri']})", "32")
    elif status == 409:
        log("IDEMPOTENT", "grp_fleet_telemetry already exists on CSE (HTTP 409)", "33")
    else:
        log("WARN", f"Unexpected status {status} for Group creation: {res}", "33")

    # -------------------------------------------------------------------------
    # STEP 2: Onboard Vehicles (vehicle-001 and vehicle-002)
    # -------------------------------------------------------------------------
    vehicles_to_onboard = [
        {"rn": "vehicle-001", "vin": "VIN-WAUZZZ-SDV-2026-0042", "temp": 22.4, "rh": 46.5, "co2": 620.0, "co": 0.2, "pwm": 75, "rpm": 1850},
        {"rn": "vehicle-002", "vin": "VIN-WAUZZZ-SDV-2026-0099", "temp": 21.8, "rh": 48.0, "co2": 580.0, "co": 0.1, "pwm": 50, "rpm": 1200}
    ]

    for v in vehicles_to_onboard:
        v_rn = v["rn"]
        v_vin = v["vin"]
        log("STEP 2.1", f"Onboarding Vehicle Application Entity: {v_rn} ({v_vin})...", "36")
        
        ae_payload = {
            "m2m:ae": {
                "rn": v_rn,
                "api": API_ID,
                "rr": True,
                "srv": ["2a", "3"],
                "lbl": ["vehicle", "sdv-fleet", f"identity:{v_vin}"]
            }
        }
        status, res = request_m2m(f"{BASE_URL}/{CSE_RN}", method="POST", payload=ae_payload, ty=2, origin="S")
        if status == 201:
            ae_ri = res["m2m:ae"]["ri"]
            ae_aei = res["m2m:ae"].get("aei", ae_ri)
            log("SUCCESS", f"Registered AE {v_rn} (RI: {ae_ri}, AEI: {ae_aei})", "32")
        elif status == 409:
            log("IDEMPOTENT", f"AE {v_rn} already exists. Querying existing AE...", "33")
            _, res = request_m2m(f"{BASE_URL}/{CSE_RN}/{v_rn}")
            ae_ri = res.get("m2m:ae", {}).get("ri", v_rn)
            ae_aei = res.get("m2m:ae", {}).get("aei", ae_ri)
            log("INFO", f"Captured existing AE {v_rn} (RI: {ae_ri}, AEI: {ae_aei})", "34")
        else:
            log("ERROR", f"Failed to register AE {v_rn}: {status} {res}", "31")
            continue

        # Step 2.2: Reconcile all 8 manifest containers
        log("STEP 2.2", f"Reconciling 8 Manifest Containers for {v_rn} (with mia: 86400)...", "36")
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
                    "lbl": ["sensor", cnt_def["location"], cnt_def["measurement"], v_rn]
                }
            }
            c_status, c_res = request_m2m(f"{BASE_URL}/{CSE_RN}/{v_rn}", method="POST", payload=cnt_payload, ty=3)
            if c_status == 201:
                log("CREATED", f"  -> Container: {c_name} (mni={mni}, mia=86400, RI={c_res['m2m:cnt']['ri']})", "32")
            elif c_status == 409:
                log("VERIFIED", f"  -> Container: {c_name} (already verified)", "34")
            else:
                log("WARN", f"  -> Failed to create {c_name}: {c_status} {c_res}", "33")

        # Step 3: Subscriptions for vehicle
        log("STEP 3", f"Reconciling Subscriptions for {v_rn}...", "36")
        # 3.1: sub_co_alert
        sub_co = {
            "m2m:sub": {
                "rn": "sub_co_alert",
                "nu": [f"{BASE_URL}/emergency-monitor"],
                "nct": 1,
                "enc": {"net": [3]}
            }
        }
        s_status, _ = request_m2m(f"{BASE_URL}/{CSE_RN}/{v_rn}/co-cabin", method="POST", payload=sub_co, ty=23)
        log("SUBSCRIPTION", f"  -> sub_co_alert on co-cabin: status {s_status}", "32" if s_status in (201, 409) else "33")

        # 3.2: sub_fleet_telemetry
        sub_tel = {
            "m2m:sub": {
                "rn": "sub_fleet_telemetry",
                "nu": [f"{BASE_URL}/fleet-ingest"],
                "nct": 1,
                "enc": {"net": [3]}
            }
        }
        s_status, _ = request_m2m(f"{BASE_URL}/{CSE_RN}/{v_rn}/raw-telemetry", method="POST", payload=sub_tel, ty=23)
        log("SUBSCRIPTION", f"  -> sub_fleet_telemetry on raw-telemetry: status {s_status}", "32" if s_status in (201, 409) else "33")

        # 3.3: sub_downlink
        sub_down = {
            "m2m:sub": {
                "rn": "sub_downlink",
                "nu": [f"{BASE_URL}/downlink"],
                "nct": 1,
                "enc": {"net": [3]}
            }
        }
        s_status, _ = request_m2m(f"{BASE_URL}/{CSE_RN}/{v_rn}/commands", method="POST", payload=sub_down, ty=23)
        log("SUBSCRIPTION", f"  -> sub_downlink on commands: status {s_status}", "32" if s_status in (201, 409) else "33")

        # Step 4: Ingest Telemetry & Actuation Commands
        log("STEP 4", f"Ingesting Telemetry and Actuation Frames for {v_rn}...", "36")
        
        # 4.1: Synchronised raw telemetry
        now_ts = int(time.time())
        sample_frame = {
            "is_simulated": True,
            "vehicle_id": v_rn,
            "vin": v_vin,
            "timestamp_unix_s": now_ts,
            "cabin": {
                "temperature_c": v["temp"],
                "temperature_scd30": v["temp"],
                "temperature_dht22": round(v["temp"] - 0.3, 2),
                "humidity_pct": v["rh"],
                "humidity_scd30": v["rh"],
                "humidity_dht22": round(v["rh"] - 1.3, 1),
                "co2_ppm": v["co2"],
                "co_ppm": v["co"],
                "air_quality_score": 42,
                "exterior_aqi": 28
            },
            "actuator_state": {
                "pwm_duty_pct": v["pwm"],
                "tachometer_rpm": v["rpm"],
                "carrier_freq_hz": 25000,
                "heater_state": "STANDBY",
                "eco_vent_state": "ACTIVE",
                "dehumidifier_state": "STANDBY",
                "recirculation_flap": "FRESH_AIR"
            }
        }
        cin_tel = {
            "m2m:cin": {
                "cnf": "application/json:0",
                "con": json.dumps(sample_frame)
            }
        }
        t_status, t_res = request_m2m(f"{BASE_URL}/{CSE_RN}/{v_rn}/raw-telemetry", method="POST", payload=cin_tel, ty=4)
        if t_status == 201:
            log("INGESTED", f"  -> raw-telemetry <cin> (RI: {t_res['m2m:cin']['ri']}, CO2={v['co2']}ppm, Fan={v['pwm']}%)", "32")
        else:
            log("WARN", f"  -> raw-telemetry ingest status {t_status}: {t_res}", "33")

        # 4.2: CO safety reading
        co_reading = {
            "is_simulated": True,
            "val": v["co"],
            "unit": "ppm",
            "alarm": False,
            "severity": "NORMAL",
            "ts": now_ts
        }
        cin_co = {
            "m2m:cin": {
                "cnf": "application/json:0",
                "con": json.dumps(co_reading)
            }
        }
        co_status, co_res = request_m2m(f"{BASE_URL}/{CSE_RN}/{v_rn}/co-cabin", method="POST", payload=cin_co, ty=4)
        if co_status == 201:
            log("INGESTED", f"  -> co-cabin <cin> (RI: {co_res['m2m:cin']['ri']}, CO={v['co']}ppm)", "32")

        # 4.3: Actuator command instance
        cmd_payload = {
            "target_fan_pwm": float(v["pwm"]),
            "fan_mode": "AUTO",
            "aux_heater_state": "STANDBY",
            "eco_vent_state": "ACTIVE",
            "dehumidifier_state": "STANDBY",
            "recirculation_flap": "FRESH_AIR",
            "trigger_source": "IN_CSE_REGULATION_RULE_1",
            "dispatched_at": now_ts
        }
        cin_cmd = {
            "m2m:cin": {
                "cnf": "application/json:0",
                "con": json.dumps(cmd_payload)
            }
        }
        cmd_status, cmd_res = request_m2m(f"{BASE_URL}/{CSE_RN}/{v_rn}/commands", method="POST", payload=cin_cmd, ty=4)
        if cmd_status == 201:
            log("INGESTED", f"  -> commands <cin> (RI: {cmd_res['m2m:cin']['ri']}, PWM={v['pwm']}%, Flap=FRESH_AIR)", "32")

    # -------------------------------------------------------------------------
    # STEP 5: Fleet Registry, Discovery & Dynamic Group Synchronization
    # -------------------------------------------------------------------------
    log("STEP 5.1", "Discovering registered fleet vehicle AEs (fu=1&ty=2)...", "36")
    status, disc_ae = request_m2m(f"{BASE_URL}/{CSE_RN}?fu=1&ty=2")
    discovered_aes = disc_ae.get("m2m:uril", [])
    log("DISCOVERED", f"Active Fleet Vehicles: {discovered_aes}", "32")

    log("STEP 5.2", "Discovering fleet telemetry containers (fu=1&ty=3)...", "36")
    status, disc_cnt = request_m2m(f"{BASE_URL}/{CSE_RN}?fu=1&ty=3")
    all_cnts = disc_cnt.get("m2m:uril", [])
    raw_cnts = [c for c in all_cnts if c.endswith("/raw-telemetry") or "raw-telemetry" in c]
    log("DISCOVERED", f"Target Group Members (raw-telemetry): {raw_cnts}", "32")

    log("STEP 5.3", f"Updating grp_fleet_telemetry membership with {len(raw_cnts)} endpoints...", "36")
    grp_update = {
        "m2m:grp": {
            "mid": raw_cnts
        }
    }
    status, grp_res = request_m2m(f"{BASE_URL}/{CSE_RN}/grp_fleet_telemetry", method="PUT", payload=grp_update)
    if status == 200:
        log("SYNCHRONISED", f"grp_fleet_telemetry mid updated! cnm={grp_res['m2m:grp'].get('cnm')}, members={raw_cnts}", "32")
    else:
        log("WARN", f"Failed to update group members: {status} {grp_res}", "33")

    log("STEP 5.4", "Executing Atomic Group Fan-Out Query across Fleet (/fopt/la)...", "36")
    status, fopt_res = request_m2m(f"{BASE_URL}/{CSE_RN}/grp_fleet_telemetry/fopt/la")
    if status in (200, 207):
        log("FAN-OUT SUCCESS", "Single REST request retrieved latest telemetry across ALL fleet vehicles atomically!", "32")
        agr = fopt_res.get("m2m:agr", fopt_res)
        log("INFO", f"Aggregated Response Payload: {json.dumps(agr)[:180]}...", "34")
    else:
        log("WARN", f"Fan-out query status {status}: {fopt_res}", "33")

    # -------------------------------------------------------------------------
    # STEP 6: Validation & Observability Audit
    # -------------------------------------------------------------------------
    log("STEP 6.1", "Auditing vehicle-001 resource tree against 8-container manifest (rcn=4)...", "36")
    status, tree_audit = request_m2m(f"{BASE_URL}/{CSE_RN}/vehicle-001?rcn=4")
    if status == 200:
        ae_data = tree_audit.get("m2m:ae", {})
        child_cnts = ae_data.get("m2m:cnt", [])
        child_names = [c["rn"] for c in child_cnts]
        manifest_names = [m["name"] for m in SENSOR_MANIFEST]
        verified = [n for n in manifest_names if n in child_names]
        missing = [n for n in manifest_names if n not in child_names]
        
        print("\n" + "=" * 60)
        print("  VEHICLE-001 AUDIT & VALIDATION REPORT")
        print("=" * 60)
        print(f"  Target AE:           {ae_data.get('rn')}")
        print(f"  Resource ID (RI):    {ae_data.get('ri')}")
        print(f"  Assigned AEI:        {ae_data.get('aei')}")
        print(f"  Expected Containers: {len(manifest_names)}")
        print(f"  Verified Count:      {len(verified)} / {len(manifest_names)}")
        print(f"  Verified Names:      {verified}")
        print(f"  Missing Names:       {missing}")
        print(f"  Audit Status:        {'PASSED - 100% RECONCILED' if len(missing) == 0 else 'FAILED'}")
        print("=" * 60 + "\n")

    log("STEP 6.3", "Auditing Root CSEBase Hierarchy...", "36")
    status, root_audit = request_m2m(f"{BASE_URL}/{CSE_RN}?rcn=4")
    if status == 200:
        cb_res = root_audit.get("m2m:cb", {})
        aes = [a["rn"] for a in cb_res.get("m2m:ae", [])]
        grps = [g["rn"] for g in cb_res.get("m2m:grp", [])]
        acps = [p["rn"] for p in cb_res.get("m2m:acp", [])]
        log("CSE HIERARCHY", f"Registered AEs: {aes}", "32")
        log("CSE HIERARCHY", f"Fleet Groups:   {grps}", "32")
        log("CSE HIERARCHY", f"Security ACPs:  {acps}", "32")

    print("\n\033[32m[COMPLETE]\033[0m SDV Expandable Fleet Collection deployed successfully to ACME oneM2M CSE!\n")

if __name__ == "__main__":
    main()
