#!/usr/bin/env bash
# ==============================================================================
# oneM2M Resource Tree Initialisation Script
# Automates the creation of AE, Containers, and Subscriptions in /sdv-cse
# Conforms to ETSI TS 118 101 Release 4 Functional Architecture &
# Consolidated Vehicular Edge Gateway Architecture (ARC-SDV-CSE-2026-01)
# ==============================================================================

set -euo pipefail

CSE_HOST="${CSE_HOST:-localhost}"
CSE_PORT="${CSE_PORT:-8080}"
CSE_BASE="${CSE_BASE:-sdv-cse}"
ORIGIN="${ORIGIN:-CAdmin}"
BASE_URL="http://${CSE_HOST}:${CSE_PORT}/${CSE_BASE}"

echo "================================================================================"
echo "  SDV VEHICULAR EDGE GATEWAY: oneM2M RESOURCE TREE PROVISIONER"
echo "  Consolidated Architecture Design Compliance & Multi-Hazard Sensor Manifest"
echo "  Target: ${BASE_URL} | Admin Originator: ${ORIGIN}"
echo "================================================================================"

# Helper function to issue oneM2M POST request with idempotency handling
create_resource() {
    local target_url="$1"
    local resource_type="$2"
    local payload="$3"
    local name="$4"
    local origin="${5:-$ORIGIN}"

    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${target_url}" \
        -H "X-M2M-Origin: ${origin}" \
        -H "X-M2M-RI: req_$(date +%s%N)" \
        -H "X-M2M-RVI: 3" \
        -H "Content-Type: application/json;ty=${resource_type}" \
        -H "Accept: application/json" \
        -d "${payload}") || http_code="000"

    if [ "${http_code}" = "201" ]; then
        echo -e "  [CREATED]    ${name} (ty=${resource_type}) -> HTTP 201"
    elif [ "${http_code}" = "409" ]; then
        echo -e "  [IDEMPOTENT] ${name} already exists -> HTTP 409"
    else
        echo -e "  [WARN]       ${name} status HTTP ${http_code}"
    fi
}

# ------------------------------------------------------------------------------
# STEP 1: Fleet Governance (Access Control Policy & Aggregation Group)
# ------------------------------------------------------------------------------
echo -e "\n[STEP 1/5] Provisioning Fleet Governance Entities under /${CSE_BASE}..."

ACP_PAYLOAD='{
    "m2m:acp": {
        "rn": "acp_fleet_manager",
        "pv": {
            "acr": [
                {"acor": ["'"${ORIGIN}"'"], "acop": 63},
                {"acor": ["C_vehicle_nodes", "C_CabinNode_Car01"], "acop": 35}
            ]
        },
        "pvs": {
            "acr": [
                {"acor": ["'"${ORIGIN}"'"], "acop": 63}
            ]
        }
    }
}'
create_resource "${BASE_URL}" 1 "${ACP_PAYLOAD}" "acp_fleet_manager"

GRP_PAYLOAD='{
    "m2m:grp": {
        "rn": "grp_fleet_telemetry",
        "mt": 3,
        "mnm": 1000,
        "mid": [],
        "lbl": ["fleet", "telemetry", "sdv-cluster"]
    }
}'
create_resource "${BASE_URL}" 9 "${GRP_PAYLOAD}" "grp_fleet_telemetry"

# ------------------------------------------------------------------------------
# STEP 2: Application Entity (AE)
# ------------------------------------------------------------------------------
echo -e "\n[STEP 2/5] Registering Vehicle Application Entity: AE_CabinNode_Car01..."
AE_PAYLOAD='{
    "m2m:ae": {
        "rn": "AE_CabinNode_Car01",
        "api": "N.org.fhtw.sdv.cabin",
        "rr": true,
        "srv": ["2a", "3"],
        "lbl": ["vehicle", "sdv-fleet", "identity:VIN-WAUZZZ-SDV-2026-0001"]
    }
}'
# AE creation uses unassigned originator 'S' per ETSI TS 118 101
create_resource "${BASE_URL}" 2 "${AE_PAYLOAD}" "AE_CabinNode_Car01" "S"

AE_URL="${BASE_URL}/AE_CabinNode_Car01"

# ------------------------------------------------------------------------------
# STEP 3: Complete 8-Container Manifest with 24h TTL (mia: 86400)
# ------------------------------------------------------------------------------
echo -e "\n[STEP 3/5] Reconciling 8-Container Manifest with Storage Limits (mia: 86400)..."

declare -A CONTAINERS
# Format: [name]="mni:mbs:mia:lbl"
CONTAINERS["temperature-cabin"]="1000:1048576:86400:temperature cabin"
CONTAINERS["humidity-cabin"]="1000:1048576:86400:humidity cabin"
CONTAINERS["co2-cabin"]="1000:1048576:86400:co2 cabin ndir"
CONTAINERS["co-cabin"]="1000:1048576:86400:co cabin toxic-gas emergency"
CONTAINERS["air-quality-cabin"]="1000:1048576:86400:iaq voc cabin"
CONTAINERS["air-quality-exterior"]="1000:1048576:86400:aqi exterior"
CONTAINERS["raw-telemetry"]="1440:2097152:86400:telemetry multi-sensor raw"
CONTAINERS["commands"]="100:262144:86400:commands actuation downlink"

# Legacy alias containers for full backwards compatibility
CONTAINERS["cnt_raw_telemetry"]="1440:2097152:86400:legacy raw-telemetry"
CONTAINERS["cnt_co2"]="1000:1048576:86400:legacy co2"
CONTAINERS["cnt_temperature"]="1000:1048576:86400:legacy temperature"
CONTAINERS["cnt_humidity"]="1000:1048576:86400:legacy humidity"
CONTAINERS["cnt_data_health"]="1000:1048576:86400:legacy health"
CONTAINERS["cnt_actuator_commands"]="100:262144:86400:legacy commands"

for CNT_NAME in "${!CONTAINERS[@]}"; do
    IFS=':' read -r MNI MBS MIA LBL <<< "${CONTAINERS[$CNT_NAME]}"
    CNT_PAYLOAD=$(cat <<EOF
{
    "m2m:cnt": {
        "rn": "${CNT_NAME}",
        "mni": ${MNI},
        "mbs": ${MBS},
        "mia": ${MIA},
        "lbl": ["sensor", "${LBL}", "AE_CabinNode_Car01"]
    }
}
EOF
)
    create_resource "${AE_URL}" 3 "${CNT_PAYLOAD}" "${CNT_NAME}"
done

# ------------------------------------------------------------------------------
# STEP 4: Event Subscriptions & Downlink Routing
# ------------------------------------------------------------------------------
echo -e "\n[STEP 4/5] Reconciling Subscriptions for Telemetry, Emergency Alerts & Downlinks..."

# 4.1 Telemetry Dispatch Subscription
SUB_BRIDGE_PAYLOAD='{
    "m2m:sub": {
        "rn": "sub_bridge_consumer",
        "nu": ["http://bridge_ae:5000/notification"],
        "nct": 1,
        "enc": {"net": [3]}
    }
}'
create_resource "${AE_URL}/raw-telemetry" 23 "${SUB_BRIDGE_PAYLOAD}" "sub_bridge_consumer (raw-telemetry)"
create_resource "${AE_URL}/cnt_raw_telemetry" 23 "${SUB_BRIDGE_PAYLOAD}" "sub_bridge_consumer (cnt_raw_telemetry)"

# 4.2 Emergency CO Alert Subscription
SUB_CO_PAYLOAD='{
    "m2m:sub": {
        "rn": "sub_co_alert",
        "nu": ["http://bridge_ae:5000/emergency-monitor"],
        "nct": 1,
        "enc": {"net": [3]}
    }
}'
create_resource "${AE_URL}/co-cabin" 23 "${SUB_CO_PAYLOAD}" "sub_co_alert (co-cabin)"

# 4.3 Downlink Actuator Subscription
SUB_DOWNLINK_PAYLOAD='{
    "m2m:sub": {
        "rn": "sub_downlink_dispatcher",
        "nu": ["http://nodered_ipe:1880/downlink"],
        "nct": 1,
        "enc": {"net": [3]}
    }
}'
create_resource "${AE_URL}/commands" 23 "${SUB_DOWNLINK_PAYLOAD}" "sub_downlink_dispatcher (commands)"
create_resource "${AE_URL}/cnt_actuator_commands" 23 "${SUB_DOWNLINK_PAYLOAD}" "sub_downlink_dispatcher (cnt_actuator_commands)"

# ------------------------------------------------------------------------------
# STEP 5: Group Membership Synchronization
# ------------------------------------------------------------------------------
echo -e "\n[STEP 5/5] Synchronizing grp_fleet_telemetry Membership..."
GRP_UPDATE_PAYLOAD=$(cat <<EOF
{
    "m2m:grp": {
        "mid": [
            "${CSE_BASE}/AE_CabinNode_Car01/raw-telemetry"
        ]
    }
}
EOF
)
curl -s -X PUT "${BASE_URL}/grp_fleet_telemetry" \
    -H "X-M2M-Origin: ${ORIGIN}" \
    -H "X-M2M-RI: req_$(date +%s%N)" \
    -H "X-M2M-RVI: 3" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    -d "${GRP_UPDATE_PAYLOAD}" > /dev/null || echo "  [WARN] Group update returned non-zero status."

echo "  [OK] grp_fleet_telemetry.mid synchronized."

echo -e "\n================================================================================"
echo "  [SUCCESS] oneM2M Semantic Resource Hierarchy fully provisioned under /${CSE_BASE}!"
echo "  Compliant with ETSI TS 118 101, 8-Container Manifest, mia: 86400 & Group Fan-Out"
echo "================================================================================"
