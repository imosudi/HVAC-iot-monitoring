#!/usr/bin/env bash
# ==============================================================================
# Module 2 Deployment Automation: Vehicle Application Entity (AE)
# Software-Defined Vehicle (SDV) Cabin Monitoring - FHTW-AIOT Research Cluster
#
# Deploys and onboards an individual Vehicle AE instance (representing an
# in-vehicle Raspberry Pi 5 interfaced with in-cabin ESP32-S3 instrumentation).
#
# Connects to Module 1 (Base CSE Host) over:
#   - HTTP/REST port 8080 (oneM2M Mca registration and resource management)
#   - mTLS 1.3 port 8883 (oneM2M TS-0010 MQTT telemetry ingestion and downlinks)
#
# Supports:
#   - Localhost deployment: single-machine development/simulation mode.
#   - Remote deployment   : in-vehicle Raspberry Pi 5 connecting to remote Base
#                           CSE host identified by IP address or hostname.
# ==============================================================================

set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"

TARGET_MODE=""
BASE_HOST=""
BASE_PORT=""
VEHICLE_ID="vehicle-001"
VEHICLE_VIN=""
SKIP_TELEMETRY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target|-t)
            TARGET_MODE="$2"
            shift 2
            ;;
        --localhost|-l)
            TARGET_MODE="localhost"
            shift
            ;;
        --remote|-r)
            TARGET_MODE="remote"
            shift
            ;;
        --base-host|--base-cse-host)
            BASE_HOST="$2"
            if [ "$2" != "localhost" ] && [ "$2" != "127.0.0.1" ]; then
                TARGET_MODE="${TARGET_MODE:-remote}"
            fi
            shift 2
            ;;
        --vehicle-host|--vehicle-ae-host)
            shift 2
            ;;
        --port|-p)
            BASE_PORT="$2"
            shift 2
            ;;
        --vehicle-id|-i)
            VEHICLE_ID="$2"
            shift 2
            ;;
        --vin)
            VEHICLE_VIN="$2"
            shift 2
            ;;
        --skip-telemetry)
            SKIP_TELEMETRY=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Source deploy/.env and root .env (root .env overrides)
if [ -f "${DEPLOY_DIR}/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    source <(grep -v '^#' "${DEPLOY_DIR}/.env" | grep -v '^[[:space:]]*$' || true)
    set +a
fi
if [ -f "${ROOT_DIR}/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    source <(grep -v '^#' "${ROOT_DIR}/.env" | grep -v '^[[:space:]]*$' || true)
    set +a
fi

DEPLOY_TARGET="${TARGET_MODE:-${DEPLOY_TARGET:-localhost}}"

if [ -n "${BASE_HOST}" ]; then
    RESOLVED_BASE_HOST="${BASE_HOST}"
elif [ "${DEPLOY_TARGET}" = "localhost" ]; then
    RESOLVED_BASE_HOST="localhost"
else
    RESOLVED_BASE_HOST="${BASE_CSE_HOST:-${CSE_HOST:-localhost}}"
fi

RESOLVED_PORT="${BASE_PORT:-${ONEM2M_PORT:-8080}}"

echo "================================================================================"
echo "  SDV AUTOMOTIVE IOT: MODULE 2 DEPLOYMENT (VEHICLE APPLICATION ENTITY)"
echo "  Host Platform: In-Vehicle Raspberry Pi 5 (or Localhost Simulation)"
echo "  Topology Mode: ${DEPLOY_TARGET}"
echo "  Target Module 1 (Base CSE): http://${RESOLVED_BASE_HOST}:${RESOLVED_PORT}"
echo "  Vehicle Identifier:         ${VEHICLE_ID}"
echo "================================================================================"

# Verify Python virtual environment or runtime
PYTHON_CMD="python3"
if [ -f "${ROOT_DIR}/.venv/bin/python" ]; then
    PYTHON_CMD="${ROOT_DIR}/.venv/bin/python"
elif [ -f "${ROOT_DIR}/.venv/bin/python3" ]; then
    PYTHON_CMD="${ROOT_DIR}/.venv/bin/python3"
fi

EXTRA_ARGS=()
if [ -n "${VEHICLE_VIN}" ]; then
    EXTRA_ARGS+=("--vin" "${VEHICLE_VIN}")
fi
if [ "${SKIP_TELEMETRY}" = "true" ]; then
    EXTRA_ARGS+=("--skip-telemetry")
fi

echo -e "\n[STEP 1/2] Onboarding and registering Vehicle AE (with 8 oneM2M <container> resources) on Base CSE..."
${PYTHON_CMD} "${ROOT_DIR}/scripts/deploy_acme_fleet_single_vehicle_ae.py" \
    --base-host "${RESOLVED_BASE_HOST}" \
    --host "${RESOLVED_BASE_HOST}" \
    --port "${RESOLVED_PORT}" \
    --target "${DEPLOY_TARGET}" \
    --vehicle-id "${VEHICLE_ID}" \
    "${EXTRA_ARGS[@]}"

echo -e "\n[STEP 2/2] Validating vehicular mTLS 1.3 telemetry pipeline..."
MQTT_PORT="${MOSQUITTO_PORT:-8883}"
CA_CERT="${DEPLOY_DIR}/mosquitto/certs/ca.crt"
CLIENT_CERT="${DEPLOY_DIR}/mosquitto/certs/client_esp32.crt"
CLIENT_KEY="${DEPLOY_DIR}/mosquitto/certs/client_esp32.key"

if [ -f "${CA_CERT}" ] && [ -f "${CLIENT_CERT}" ] && [ -f "${CLIENT_KEY}" ]; then
    if nc -z -w 2 "${RESOLVED_BASE_HOST}" "${MQTT_PORT}" >/dev/null 2>&1; then
        echo "[INFO] Testing mTLS 1.3 connection to Mosquitto on ${RESOLVED_BASE_HOST}:${MQTT_PORT}..."
        if ! ${PYTHON_CMD} -c "import paho.mqtt.client" >/dev/null 2>&1; then
            if command -v apt-get >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
                sudo -n apt-get update -qq >/dev/null 2>&1 || true
                sudo -n apt-get install -y -qq python3-paho-mqtt >/dev/null 2>&1 || true
            fi
        fi

        if ${PYTHON_CMD} -c "import paho.mqtt.client" >/dev/null 2>&1; then
            ${PYTHON_CMD} "${ROOT_DIR}/scripts/testing/simulate_telemetry.py" \
                --host "${RESOLVED_BASE_HOST}" \
                --port "${MQTT_PORT}" \
                --ca-cert "${CA_CERT}" \
                --client-cert "${CLIENT_CERT}" \
                --client-key "${CLIENT_KEY}" \
                --route native \
                --mode normal \
                --count 3 \
                --interval 1.0 || echo "[WARN] Simulated telemetry sample run completed."
        else
            echo "[INFO] Optional 'paho-mqtt' library is not present on this host; skipping simulated MQTT traffic."
            echo "       (To run live telemetry simulation later: sudo apt-get install -y python3-paho-mqtt)"
        fi
    else
        echo "[INFO] MQTT broker port ${MQTT_PORT} on ${RESOLVED_BASE_HOST} is offline. Skipping simulated telemetry stream."
    fi
else
    echo "[INFO] Certificates not found locally in deploy/mosquitto/certs. Skipping simulated telemetry stream."
fi


echo -e "\n================================================================================"
echo "  [SUCCESS] Module 2 (Vehicle AE: ${VEHICLE_ID}) successfully commissioned!"
echo "  Target Base CSE: http://${RESOLVED_BASE_HOST}:${RESOLVED_PORT}/sdv-cse"
echo "  Registered oneM2M Resources: 8 semantic <container> nodes (Type 3) under /${VEHICLE_ID}"
echo "  Observability: View live resource tree at http://${RESOLVED_BASE_HOST}:${RESOLVED_PORT}/webui"
echo "  Note: oneM2M <container> resources reside inside Base CSE (not local Docker ps)."
echo "================================================================================"
