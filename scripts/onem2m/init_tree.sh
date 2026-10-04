#!/usr/bin/env bash
# ==============================================================================
# oneM2M Resource Tree Initialisation Script
# Automates the creation of AE, Containers, and Subscriptions in /sdv-cse
# Conforms to ETSI TS 118 101 Functional Architecture
# ==============================================================================

set -euo pipefail

CSE_HOST="${CSE_HOST:-localhost}"
CSE_PORT="${CSE_PORT:-8080}"
CSE_BASE="${CSE_BASE:-sdv-cse}"
ORIGIN="${ORIGIN:-CAdmin}"
BASE_URL="http://${CSE_HOST}:${CSE_PORT}/${CSE_BASE}"

echo "[INFO] Connecting to oneM2M CSE at ${BASE_URL}..."

# Helper function to issue oneM2M POST request
create_resource() {
    local target_url="$1"
    local resource_type="$2"
    local payload="$3"
    local name="$4"

    echo "[INFO] Creating ${name} (type ${resource_type}) at ${target_url}..."
    curl -s -X POST "${target_url}" \
        -H "X-M2M-Origin: ${ORIGIN}" \
        -H "X-M2M-RI: req_$(date +%s%N)" \
        -H "Content-Type: application/json;ty=${resource_type}" \
        -H "Accept: application/json" \
        -d "${payload}" > /dev/null || echo "[WARN] ${name} may already exist."
}

# 1. Create Application Entity (AE)
AE_PAYLOAD='{
    "m2m:ae": {
        "rn": "AE_CabinNode_Car01",
        "api": "N.org.fhtw.sdv.cabin",
        "rr": true,
        "srv": ["2a"]
    }
}'
create_resource "${BASE_URL}" 2 "${AE_PAYLOAD}" "AE_CabinNode_Car01"

AE_URL="${BASE_URL}/AE_CabinNode_Car01"

# 2. Create Containers
for CNT in "cnt_raw_telemetry" "cnt_co2" "cnt_temperature" "cnt_humidity" "cnt_data_health" "cnt_actuator_commands"; do
    CNT_PAYLOAD=$(cat <<EOF
{
    "m2m:cnt": {
        "rn": "${CNT}",
        "mni": 1000
    }
}
EOF
)
    create_resource "${AE_URL}" 3 "${CNT_PAYLOAD}" "${CNT}"
done

# 3. Create Subscription for Bridge AE on cnt_raw_telemetry
SUB_BRIDGE_PAYLOAD='{
    "m2m:sub": {
        "rn": "sub_bridge_consumer",
        "nu": ["http://bridge_ae:5000/notification"],
        "nct": 1,
        "enc": {
            "net": [3]
        }
    }
}'
create_resource "${AE_URL}/cnt_raw_telemetry" 23 "${SUB_BRIDGE_PAYLOAD}" "sub_bridge_consumer"

# 4. Create Subscription for Downlink Dispatcher on cnt_actuator_commands
SUB_DOWNLINK_PAYLOAD='{
    "m2m:sub": {
        "rn": "sub_downlink_dispatcher",
        "nu": ["http://nodered_ipe:1880/downlink"],
        "nct": 1,
        "enc": {
            "net": [3]
        }
    }
}'
create_resource "${AE_URL}/cnt_actuator_commands" 23 "${SUB_DOWNLINK_PAYLOAD}" "sub_downlink_dispatcher"

echo "[SUCCESS] oneM2M semantic resource hierarchy initialised successfully under /${CSE_BASE}."
