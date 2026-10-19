#!/usr/bin/env bash
# ==============================================================================
# Ubuntu Server LTS Prerequisites Installation & Setup Script
# Automotive IoT HVAC Monitoring - FHTW-AIOT Research Cluster
#
# Target Environments:
#   - Ubuntu Server 20.04, 22.04, 24.04, 26.04 LTS
#   - Architectures: x86_64 (amd64), aarch64 (arm64, Raspberry Pi 5 / MEC)
#
# Capabilities:
#   - Checks existing container engines (Docker Compose / Podman Compose)
#   - Automated installation of Docker Engine, containerd, and Compose plugin
#   - Optional installation of Podman & podman-compose
#   - Installs OpenSSL, Make, Git, JQ, Python3, and Python3 venv
#   - Configures non-root Docker permissions for the target user
#   - Self-tests the container engine and execution environment
# ==============================================================================

set -euo pipefail

# ANSI Colour Palettes
CLR_GREEN="\033[1;32m"
CLR_BLUE="\033[1;34m"
CLR_YELLOW="\033[1;33m"
CLR_RED="\033[1;31m"
CLR_CYAN="\033[1;36m"
CLR_RESET="\033[0m"

log_info()    { echo -e "${CLR_BLUE}[INFO]${CLR_RESET} $1"; }
log_ok()      { echo -e "${CLR_GREEN}[OK]${CLR_RESET} $1"; }
log_warn()    { echo -e "${CLR_YELLOW}[WARN]${CLR_RESET} $1"; }
log_error()   { echo -e "${CLR_RED}[ERROR]${CLR_RESET} $1"; }
log_section() { echo -e "\n${CLR_CYAN}=== $1 ===${CLR_RESET}"; }

# Defaults
CONTAINER_ENGINE="docker"
CHECK_ONLY=false
NON_INTERACTIVE=false

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Installs container runtimes (Docker/Podman) and system dependencies on Ubuntu Server LTS.

Options:
    --docker          Install Docker CE and Docker Compose plugin (Default)
    --podman          Install Podman, podman-compose, and podman-docker
    --all             Install both Docker and Podman runtimes
    --check-only      Verify requirements without making modifications
    -y, --yes         Non-interactive mode (assume Yes to all prompts)
    -h, --help        Display this help message

Examples:
    $(basename "$0")                 # Check and install Docker & core dependencies
    $(basename "$0") --podman        # Install Podman ecosystem
    $(basename "$0") --check-only    # Audit current requirements status
EOF
    exit 0
}

# Parse CLI arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --docker)
            CONTAINER_ENGINE="docker"
            shift
            ;;
        --podman)
            CONTAINER_ENGINE="podman"
            shift
            ;;
        --all)
            CONTAINER_ENGINE="all"
            shift
            ;;
        --check-only)
            CHECK_ONLY=true
            shift
            ;;
        -y|--yes|--non-interactive)
            NON_INTERACTIVE=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Resolve execution user for group assignment
TARGET_USER="${SUDO_USER:-$USER}"

# ------------------------------------------------------------------------------
# STEP 1: Audit System Requirements
# ------------------------------------------------------------------------------
audit_requirements() {
    local missing=0

    log_section "Auditing System Requirements"

    # Check OS Release
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        log_info "Operating System: ${NAME:-Linux} ${VERSION:-} (${ID:-ubuntu})"
        if [[ "${ID:-}" != "ubuntu" && "${ID_LIKE:-}" != *"ubuntu"* && "${ID_LIKE:-}" != *"debian"* ]]; then
            log_warn "This script is tailored for Ubuntu Server LTS. Proceeding on ${ID:-unknown}..."
        fi
    else
        log_warn "Unable to detect /etc/os-release."
    fi

    log_info "System Architecture: $(uname -m)"

    # Check Container Compose Command
    COMPOSE_FOUND=""
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_FOUND="docker compose ($(docker compose version --short 2>/dev/null || docker compose version))"
        log_ok "Docker Compose found: ${COMPOSE_FOUND}"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_FOUND="docker-compose ($(docker-compose --version 2>/dev/null))"
        log_ok "Legacy docker-compose found: ${COMPOSE_FOUND}"
    elif command -v podman-compose >/dev/null 2>&1; then
        COMPOSE_FOUND="podman-compose ($(podman-compose --version 2>/dev/null || echo 'present'))"
        log_ok "Podman Compose found: ${COMPOSE_FOUND}"
    else
        log_error "Missing Container Compose: neither 'docker compose', 'docker-compose', nor 'podman-compose' found in PATH."
        missing=$((missing + 1))
    fi

    # Check Docker Daemon access (if Docker is present)
    if command -v docker >/dev/null 2>&1; then
        if docker info >/dev/null 2>&1; then
            log_ok "Docker daemon accessible by user '${TARGET_USER}'."
        else
            log_warn "Docker CLI found, but daemon is not accessible without sudo (User may need 'docker' group)."
            if [ -z "${COMPOSE_FOUND}" ]; then
                missing=$((missing + 1))
            fi
        fi
    fi

    # Check Make
    if command -v make >/dev/null 2>&1; then
        log_ok "Make utility: $(make --version | head -n1)"
    else
        log_error "Missing build tool: 'make' not found."
        missing=$((missing + 1))
    fi

    # Check OpenSSL
    if command -v openssl >/dev/null 2>&1; then
        log_ok "OpenSSL: $(openssl version)"
    else
        log_error "Missing cryptographic tool: 'openssl' not found."
        missing=$((missing + 1))
    fi

    # Check Python 3
    if command -v python3 >/dev/null 2>&1; then
        log_ok "Python 3: $(python3 --version)"
        if python3 -m venv --help >/dev/null 2>&1; then
            log_ok "Python venv module available."
        else
            log_error "Missing Python module: 'python3-venv' not available."
            missing=$((missing + 1))
        fi
    else
        log_error "Missing runtime: 'python3' not found."
        missing=$((missing + 1))
    fi

    # Check JQ & Curl
    if command -v curl >/dev/null 2>&1; then
        log_ok "cURL found."
    else
        log_error "Missing tool: 'curl' not found."
        missing=$((missing + 1))
    fi

    if command -v jq >/dev/null 2>&1; then
        log_ok "JQ processor found."
    else
        log_warn "'jq' JSON parser not found."
        missing=$((missing + 1))
    fi

    # Check Git
    if command -v git >/dev/null 2>&1; then
        log_ok "Git: $(git --version)"
    else
        log_error "Missing tool: 'git' not found."
        missing=$((missing + 1))
    fi

    # Check Ping
    if command -v ping >/dev/null 2>&1; then
        log_ok "Ping utility (iputils-ping) found."
    else
        log_warn "'ping' utility not found."
        missing=$((missing + 1))
    fi

    return ${missing}
}

# Run requirement check
if audit_requirements; then
    log_section "Prerequisites Audit Summary"
    log_ok "All required build, container, and runtime tools are satisfied on this machine!"
    exit 0
fi

if [ "${CHECK_ONLY}" = true ]; then
    log_section "Prerequisites Audit Summary"
    log_error "Prerequisites audit failed. Run without '--check-only' to install missing requirements."
    exit 1
fi

# ------------------------------------------------------------------------------
# STEP 2: Privilege Escalation
# ------------------------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    log_warn "Installation requires superuser (root) privileges."
    log_info "Re-launching setup script with sudo..."
    exec sudo bash "$0" "$@"
fi

# ------------------------------------------------------------------------------
# STEP 3: Core Tooling & Package Repository Setup
# ------------------------------------------------------------------------------
log_section "Installing Core System Dependencies"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    make \
    iputils-ping \
    openssl \
    jq \
    git \
    python3 \
    python3-pip \
    python3-venv \
    net-tools \
    util-linux-extra || apt-get install -y --no-install-recommends util-linux

log_ok "Core utilities installed successfully."

# ------------------------------------------------------------------------------
# STEP 4: Container Engine Installation
# ------------------------------------------------------------------------------
install_docker() {
    log_section "Configuring Official Docker CE Repository"

    # Set up Docker official GPG key
    install -m 0755 -d /etc/apt/keyrings
    if [ ! -f /etc/apt/keyrings/docker.asc ]; then
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
        chmod a+r /etc/apt/keyrings/docker.asc
    fi

    # Detect Ubuntu release codename
    UBUNTU_CODENAME="${UBUNTU_CODENAME:-}"
    if [ -z "${UBUNTU_CODENAME}" ] && [ -f /etc/os-release ]; then
        . /etc/os-release
        UBUNTU_CODENAME="${UBUNTU_CODENAME:-$VERSION_CODENAME}"
    fi
    UBUNTU_CODENAME="${UBUNTU_CODENAME:-noble}"

    ARCH="$(dpkg --print-architecture)"
    echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list

    apt-get update -y || {
        log_warn "Updating repository with codename '${UBUNTU_CODENAME}' failed. Falling back to Ubuntu LTS upstream..."
        echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable" \
            > /etc/apt/sources.list.d/docker.list
        apt-get update -y
    }

    log_info "Installing Docker Engine, containerd, and Docker Compose plugin..."
    apt-get install -y --no-install-recommends \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin

    # Enable and start services
    systemctl enable docker.service || true
    systemctl enable containerd.service || true
    systemctl restart docker.service || true

    # Configure non-root user permissions
    if [ -n "${TARGET_USER}" ] && id "${TARGET_USER}" >/dev/null 2>&1; then
        groupadd -f docker
        usermod -aG docker "${TARGET_USER}"
        log_ok "User '${TARGET_USER}' added to 'docker' group."
    fi

    log_ok "Docker CE and Docker Compose plugin installed successfully."
}

install_podman() {
    log_section "Installing Podman Ecosystem"
    apt-get update -y
    apt-get install -y --no-install-recommends \
        podman \
        podman-compose || {
            log_warn "podman-compose not available via apt. Installing via pip3..."
            python3 -m pip install --upgrade --no-cache-dir podman-compose
        }
    log_ok "Podman and podman-compose installed successfully."
}

if [ "${CONTAINER_ENGINE}" = "docker" ] || [ "${CONTAINER_ENGINE}" = "all" ]; then
    install_docker
fi

if [ "${CONTAINER_ENGINE}" = "podman" ] || [ "${CONTAINER_ENGINE}" = "all" ]; then
    install_podman
fi

# ------------------------------------------------------------------------------
# STEP 5: Verification and Final Self-Test
# ------------------------------------------------------------------------------
log_section "Post-Installation Verification"

if audit_requirements; then
    log_section "Setup Completed Successfully"
    log_ok "All system requirements for SDV Automotive IoT HVAC Monitoring are satisfied!"
    echo -e "\n${CLR_GREEN}Next Steps:${CLR_RESET}"
    if docker info >/dev/null 2>&1; then
        echo "  [READY] Docker permissions are already active in this shell!"
        echo "  Deploy the edge gateway container mesh directly:"
        echo "     $ make deploy-gateway"
    else
        echo "  1. If your user was just added to the docker group, refresh your session:"
        if command -v newgrp >/dev/null 2>&1; then
            echo "     $ newgrp docker"
        else
            echo "     $ su - ${TARGET_USER}   (or log out and re-connect via SSH)"
        fi
        echo "  2. Deploy the edge gateway container mesh:"
        echo "     $ make deploy-gateway"
    fi
    echo "  3. Provision the oneM2M semantic tree:"
    echo "     $ make init-onem2m"
else
    log_warn "Some dependencies could not be automatically resolved. Please inspect the audit output above."
fi
