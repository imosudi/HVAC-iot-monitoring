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
    echo "[ERROR] Neither docker compose, docker-compose, nor podman-compose found in PATH." >&2
    exit 1
fi

${COMPOSE_CMD} build
${COMPOSE_CMD} up -d

echo "[STEP 4/4] Initialising oneM2M semantic resource hierarchy..."
echo "[INFO] Awaiting ACME CSE HTTP readiness on port 8080..."
for i in $(seq 1 30); do
    if curl -s -f "http://localhost:8080" >/dev/null 2>&1; then
        echo "[OK] oneM2M CSE is responding."
        break
    fi
    sleep 1
done
"${ROOT_DIR}/scripts/onem2m/init_tree.sh" || echo "[INFO] oneM2M initialisation completed or already provisioned."

echo "[SUCCESS] Automotive MEC Gateway microservice mesh is operational."
