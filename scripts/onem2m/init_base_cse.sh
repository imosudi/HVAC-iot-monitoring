#!/usr/bin/env bash
# ==============================================================================
# Lean oneM2M Base CSE Initialisation Script
# Software-Defined Vehicle (SDV) Cabin Monitoring - FHTW-AIOT Research Cluster
#
# Provisions a lean, vanilla oneM2M IN-CSEBase with environment variables.
# Strictly excludes Application Entities (e.g. AE_CabinNode_Car01), preparing
# the CSE for dynamic, on-demand vehicular AE commissioning via the Web Portal
# or Insomnia Collection 2 (Single Vehicle Deploy & Validation).
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}/../.."
ENV_FILE="${ROOT_DIR}/deploy/.env"

# Source environment variables if .env exists
if [ -f "${ENV_FILE}" ]; then
    # Export non-comment lines
    set -a
    # shellcheck disable=SC1090
    source <(grep -v '^#' "${ENV_FILE}" | grep -v '^[[:space:]]*$' || true)
    set +a
fi

CSE_HOST="${CSE_HOST:-localhost}"
CSE_PORT="${ONEM2M_PORT:-${CSE_PORT:-8080}}"
CSE_BASE="${ONEM2M_CSE_NAME:-${CSE_BASE:-sdv-cse}}"
ORIGIN="${ONEM2M_ADMIN_ORIGIN:-${ORIGIN:-CAdmin}}"
RVI="${ONEM2M_RVI:-${RVI:-3}}"
BASE_URL="http://${CSE_HOST}:${CSE_PORT}/${CSE_BASE}"

echo "================================================================================"
echo "  SDV VEHICULAR EDGE GATEWAY: LEAN oneM2M BASE CSE PROVISIONER"
echo "  Mode: Vanilla Base CSE (Strictly Zero Application Entities)"
echo "  Target: ${BASE_URL} | Admin Originator: ${ORIGIN} | RVI: ${RVI}"
echo "================================================================================"

# Helper function to issue oneM2M POST request with idempotency handling
create_resource() {
    local target_url="$1"
    local resource_type="$2"
    local payload="$3"
    local name="$4"
    local origin="${5:-$ORIGIN}"

    local http_code
    local body
    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "${target_url}" \
        -H "X-M2M-Origin: ${origin}" \
        -H "X-M2M-RI: req_$(date +%s%N)" \
        -H "X-M2M-RVI: ${RVI}" \
        -H "Content-Type: application/json;ty=${resource_type}" \
        -H "Accept: application/json" \
        -d "${payload}") || response=$'\n000'

    http_code=$(echo "${response}" | tail -n 1)
    body=$(echo "${response}" | sed '$d')

    if [ "${http_code}" = "201" ]; then
        echo -e "  [CREATED]    ${name} (ty=${resource_type}) -> HTTP 201"
    elif [ "${http_code}" = "409" ]; then
        echo -e "  [IDEMPOTENT] ${name} already exists -> HTTP 409"
    else
        local dbg_msg
        dbg_msg=$(echo "${body}" | grep -o '"m2m:dbg"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 || echo "")
        if [ -n "${dbg_msg}" ]; then
            echo -e "  [WARN]       ${name} status HTTP ${http_code} (${dbg_msg})"
        else
            echo -e "  [WARN]       ${name} status HTTP ${http_code}"
        fi
    fi
}

# ------------------------------------------------------------------------------
# STEP 1: Verify CSEBase Connectivity
# ------------------------------------------------------------------------------
echo -e "\n[STEP 1/3] Verifying Base CSE reachability at ${BASE_URL}..."
CSE_READY=0
for i in $(seq 1 30); do
    if curl -s -f -o /dev/null \
        -H "X-M2M-Origin: ${ORIGIN}" \
        -H "X-M2M-RI: preflight_check" \
        -H "X-M2M-RVI: ${RVI}" \
        "${BASE_URL}" >/dev/null 2>&1; then
        echo "  [OK] oneM2M CSEBase /${CSE_BASE} is reachable and responding (HTTP 200)."
        CSE_READY=1
        break
    fi
    sleep 1
done

if [ "${CSE_READY}" -ne 1 ]; then
    echo "  [ERROR] CSEBase /${CSE_BASE} failed to respond within 30 seconds." >&2
    exit 1
fi

# ------------------------------------------------------------------------------
# STEP 2: Purge any Pre-Existing Application Entities (Guarantee Vanilla Base)
# ------------------------------------------------------------------------------
echo -e "\n[STEP 2/3] Auditing registered Application Entities (enforcing zero AEs)..."
EXISTING_AES=$(curl -s \
    -H "X-M2M-Origin: ${ORIGIN}" \
    -H "X-M2M-RI: audit_aes_$(date +%s)" \
    -H "X-M2M-RVI: ${RVI}" \
    -H "Accept: application/json" \
    "${BASE_URL}?fu=1&ty=2" || echo "{}")

AE_LIST=$(echo "${EXISTING_AES}" | grep -o '"[^"]*"' | grep -v 'm2m:uril' || true)

DELETED_COUNT=0
for ae_item in ${AE_LIST}; do
    ae_path=$(echo "${ae_item}" | tr -d '"')
    ae_rn=$(basename "${ae_path}")
    if [ "${ae_rn}" = "${ORIGIN}" ] || [ "${ae_rn}" = "CAdmin" ]; then
        continue
    fi
    echo "  [PURGING] Existing AE detected: ${ae_rn}. Cascading delete for vanilla deployment..."
    curl -s -X DELETE \
        -H "X-M2M-Origin: ${ORIGIN}" \
        -H "X-M2M-RI: del_${ae_rn}_$(date +%s)" \
        -H "X-M2M-RVI: ${RVI}" \
        "${BASE_URL}/${ae_rn}" >/dev/null 2>&1 || true
    echo "  [PURGED]  ${ae_rn} removed from CSEBase."
    DELETED_COUNT=$((DELETED_COUNT + 1))
done

if [ "${DELETED_COUNT}" -eq 0 ]; then
    echo "  [OK] Verified clean state: 0 Application Entities present."
fi

# ------------------------------------------------------------------------------
# STEP 3: Provision Baseline Fleet Governance (ACP & Aggregation Group)
# ------------------------------------------------------------------------------
echo -e "\n[STEP 3/3] Reconciling Baseline Fleet Governance under /${CSE_BASE}..."

ACP_PAYLOAD='{
    "m2m:acp": {
        "rn": "acp_fleet_manager",
        "pv": {
            "acr": [
                {"acor": ["'"${ORIGIN}"'"], "acop": 63},
                {"acor": ["C_vehicle_nodes", "all"], "acop": 63}
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

echo -e "\n================================================================================"
echo "  [SUCCESS] Vanilla oneM2M Base CSE Initialisation Complete!"
echo "  CSEBase:        /${CSE_BASE} (ty=5, csi=id-sdv)"
echo "  Governance:     acp_fleet_manager (ty=1), grp_fleet_telemetry (ty=9, 0 members)"
echo "  Application Entities: 0 (Vanilla Base CSE ready for on-demand AE onboarding)"
echo "================================================================================"
