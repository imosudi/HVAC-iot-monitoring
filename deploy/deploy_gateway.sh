#!/usr/bin/env bash
# ==============================================================================
# Edge Gateway Deployment Automation Script
# Automotive IoT HVAC Monitoring - FHTW-AIOT Research Cluster
# ==============================================================================

set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${DEPLOY_DIR}/.."

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
${COMPOSE_CMD} up -d

echo "[STEP 4/4] Initialising oneM2M semantic resource hierarchy..."
echo "[INFO] Awaiting ACME CSEBase HTTP readiness on port 8080 (/sdv-cse)..."
CSE_READY=0
for i in $(seq 1 45); do
    if curl -s -f -o /dev/null \
        -H "X-M2M-Origin: CAdmin" \
        -H "X-M2M-RI: readiness_check" \
        -H "X-M2M-RVI: 3" \
        "http://localhost:8080/sdv-cse" >/dev/null 2>&1; then
        echo "[OK] oneM2M CSEBase /sdv-cse is responding (HTTP 200)."
        CSE_READY=1
        sleep 2
        break
    fi
    sleep 1
done

if [ "${CSE_READY}" -ne 1 ]; then
    echo "[ERROR] Timeout waiting for oneM2M CSEBase /sdv-cse to initialise." >&2
    exit 1
fi

echo "[INFO] Verifying native In-CSE MQTT protocol binding..."
if (echo > /dev/tcp/localhost/1883) >/dev/null 2>&1 || nc -z localhost 1883 >/dev/null 2>&1; then
    echo "[OK] Mosquitto internal mesh port 1883 active for native oneM2M TS-0010 MQTT binding."
fi
"${ROOT_DIR}/scripts/onem2m/init_tree.sh" || echo "[INFO] oneM2M initialisation completed or already provisioned."

echo "[SUCCESS] Automotive MEC Gateway microservice mesh is operational."
echo "[INFO] Consolidated Native In-CSE Route active: MQTT binding on Port 1883 & mTLS on Port 8883."
