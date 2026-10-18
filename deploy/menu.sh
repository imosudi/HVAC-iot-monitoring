#!/usr/bin/env bash
# ==============================================================================
# SDV Automotive IoT: Interactive Deployment Selection Menu
# Standard Conformance: ETSI TS 118 101 Rel 4 / oneM2M TS-0004 & TS-0010
#
# Interactive terminal dashboard and orchestrator for:
#   - Distributed Multi-Host Deployment (Server/VM + Raspberry Pi 5)
#   - Module 1 (Base CSE Infrastructure) & Module 2 (Vehicle AE Instances)
#   - Localhost Development, Container Mesh, & Simulation
#   - systemd Host Service Management (sdv-acme-cse.service)
#   - Pre-Flight Diagnostics, Hardware Discovery, & Network Verification
#   - Telemetry Simulation & Least-Privilege Security Conformance Matrix
# ==============================================================================

set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"

# Load environment configuration (deploy/.env first, root .env overrides)
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

# ANSI Colour Codes
CYAN="\033[1;36m"
BLUE="\033[0;36m"
WHITE="\033[1;37m"
GRAY="\033[0;37m"
YELLOW="\033[1;33m"
DIM_YELLOW="\033[0;33m"
GREEN="\033[1;32m"
RED="\033[1;31m"
BOLD="\033[1m"
RESET="\033[0m"

# Default Configuration Parameters
DEF_BASE_HOST="${BASE_CSE_HOST:-192.168.122.91}"
DEF_BASE_USER="${BASE_CSE_USER:-${USER}}"
DEF_BASE_PORT="${BASE_CSE_SSH_PORT:-22}"
DEF_BASE_KEY="${BASE_CSE_SSH_KEY:-${HOME}/.ssh/id_ed25519}"

DEF_VEHICLE_HOST="${VEHICLE_AE_HOST:-192.168.122.145}"
DEF_VEHICLE_USER="${VEHICLE_AE_USER:-${USER}}"
DEF_VEHICLE_PORT="${VEHICLE_AE_SSH_PORT:-22}"
DEF_VEHICLE_KEY="${VEHICLE_AE_SSH_KEY:-${HOME}/.ssh/id_ed25519}"
DEF_VEHICLE_ID="vehicle-001"

# ------------------------------------------------------------------------------
# Universal Prompt Helper (Safe for stdout, stdin, defaults, and EOF)
# ------------------------------------------------------------------------------
prompt_input() {
    local prompt_msg="$1"
    local default_val="${2:-}"
    local var_name="$3"

    echo -ne "${YELLOW}${prompt_msg}${RESET}"
    local user_input=""
    if ! read -r user_input; then
        echo ""
        user_input=""
    fi
    user_input="${user_input:-${default_val}}"
    eval "${var_name}=\"${user_input}\""
}

pause_to_continue() {
    echo ""
    echo -ne "${YELLOW}Press [Enter] to return to the menu...${RESET}"
    read -r _ || true
}

# ------------------------------------------------------------------------------
# Banner and Header Rendering
# ------------------------------------------------------------------------------
print_banner() {
    clear 2>/dev/null || true
    echo -e "${CYAN}"
    cat << "EOF"
  _____ ______     __   ____      _     _         __  __             _ _             
 / ____|  _ \ \   / /  / ___|__ _| |__ (_)_ __   |  \/  | ___  _ __ (_) |_ ___  _ __ 
| (___ | | | \ \ / /  | |   / _` | '_ \| | '_ \  | |\/| |/ _ \| '_ \| | __/ _ \| '__|
 \___ \| | | |\ V /   | |__| (_| | |_) | | | | | | |  | | (_) | | | | | || (_) | |   
 |_____/____/  \_/     \____\__,_|_.__/|_|_| |_| |_|  |_|\___/|_| |_|_|\__\___/|_|   
EOF
    echo -e "${BLUE}             Raspberry Pi 5 + Central Server/VM • oneM2M In-CSE Platform${RESET}"
    echo ""
}

# ------------------------------------------------------------------------------
# Reusable Host Selection and Credential Prompts
# ------------------------------------------------------------------------------
prompt_remote_credentials() {
    local target_label="$1"
    local default_host="$2"
    local default_user="$3"
    local default_port="$4"
    local default_key="$5"

    echo ""
    prompt_input "Enter remote host IP address or hostname [default: ${default_host}]: " "${default_host}" RET_HOST
    prompt_input "Enter privileged login user (e.g. root, docker-enabled user) [default: ${default_user}]: " "${default_user}" RET_USER
    prompt_input "Enter remote SSH port [default: ${default_port}]: " "${default_port}" RET_PORT

    echo -e "${GRAY}Select SSH authentication method:${RESET}"
    echo -e "  ${CYAN}[1]${RESET} SSH identity key / agent [default]"
    echo -e "  ${CYAN}[2]${RESET} Password authentication"
    prompt_input "Enter choice [1-2] (default: 1): " "1" AUTH_CHOICE

    if [ "${AUTH_CHOICE}" = "1" ]; then
        prompt_input "Enter SSH identity key path [default: ${default_key}]: " "${default_key}" RET_KEY
    else
        RET_KEY=""
    fi
}

prompt_host_type() {
    local feature_name="$1"
    echo ""
    echo -e "${GRAY}Select deployment host for ${feature_name}:${RESET}"
    echo -e "  ${CYAN}[1]${RESET} Local host [default]"
    echo -e "  ${CYAN}[2]${RESET} Remote host"
    prompt_input "Enter choice [1-2] (default: 1): " "1" HOST_CHOICE
}

# ------------------------------------------------------------------------------
# Action 1: Distributed Multi-Host Deployment (Base CSE Server + Vehicle AE Pi 5)
# ------------------------------------------------------------------------------
action_distributed_deployment() {
    echo -e "\n${CYAN}===> Distributed Multi-Host Deployment (SSH Orchestration)${RESET}"
    echo -e "${GRAY}Orchestrates Module 1 (Base CSE Platform) on Server/VM and Module 2 (Vehicle AE) on Raspberry Pi 5.${RESET}"

    echo -e "\n${BOLD}[1/2] Configure Module 1 (Base CSE Server / VM Host):${RESET}"
    prompt_remote_credentials "Base CSE" "${DEF_BASE_HOST}" "${DEF_BASE_USER}" "${DEF_BASE_PORT}" "${DEF_BASE_KEY}"
    local b_host="${RET_HOST}"
    local b_user="${RET_USER}"
    local b_port="${RET_PORT}"
    local b_key="${RET_KEY}"

    echo -e "\n${BOLD}[2/2] Configure Module 2 (Vehicle AE Host — Raspberry Pi 5):${RESET}"
    prompt_remote_credentials "Vehicle AE" "${DEF_VEHICLE_HOST}" "${DEF_VEHICLE_USER}" "${DEF_VEHICLE_PORT}" "${DEF_VEHICLE_KEY}"
    local v_host="${RET_HOST}"
    local v_user="${RET_USER}"
    local v_port="${RET_PORT}"
    local v_key="${RET_KEY}"

    echo ""
    prompt_input "Enter Vehicle Identifier for AE registration [default: ${DEF_VEHICLE_ID}]: " "${DEF_VEHICLE_ID}" v_id

    echo -e "\n${CYAN}[INFO] Launching Distributed Remote Modular Orchestrator...${RESET}"
    bash "${DEPLOY_DIR}/deploy_remote.sh" \
        --base-host "${b_host}" \
        --base-user "${b_user}" \
        --base-port "${b_port}" \
        $( [ -n "${b_key}" ] && echo "--base-key ${b_key}" || true ) \
        --vehicle-host "${v_host}" \
        --vehicle-user "${v_user}" \
        --vehicle-port "${v_port}" \
        $( [ -n "${v_key}" ] && echo "--vehicle-key ${v_key}" || true ) \
        --vehicle-id "${v_id}" \
        --module all
}

# ------------------------------------------------------------------------------
# Action 2: Standalone Base CSE Infrastructure (Module 1)
# ------------------------------------------------------------------------------
action_base_cse() {
    echo -e "\n${CYAN}===> Standalone Base CSE Infrastructure Deployment (ACME IN-CSE, Zero AEs, Baseline Governance)${RESET}"
    echo -e "${GRAY}Deploys full Module 1 Base CSE platform ensuring all 6 co-located microservices reside on the same device:${RESET}"
    echo -e "  - ${CYAN}sdv_onem2m_cse${RESET}       (ACME oneM2M IN-CSE, Port 8080)"
    echo -e "  - ${CYAN}sdv_mosquitto_broker${RESET} (Mosquitto MQTT Broker mTLS 1.3, Ports 1883/8883)"
    echo -e "  - ${CYAN}sdv_bridge_ae${RESET}        (Bridge Application Entity Service, Port 5000)"
    echo -e "  - ${CYAN}sdv_influxdb${RESET}         (InfluxDB 2.x Time-Series Storage, Port 8087)"
    echo -e "  - ${CYAN}sdv_grafana${RESET}          (Grafana Observability Cockpit, Port 3000)"
    echo -e "  - ${CYAN}sdv_web_portal${RESET}       (Management Operations Portal, Port 8000)\n"

    prompt_host_type "Base CSE Infrastructure"
    if [ "${HOST_CHOICE}" = "1" ]; then
        echo -e "\n${CYAN}[INFO] Commissioning Base CSE locally on current host (all 6 co-located microservices)...${RESET}"
        bash "${DEPLOY_DIR}/deploy_base_cse.sh" --localhost --port 8080
    else
        prompt_remote_credentials "Base CSE Host" "${DEF_BASE_HOST}" "${DEF_BASE_USER}" "${DEF_BASE_PORT}" "${DEF_BASE_KEY}"
        echo -e "\n${CYAN}[INFO] Commissioning Base CSE on remote host ${RET_HOST} (all 6 co-located microservices)...${RESET}"
        bash "${DEPLOY_DIR}/deploy_remote.sh" \
            --base-host "${RET_HOST}" \
            --base-user "${RET_USER}" \
            --base-port "${RET_PORT}" \
            $( [ -n "${RET_KEY}" ] && echo "--base-key ${RET_KEY}" || true ) \
            --module base-cse
    fi
}

# ------------------------------------------------------------------------------
# Action 3: Standalone Vehicle Application Entity (Module 2)
# ------------------------------------------------------------------------------
action_vehicle_ae() {
    echo -e "\n${CYAN}===> Standalone Vehicle Application Entity (AE) Deployment${RESET}"
    echo -e "${GRAY}Onboards Vehicle AE to Base CSE and deploys containerised microservices (sdv_edge_serial_client, sdv_actuator_module).${RESET}"
    echo -e "${GRAY}Hosts: Ingests serial bus from ESP32-S3 and dispatches downlink actuation directives to cabin actuators.${RESET}\n"

    prompt_input "Enter target Base CSE host or IP [default: ${DEF_BASE_HOST}]: " "${DEF_BASE_HOST}" target_base
    prompt_input "Enter Vehicle Identifier [default: ${DEF_VEHICLE_ID}]: " "${DEF_VEHICLE_ID}" v_id

    prompt_host_type "Vehicle AE Runtime"
    if [ "${HOST_CHOICE}" = "1" ]; then
        echo -e "\n${CYAN}[INFO] Executing Vehicle AE onboarding locally targeting Base CSE at ${target_base}:8080...${RESET}"
        bash "${DEPLOY_DIR}/deploy_vehicle_ae.sh" --base-host "${target_base}" --vehicle-id "${v_id}"
    else
        prompt_remote_credentials "Vehicle AE Host" "${DEF_VEHICLE_HOST}" "${DEF_VEHICLE_USER}" "${DEF_VEHICLE_PORT}" "${DEF_VEHICLE_KEY}"
        echo -e "\n${CYAN}[INFO] Commissioning Vehicle AE on remote host ${RET_HOST} targeting Base CSE at ${target_base}...${RESET}"
        bash "${DEPLOY_DIR}/deploy_remote.sh" \
            --base-host "${target_base}" \
            --vehicle-host "${RET_HOST}" \
            --vehicle-user "${RET_USER}" \
            --vehicle-port "${RET_PORT}" \
            $( [ -n "${RET_KEY}" ] && echo "--vehicle-key ${RET_KEY}" || true ) \
            --vehicle-id "${v_id}" \
            --module vehicle-ae
    fi
}

# ------------------------------------------------------------------------------
# Action 4: Localhost Development Stack (Microservices Decomposition)
# ------------------------------------------------------------------------------
action_localhost_stack() {
    echo -e "\n${CYAN}===> Complete Localhost Development Stack (Decomposed Mesh)${RESET}"
    echo -e "${GRAY}Launches the complete development stack (Base CSE, InfluxDB, Grafana, Web Portal) on localhost.${RESET}"

    prompt_host_type "Microservices Decomposition"
    if [ "${HOST_CHOICE}" = "1" ]; then
        echo -e "\n${CYAN}[INFO] Starting decomposed container mesh in lean mode on localhost...${RESET}"
        bash "${DEPLOY_DIR}/deploy_gateway.sh" --localhost --lean
    else
        echo -e "\n${CYAN}[INFO] Remote execution selected for decomposed container stack.${RESET}"
        prompt_remote_credentials "Target Host" "${DEF_BASE_HOST}" "${DEF_BASE_USER}" "${DEF_BASE_PORT}" "${DEF_BASE_KEY}"
        bash "${DEPLOY_DIR}/deploy_remote.sh" \
            --base-host "${RET_HOST}" \
            --base-user "${RET_USER}" \
            --base-port "${RET_PORT}" \
            $( [ -n "${RET_KEY}" ] && echo "--base-key ${RET_KEY}" || true ) \
            --module base-cse
    fi
}

# ------------------------------------------------------------------------------
# Action 5: systemd Host Service Management (Install, Status, Logs, Restart)
# ------------------------------------------------------------------------------
action_systemd_management() {
    echo -e "\n${CYAN}===> systemd Host Service Management (sdv-acme-cse.service)${RESET}"
    echo -e "${GRAY}Manages the native background daemon for ACME oneM2M CSE.${RESET}"

    echo -e "\n${GRAY}Select target host for systemd Service Management:${RESET}"
    echo -e "  ${CYAN}[1]${RESET} Local host [default]"
    echo -e "  ${CYAN}[2]${RESET} Remote Base CSE host (${DEF_BASE_HOST})"
    prompt_input "Enter choice [1-2] (default: 1): " "1" s_host_choice

    local ssh_prefix=""
    if [ "${s_host_choice}" = "2" ]; then
        prompt_remote_credentials "Base CSE Host" "${DEF_BASE_HOST}" "${DEF_BASE_USER}" "${DEF_BASE_PORT}" "${DEF_BASE_KEY}"
        local key_opt=""
        if [ -n "${RET_KEY}" ] && [ -f "${RET_KEY}" ]; then
            key_opt="-i ${RET_KEY} -o IdentitiesOnly=yes"
        fi
        ssh_prefix="ssh -p ${RET_PORT} ${key_opt} ${RET_USER}@${RET_HOST}"
    fi

    while true; do
        echo -e "\n${CYAN}systemd Management Actions (sdv-acme-cse.service):${RESET}"
        echo -e "  ${CYAN}[1]${RESET} Service Status (systemctl --user status)"
        echo -e "  ${CYAN}[2]${RESET} Start Service (systemctl --user start)"
        echo -e "  ${CYAN}[3]${RESET} Stop Service (systemctl --user stop)"
        echo -e "  ${CYAN}[4]${RESET} Restart Service (systemctl --user restart)"
        echo -e "  ${CYAN}[5]${RESET} Tail Service Logs (journalctl -u sdv-acme-cse.service -n 25)"
        echo -e "  ${CYAN}[6]${RESET} Enable User Service Lingering (loginctl enable-linger)"
        echo -e "  ${RED}[0]${RESET} Return to Main Menu"

        prompt_input "Enter action [1-6, 0 to return] (default: 1): " "1" S_ACTION

        case "${S_ACTION}" in
            1)
                echo -e "\n${CYAN}[INFO] Querying systemd user service status...${RESET}"
                if [ -n "${ssh_prefix}" ]; then
                    ${ssh_prefix} "systemctl --user status sdv-acme-cse.service --no-pager" || true
                else
                    systemctl --user status sdv-acme-cse.service --no-pager || true
                fi
                ;;
            2)
                echo -e "\n${CYAN}[INFO] Starting sdv-acme-cse.service...${RESET}"
                if [ -n "${ssh_prefix}" ]; then
                    ${ssh_prefix} "systemctl --user start sdv-acme-cse.service && systemctl --user is-active sdv-acme-cse.service" || true
                else
                    systemctl --user start sdv-acme-cse.service && systemctl --user is-active sdv-acme-cse.service || true
                fi
                ;;
            3)
                echo -e "\n${CYAN}[INFO] Stopping sdv-acme-cse.service...${RESET}"
                if [ -n "${ssh_prefix}" ]; then
                    ${ssh_prefix} "systemctl --user stop sdv-acme-cse.service" || true
                else
                    systemctl --user stop sdv-acme-cse.service || true
                fi
                ;;
            4)
                echo -e "\n${CYAN}[INFO] Restarting sdv-acme-cse.service...${RESET}"
                if [ -n "${ssh_prefix}" ]; then
                    ${ssh_prefix} "systemctl --user restart sdv-acme-cse.service && systemctl --user is-active sdv-acme-cse.service" || true
                else
                    systemctl --user restart sdv-acme-cse.service && systemctl --user is-active sdv-acme-cse.service || true
                fi
                ;;
            5)
                echo -e "\n${CYAN}[INFO] Retrieving last 25 journal log lines...${RESET}"
                if [ -n "${ssh_prefix}" ]; then
                    ${ssh_prefix} "journalctl --user -u sdv-acme-cse.service -n 25 --no-pager" || true
                else
                    journalctl --user -u sdv-acme-cse.service -n 25 --no-pager || true
                fi
                ;;
            6)
                echo -e "\n${CYAN}[INFO] Enabling user service lingering...${RESET}"
                if [ -n "${ssh_prefix}" ]; then
                    ${ssh_prefix} "loginctl enable-linger \${USER} && echo '[OK] Lingering enabled for remote user.'" || true
                else
                    loginctl enable-linger "${USER}" && echo "[OK] Lingering enabled for user ${USER}." || true
                fi
                ;;
            0)
                break
                ;;
            *)
                echo -e "${RED}[WARN] Invalid selection.${RESET}"
                ;;
        esac
    done
}

# ------------------------------------------------------------------------------
# Action 6: Pre-flight Software & Hardware Diagnostics Check
# ------------------------------------------------------------------------------
run_local_hardware_diagnostics() {
    echo -e "\n${CYAN}===> Local Peripheral, Hardware & Network Diagnostics Suite${RESET}"
    echo -e "${GRAY}Probes host hardware, sensor buses, peripheral interfaces, TCP endpoints, and SSH key authentication.${RESET}\n"

    # 1. Peripheral & Transducer Bus Diagnostics
    echo -e "${BOLD}[1/4] Hardware Peripheral & Transducer Bus Discovery:${RESET}"

    # V4L2 Video Devices (Cabin camera / monitoring)
    local v4l2_devs
    v4l2_devs=$(ls -1 /dev/video* 2>/dev/null || true)
    if [ -n "${v4l2_devs}" ]; then
        echo -e "  [OK] V4L2 Video Capture Devices present: $(echo "${v4l2_devs}" | tr '\n' ' ')"
    else
        echo -e "  [INFO] No V4L2 video devices attached locally."
    fi

    # Serial / UART Transducer Bus (Micro-ECU / ESP32 sensor telemetry)
    local serial_devs
    serial_devs=$(ls -1 /dev/ttyUSB* /dev/ttyACM* /dev/ttyAMA* 2>/dev/null || true)
    if [ -n "${serial_devs}" ]; then
        echo -e "  [OK] Serial Transducer / Micro-ECU interfaces found: $(echo "${serial_devs}" | tr '\n' ' ')"
    else
        echo -e "  [INFO] Zero USB/UART serial interfaces detected locally (simulation/native mode)."
    fi

    # I2C Environmental Sensor Bus (SCD40 CO2, SHT40 Temperature/Humidity, etc.)
    local i2c_devs
    i2c_devs=$(ls -1 /dev/i2c-* 2>/dev/null || true)
    if [ -n "${i2c_devs}" ]; then
        echo -e "  [OK] I2C Sensor Bus interfaces active: $(echo "${i2c_devs}" | tr '\n' ' ')"
    fi

    # Automotive CAN Bus / SocketCAN Interfaces
    local can_devs
    can_devs=$(ip link show type can 2>/dev/null | grep -oE 'can[0-9]+' || true)
    if [ -n "${can_devs}" ]; then
        echo -e "  [OK] Automotive SocketCAN interfaces active: $(echo "${can_devs}" | tr '\n' ' ')"
    fi

    # 2. Local Cryptographic Assets
    echo -e "\n${BOLD}[2/4] Cryptographic X.509 Assets Verification:${RESET}"
    if [ -f "${DEPLOY_DIR}/mosquitto/certs/ca.crt" ] && [ -f "${DEPLOY_DIR}/mosquitto/certs/client_esp32.crt" ]; then
        echo -e "  [OK] Valid X.509 PKI certificates present in deploy/mosquitto/certs/."
    else
        echo -e "  [WARN] PKI certificates missing. Run 'make setup-pki' to generate certificates."
    fi

    # 3. Network & Endpoints Reachability
    echo -e "\n${BOLD}[3/4] Platform Network Reachability Probes:${RESET}"
    # Local CSE
    if nc -z -w 1 127.0.0.1 8080 >/dev/null 2>&1; then
        echo -e "  [OK] Localhost Base CSE port 8080 is ${GREEN}LISTENING${RESET}."
    else
        echo -e "  [INFO] Localhost Base CSE port 8080 is closed (not running locally)."
    fi

    # Local MQTT
    if nc -z -w 1 127.0.0.1 8883 >/dev/null 2>&1; then
        echo -e "  [OK] Localhost Mosquitto mTLS port 8883 is ${GREEN}LISTENING${RESET}."
    else
        echo -e "  [INFO] Localhost Mosquitto port 8883 is closed."
    fi

    # Local Web Portal
    if nc -z -w 1 127.0.0.1 8000 >/dev/null 2>&1; then
        echo -e "  [OK] Localhost Web Management Portal port 8000 is ${GREEN}LISTENING${RESET}."
    else
        echo -e "  [INFO] Localhost Web Management Portal port 8000 is closed."
    fi

    # Remote Base CSE Host
    if nc -z -w 1 "${DEF_BASE_HOST}" 22 >/dev/null 2>&1; then
        echo -e "  [OK] Remote Base CSE Host (${DEF_BASE_HOST}:22 SSH) is ${GREEN}REACHABLE${RESET}."
        if nc -z -w 1 "${DEF_BASE_HOST}" 8080 >/dev/null 2>&1; then
            echo -e "  [OK] Remote Base CSE HTTP port 8080 is ${GREEN}OPEN${RESET}."
            local http_code
            http_code=$(curl -s -o /dev/null -w "%{http_code}" -H "X-M2M-Origin: CAdmin" -H "X-M2M-RI: diag" -H "X-M2M-RVI: 3" "http://${DEF_BASE_HOST}:8080/sdv-cse" || echo "000")
            if [ "${http_code}" = "200" ]; then
                echo -e "  [OK] oneM2M CSEBase /sdv-cse responding (HTTP ${GREEN}200 OK${RESET})."
            else
                echo -e "  [WARN] oneM2M CSEBase /sdv-cse returned status: ${http_code}."
            fi
        else
            echo -e "  [INFO] Remote Base CSE HTTP port 8080 is not currently open."
        fi

        if nc -z -w 1 "${DEF_BASE_HOST}" 8000 >/dev/null 2>&1; then
            echo -e "  [OK] Remote Base CSE Web Management Portal port 8000 is ${GREEN}ONLINE${RESET} (http://${DEF_BASE_HOST}:8000)."
        else
            echo -e "  [INFO] Remote Base CSE Web Management Portal port 8000 is closed."
        fi
    else
        echo -e "  [WARN] Remote Base CSE Host (${DEF_BASE_HOST}:22) is unreachable."
    fi

    # Remote Vehicle AE Host
    if nc -z -w 1 "${DEF_VEHICLE_AE_HOST:-${DEF_VEHICLE_HOST}}" 22 >/dev/null 2>&1; then
        echo -e "  [OK] Remote Vehicle AE Host (${DEF_VEHICLE_HOST}:22 SSH) is ${GREEN}REACHABLE${RESET}."
    else
        echo -e "  [INFO] Remote Vehicle AE Host (${DEF_VEHICLE_HOST}:22) is not reachable on current network."
    fi

    # 4. SSH Authentication Check
    echo -e "\n${BOLD}[4/4] SSH Authentication Verification:${RESET}"
    if [ -f "${DEF_BASE_KEY}" ]; then
        if ssh -p "${DEF_BASE_PORT}" -o ConnectTimeout=2 -o BatchMode=yes -i "${DEF_BASE_KEY}" -o IdentitiesOnly=yes "${DEF_BASE_USER}@${DEF_BASE_HOST}" "id -u" >/dev/null 2>&1; then
            echo -e "  [OK] Passwordless SSH key authentication to Base CSE (${DEF_BASE_USER}@${DEF_BASE_HOST}) ${GREEN}VERIFIED${RESET}."
        else
            echo -e "  [WARN] Passwordless SSH key authentication to Base CSE (${DEF_BASE_USER}@${DEF_BASE_HOST}) failed."
        fi
    fi

    if [ -f "${DEF_VEHICLE_KEY}" ]; then
        if ssh -p "${DEF_VEHICLE_PORT}" -o ConnectTimeout=2 -o BatchMode=yes -i "${DEF_VEHICLE_KEY}" -o IdentitiesOnly=yes "${DEF_VEHICLE_USER}@${DEF_VEHICLE_HOST}" "id -u" >/dev/null 2>&1; then
            echo -e "  [OK] Passwordless SSH key authentication to Vehicle AE (${DEF_VEHICLE_USER}@${DEF_VEHICLE_HOST}) ${GREEN}VERIFIED${RESET}."
        else
            echo -e "  [WARN] Passwordless SSH key authentication to Vehicle AE (${DEF_VEHICLE_USER}@${DEF_VEHICLE_HOST}) failed."
        fi
    fi
}

action_diagnostics() {
    echo -e "\n${CYAN}===> Pre-Flight Software & Hardware Diagnostics Check${RESET}"
    echo -e "${GRAY}Diagnostic toolchain for Docker Engine, SSH passwordless/password authentication, build tools, and hardware interfaces.${RESET}\n"

    echo -e "${WHITE}Select pre-flight diagnostic workflow:${RESET}"
    echo -e "  ${CYAN}[1]${RESET} Full pre-flight check with automated Docker, build tools, update & upgrade, and SSH setup (--preflight)"
    echo -e "  ${CYAN}[2]${RESET} Inspection-only report (changes nothing, reports missing dependencies) (--check-only)"
    echo -e "  ${CYAN}[3]${RESET} Explicitly ensure SSH password authentication is enabled (--enable-password-auth)"
    echo -e "  ${CYAN}[4]${RESET} Optional: Enforce key-only authentication (disable password logins) (--disable-password-auth)"
    echo -e "  ${CYAN}[5]${RESET} Local Hardware Peripheral & Network Diagnostics (V4L2, UART, I2C, CAN, sysfs, TCP)"
    echo -e "  ${CYAN}[6]${RESET} Comprehensive Diagnostics (Run both remote preflight check & local hardware probes)"
    echo -e "  ${RED}[0]${RESET} Return to main menu\n"

    prompt_input "Enter choice [1-6, 0 to return] (default: 1): " "1" diag_choice

    case "${diag_choice}" in
        1|2|3|4|6)
            echo -e "\n${CYAN}--- Target Remote Host Configuration ---${RESET}"
            prompt_input "Enter target remote username [default: ${DEF_BASE_USER}]: " "${DEF_BASE_USER}" diag_user
            prompt_input "Enter target remote hostname or IP address [default: ${DEF_BASE_HOST}]: " "${DEF_BASE_HOST}" diag_host
            prompt_input "Enter target remote SSH port [default: ${DEF_BASE_PORT}]: " "${DEF_BASE_PORT}" diag_port
            prompt_input "Enter path to SSH private key [default: ${DEF_BASE_KEY}]: " "${DEF_BASE_KEY}" diag_key

            local script_path="${ROOT_DIR}/scripts/check_install-docker_ssh.sh"
            local flag="--preflight"
            [ "${diag_choice}" = "2" ] && flag="--check-only"
            [ "${diag_choice}" = "3" ] && flag="--enable-password-auth"
            [ "${diag_choice}" = "4" ] && flag="--disable-password-auth"

            echo -e "\n${CYAN}[INFO] Executing pre-flight diagnostic (${flag}) against ${diag_user}@${diag_host}:${diag_port}...${RESET}\n"
            bash "${script_path}" \
                --port "${diag_port}" \
                $( [ -n "${diag_key}" ] && [ -f "${diag_key}" ] && echo "--identity ${diag_key}" || true ) \
                ${flag} \
                "${diag_user}@${diag_host}" || true

            if [ "${diag_choice}" = "6" ]; then
                echo -e "\n${CYAN}================================================================================${RESET}"
                echo -e "${CYAN}Executing Local Peripheral & Hardware Diagnostic Suite...${RESET}"
                echo -e "${CYAN}================================================================================${RESET}"
                run_local_hardware_diagnostics
            fi
            ;;
        5)
            run_local_hardware_diagnostics
            ;;
        0)
            return 0
            ;;
        *)
            echo -e "${RED}[ERROR] Invalid selection.${RESET}"
            ;;
    esac
}

# ------------------------------------------------------------------------------
# Action 7: Telemetry Pipeline Simulation & Ingestion Validation
# ------------------------------------------------------------------------------
action_telemetry_simulation() {
    echo -e "\n${CYAN}===> Vehicular Telemetry Simulation & Validation Pipeline${RESET}"
    echo -e "${GRAY}Simulates multi-sensor environmental frames (CO2, Temp, Humidity, CO, IAQ, Fan Tachometer).${RESET}\n"

    prompt_input "Enter target host IP/hostname [default: ${DEF_BASE_HOST}]: " "${DEF_BASE_HOST}" sim_host
    prompt_input "Enter Vehicle Identifier [default: ${DEF_VEHICLE_ID}]: " "${DEF_VEHICLE_ID}" sim_vid

    echo -e "${GRAY}Select operating simulation mode:${RESET}"
    echo -e "  ${CYAN}[1]${RESET} Normal nominal operation (CO2: ~480-530 ppm, CO: ~0.1 ppm) [default]"
    echo -e "  ${CYAN}[2]${RESET} Elevated CO2 alert condition (CO2: 850+ ppm, Fresh air demand)"
    echo -e "  ${CYAN}[3]${RESET} Life-safety CO hazard (CO: 45 ppm, Immediate ventilation purging)"
    prompt_input "Enter choice [1-3] (default: 1): " "1" m_choice

    local s_mode="normal"
    [ "${m_choice}" = "2" ] && s_mode="co2_alert"
    [ "${m_choice}" = "3" ] && s_mode="co_hazard"

    prompt_input "Enter number of sample telemetry frames to transmit [default: 5]: " "5" s_count

    # Verify python runtime
    local py_cmd="python3"
    if [ -f "${ROOT_DIR}/.venv/bin/python" ]; then
        py_cmd="${ROOT_DIR}/.venv/bin/python"
    fi

    local ca_cert="${DEPLOY_DIR}/mosquitto/certs/ca.crt"
    local c_cert="${DEPLOY_DIR}/mosquitto/certs/client_esp32.crt"
    local c_key="${DEPLOY_DIR}/mosquitto/certs/client_esp32.key"

    if nc -z -w 2 "${sim_host}" 8883 >/dev/null 2>&1 && [ -f "${ca_cert}" ]; then
        echo -e "\n${CYAN}[INFO] Streaming telemetry via mTLS 1.3 to ${sim_host}:8883 (mode: ${s_mode})...${RESET}"
        ${py_cmd} "${ROOT_DIR}/scripts/testing/simulate_telemetry.py" \
            --host "${sim_host}" \
            --port 8883 \
            --ca-cert "${ca_cert}" \
            --client-cert "${c_cert}" \
            --client-key "${c_key}" \
            --route native \
            --mode "${s_mode}" \
            --vehicle-id "${sim_vid}" \
            --count "${s_count}" \
            --interval 1.0 || true
    else
        echo -e "\n${CYAN}[INFO] Mosquitto mTLS port 8883 offline on ${sim_host}. Executing HTTP REST Mca ingestion test...${RESET}"
        ${py_cmd} "${ROOT_DIR}/scripts/deploy_acme_fleet_single_vehicle_ae.py" \
            --base-host "${sim_host}" \
            --port 8080 \
            --vehicle-id "${sim_vid}" || true
    fi

    echo -e "\n${CYAN}[INFO] Testing cluster fan-out retrieval (/fopt/la) across fleet aggregation group...${RESET}"
    curl -s -H "X-M2M-Origin: CAdmin" -H "X-M2M-RI: menu_fanout" -H "X-M2M-RVI: 3" \
        "http://${sim_host}:8080/sdv-cse/grp_fleet_telemetry/fopt/la" | jq . 2>/dev/null || true
}

# ------------------------------------------------------------------------------
# Action 8: Display Least-Privilege Service Comparison Matrix
# ------------------------------------------------------------------------------
action_comparison_matrix() {
    echo -e "\n${CYAN}===> SDV Platform Least-Privilege & Security Isolation Matrix${RESET}"
    echo -e "${GRAY}Standard Conformance: ETSI TS 118 101 Rel 4 / oneM2M TS-0004 & TS-0010 Security Guidelines${RESET}\n"

    echo -e "${BOLD}+---------------------------+---------------+-----------+-------------+-----------------------------+---------------------+${RESET}"
    echo -e "${BOLD}| Microservice / Entity     | Host Topology | UID : GID | Ports Bound | Capabilities & Privileges   | Standard / Role     |${RESET}"
    echo -e "${BOLD}+---------------------------+---------------+-----------+-------------+-----------------------------+---------------------+${RESET}"
    echo -e "| ${CYAN}ACME oneM2M IN-CSE${RESET}        | Server / VM   | 1000:1000 | 8080, 1883  | Non-root, Drop ALL, No New  | ETSI TS 118 101     |"
    echo -e "| ${CYAN}Mosquitto MQTT Broker${RESET}     | Server / VM   | 1883:1883 | 8883 (mTLS) | Drop ALL, Read-Only rootfs  | oneM2M TS-0010 Sec  |"
    echo -e "| ${CYAN}InfluxDB Time-Series DB${RESET}   | Server / VM   | 1000:1000 | 8087        | Non-root, Ephemeral tmpfs   | Telemetry Historian |"
    echo -e "| ${CYAN}Grafana Enterprise Dashboard${RESET}| Server / VM | 472:472   | 3000        | Unprivileged user, R/O conf | Cockpit Visualiser  |"
    echo -e "| ${CYAN}Web Management Portal${RESET}     | Server / VM   | 1000:1000 | 8000        | Gunicorn unprivileged worker| Fleet Admin / Mca   |"
    echo -e "| ${CYAN}Bridge AE Ingestion Node${RESET}  | Server / VM   | 1000:1000 | Internal    | Non-root, TS-0010 Interwork | Bridge AE Protocol  |"
    echo -e "| ${GREEN}Vehicular AE Client Daemon${RESET}| Pi 5 in-cabin | 1000:1000 | Outbound 0  | CAP_DAC_OVERRIDE dropped    | Vehicular Edge AE   |"
    echo -e "| ${GREEN}ESP32-S3 Micro-ECU${RESET}        | Hardware Bus  | Bare-Metal| UART / I2C  | FreeRTOS deterministic task | Physical Sensor Hub |"
    echo -e "${BOLD}+---------------------------+---------------+-----------+-------------+-----------------------------+---------------------+${RESET}"

    echo -e "\n${BOLD}Key Architectural Isolation Highlights:${RESET}"
    echo -e "  ${GREEN}✓ In-Vehicle Perimeter:${RESET} Raspberry Pi 5 runs strictly ${BOLD}0 open ingress ports${RESET}; all WAN links are outbound."
    echo -e "  ${GREEN}✓ Mutual TLS 1.3 Perimeter:${RESET} Telemetry encrypted in flight with dual-sided X.509 hardware verification."
    echo -e "  ${GREEN}✓ Stateless Central CSE:${RESET} Base CSE starts in a strictly vanilla state (0 AEs) ensuring dynamic on-demand onboarding."
    echo -e "  ${GREEN}✓ Fail-Safe Containment:${RESET} Fault injection or severance of Vehicle A cannot degrade Vehicle B or Base CSE."
}

# ------------------------------------------------------------------------------
# Main Interactive Dispatcher Loop
# ------------------------------------------------------------------------------
main() {
    while true; do
        print_banner

        echo -e "${CYAN}===> ${WHITE}Interactive Deployment Selection${RESET}\n"
        echo -e "${GRAY}Please choose an execution or deployment option:${RESET}\n"
        echo -e "  ${CYAN}[1]${RESET} Distributed Multi-Host Deployment (Module 1 Base CSE on Server + Module 2 Vehicle AE on Pi 5)"
        echo -e "  ${CYAN}[2]${RESET} Standalone Base CSE Infrastructure (ACME IN-CSE, Zero AEs, Baseline Governance)"
        echo -e "  ${CYAN}[3]${RESET} Standalone Vehicle Application Entity (Raspberry Pi 5 AE Onboarding to Base CSE)"
        echo -e "  ${CYAN}[4]${RESET} Complete Localhost Development Stack (Local Base CSE + InfluxDB + Grafana + Web Portal)"
        echo -e "  ${CYAN}[5]${RESET} systemd Host Service Management (Install, Status, Logs, Restart)"
        echo -e "  ${CYAN}[6]${RESET} Pre-flight Software & Hardware Diagnostics Check (Docker, SSH passwordless, build tools, sysfs, TCP)"
        echo -e "  ${CYAN}[7]${RESET} Telemetry Ingestion & Simulation Pipeline (mTLS 1.3, Native TS-0010 MQTT, Fan-Out)"
        echo -e "  ${CYAN}[8]${RESET} Display Least-Privilege Service Comparison Matrix"
        echo -e "  ${RED}[0]${RESET} Exit\n"

        prompt_input "Enter selection [1-8, 0 to exit] (default: 1): " "1" SELECTION

        case "${SELECTION}" in
            1)
                action_distributed_deployment
                pause_to_continue
                ;;
            2)
                action_base_cse
                pause_to_continue
                ;;
            3)
                action_vehicle_ae
                pause_to_continue
                ;;
            4)
                action_localhost_stack
                pause_to_continue
                ;;
            5)
                action_systemd_management
                ;;
            6)
                action_diagnostics
                pause_to_continue
                ;;
            7)
                action_telemetry_simulation
                pause_to_continue
                ;;
            8)
                action_comparison_matrix
                pause_to_continue
                ;;
            0)
                echo -e "\n${CYAN}Exiting SDV Automotive IoT Orchestrator. Goodbye!${RESET}"
                exit 0
                ;;
            *)
                echo -e "\n${RED}[WARN] Invalid option: '${SELECTION}'. Please enter a number between 0 and 8.${RESET}"
                sleep 1.5
                ;;
        esac
    done
}

# Run main if invoked directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
