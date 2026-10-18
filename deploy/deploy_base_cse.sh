#!/usr/bin/env bash
# ==============================================================================
# Module 1 Deployment Automation: Base CSE Infrastructure
# Software-Defined Vehicle (SDV) Cabin Monitoring - FHTW-AIOT Research Cluster
#
# Deploys the singleton Base CSE Infrastructure (ACME oneM2M IN-CSE,
# Mosquitto MQTT Broker with mTLS 1.3, InfluxDB 2.x, Grafana, Bridge AE,
# and Web Portal).
#
# Supports:
#   - Localhost deployment: single-machine development/test environment.
#   - Remote deployment   : dedicated central Server or Virtual Machine identified
#                           by hostname (e.g. base-cse.sdv.cluster.local) or IP.
# ==============================================================================

set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${DEPLOY_DIR}/.."

TARGET_MODE=""
BASE_HOST=""
BASE_PORT=""

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
        --host|-h|--base-host)
            BASE_HOST="$2"
            shift 2
            ;;
        --port|-p)
            BASE_PORT="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# Source deploy/.env if present
if [ -f "${DEPLOY_DIR}/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    source <(grep -v '^#' "${DEPLOY_DIR}/.env" | grep -v '^[[:space:]]*$' || true)
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
echo "  SDV AUTOMOTIVE IOT: MODULE 1 DEPLOYMENT (BASE CSE INFRASTRUCTURE)"
echo "  Architecture: Singleton Central Platform (Server / Virtual Machine)"
echo "  Topology Mode: ${DEPLOY_TARGET}"
echo "  Base CSE Host: ${RESOLVED_BASE_HOST}:${RESOLVED_PORT}"
echo "================================================================================"

# Execute deployment: Containerised mesh if docker available, or native Python ACME CSE
if docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1 || command -v podman-compose >/dev/null 2>&1; then
    bash "${DEPLOY_DIR}/deploy_gateway.sh" \
        --lean \
        --localhost \
        --base-host "${RESOLVED_BASE_HOST}"
elif [ -d "${HOME}/onem2m/venv" ] && [ -f "${HOME}/onem2m/acme.ini" ]; then
    echo "[INFO] Container runtime not installed on host, but native ACME oneM2M CSE detected in ~/onem2m."
    echo "[INFO] Launching native Python ACME IN-CSE daemon..."
    # shellcheck disable=SC1091
    source "${HOME}/onem2m/venv/bin/activate"
    nohup python3 -m acmecse --config "${HOME}/onem2m/acme.ini" > "${HOME}/onem2m/acme.log" 2>&1 &
    sleep 3
    bash "${ROOT_DIR}/scripts/onem2m/init_base_cse.sh" --localhost --port "${RESOLVED_PORT}"
else
    echo "[ERROR] Neither container runtime (Docker/Podman) nor native ACME CSE (~/onem2m) found on host." >&2
    exit 1
fi

echo -e "\n[SUCCESS] Module 1 (Base CSE Infrastructure) deployment is operational."
echo "[INFO] Ready to accept dynamic registration from Module 2 (Vehicle AE instances)."
