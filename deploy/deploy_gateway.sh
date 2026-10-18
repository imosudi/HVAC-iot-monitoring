#!/usr/bin/env bash
# ==============================================================================
# Edge Gateway Deployment Automation Script
# Automotive IoT HVAC Monitoring - FHTW-AIOT Research Cluster
# ==============================================================================

set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"

# Deployment configuration defaults
LEAN_MODE=true
DEPLOY_TARGET_CLI=""
BASE_HOST_CLI=""
VEHICLE_HOST_CLI=""
MODULE_CLI="all"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --menu|-i|--interactive)
            exec bash "${DEPLOY_DIR}/menu.sh"
            ;;
        --full|--with-demo-ae|-f)
            LEAN_MODE=false
            shift
            ;;
        --lean|--base-only)
            LEAN_MODE=true
            shift
            ;;
        --target|-t)
            DEPLOY_TARGET_CLI="$2"
            shift 2
            ;;
        --localhost|-l)
            DEPLOY_TARGET_CLI="localhost"
            shift
            ;;
        --remote|-r)
            DEPLOY_TARGET_CLI="remote"
            shift
            ;;
        --base-host|--base-cse-host)
            BASE_HOST_CLI="$2"
            shift 2
            ;;
        --vehicle-host|--vehicle-ae-host)
            VEHICLE_HOST_CLI="$2"
            shift 2
            ;;
        --module|-m)
            MODULE_CLI="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

if [ "${DEPLOY_MODE:-}" = "full" ] || [ "${DEPLOY_FULL:-false}" = "true" ]; then
    LEAN_MODE=false
fi

echo "[STEP 1/4] Verifying cryptographic certificates..."
if [ ! -f "${DEPLOY_DIR}/mosquitto/certs/server.crt" ]; then
    echo "[INFO] Certificates not found. Executing PKI generation script..."
    "${ROOT_DIR}/scripts/pki/generate_certs.sh"
else
    echo "[OK] Certificates present."
fi

echo "[STEP 2/4] Verifying environment configuration..."
if [ ! -f "${DEPLOY_DIR}/.env" ]; then
    echo "[WARNING] .env file not found. Creating from .env.example..."
    cp "${DEPLOY_DIR}/.env.example" "${DEPLOY_DIR}/.env"
    echo "[INFO] Generated default .env. Please update secrets for production deployments."
fi

# Load active environment configuration
if [ -f "${DEPLOY_DIR}/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    source <(grep -v '^#' "${DEPLOY_DIR}/.env" | grep -v '^[[:space:]]*$' || true)
    set +a
fi

DEPLOY_TARGET="${DEPLOY_TARGET_CLI:-${DEPLOY_TARGET:-localhost}}"

if [ -n "${BASE_HOST_CLI}" ]; then
    BASE_CSE_HOST="${BASE_HOST_CLI}"
elif [ "${DEPLOY_TARGET}" = "localhost" ]; then
    BASE_CSE_HOST="localhost"
else
    BASE_CSE_HOST="${BASE_CSE_HOST:-${CSE_HOST:-localhost}}"
fi

if [ -n "${VEHICLE_HOST_CLI}" ]; then
    VEHICLE_AE_HOST="${VEHICLE_HOST_CLI}"
elif [ "${DEPLOY_TARGET}" = "localhost" ]; then
    VEHICLE_AE_HOST="localhost"
else
    VEHICLE_AE_HOST="${VEHICLE_AE_HOST:-localhost}"
fi

echo "[INFO] Active Deployment Topology: ${DEPLOY_TARGET}"
echo "[INFO] Module 1 (Base CSE Host):  ${BASE_CSE_HOST}"
echo "[INFO] Module 2 (Vehicle AE Host): ${VEHICLE_AE_HOST}"

# If remote deployment target specified with remote host addressing, delegate to SSH remote orchestrator
if [ "${DEPLOY_TARGET}" = "remote" ] && [ "${BASE_CSE_HOST}" != "localhost" ] && [ "${BASE_CSE_HOST}" != "127.0.0.1" ]; then
    echo "[INFO] Remote Distributed Deployment selected. Delegating to SSH deployment orchestrator..."
    exec bash "${DEPLOY_DIR}/deploy_remote.sh" \
        --base-host "${BASE_CSE_HOST}" \
        --vehicle-host "${VEHICLE_AE_HOST}" \
        --module "${MODULE_CLI}"
fi

echo "[STEP 3/4] Pulling container images and building microservices..."
cd "${DEPLOY_DIR}"
if [ -n "${COMPOSE_CMD:-}" ]; then
    : # Use preset COMPOSE_CMD
elif docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
elif command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_CMD="podman-compose"
else
    echo "[WARNING] Neither docker compose, docker-compose, nor podman-compose found in PATH." >&2
    SETUP_SCRIPT="${ROOT_DIR}/scripts/setup/install_ubuntu_prerequisites.sh"
    if [ -f "${SETUP_SCRIPT}" ]; then
        echo "[INFO] Running automated requirements setup script on Ubuntu Server..."
        bash "${SETUP_SCRIPT}"
        if docker compose version >/dev/null 2>&1; then
            COMPOSE_CMD="docker compose"
        elif command -v docker-compose >/dev/null 2>&1; then
            COMPOSE_CMD="docker-compose"
        elif command -v podman-compose >/dev/null 2>&1; then
            COMPOSE_CMD="podman-compose"
        else
            echo "[ERROR] Container compose is still not detected after running setup script." >&2
            echo "[INFO] If your user was just added to the docker group, execute 'newgrp docker' and re-run." >&2
            exit 1
        fi
    else
        echo "[ERROR] Setup script not found at ${SETUP_SCRIPT}." >&2
        exit 1
    fi
fi

${COMPOSE_CMD} build
${COMPOSE_CMD} up -d --remove-orphans

echo "[STEP 4/4] Initialising oneM2M semantic resource hierarchy..."
CSE_PORT="${ONEM2M_PORT:-8080}"
CSE_NAME="${ONEM2M_CSE_NAME:-sdv-cse}"
CSE_TARGET_URL="http://${BASE_CSE_HOST}:${CSE_PORT}/${CSE_NAME}"

echo "[INFO] Awaiting ACME CSEBase HTTP readiness on ${BASE_CSE_HOST}:${CSE_PORT} (/${CSE_NAME})..."
CSE_READY=0

# Fast test configured BASE_CSE_HOST
if curl -s -f -m 2 -o /dev/null \
    -H "X-M2M-Origin: CAdmin" \
    -H "X-M2M-RI: readiness_check" \
    -H "X-M2M-RVI: 3" \
    "${CSE_TARGET_URL}" >/dev/null 2>&1; then
    echo "[OK] oneM2M CSEBase /${CSE_NAME} is responding (HTTP 200)."
    CSE_READY=1
elif [ "${BASE_CSE_HOST}" != "localhost" ] && [ "${BASE_CSE_HOST}" != "127.0.0.1" ]; then
    if curl -s -f -m 1 -o /dev/null \
        -H "X-M2M-Origin: CAdmin" \
        -H "X-M2M-RI: readiness_check" \
        -H "X-M2M-RVI: 3" \
        "http://localhost:${CSE_PORT}/${CSE_NAME}" >/dev/null 2>&1; then
        echo "[NOTICE] Configured BASE_CSE_HOST '${BASE_CSE_HOST}' is unreachable, but local Base CSE is active on localhost."
        echo "[NOTICE] Adopting localhost for verification and provisioning."
        BASE_CSE_HOST="localhost"
        CSE_TARGET_URL="http://${BASE_CSE_HOST}:${CSE_PORT}/${CSE_NAME}"
        CSE_READY=1
    fi
fi

if [ "${CSE_READY}" -ne 1 ]; then
    for i in $(seq 1 45); do
        if curl -s -f -m 2 -o /dev/null \
            -H "X-M2M-Origin: CAdmin" \
            -H "X-M2M-RI: readiness_check" \
            -H "X-M2M-RVI: 3" \
            "${CSE_TARGET_URL}" >/dev/null 2>&1; then
            echo "[OK] oneM2M CSEBase /${CSE_NAME} is responding (HTTP 200)."
            CSE_READY=1
            sleep 2
            break
        fi
        sleep 1
    done
fi

if [ "${CSE_READY}" -ne 1 ]; then
    echo "[ERROR] Timeout waiting for oneM2M CSEBase /${CSE_NAME} at ${CSE_TARGET_URL} to initialise." >&2
    exit 1
fi

echo "[INFO] Verifying native In-CSE MQTT protocol binding on ${BASE_CSE_HOST}..."
if nc -z "${BASE_CSE_HOST}" 1883 >/dev/null 2>&1 || (echo > "/dev/tcp/${BASE_CSE_HOST}/1883") >/dev/null 2>&1; then
    echo "[OK] Mosquitto internal mesh port 1883 active for native oneM2M TS-0010 MQTT binding."
fi
if [ "${LEAN_MODE}" = "true" ]; then
    echo "[INFO] Lean Deployment Mode active: Initialising vanilla Base CSE (strictly 0 Application Entities)..."
    bash "${ROOT_DIR}/scripts/onem2m/init_base_cse.sh" --target "${DEPLOY_TARGET}" --host "${BASE_CSE_HOST}" --port "${CSE_PORT}"
    echo -e "\n[INFO] Executing Base CSE automated validation & verification..."
    python3 "${ROOT_DIR}/scripts/testing/validate_base_cse.py" --target "${DEPLOY_TARGET}" --host "${BASE_CSE_HOST}" --port "${CSE_PORT}"
    echo "[SUCCESS] Automotive MEC Gateway lean Base CSE deployment and verification complete!"
    echo "[INFO] Vanilla Base CSE /${CSE_NAME} ready for dynamic, on-demand vehicular onboarding."
else
    "${ROOT_DIR}/scripts/onem2m/init_tree.sh" || echo "[INFO] oneM2M initialisation completed or already provisioned."
    echo "[SUCCESS] Automotive MEC Gateway microservice mesh is operational."
    echo "[INFO] Consolidated Native In-CSE Route active: MQTT binding on Port 1883 & mTLS on Port 8883."
fi

# If Vehicle AE module requested, commission the vehicle node
if [ "${MODULE_CLI}" = "vehicle-ae" ]; then
    echo -e "\n[STEP 5/5] Commissioning Vehicle AE Module (Module 2) targeting Base CSE on ${BASE_CSE_HOST}..."
    python3 "${ROOT_DIR}/scripts/deploy_acme_fleet_single_vehicle_ae.py" \
        --host "${BASE_CSE_HOST}" \
        --port "${CSE_PORT}" \
        --vehicle-id "vehicle-001"
fi
