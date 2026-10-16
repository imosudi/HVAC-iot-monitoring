#!/usr/bin/env python3
"""
Single Vehicle Application Entity (AE) Deployment Script
Automates the horizontal scaling and onboarding of a single Software-Defined Vehicle (SDV)
Application Entity onto the ACME oneM2M CSE.

Conforms to:
  - ETSI TS 118 101 Release 4 (RVI 3)
  - collections/acme_fleet_insomnia_collection.yaml (Folder 2: Vehicle AE Onboarding)
  - collections/SDV_Expandable_Fleet_ACME_CSE_SOP.md

Functionality:
  1. Preflight connectivity check to target ACME CSEBase.
  2. Idempotent registration of the Vehicle Application Entity (<m2m:ae>) using origin 'S'.
  3. Provisioning the full 8-container manifest with mia=86400 (24h retention) & sizing quotas:
       - temperature-cabin (mni=1000, mia=86400)
       - humidity-cabin (mni=1000, mia=86400)
       - co2-cabin (mni=1000, mia=86400)
       - co-cabin (mni=1000, mia=86400, life-safety)
       - air-quality-cabin (mni=1000, mia=86400)
       - air-quality-exterior (mni=1000, mia=86400)
       - raw-telemetry (mni=1440, mbs=2097152, mia=86400)
       - commands (mni=100, mbs=262144, mia=86400)
  4. Provisioning the 3 standard subscriptions:
       - sub_co_alert on co-cabin
       - sub_fleet_telemetry on raw-telemetry
       - sub_downlink on commands
  5. Ingestion of initial synchronised multi-sensor baseline telemetry and actuation command.
  6. Reconciling the vehicle's telemetry endpoint into the fleet aggregation group (grp_fleet_telemetry.mid).
  7. Validating cluster fan-out retrieval (/fopt/la) and producing a comprehensive audit report (rcn=4).
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

API_ID = "N.org.fhtw.sdv.cabin"
RVI = "3"

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
        description="Deploy a Single SDV Vehicle Application Entity to ACME oneM2M CSE",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--vehicle-id", "-i",
        default="vehicle-003",
        help="Target Resource Name (rn) for the vehicle Application Entity"
    )
    parser.add_argument(
        "--vin",
        default=None,
        help="Vehicle Identification Number (default: generated based on vehicle-id)"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("ACME_HOST", "192.168.122.91"),
        help="ACME CSE hostname or IP address"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=int(os.getenv("ACME_PORT", "8080")),
        help="ACME CSE HTTP port"
    )
    parser.add_argument(
        "--cse-rn",
        default="cse-in",
        help="Root CSEBase Resource Name"
    )
    parser.add_argument(
        "--originator",
        default="CAdmin",
        help="Administrative originator for container, subscription and group operations"
    )
    parser.add_argument(
        "--notification-host",
        default=None,
        help="Target base URL for subscription notification handlers (default: http://<host>:<port>)"
    )
    parser.add_argument(
        "--temp",
        type=float,
        default=22.0,
        help="Initial cabin temperature in degrees Celsius"
    )
    parser.add_argument(
        "--rh",
        type=float,
        default=45.0,
        help="Initial cabin relative humidity percentage"
    )
    parser.add_argument(
        "--co2",
        type=float,
        default=550.0,
        help="Initial cabin CO2 concentration in ppm"
    )
    parser.add_argument(
        "--co",
        type=float,
        default=0.1,
        help="Initial cabin CO concentration in ppm"
    )
    parser.add_argument(
        "--pwm",
        type=int,
        default=60,
        help="Initial HVAC blower PWM duty cycle percentage (0-100)"
    )
    parser.add_argument(
        "--rpm",
        type=int,
        default=1500,
        help="Initial blower tachometer RPM"
    )
    parser.add_argument(
        "--no-telemetry",
        action="store_true",
        help="Skip ingesting initial sample baseline telemetry and actuation command frames"
    )
    parser.add_argument(
        "--no-group-sync",
        action="store_true",
        help="Skip synchronizing the vehicle raw-telemetry container into grp_fleet_telemetry"
    )
    return parser.parse_args()

def main():
    args = parse_arguments()
    vehicle_id = args.vehicle_id
    vin = args.vin or f"VIN-WAUZZZ-SDV-2026-{vehicle_id.split('-')[-1].zfill(4)}"
    base_url = f"http://{args.host}:{args.port}"
    cse_rn = args.cse_rn
    originator = args.originator
    notif_base = args.notification_host or base_url

    print("=" * 80)
    print("  SDV VEHICLE ONBOARDING: ACME oneM2M CSE SINGLE AE PROVISIONER")
    print(f"  Target AE: {vehicle_id} | VIN: {vin} | CSE: {base_url}/{cse_rn}")
    print("  ETSI TS 118 101 Release 4 (RVI 3) • Multi-Hazard Cyber-Physical Mesh")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # STEP 0: Preflight Verification
    # -------------------------------------------------------------------------
    log("STEP 0", f"Verifying CSEBase connection to {base_url}/{cse_rn}...", "36")
    status, body = request_m2m(f"{base_url}/{cse_rn}", origin=originator)
    if status != 200 or "m2m:cb" not in body:
        log("ERROR", f"Preflight failed! HTTP status: {status}, body: {body}", "31")
        sys.exit(1)

    cb = body["m2m:cb"]
    log("SUCCESS", f"CSEBase Verified: rn={cb.get('rn')}, ri={cb.get('ri')}, csi={cb.get('csi')}, srv={cb.get('srv')}", "32")

    # -------------------------------------------------------------------------
    # STEP 1: Onboard Vehicle Application Entity (<m2m:ae>)
    # -------------------------------------------------------------------------
    log("STEP 1", f"Provisioning Vehicle AE: {vehicle_id} (VIN: {vin})...", "36")
    ae_payload = {
        "m2m:ae": {
            "rn": vehicle_id,
            "api": API_ID,
            "rr": True,
            "srv": ["2a", "3"],
            "lbl": ["vehicle", "sdv-fleet", f"identity:{vin}"]
        }
    }
    # AE Registration must use unassigned originator 'S' per ETSI TS 118 101
    status, res = request_m2m(f"{base_url}/{cse_rn}", method="POST", payload=ae_payload, ty=2, origin="S")
    if status == 201:
        ae_ri = res["m2m:ae"]["ri"]
        ae_aei = res["m2m:ae"].get("aei", ae_ri)
        log("SUCCESS", f"Registered AE {vehicle_id} (RI: {ae_ri}, AEI: {ae_aei})", "32")
    elif status == 409:
        log("IDEMPOTENT", f"AE {vehicle_id} already exists. Querying existing resource...", "33")
        _, res = request_m2m(f"{base_url}/{cse_rn}/{vehicle_id}", origin=originator)
        ae_ri = res.get("m2m:ae", {}).get("ri", vehicle_id)
        ae_aei = res.get("m2m:ae", {}).get("aei", ae_ri)
        log("INFO", f"Captured existing AE {vehicle_id} (RI: {ae_ri}, AEI: {ae_aei})", "34")
    else:
        log("ERROR", f"Failed to register AE {vehicle_id}: HTTP {status} {res}", "31")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # STEP 2: Reconcile 8 Manifest Containers
    # -------------------------------------------------------------------------
    log("STEP 2", f"Reconciling 8 Manifest Containers for {vehicle_id} (mia: 86400)...", "36")
    reconciled_cnts = {}
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
            cnt_ri = c_res["m2m:cnt"]["ri"]
            reconciled_cnts[c_name] = cnt_ri
            log("CREATED", f"  -> Container: {c_name:<22} (mni={mni:<4}, mia=86400, RI={cnt_ri})", "32")
        elif c_status == 409:
            log("VERIFIED", f"  -> Container: {c_name:<22} (already provisioned)", "34")
            reconciled_cnts[c_name] = "existing"
        else:
            log("WARN", f"  -> Failed to provision {c_name}: HTTP {c_status} {c_res}", "33")

    # -------------------------------------------------------------------------
    # STEP 3: Reconcile Subscriptions
    # -------------------------------------------------------------------------
    log("STEP 3", f"Reconciling Event Subscriptions for {vehicle_id}...", "36")
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
            log("SUBSCRIPTION", f"  -> Created {sub['rn']:<20} on {sub['target_cnt']} (RI: {s_res['m2m:sub']['ri']})", "32")
        elif s_status == 409:
            log("SUBSCRIPTION", f"  -> Verified {sub['rn']:<19} on {sub['target_cnt']} (already active)", "34")
        else:
            log("WARN", f"  -> Subscription {sub['rn']} status {s_status}: {s_res}", "33")

    # -------------------------------------------------------------------------
    # STEP 4: Ingest Initial Telemetry & Actuation Frames
    # -------------------------------------------------------------------------
    if not args.no_telemetry:
        log("STEP 4", f"Ingesting Initial Baseline Frames for {vehicle_id}...", "36")
        now_ts = int(time.time())

        # 4.1: Synchronised raw telemetry
        sample_frame = {
            "is_simulated": True,
            "vehicle_id": vehicle_id,
            "vin": vin,
            "timestamp_unix_s": now_ts,
            "cabin": {
                "temperature_c": args.temp,
                "temperature_scd30": args.temp,
                "temperature_dht22": round(args.temp - 0.3, 2),
                "humidity_pct": args.rh,
                "humidity_scd30": args.rh,
                "humidity_dht22": round(args.rh - 1.2, 1),
                "co2_ppm": args.co2,
                "co_ppm": args.co,
                "air_quality_score": 42,
                "exterior_aqi": 25
            },
            "actuator_state": {
                "pwm_duty_pct": args.pwm,
                "tachometer_rpm": args.rpm,
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
        t_status, t_res = request_m2m(
            f"{base_url}/{cse_rn}/{vehicle_id}/raw-telemetry",
            method="POST",
            payload=cin_tel,
            ty=4,
            origin=originator
        )
        if t_status == 201:
            log("INGESTED", f"  -> raw-telemetry <cin> (RI: {t_res['m2m:cin']['ri']}, CO2={args.co2}ppm, Fan={args.pwm}%)", "32")
        else:
            log("WARN", f"  -> raw-telemetry ingest status {t_status}: {t_res}", "33")

        # 4.2: CO safety reading
        co_reading = {
            "is_simulated": True,
            "val": args.co,
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
        co_status, co_res = request_m2m(
            f"{base_url}/{cse_rn}/{vehicle_id}/co-cabin",
            method="POST",
            payload=cin_co,
            ty=4,
            origin=originator
        )
        if co_status == 201:
            log("INGESTED", f"  -> co-cabin <cin> (RI: {co_res['m2m:cin']['ri']}, CO={args.co}ppm)", "32")

        # 4.3: Actuator command instance
        cmd_payload = {
            "target_fan_pwm": float(args.pwm),
            "fan_mode": "AUTO",
            "aux_heater_state": "STANDBY",
            "eco_vent_state": "ACTIVE",
            "dehumidifier_state": "STANDBY",
            "recirculation_flap": "FRESH_AIR",
            "trigger_source": "IN_CSE_REGULATION_RULE_ONBOARDING",
            "dispatched_at": now_ts
        }
        cin_cmd = {
            "m2m:cin": {
                "cnf": "application/json:0",
                "con": json.dumps(cmd_payload)
            }
        }
        cmd_status, cmd_res = request_m2m(
            f"{base_url}/{cse_rn}/{vehicle_id}/commands",
            method="POST",
            payload=cin_cmd,
            ty=4,
            origin=originator
        )
        if cmd_status == 201:
            log("INGESTED", f"  -> commands <cin> (RI: {cmd_res['m2m:cin']['ri']}, PWM={args.pwm}%, Flap=FRESH_AIR)", "32")
    else:
        log("STEP 4", "Skipping initial telemetry ingestion (--no-telemetry specified).", "33")

    # -------------------------------------------------------------------------
    # STEP 5: Dynamic Group Membership Reconciliation
    # -------------------------------------------------------------------------
    if not args.no_group_sync:
        log("STEP 5", "Reconciling Fleet Aggregation Group (grp_fleet_telemetry)...", "36")
        grp_target = f"{base_url}/{cse_rn}/grp_fleet_telemetry"
        status, grp_data = request_m2m(grp_target, origin=originator)
        if status == 200 and "m2m:grp" in grp_data:
            current_mids = list(grp_data["m2m:grp"].get("mid", []))
            target_endpoint = f"{cse_rn}/{vehicle_id}/raw-telemetry"

            # Resolve raw-telemetry resource ID to ensure robust comparison against normalized mids
            raw_ri = reconciled_cnts.get("raw-telemetry")
            if not raw_ri or raw_ri == "existing":
                _, raw_data = request_m2m(f"{base_url}/{target_endpoint}", origin=originator)
                raw_ri = raw_data.get("m2m:cnt", {}).get("ri")

            is_already_member = (
                target_endpoint in current_mids or
                (raw_ri and raw_ri in current_mids) or
                any(m.endswith(f"/{vehicle_id}/raw-telemetry") for m in current_mids)
            )

            if not is_already_member:
                current_mids.append(target_endpoint)
                update_payload = {"m2m:grp": {"mid": current_mids}}
                up_status, up_res = request_m2m(grp_target, method="PUT", payload=update_payload, origin=originator)
                if up_status == 200:
                    cnm = up_res.get("m2m:grp", {}).get("cnm", len(current_mids))
                    log("SYNCHRONISED", f"Added {target_endpoint} to grp_fleet_telemetry (Total members: {cnm})", "32")
                else:
                    log("WARN", f"Failed to update group members: HTTP {up_status} {up_res}", "33")
            else:
                log("INFO", f"Endpoint {target_endpoint} (RI: {raw_ri}) is already a member of grp_fleet_telemetry (Total members: {len(current_mids)})", "34")

            # Validate atomic fan-out query
            log("STEP 5.1", "Testing Fleet Fan-Out Query (/fopt/la)...", "36")
            f_status, fopt_res = request_m2m(f"{grp_target}/fopt/la", origin=originator)
            if f_status in (200, 207):
                log("FAN-OUT OK", f"Retrieved latest telemetry across all {len(current_mids)} fleet members!", "32")
            else:
                log("WARN", f"Fan-out query returned status {f_status}: {fopt_res}", "33")
        else:
            log("INFO", f"grp_fleet_telemetry not found or status {status}. Skipping group join.", "33")
    else:
        log("STEP 5", "Skipping group synchronization (--no-group-sync specified).", "33")

    # -------------------------------------------------------------------------
    # STEP 6: Validation & Observability Audit
    # -------------------------------------------------------------------------
    log("STEP 6", f"Executing Tree Audit for {vehicle_id} (rcn=4)...", "36")
    status, tree_audit = request_m2m(f"{base_url}/{cse_rn}/{vehicle_id}?rcn=4", origin=originator)
    if status == 200:
        ae_data = tree_audit.get("m2m:ae", {})
        child_cnts = ae_data.get("m2m:cnt", [])
        child_names = [c["rn"] for c in child_cnts]
        manifest_names = [m["name"] for m in SENSOR_MANIFEST]
        verified = [n for n in manifest_names if n in child_names]
        missing = [n for n in manifest_names if n not in child_names]

        print("\n" + "=" * 60)
        print(f"  VEHICLE AUDIT & RECONCILIATION REPORT: {vehicle_id}")
        print("=" * 60)
        print(f"  Target AE:           {ae_data.get('rn')}")
        print(f"  Resource ID (RI):    {ae_data.get('ri')}")
        print(f"  Assigned AEI:        {ae_data.get('aei')}")
        print(f"  Labels:              {ae_data.get('lbl')}")
        print(f"  Expected Containers: {len(manifest_names)}")
        print(f"  Verified Count:      {len(verified)} / {len(manifest_names)}")
        print(f"  Verified Names:      {verified}")
        print(f"  Missing Names:       {missing}")
        print(f"  Audit Status:        {'PASSED - 100% RECONCILED' if len(missing) == 0 else 'FAILED'}")
        print("=" * 60 + "\n")

    log("COMPLETE", f"Vehicle Application Entity '{vehicle_id}' successfully deployed to ACME CSE!\n", "32")

if __name__ == "__main__":
    main()
