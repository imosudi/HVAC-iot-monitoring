#!/usr/bin/env bash
# ==============================================================================
# SDV Automotive IoT: Remote Distributed Modular Deployment Orchestrator
# Connects via SSH to deploy and commission:
#   Module 1 (Base CSE Host): Server/VM identified by BASE_CSE_HOST (e.g. 192.168.122.91)
#   Module 2 (Vehicle AE Host): Raspberry Pi 5 identified by VEHICLE_AE_HOST (e.g. 192.168.122.145)
# ==============================================================================

set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"

# Load local environment configuration (deploy/.env first, root .env overrides)
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

# CLI Option Defaults
BASE_HOST_CLI=""
BASE_USER_CLI=""
BASE_PORT_CLI=""
BASE_KEY_CLI=""

VEHICLE_HOST_CLI=""
VEHICLE_USER_CLI=""
VEHICLE_PORT_CLI=""
VEHICLE_KEY_CLI=""

MODULE_CLI="all"
VEHICLE_ID_CLI="vehicle-001"
SKIP_SYNC=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --base-host|--base-cse-host)
            BASE_HOST_CLI="$2"
            shift 2
            ;;
        --base-user)
            BASE_USER_CLI="$2"
            shift 2
            ;;
        --base-port)
            BASE_PORT_CLI="$2"
            shift 2
            ;;
        --base-key)
            BASE_KEY_CLI="$2"
            shift 2
            ;;
        --vehicle-host|--vehicle-ae-host)
            VEHICLE_HOST_CLI="$2"
            shift 2
            ;;
        --vehicle-user)
            VEHICLE_USER_CLI="$2"
            shift 2
            ;;
        --vehicle-port)
            VEHICLE_PORT_CLI="$2"
            shift 2
            ;;
        --vehicle-key)
            VEHICLE_KEY_CLI="$2"
            shift 2
            ;;
        --vehicle-id)
            VEHICLE_ID_CLI="$2"
            shift 2
            ;;
        --module|-m)
            MODULE_CLI="$2"
            shift 2
            ;;
        --skip-sync)
            SKIP_SYNC=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --base-host <ip/fqdn>     Remote Base CSE server hostname/IP (default: \$BASE_CSE_HOST or 192.168.122.91)"
            echo "  --base-user <user>        Remote SSH user for Base CSE (default: \$BASE_CSE_USER or \$USER)"
            echo "  --base-port <port>        Remote SSH port for Base CSE (default: \$BASE_CSE_SSH_PORT or 22)"
            echo "  --base-key <path>         SSH private key for Base CSE (default: \$BASE_CSE_SSH_KEY)"
            echo "  --vehicle-host <ip/fqdn>  Remote Vehicle AE host (default: \$VEHICLE_AE_HOST or 192.168.122.145)"
            echo "  --vehicle-user <user>     Remote SSH user for Vehicle AE (default: \$VEHICLE_AE_USER or \$USER)"
            echo "  --vehicle-port <port>     Remote SSH port for Vehicle AE (default: \$VEHICLE_AE_SSH_PORT or 22)"
            echo "  --vehicle-key <path>      SSH private key for Vehicle AE (default: \$VEHICLE_AE_SSH_KEY)"
            echo "  --vehicle-id <id>         Vehicle ID for AE onboarding (default: vehicle-001)"
            echo "  --module all|base-cse|vehicle-ae  Select module to deploy (default: all)"
            echo "  --skip-sync               Skip rsync of deployment assets before remote execution"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

# Resolve Base CSE Host & Login details
BASE_HOST="${BASE_HOST_CLI:-${BASE_CSE_HOST:-192.168.122.91}}"
BASE_USER="${BASE_USER_CLI:-${BASE_CSE_USER:-${USER}}}"
BASE_PORT="${BASE_PORT_CLI:-${BASE_CSE_SSH_PORT:-22}}"
BASE_KEY="${BASE_KEY_CLI:-${BASE_CSE_SSH_KEY:-}}"
BASE_DIR="${BASE_CSE_REMOTE_DIR:-~/HVAC-iot-monitoring}"

# Resolve Vehicle AE Host & Login details
VEHICLE_HOST="${VEHICLE_HOST_CLI:-${VEHICLE_AE_HOST:-192.168.122.145}}"
VEHICLE_USER="${VEHICLE_USER_CLI:-${VEHICLE_AE_USER:-${USER}}}"
VEHICLE_PORT="${VEHICLE_PORT_CLI:-${VEHICLE_AE_SSH_PORT:-22}}"
VEHICLE_KEY="${VEHICLE_KEY_CLI:-${VEHICLE_AE_SSH_KEY:-}}"
VEHICLE_DIR="${VEHICLE_AE_REMOTE_DIR:-~/HVAC-iot-monitoring}"

# Auto-detect default identity file if none provided and id_ed25519 exists
if [ -z "${BASE_KEY}" ] && [ -f "${HOME}/.ssh/id_ed25519" ]; then
    BASE_KEY="${HOME}/.ssh/id_ed25519"
fi
if [ -z "${VEHICLE_KEY}" ] && [ -f "${HOME}/.ssh/id_ed25519" ]; then
    VEHICLE_KEY="${HOME}/.ssh/id_ed25519"
fi

echo "================================================================================"
echo "  SDV AUTOMOTIVE IOT: DISTRIBUTED REMOTE MODULAR DEPLOYMENT ORCHESTRATOR"
echo "  Standard Conformance: ETSI TS 118 101 Rel 4 / oneM2M TS-0004 & TS-0010"
echo "  Active Module Selection: ${MODULE_CLI}"
echo "================================================================================"
echo "[INFO] Module 1 (Base CSE Host):  ${BASE_USER}@${BASE_HOST}:${BASE_PORT} (Target Dir: ${BASE_DIR})"
echo "[INFO] Module 2 (Vehicle AE Host): ${VEHICLE_USER}@${VEHICLE_HOST}:${VEHICLE_PORT} (Target Dir: ${VEHICLE_DIR})"
echo "================================================================================"

build_ssh_cmd() {
    local host="$1"
    local user="$2"
    local port="$3"
    local key="$4"
    local cmd="ssh -p ${port} -o ConnectTimeout=5 -o BatchMode=yes"
    if [ -n "${key}" ] && [ -f "${key}" ]; then
        cmd="${cmd} -i ${key} -o IdentitiesOnly=yes"
    fi
    cmd="${cmd} ${user}@${host}"
    echo "${cmd}"
}

build_rsync_ssh_opt() {
    local port="$1"
    local key="$2"
    local opt="ssh -p ${port}"
    if [ -n "${key}" ] && [ -f "${key}" ]; then
        opt="${opt} -i ${key} -o IdentitiesOnly=yes"
    fi
    echo "${opt}"
}

# ------------------------------------------------------------------------------
# Universal Remote Synchronisation (rsync with POSIX tar/scp streaming fallback)
# ------------------------------------------------------------------------------
sync_directory() {
    local host="$1"
    local user="$2"
    local port="$3"
    local key="$4"
    local src_dir="$5"
    local dst_dir="$6"

    local ssh_cmd
    ssh_cmd=$(build_ssh_cmd "${host}" "${user}" "${port}" "${key}")

    local has_remote_rsync=false
    if ${ssh_cmd} "command -v rsync" >/dev/null 2>&1; then
        has_remote_rsync=true
    fi

    if [ "${has_remote_rsync}" = "true" ] && command -v rsync >/dev/null 2>&1; then
        local rsync_ssh
        rsync_ssh=$(build_rsync_ssh_opt "${port}" "${key}")
        rsync -avz -e "${rsync_ssh}" \
            --exclude '.git' \
            --exclude '.pytest_cache' \
            --exclude '__pycache__' \
            --exclude 'firmware' \
            "${src_dir}/" "${user}@${host}:${dst_dir}/"
    else
        echo "       (Streaming directory '${src_dir}' via POSIX tar over SSH...)"
        ${ssh_cmd} "mkdir -p '${dst_dir}'"
        tar -C "${src_dir}" \
            --exclude='.git' \
            --exclude='.pytest_cache' \
            --exclude='__pycache__' \
            --exclude='firmware' \
            -czf - . | ${ssh_cmd} "tar -xzf - -C '${dst_dir}'"
    fi
}

sync_file() {
    local host="$1"
    local user="$2"
    local port="$3"
    local key="$4"
    local src_file="$5"
    local dst_file="$6"

    local ssh_cmd
    ssh_cmd=$(build_ssh_cmd "${host}" "${user}" "${port}" "${key}")
    local dst_parent
    dst_parent=$(dirname "${dst_file}")

    ${ssh_cmd} "mkdir -p '${dst_parent}'"

    local has_remote_rsync=false
    if ${ssh_cmd} "command -v rsync" >/dev/null 2>&1; then
        has_remote_rsync=true
    fi

    if [ "${has_remote_rsync}" = "true" ] && command -v rsync >/dev/null 2>&1; then
        local rsync_ssh
        rsync_ssh=$(build_rsync_ssh_opt "${port}" "${key}")
        rsync -avz -e "${rsync_ssh}" "${src_file}" "${user}@${host}:${dst_file}"
    else
        echo "       (Streaming file '${src_file}' via scp over SSH...)"
        local scp_cmd="scp -P ${port} -o ConnectTimeout=5 -o BatchMode=yes"
        if [ -n "${key}" ] && [ -f "${key}" ]; then
            scp_cmd="${scp_cmd} -i ${key} -o IdentitiesOnly=yes"
        fi
        ${scp_cmd} "${src_file}" "${user}@${host}:${dst_file}"
    fi

    if [ -x "${src_file}" ]; then
        ${ssh_cmd} "chmod +x '${dst_file}'"
    fi
}

# ------------------------------------------------------------------------------
# Pre-Flight Reachability & Authentication Check
# ------------------------------------------------------------------------------
check_remote_host() {
    local label="$1"
    local host="$2"
    local user="$3"
    local port="$4"
    local key="$5"

    echo "[CHECK] Probing ${label} at ${user}@${host}:${port}..."
    if ! nc -z -w 2 "${host}" "${port}" >/dev/null 2>&1; then
        echo "[ERROR] ${label} (${host}:${port}) is unreachable over TCP port ${port}." >&2
        echo "        Please verify network routing, host power state, or firewall settings." >&2
        return 1
    fi

    local ssh_cmd
    ssh_cmd=$(build_ssh_cmd "${host}" "${user}" "${port}" "${key}")
    if ${ssh_cmd} "id -u" >/dev/null 2>&1; then
        echo "[OK] SSH key authentication to ${user}@${host} verified."
        return 0
    else
        echo "[WARN] Passwordless SSH authentication failed for ${user}@${host}." >&2
        echo "       To configure SSH key access, password login, and Docker runtime automatically, run:" >&2
        echo "       bash scripts/check_install-docker_ssh.sh --preflight -p ${port} ${user}@${host}" >&2
        echo "       Or install your public key manually via:" >&2
        if [ -n "${key}" ]; then
            echo "       ssh-copy-id -i ${key}.pub -o IdentitiesOnly=yes -p ${port} ${user}@${host}" >&2
        else
            echo "       ssh-copy-id -o IdentitiesOnly=yes -p ${port} ${user}@${host}" >&2
        fi
        return 2
    fi
}

# ------------------------------------------------------------------------------
# Deploy Module 1: Base CSE on Central Server / VM
# ------------------------------------------------------------------------------
deploy_remote_base_cse() {
    echo -e "\n--------------------------------------------------------------------------------"
    echo " [STEP 1/2] Commissioning Module 1 (Base CSE Host) on ${BASE_HOST}"
    echo "--------------------------------------------------------------------------------"

    local auth_status=0
    check_remote_host "Base CSE Host" "${BASE_HOST}" "${BASE_USER}" "${BASE_PORT}" "${BASE_KEY}" || auth_status=$?

    if [ "${auth_status}" -eq 1 ]; then
        echo "[ERROR] Aborting Base CSE deployment: Host unreachable." >&2
        return 1
    elif [ "${auth_status}" -eq 2 ]; then
        echo "[ERROR] Aborting Base CSE deployment: SSH key authentication required." >&2
        echo "        Please configure SSH key access for ${BASE_USER}@${BASE_HOST}." >&2
        return 1
    fi

    local ssh_cmd
    ssh_cmd=$(build_ssh_cmd "${BASE_HOST}" "${BASE_USER}" "${BASE_PORT}" "${BASE_KEY}")

    # Ensure remote directory exists
    ${ssh_cmd} "mkdir -p ${BASE_DIR}"

    if [ "${SKIP_SYNC}" = "false" ]; then
        echo "[INFO] Synchronising deployment configuration and scripts to ${BASE_HOST}:${BASE_DIR}..."
        sync_directory "${BASE_HOST}" "${BASE_USER}" "${BASE_PORT}" "${BASE_KEY}" "${DEPLOY_DIR}" "${BASE_DIR}/deploy"
        sync_directory "${BASE_HOST}" "${BASE_USER}" "${BASE_PORT}" "${BASE_KEY}" "${ROOT_DIR}/scripts" "${BASE_DIR}/scripts"
        sync_directory "${BASE_HOST}" "${BASE_USER}" "${BASE_PORT}" "${BASE_KEY}" "${ROOT_DIR}/services" "${BASE_DIR}/services"

        if [ -f "${ROOT_DIR}/.env" ]; then
            sync_file "${BASE_HOST}" "${BASE_USER}" "${BASE_PORT}" "${BASE_KEY}" "${ROOT_DIR}/.env" "${BASE_DIR}/.env"
        fi
    fi

    # Trigger deployment on remote Base CSE host with interactive TTY support
    echo "[INFO] Executing Base CSE deployment on remote host ${BASE_HOST}..."
    local exec_ssh="ssh -p ${BASE_PORT}"
    if [ -n "${BASE_KEY}" ] && [ -f "${BASE_KEY}" ]; then
        exec_ssh="${exec_ssh} -i ${BASE_KEY} -o IdentitiesOnly=yes"
    fi
    if [ -t 0 ]; then
        exec_ssh="${exec_ssh} -t"
    fi
    ${exec_ssh} "${BASE_USER}@${BASE_HOST}" "cd ${BASE_DIR} && bash deploy/deploy_base_cse.sh --host ${BASE_HOST} --port 8080"

    echo "[SUCCESS] Module 1 (Base CSE Host) commissioned on ${BASE_HOST}."
}

# ------------------------------------------------------------------------------
# Deploy Module 2: Vehicle AE on In-Vehicle Raspberry Pi 5
# ------------------------------------------------------------------------------
deploy_remote_vehicle_ae() {
    echo -e "\n--------------------------------------------------------------------------------"
    echo " [STEP 2/2] Commissioning Module 2 (Vehicle AE Host) on ${VEHICLE_HOST}"
    echo "--------------------------------------------------------------------------------"

    local auth_status=0
    check_remote_host "Vehicle AE Host" "${VEHICLE_HOST}" "${VEHICLE_USER}" "${VEHICLE_PORT}" "${VEHICLE_KEY}" || auth_status=$?

    if [ "${auth_status}" -eq 1 ]; then
        echo "[ERROR] Aborting Vehicle AE deployment: Host unreachable." >&2
        return 1
    elif [ "${auth_status}" -eq 2 ]; then
        echo "[ERROR] Aborting Vehicle AE deployment: SSH key authentication required." >&2
        echo "        Please configure SSH key access for ${VEHICLE_USER}@${VEHICLE_HOST}." >&2
        return 1
    fi

    local ssh_cmd
    ssh_cmd=$(build_ssh_cmd "${VEHICLE_HOST}" "${VEHICLE_USER}" "${VEHICLE_PORT}" "${VEHICLE_KEY}")

    # Ensure remote directory exists
    ${ssh_cmd} "mkdir -p ${VEHICLE_DIR} ${VEHICLE_DIR}/deploy"

    if [ "${SKIP_SYNC}" = "false" ]; then
        echo "[INFO] Synchronising Vehicle AE services, scripts, and configuration to ${VEHICLE_HOST}:${VEHICLE_DIR}..."
        sync_directory "${VEHICLE_HOST}" "${VEHICLE_USER}" "${VEHICLE_PORT}" "${VEHICLE_KEY}" "${DEPLOY_DIR}" "${VEHICLE_DIR}/deploy"
        sync_directory "${VEHICLE_HOST}" "${VEHICLE_USER}" "${VEHICLE_PORT}" "${VEHICLE_KEY}" "${ROOT_DIR}/scripts" "${VEHICLE_DIR}/scripts"
        sync_directory "${VEHICLE_HOST}" "${VEHICLE_USER}" "${VEHICLE_PORT}" "${VEHICLE_KEY}" "${ROOT_DIR}/services" "${VEHICLE_DIR}/services"

        if [ -f "${ROOT_DIR}/.env" ]; then
            sync_file "${VEHICLE_HOST}" "${VEHICLE_USER}" "${VEHICLE_PORT}" "${VEHICLE_KEY}" "${ROOT_DIR}/.env" "${VEHICLE_DIR}/.env"
        fi
    fi

    echo "[INFO] Executing Vehicle AE onboarding on ${VEHICLE_HOST} targeting Base CSE at ${BASE_HOST}:8080..."
    ${ssh_cmd} "cd ${VEHICLE_DIR} && bash deploy/deploy_vehicle_ae.sh --base-host ${BASE_HOST} --remote --vehicle-id ${VEHICLE_ID_CLI}"

    echo "[SUCCESS] Module 2 (Vehicle AE Host) commissioned on ${VEHICLE_HOST}."
}

# ------------------------------------------------------------------------------
# Dispatcher
# ------------------------------------------------------------------------------
case "${MODULE_CLI}" in
    base-cse)
        deploy_remote_base_cse
        ;;
    vehicle-ae)
        deploy_remote_vehicle_ae
        ;;
    all)
        deploy_remote_base_cse
        deploy_remote_vehicle_ae
        ;;
    *)
        echo "[ERROR] Unknown module: ${MODULE_CLI}. Must be 'all', 'base-cse', or 'vehicle-ae'." >&2
        exit 1
        ;;
esac

echo -e "\n================================================================================"
echo "  [COMPLETE] Distributed Remote Deployment Complete!"
echo "  Module 1 (Base CSE):  ${BASE_HOST}:8080 (/sdv-cse)"
echo "  Module 2 (Vehicle AE): ${VEHICLE_HOST} -> ${VEHICLE_ID_CLI}"
echo "================================================================================"
