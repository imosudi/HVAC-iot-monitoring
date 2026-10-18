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
elif [ -d "${HOME}/onem2m/venv" ] || [ -f "/home/mosud/onem2m/venv/bin/python3" ]; then
    echo "[INFO] Container runtime not installed on host, but native ACME oneM2M CSE detected."
    VENV_PYTHON="${HOME}/onem2m/venv/bin/python3"
    if [ ! -f "${VENV_PYTHON}" ]; then
        VENV_PYTHON="/home/mosud/onem2m/venv/bin/python3"
    fi

    # Enable lingering so user services persist across SSH logouts
    loginctl enable-linger "${USER}" 2>/dev/null || true

    # Configure acme.ini: Ensure HTTP is enabled and adjust MQTT
    if nc -z 127.0.0.1 1883 >/dev/null 2>&1; then
        sed -i 's/address = mosquitto/address = 127.0.0.1/' "${DEPLOY_DIR}/onem2m/acme.ini"
    else
        sed -i '/\[mqtt\]/,/\[/ s/enable = true/enable = false/' "${DEPLOY_DIR}/onem2m/acme.ini"
    fi
    sed -i '/\[http\]/,/\[/ s/enable = false/enable = true/' "${DEPLOY_DIR}/onem2m/acme.ini"

    # Install and configure systemd user service
    mkdir -p "${HOME}/.config/systemd/user"
    cat << EOF > "${HOME}/.config/systemd/user/sdv-acme-cse.service"
[Unit]
Description=SDV oneM2M ACME Base CSE Service
After=network.target

[Service]
Type=simple
WorkingDirectory=${DEPLOY_DIR}/onem2m
ExecStart=${VENV_PYTHON} -m acmecse --config acme.ini --headless
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

    echo "[INFO] Starting native ACME IN-CSE via systemd user service..."
    systemctl --user daemon-reload
    systemctl --user enable sdv-acme-cse.service >/dev/null 2>&1 || true
    systemctl --user restart sdv-acme-cse.service

    # Await CSEBase HTTP readiness
    echo "[INFO] Awaiting ACME CSEBase readiness on localhost:${RESOLVED_PORT} (/sdv-cse)..."
    CSE_UP=0
    for i in $(seq 1 20); do
        if curl -s -f -m 2 \
            -H "X-M2M-Origin: CAdmin" \
            -H "X-M2M-RI: readiness_check" \
            -H "X-M2M-RVI: 3" \
            "http://localhost:${RESOLVED_PORT}/sdv-cse" >/dev/null 2>&1; then
            echo "[OK] oneM2M CSEBase /sdv-cse is responding (HTTP 200)."
            CSE_UP=1
            break
        fi
        sleep 1
    done

    if [ "${CSE_UP}" -ne 1 ]; then
        echo "[ERROR] Timeout waiting for native ACME CSE to initialise. Check systemd logs:" >&2
        journalctl --user -u sdv-acme-cse.service -n 25 --no-pager >&2 || true
        exit 1
    fi

    bash "${ROOT_DIR}/scripts/onem2m/init_base_cse.sh" --localhost --port "${RESOLVED_PORT}"
else
    echo "[ERROR] Neither container runtime (Docker/Podman) nor native ACME CSE (~/onem2m) found on host." >&2
    exit 1
fi

echo -e "\n[SUCCESS] Module 1 (Base CSE Infrastructure) deployment is operational."
echo "[INFO] Ready to accept dynamic registration from Module 2 (Vehicle AE instances)."
