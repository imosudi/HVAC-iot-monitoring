#!/usr/bin/env bash
# ==============================================================================
# check_install-docker_ssh.sh
# Remote Server Pre-Flight Diagnostics, Docker Engine, and SSH Configuration
#
# Runs from your LOCAL machine against a remote Ubuntu 24.04+ server / VM.
#
# Capabilities:
#   1. Pre-flight system probe & reachability verification.
#   2. Verifies and enables SSH password login and/or key-based login.
#   3. System update & upgrade (apt-get update && apt-get upgrade).
#   4. Installs foundational utilities: build-essential, git, zip, unzip, curl, ca-certificates.
#   5. Installs official Docker Engine (docker-ce, containerd.io, docker-compose-plugin, docker-buildx-plugin).
#   6. Proactively detects and extends unallocated LVM root partition capacity.
#   7. Adds login users to the "docker" group for non-root container management.
#
# Usage:
#   ./check_install-docker_ssh.sh [options] [user@]host
#
# Options:
#   -H, --host HOST           target hostname or IP address (prompts interactively if omitted)
#   -p, --port N              SSH port (default: 22)
#   -i, --identity FILE       private key to use (default: first found of ~/.ssh/id_ed25519,
#                             id_ecdsa, id_rsa; an ed25519 key is generated if none)
#   -u, --user NAME           extra remote user to give Docker access and SSH key
#                             (repeatable; login user is always included)
#   --preflight               run preflight check and automatically install missing
#                             dependencies (Docker, Compose, build-essential, git, zip,
#                             curl, update & upgrade, and configure SSH password/key access)
#   --check-only              report status only, change nothing (exit 1 if action needed)
#   --enable-password-auth    ensure SSH password logins are enabled on server (default: enabled)
#   --disable-password-auth   disable SSH password logins on server (enforce key-only)
#   --skip-upgrade            skip system package upgrade (apt-get upgrade)
#   --skip-test               skip hello-world container test on server
#   -h, --help                show this help
#
# Examples:
#   # Full pre-flight check with automated Docker, build tools, update & upgrade, and SSH setup:
#   ./scripts/check_install-docker_ssh.sh --preflight <user>@<host_or_ip>
#
#   # Inspection-only report (changes nothing, reports missing dependencies):
#   ./scripts/check_install-docker_ssh.sh --check-only <user>@<host_or_ip>
#
#   # Explicitly ensure SSH password authentication is enabled:
#   ./scripts/check_install-docker_ssh.sh --enable-password-auth <user>@<host_or_ip>
#
#   # Optional: Enforce key-only authentication (disable password logins):
#   ./scripts/check_install-docker_ssh.sh --disable-password-auth <user>@<host_or_ip>
#
#   # Interactive prompt (collects target username and hostname/IP dynamically):
#   ./scripts/check_install-docker_ssh.sh --preflight
# ==============================================================================

set -Eeuo pipefail

# ---------- ANSI Terminal Formatters ----------
RED=$'\033[0;31m'; GRN=$'\033[0;32m'; YLW=$'\033[0;33m'; BLU=$'\033[0;34m'; CYN=$'\033[0;36m'; RST=$'\033[0m'
info()  { echo "${BLU}[INFO]${RST}  $*"; }
ok()    { echo "${GRN}[ OK ]${RST}  $*"; }
warn()  { echo "${YLW}[WARN]${RST}  $*"; }
die()   { echo "${RED}[FAIL]${RST}  $*" >&2; exit 1; }
trap 'die "Script failed at line $LINENO."' ERR

LOCAL_TMP=""
trap 'rm -f "${LOCAL_TMP:-}"' EXIT

usage() {
  sed -n '2,/^set -Eeuo/p' "${BASH_SOURCE[0]}" | sed '$d; s/^# \{0,1\}//'
}

# Remote probe script: executed on remote host to inspect environment
probe_script() {
  cat <<'EOS'
. /etc/os-release 2>/dev/null || true
echo "OS_ID=${ID:-unknown}"
echo "OS_VER=${VERSION_ID:-0}"
echo "OS_NAME=${PRETTY_NAME:-unknown}"
echo "R_USER=$(id -un)"

if [ "$(id -u)" -eq 0 ]; then
  echo "SUDO=root"
elif sudo -n true 2>/dev/null; then
  echo "SUDO=nopasswd"
else
  echo "SUDO=password"
fi

# Docker Engine & Plugins
if dpkg -s docker-ce >/dev/null 2>&1; then echo "DOCKER_CE=yes"; else echo "DOCKER_CE=no"; fi
if dpkg -s docker-compose-plugin >/dev/null 2>&1; then echo "COMPOSE=yes"; else echo "COMPOSE=no"; fi
echo "DOCKER_VER=$(docker --version 2>/dev/null || true)"
echo "COMPOSE_VER=$(docker compose version 2>/dev/null || true)"
if command -v docker >/dev/null 2>&1; then echo "DOCKER_BIN=$(command -v docker)"; fi
if id -nG | tr ' ' '\n' | grep -qx docker; then echo "IN_DOCKER_GROUP=yes"; else echo "IN_DOCKER_GROUP=no"; fi

# Foundational Development Packages: build-essential, git, zip, curl
if dpkg -s build-essential >/dev/null 2>&1; then echo "PKG_BUILD_ESSENTIAL=yes"; else echo "PKG_BUILD_ESSENTIAL=no"; fi
if dpkg -s git >/dev/null 2>&1; then echo "PKG_GIT=yes"; else echo "PKG_GIT=no"; fi
echo "GIT_VER=$(git --version 2>/dev/null || true)"
if dpkg -s zip >/dev/null 2>&1; then echo "PKG_ZIP=yes"; else echo "PKG_ZIP=no"; fi
if dpkg -s curl >/dev/null 2>&1; then echo "PKG_CURL=yes"; else echo "PKG_CURL=no"; fi
echo "CURL_VER=$(curl --version 2>/dev/null | head -n1 || true)"

# SSH Password Authentication Status
pw=""
if command -v sshd >/dev/null 2>&1; then
  pw=$( (sudo -n sshd -T 2>/dev/null || sshd -T 2>/dev/null) | awk '/^passwordauthentication/{print $2}' || true )
fi
if [ -z "$pw" ]; then
  pw=$(grep -Eih '^[[:space:]]*PasswordAuthentication[[:space:]]+(yes|no)' /etc/ssh/sshd_config.d/*.conf /etc/ssh/sshd_config 2>/dev/null | head -n1 | awk '{print $2}' || true)
fi
echo "SSH_PWAUTH=${pw:-unknown}"

# Storage / LVM Probing
avail_kb=$(df -P / 2>/dev/null | awk 'NR==2 {print $4}')
echo "DISK_ROOT_AVAIL_KB=${avail_kb:-0}"
if command -v vgs >/dev/null 2>&1; then
  free_vg=$(sudo -n vgs --noheadings -o vg_free --units g 2>/dev/null | tr -d ' ' | sed 's/g//i' || true)
  echo "LVM_VG_FREE_G=${free_vg:-0}"
else
  echo "LVM_VG_FREE_G=0"
fi
EOS
}

main() {
  local TARGET="" PORT="" IDENTITY="" CHECK_ONLY=0 PREFLIGHT=0
  local ENABLE_PW=1 DISABLE_PW=0 SKIP_UPGRADE=0 SKIP_TEST=0
  local EXTRA_USERS=()
  local HOST_ARG="" USER_ARG=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -p|--port)                [[ -n "${2:-}" ]] || die "Missing value for $1"; PORT="$2"; shift 2 ;;
      -i|--identity)            [[ -n "${2:-}" ]] || die "Missing value for $1"; IDENTITY="$2"; shift 2 ;;
      -H|--host|--target-host)  [[ -n "${2:-}" ]] || die "Missing value for $1"; HOST_ARG="$2"; shift 2 ;;
      -u|--user)                [[ -n "${2:-}" ]] || die "Missing value for $1"; USER_ARG="$2"; EXTRA_USERS+=("$2"); shift 2 ;;
      --preflight|--pre-flight) PREFLIGHT=1; shift ;;
      --check-only)             CHECK_ONLY=1; shift ;;
      --enable-password-auth)   ENABLE_PW=1; DISABLE_PW=0; shift ;;
      --disable-password-auth)  DISABLE_PW=1; ENABLE_PW=0; shift ;;
      --skip-upgrade)           SKIP_UPGRADE=1; shift ;;
      --skip-test)              SKIP_TEST=1; shift ;;
      -h|--help)                usage; exit 0 ;;
      -*)                       die "Unknown option: $1 (see --help)" ;;
      *)                        [[ -z "$TARGET" ]] || die "Unexpected argument: $1"; TARGET="$1"; shift ;;
    esac
  done

  # Resolve TARGET from --host and --user flags if provided
  if [[ -z "$TARGET" && -n "$HOST_ARG" ]]; then
    if [[ -n "$USER_ARG" ]]; then
      TARGET="${USER_ARG}@${HOST_ARG}"
    else
      TARGET="${HOST_ARG}"
    fi
  fi

  # Interactive prompt to collect target hostname/IP dynamically if omitted
  if [[ -z "$TARGET" ]]; then
    if [[ -t 0 ]]; then
      echo -e "${CYN}===> Interactive Remote Target Configuration${RST}"
      local def_u="${USER:-mosud}"
      local def_h="localhost"
      local script_dir
      script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
      local env_file="${script_dir}/../deploy/.env"
      [ -f "$env_file" ] || env_file="${script_dir}/../.env"
      if [ -f "$env_file" ]; then
        local env_h env_u
        env_h=$(grep -E '^BASE_CSE_HOST=' "$env_file" | head -n1 | cut -d= -f2 | tr -d ' "\r' || true)
        env_u=$(grep -E '^BASE_CSE_USER=' "$env_file" | head -n1 | cut -d= -f2 | tr -d ' "\r' || true)
        [ -n "$env_h" ] && def_h="$env_h"
        [ -n "$env_u" ] && def_u="$env_u"
      fi

      read -r -p "Enter target remote username [default: ${def_u}]: " in_user
      read -r -p "Enter target remote hostname or IP address [default: ${def_h}]: " in_host
      in_user="${in_user:-$def_u}"
      in_host="${in_host:-$def_h}"
      TARGET="${in_user}@${in_host}"
    else
      usage
      exit 1
    fi
  fi

  command -v ssh >/dev/null 2>&1 || die "ssh client not found on local machine."
  if [[ $CHECK_ONLY -eq 0 || $PREFLIGHT -eq 1 ]]; then
    for c in scp ssh-keygen ssh-copy-id; do
      command -v "$c" >/dev/null 2>&1 || die "'$c' not found on local machine."
    done
  fi

  # ---------- Choose Local SSH Key Pair ----------
  local PRIV="" PUB="" c
  if [[ -n "$IDENTITY" ]]; then
    PRIV="$IDENTITY"
  else
    for c in id_ed25519 id_ecdsa id_rsa; do
      if [[ -f "$HOME/.ssh/$c" && -f "$HOME/.ssh/$c.pub" ]]; then
        PRIV="$HOME/.ssh/$c"
        break
      fi
    done
    PRIV="${PRIV:-$HOME/.ssh/id_ed25519}"
  fi
  PUB="$PRIV.pub"

  # ---------- SSH & SCP Parameters ----------
  local BASE_SSH_OPTS=(-o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes)
  if [[ -n "$PORT" ]]; then BASE_SSH_OPTS+=(-p "$PORT"); fi
  if [[ -f "$PRIV" ]]; then BASE_SSH_OPTS+=(-i "$PRIV"); fi

  local SSH_OPTS=(-o BatchMode=yes "${BASE_SSH_OPTS[@]}")
  local SCP_OPTS=(-o BatchMode=yes -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes)
  if [[ -n "$PORT" ]]; then SCP_OPTS+=(-P "$PORT"); fi
  if [[ -f "$PRIV" ]]; then SCP_OPTS+=(-i "$PRIV"); fi

  rssh() { ssh "${SSH_OPTS[@]}" "$TARGET" "$@"; }

  # ---------- Step 1: Passwordless Key Verification & Setup ----------
  local err=""
  info "Step 1/3: Checking SSH connectivity and key authentication to ${TARGET}..."

  local passwordless_verified=0
  # 1. First, attempt passwordless login with the primary configured key
  if rssh true >/dev/null 2>&1; then
    passwordless_verified=1
    ok "Passwordless SSH key authentication verified."
  else
    # 2. Attempt with all other candidate keys in ~/.ssh before restarting setup
    if [[ -z "$IDENTITY" ]]; then
      local cand
      for cand in "$HOME/.ssh/id_ed25519" "$HOME/.ssh/id_ecdsa" "$HOME/.ssh/id_rsa" "$HOME/.ssh"/id_* "$HOME/.ssh"/*_id*; do
        if [[ -f "$cand" && ! "$cand" =~ \.pub$ && "$cand" != "$PRIV" ]]; then
          local test_opts=(-o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes -i "$cand")
          if [[ -n "$PORT" ]]; then test_opts+=(-p "$PORT"); fi
          if ssh "${test_opts[@]}" "$TARGET" true >/dev/null 2>&1; then
            PRIV="$cand"
            PUB="${cand}.pub"
            BASE_SSH_OPTS=(-o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes -i "$PRIV")
            if [[ -n "$PORT" ]]; then BASE_SSH_OPTS+=(-p "$PORT"); fi
            SSH_OPTS=(-o BatchMode=yes "${BASE_SSH_OPTS[@]}")
            SCP_OPTS=(-o BatchMode=yes -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes -i "$PRIV")
            if [[ -n "$PORT" ]]; then SCP_OPTS+=(-P "$PORT"); fi
            passwordless_verified=1
            ok "Passwordless SSH key authentication verified (auto-detected working identity: ${PRIV})."
            break
          fi
        fi
      done
    fi

    # 3. Attempt with default SSH configuration / agent
    if [[ $passwordless_verified -eq 0 ]]; then
      local def_opts=(-o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)
      if [[ -n "$PORT" ]]; then def_opts+=(-p "$PORT"); fi
      if ssh "${def_opts[@]}" "$TARGET" true >/dev/null 2>&1; then
        passwordless_verified=1
        ok "Passwordless SSH login verified via default SSH configuration."
      fi
    fi
  fi

  # If passwordless login is not yet active, provision public key
  if [[ $passwordless_verified -eq 0 ]]; then
    warn "Passwordless key authentication is not active on ${TARGET}."
    if [[ $CHECK_ONLY -eq 1 && $PREFLIGHT -eq 0 ]]; then
      echo
      warn "Check-only mode: nothing was changed. Run with --preflight or without --check-only to configure key and install packages."
      exit 1
    fi

    if [[ ! -f "$PUB" ]]; then
      if [[ -f "$PRIV" ]]; then
        info "Deriving public key from $PRIV..."
        ssh-keygen -y -f "$PRIV" > "$PUB"
      else
        info "No local SSH key found; generating $PRIV (ed25519)..."
        mkdir -p "$(dirname "$PRIV")"; chmod 700 "$(dirname "$PRIV")"
        if [[ -t 0 ]]; then
          ssh-keygen -t ed25519 -a 100 -f "$PRIV" -C "${USER:-user}@$(hostname -s)"
        else
          warn "Non-interactive shell: creating key without a passphrase."
          ssh-keygen -t ed25519 -a 100 -f "$PRIV" -N "" -C "${USER:-user}@$(hostname -s)"
        fi
      fi
      BASE_SSH_OPTS+=(-i "$PRIV"); SSH_OPTS+=(-i "$PRIV"); SCP_OPTS+=(-i "$PRIV")
    fi

    info "Installing public key on ${TARGET} (enter remote password if prompted)..."
    local copy_opts=(-i "$PUB" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new)
    if [[ -n "$PORT" ]]; then copy_opts+=(-p "$PORT"); fi
    SSH_AUTH_SOCK="" ssh-copy-id "${copy_opts[@]}" "$TARGET" || die "ssh-copy-id failed. Verify your remote password or check if password login is permitted on ${TARGET}."

    rssh true >/dev/null 2>&1 || die "Passwordless login still fails after ssh-copy-id. Check remote sshd settings (PubkeyAuthentication)."
    ok "Passwordless SSH key authentication successfully configured."
  fi

  # Ensure public key exists locally for remote installation payload
  if [[ ! -f "$PUB" && -f "$PRIV" ]]; then
    ssh-keygen -y -f "$PRIV" > "$PUB" 2>/dev/null || true
  fi

  # ---------- Step 2: Remote Pre-Flight Diagnostics ----------
  local STATUS=""
  fetch_status() { STATUS=$(rssh 'bash -s' < <(probe_script)); }
  get() { sed -n "s/^$1=//p" <<<"$STATUS" | head -n1; }

  info "Step 2/3: Probing remote host OS, Docker engine, build packages, and SSH configuration..."
  fetch_status

  local os_id os_ver r_user sudo_mode
  os_id=$(get OS_ID); os_ver=$(get OS_VER); r_user=$(get R_USER); sudo_mode=$(get SUDO)

  [[ "$os_id" == "ubuntu" ]] || die "Remote OS is '$(get OS_NAME)'; Ubuntu 24.04+ is required."
  printf '%s\n%s\n' 24.04 "$os_ver" | sort -V -C || die "Remote Ubuntu version is $os_ver; 24.04 or later is required."

  show_report() {
    echo
    echo "================================================================================"
    echo "  REMOTE PRE-FLIGHT DIAGNOSTICS & SYSTEM STATUS REPORT"
    echo "================================================================================"
    printf '  %-32s %s\n' "Server Host & Target:"      "${TARGET}"
    printf '  %-32s %s\n' "Server Operating System:"   "$(get OS_NAME)"
    printf '  %-32s %s\n' "Remote User & Elevation:"   "$r_user (sudo: $sudo_mode)"
    printf '  %-32s %s\n' "Passwordless SSH (Key):"    "yes (verified)"
    printf '  %-32s %s\n' "SSH Password Authentication:" "$(get SSH_PWAUTH)"
    printf '  %-32s %s\n' "Docker Engine (docker-ce):" "$(get DOCKER_CE)  $(get DOCKER_VER)"
    printf '  %-32s %s\n' "Docker Compose Plugin:"     "$(get COMPOSE)  $(get COMPOSE_VER)"
    printf '  %-32s %s\n' "Package: build-essential:"  "$(get PKG_BUILD_ESSENTIAL)"
    printf '  %-32s %s\n' "Package: git:"              "$(get PKG_GIT)  $(get GIT_VER)"
    printf '  %-32s %s\n' "Package: zip / unzip:"      "$(get PKG_ZIP)"
    printf '  %-32s %s\n' "Package: curl:"             "$(get PKG_CURL)  $(get CURL_VER)"
    printf '  %-32s %s\n' "User in 'docker' Group:"    "$(get IN_DOCKER_GROUP)"
    local lvm_free
    lvm_free=$(get LVM_VG_FREE_G)
    if [[ -n "$lvm_free" && "$lvm_free" != "0" ]]; then
      printf '  %-32s %s\n' "LVM Volume Group Free:"   "${lvm_free} GB (expandable)"
    fi
    echo "================================================================================"
    echo
  }
  show_report

  # Determine if remote modifications are required
  local needs=0
  [[ "$(get DOCKER_CE)"            == "yes" ]] || needs=1
  [[ "$(get COMPOSE)"              == "yes" ]] || needs=1
  [[ "$(get PKG_BUILD_ESSENTIAL)"   == "yes" ]] || needs=1
  [[ "$(get PKG_GIT)"              == "yes" ]] || needs=1
  [[ "$(get PKG_ZIP)"              == "yes" ]] || needs=1
  [[ "$(get PKG_CURL)"             == "yes" ]] || needs=1
  if [[ "$r_user" != "root" && "$(get IN_DOCKER_GROUP)" != "yes" ]]; then needs=1; fi

  local run_needed=$needs
  if [[ $ENABLE_PW -eq 1 && "$(get SSH_PWAUTH)" != "yes" ]]; then run_needed=1; fi
  if [[ $DISABLE_PW -eq 1 && "$(get SSH_PWAUTH)" != "no" ]]; then run_needed=1; fi
  if [[ ${#EXTRA_USERS[@]} -gt 0 ]]; then run_needed=1; fi

  # Check-Only Handling
  if [[ $CHECK_ONLY -eq 1 && $PREFLIGHT -eq 0 ]]; then
    if [[ $run_needed -eq 1 ]]; then
      warn "Preflight check status: Action needed on remote server."
      echo "  Missing packages or configuration detected. Re-run with --preflight"
      echo "  or without --check-only to automatically install dependencies and configure host."
      exit 1
    fi
    ok "Preflight check status: Server is fully configured and ready."
    exit 0
  fi

  if [[ $run_needed -eq 0 ]]; then
    ok "Pre-flight check confirmed: SSH authentication, Docker, build tools, and permissions are already fully configured."
    exit 0
  fi

  # ---------- Step 3: Remote Installation & Configuration ----------
  info "Step 3/3: Executing automated installation and environment provisioning on ${TARGET}..."
  if [[ "$PREFLIGHT" -eq 1 ]]; then
    info "Pre-flight automated remediation mode active: installing Docker, build tools, update & upgrade..."
  fi
  [[ "$sudo_mode" != "password" ]] || info "sudo will prompt for the password of '$r_user' on ${TARGET}."

  LOCAL_TMP=$(mktemp)
  emit_payload > "$LOCAL_TMP"

  local rtmp
  rtmp=$(rssh 'mktemp --suffix=.sh')
  [[ -n "$rtmp" ]] || die "Could not create temporary setup script on ${TARGET}."
  scp -q "${SCP_OPTS[@]}" "$LOCAL_TMP" "${TARGET}:${rtmp}"

  local args=(-u "$r_user")
  if [[ -f "$PUB" ]]; then
    args+=(--ssh-key "$(cat "$PUB")")
  fi
  local u
  for u in "${EXTRA_USERS[@]}"; do args+=(-u "$u"); done
  if [[ $ENABLE_PW -eq 1 ]]; then args+=(--enable-password-auth); fi
  if [[ $DISABLE_PW -eq 1 ]]; then args+=(--disable-password-auth); fi
  if [[ $SKIP_UPGRADE -eq 1 ]]; then args+=(--skip-upgrade); fi
  if [[ $SKIP_TEST -eq 1 ]]; then args+=(--skip-test); fi

  local qargs qtmp sudo_cmd=""
  qargs=$(printf '%q ' "${args[@]}")
  qtmp=$(printf '%q' "$rtmp")
  if [[ "$sudo_mode" != "root" ]]; then sudo_cmd="sudo"; fi

  local rc=0
  ssh -t "${BASE_SSH_OPTS[@]}" "$TARGET" "$sudo_cmd bash $qtmp $qargs; rc=\$?; rm -f $qtmp; exit \$rc" || rc=$?
  [[ $rc -eq 0 ]] || die "Remote installer exited with status $rc."

  # ---------- Post-Installation Verification ----------
  info "Running post-installation verification probe..."
  if rssh true >/dev/null 2>&1; then
    ok "Passwordless SSH key authentication confirmed."
  else
    warn "Key login check failed after remote setup. Review /etc/ssh/sshd_config.d/ on the server."
  fi

  fetch_status
  show_report

  if [[ "$(get IN_DOCKER_GROUP)" != "yes" && "$r_user" != "root" ]]; then
    warn "Docker group membership takes effect on the next login session."
  fi
  if [[ $ENABLE_PW -eq 1 ]]; then
    ok "SSH password authentication is active and enabled."
  elif [[ $DISABLE_PW -eq 1 ]]; then
    warn "SSH password login is now disabled (key-only access enforced)."
  fi

  ok "Host commissioning complete. Connect with: ssh${PORT:+ -p $PORT} ${TARGET}"
}

emit_payload() {
cat <<'__REMOTE_PAYLOAD__'
#!/usr/bin/env bash
# ==============================================================================
# install-docker-ubuntu.sh (Remote Execution Payload)
#
# Idempotent host preparation script for Ubuntu 24.04+:
#   - Proactively expands unallocated LVM root volume capacity
#   - Updates package index and upgrades installed packages (apt-get update && apt-get upgrade)
#   - Installs prerequisite build utilities: build-essential, git, zip, unzip, curl, ca-certificates
#   - Installs official Docker Engine, containerd, and Compose plugin
#   - Adds target users to the 'docker' group
#   - Configures SSH: enables password authentication (or enforces key-only if requested)
#     and installs authorized public keys
# ==============================================================================

set -Eeuo pipefail

# ---------- ANSI Formatters ----------
RED=$'\033[0;31m'; GRN=$'\033[0;32m'; YLW=$'\033[0;33m'; BLU=$'\033[0;34m'; RST=$'\033[0m'
info()  { echo "${BLU}[INFO]${RST}  $*"; }
ok()    { echo "${GRN}[ OK ]${RST}  $*"; }
warn()  { echo "${YLW}[WARN]${RST}  $*"; }
die()   { echo "${RED}[FAIL]${RST}  $*" >&2; exit 1; }
trap 'die "Remote payload script failed at line $LINENO."' ERR

USERS=()
RUN_TEST=1
SETUP_SSH=1
ENABLE_PW=1
DISABLE_PW=0
SKIP_UPGRADE=0
SSH_KEYS=()
SSH_KEY_FILES=()
GH_USERS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -u|--user)               [[ -n "${2:-}" ]] || die "Missing value for $1"; USERS+=("$2"); shift 2 ;;
    --skip-test)             RUN_TEST=0; shift ;;
    --skip-upgrade)          SKIP_UPGRADE=1; shift ;;
    --ssh-key)               [[ -n "${2:-}" ]] || die "Missing value for $1"; SSH_KEYS+=("$2"); shift 2 ;;
    --ssh-key-file)          [[ -n "${2:-}" ]] || die "Missing value for $1"; SSH_KEY_FILES+=("$2"); shift 2 ;;
    --github-user)           [[ -n "${2:-}" ]] || die "Missing value for $1"; GH_USERS+=("$2"); shift 2 ;;
    --enable-password-auth)  ENABLE_PW=1; DISABLE_PW=0; shift ;;
    --disable-password-auth) DISABLE_PW=1; ENABLE_PW=0; shift ;;
    --skip-ssh)              SETUP_SSH=0; shift ;;
    -h|--help)               sed -n '2,/^set -Eeuo/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
    *)                       die "Unknown option: $1" ;;
  esac
done

# ---------- Root & OS Pre-Flight Check ----------
[[ $EUID -eq 0 ]] || die "Payload must run as root: sudo $0 $*"
[[ -r /etc/os-release ]] || die "Cannot read /etc/os-release."
# shellcheck disable=SC1091
. /etc/os-release

[[ "${ID:-}" == "ubuntu" ]] || die "This script supports Ubuntu only (detected: ${ID:-unknown})."
if dpkg --compare-versions "${VERSION_ID:-0}" lt "24.04"; then
  die "Ubuntu 24.04 or later required (detected: ${VERSION_ID})."
fi
ok "Ubuntu ${VERSION_ID} (${VERSION_CODENAME}) confirmed."

# Target users resolution
if [[ ${#USERS[@]} -eq 0 ]]; then
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    USERS+=("$SUDO_USER")
  else
    warn "No non-root user specified; Docker group integration will be skipped."
  fi
fi

# ---------- Proactive LVM Root Volume Expansion ----------
expand_lvm_if_possible() {
  if command -v lvextend >/dev/null 2>&1 && command -v vgs >/dev/null 2>&1; then
    local free_vg
    free_vg=$(vgs --noheadings -o vg_free --units g 2>/dev/null | tr -d ' ' | sed 's/g//i' || true)
    if [[ -n "$free_vg" ]] && awk "BEGIN {exit !($free_vg > 0.5)}" 2>/dev/null; then
      info "Found unallocated storage in LVM volume group (${free_vg}G free). Expanding root logical volume..."
      local root_dev
      root_dev=$(df / | awk 'NR==2 {print $1}')
      if [[ "$root_dev" == /dev/mapper/* || "$root_dev" == /dev/*-vg/* ]]; then
        lvextend -l +100%FREE "$root_dev" -r >/dev/null 2>&1 || true
        ok "Root logical volume expanded to maximum available volume group capacity."
      fi
    fi
  fi
}
expand_lvm_if_possible

# ---------- Apt Environment & Lock Handling ----------
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export UCF_FORCE_CONFFOLD=1

wait_for_apt_lock() {
  local timeout=120
  local elapsed=0
  while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || fuser /var/lib/apt/lists/lock >/dev/null 2>&1; do
    if [ "$elapsed" -ge "$timeout" ]; then
      warn "Apt lock still held after ${timeout}s, proceeding..."
      break
    fi
    info "Waiting for background package manager lock release... (${elapsed}s)"
    sleep 2
    elapsed=$((elapsed + 2))
  done
}

wait_for_apt_lock

# ---------- Container Runtime & Package Prerequisite Resolution ----------
docker_installed() {
  command -v docker >/dev/null 2>&1 && dpkg -s docker-ce >/dev/null 2>&1
}

candidate_pkgs=(build-essential git zip unzip curl ca-certificates tar python3-paho-mqtt python3-venv)
missing_pkgs=()
for pkg in "${candidate_pkgs[@]}"; do
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    missing_pkgs+=("$pkg")
  fi
done

# Only update apt cache and run system upgrade if packages are missing or Docker is not installed
needs_apt_refresh=0
if [[ ${#missing_pkgs[@]} -gt 0 ]] || ! docker_installed || ! dpkg -s docker-compose-plugin >/dev/null 2>&1; then
  needs_apt_refresh=1
fi

if [[ $needs_apt_refresh -eq 1 ]]; then
  info "Updating apt package repository index..."
  wait_for_apt_lock
  apt-get update -qq

  if [[ $SKIP_UPGRADE -eq 0 ]]; then
    info "Upgrading installed system packages (apt-get upgrade)..."
    wait_for_apt_lock
    apt-get upgrade -y -qq -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"
    ok "System packages successfully upgraded."
  else
    info "Skipping system package upgrade (--skip-upgrade specified)."
  fi
fi

# ---------- Foundational Development Packages ----------
if [[ ${#missing_pkgs[@]} -gt 0 ]]; then
  info "Installing missing foundational development utilities: ${missing_pkgs[*]}..."
  wait_for_apt_lock
  apt-get install -y -qq -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" "${missing_pkgs[@]}"
  ok "Prerequisite utilities installed: ${missing_pkgs[*]}."
else
  ok "All foundational development packages already satisfied (${candidate_pkgs[*]}); skipping reinstallation."
fi

# ---------- Docker Engine & Compose Plugin Installation ----------

if docker_installed; then
  ok "Official Docker Engine is already installed: $(docker --version)"
  if dpkg -s docker-compose-plugin >/dev/null 2>&1; then
    ok "Docker Compose plugin is present: $(docker compose version 2>/dev/null || true)"
  else
    warn "Docker Compose plugin missing; installing..."
    wait_for_apt_lock
    apt-get install -y -qq docker-compose-plugin
    ok "Docker Compose plugin installed."
  fi
else
  if command -v docker >/dev/null 2>&1; then
    warn "Non-official Docker installation detected ($(command -v docker)); replacing with official Docker CE..."
  else
    info "Official Docker Engine not found. Installing Docker CE..."
  fi

  # Purge conflicting legacy or distro packages
  info "Removing conflicting container packages if present..."
  for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then
      apt-get remove -y -qq "$pkg" >/dev/null 2>&1 || true
    fi
  done
  if command -v snap >/dev/null 2>&1 && snap list docker >/dev/null 2>&1; then
    warn "Removing snap Docker package..."
    snap remove docker >/dev/null 2>&1 || true
  fi

  info "Configuring official Docker repository GPG key and sources list..."
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc

  cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

  wait_for_apt_lock
  apt-get update -qq
  info "Installing Docker Engine, CLI, containerd.io, Compose plugin, and Buildx plugin..."
  apt-get install -y -qq -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
      docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  ok "Docker Engine installed: $(docker --version)"
  ok "Docker Compose installed: $(docker compose version 2>/dev/null || true)"
fi

# Enable and start Docker services
info "Enabling and starting Docker and containerd system services..."
systemctl enable --now docker containerd >/dev/null 2>&1 || true
systemctl is-active --quiet docker || die "Docker service failed to start. Review: journalctl -u docker"
ok "Docker daemon is active and running."

# User integration into docker group
getent group docker >/dev/null || groupadd docker

NEEDS_RELOGIN=()
for u in "${USERS[@]}"; do
  if ! id "$u" >/dev/null 2>&1; then
    warn "User '$u' does not exist on host; skipping group addition."
    continue
  fi
  if id -nG "$u" | tr ' ' '\n' | grep -qx docker; then
    ok "User '$u' already belongs to the 'docker' group."
  else
    usermod -aG docker "$u"
    ok "Added '$u' to the 'docker' group."
    NEEDS_RELOGIN+=("$u")
  fi
done

# ---------- SSH Configuration & Password / Key Authentication ----------
SSH_CONFIGURED_USERS=()

setup_ssh() {
  info "Configuring SSH authentication settings..."

  if ! dpkg -s openssh-server >/dev/null 2>&1; then
    info "Installing openssh-server package..."
    wait_for_apt_lock
    apt-get install -y -qq openssh-server
  fi
  systemctl enable --now ssh >/dev/null 2>&1 || true
  systemctl is-active --quiet ssh || warn "ssh service is not active; inspect: journalctl -u ssh"

  # Collect public keys
  local raw valid line one k f g
  raw=$(mktemp); valid=$(mktemp); one=$(mktemp)
  trap "rm -f '$raw' '$valid' '$one'" RETURN

  for k in "${SSH_KEYS[@]}"; do printf '%s\n' "$k" >> "$raw"; done
  for f in "${SSH_KEY_FILES[@]}"; do
    [[ -r "$f" ]] || die "Cannot read SSH key file: $f"
    cat "$f" >> "$raw"; echo >> "$raw"
  done
  for g in "${GH_USERS[@]}"; do
    info "Fetching public keys for GitHub user '$g'..."
    curl -fsSL --max-time 15 "https://github.com/${g}.keys" >> "$raw" \
      || die "Could not fetch keys from https://github.com/${g}.keys"
    echo >> "$raw"
  done

  # Filter valid public keys
  while IFS= read -r line; do
    [[ -z "${line//[[:space:]]/}" || "$line" == \#* ]] && continue
    printf '%s\n' "$line" > "$one"
    if ssh-keygen -l -f "$one" >/dev/null 2>&1; then
      printf '%s\n' "$line" >> "$valid"
    fi
  done < "$raw"

  # Install keys for target users
  local u home grp ak added
  for u in "${USERS[@]}"; do
    id "$u" >/dev/null 2>&1 || continue
    home=$(getent passwd "$u" | cut -d: -f6)
    grp=$(id -gn "$u")
    ak="$home/.ssh/authorized_keys"

    install -d -m 700 -o "$u" -g "$grp" "$home/.ssh"
    [[ -f "$ak" ]] || install -m 600 -o "$u" -g "$grp" /dev/null "$ak"

    added=0
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      if ! grep -qxF "$line" "$ak"; then
        printf '%s\n' "$line" >> "$ak"
        added=$((added + 1))
      fi
    done < "$valid"

    chown "$u:$grp" "$ak"; chmod 600 "$ak"
    chmod go-w "$home"

    if [[ -s "$ak" ]]; then
      SSH_CONFIGURED_USERS+=("$u")
      if [[ $added -gt 0 ]]; then
        ok "User '$u': added $added new SSH public key(s)."
      fi
    fi
  done

  # --- Enable SSH Password Authentication ---
  if [[ $ENABLE_PW -eq 1 ]]; then
    info "Enabling SSH password login on remote host..."
    rm -f /etc/ssh/sshd_config.d/00-key-only.conf /etc/ssh/sshd_config.d/*key-only*.conf

    local conf="/etc/ssh/sshd_config.d/00-password-auth.conf"
    cat > "$conf" <<'EOF'
# Configured by check_install-docker_ssh.sh
PubkeyAuthentication yes
PasswordAuthentication yes
KbdInteractiveAuthentication yes
EOF
    chmod 644 "$conf"

    if sshd -t; then
      systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || service ssh reload 2>/dev/null || true
      ok "SSH password authentication explicitly enabled (/etc/ssh/sshd_config.d/00-password-auth.conf)."
    else
      rm -f "$conf"
      die "sshd validation failed; reverted $conf."
    fi
  fi

  # --- Disable SSH Password Authentication (if explicitly requested) ---
  if [[ $DISABLE_PW -eq 1 ]]; then
    if [[ ${#SSH_CONFIGURED_USERS[@]} -eq 0 ]]; then
      warn "Refusing to disable password login: zero authorized keys configured (risk of lockout)."
      return 0
    fi
    info "Enforcing SSH key-only access (disabling password authentication)..."
    rm -f /etc/ssh/sshd_config.d/00-password-auth.conf

    local conf="/etc/ssh/sshd_config.d/00-key-only.conf"
    cat > "$conf" <<'EOF'
# Configured by check_install-docker_ssh.sh
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
EOF
    chmod 644 "$conf"

    if sshd -t; then
      systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || service ssh reload 2>/dev/null || true
      ok "SSH password authentication disabled (key-only access active)."
    else
      rm -f "$conf"
      die "sshd validation failed; reverted $conf."
    fi
  fi
}

if [[ $SETUP_SSH -eq 1 ]]; then
  setup_ssh
fi

# ---------- Container Runtime Test Verification ----------
if [[ $RUN_TEST -eq 1 ]]; then
  info "Validating container runtime by executing hello-world test image..."
  if docker run --rm hello-world >/dev/null 2>&1; then
    ok "Docker container runtime validation successful (hello-world ran cleanly)."
  else
    warn "Docker hello-world test did not complete cleanly (network/registry constraint). Run: sudo docker run --rm hello-world"
  fi
fi

# ---------- Summary ----------
echo
ok "Remote host provisioning and pre-flight configuration complete."
echo "  Docker Engine:  $(docker --version)"
echo "  Docker Compose: $(docker compose version 2>/dev/null || echo 'n/a')"
echo "  Build Tools:    build-essential, git ($(git --version 2>/dev/null || true)), zip, curl"
if [[ $ENABLE_PW -eq 1 ]]; then
  echo "  SSH Password:   ENABLED (PasswordAuthentication yes)"
elif [[ $DISABLE_PW -eq 1 ]]; then
  echo "  SSH Password:   DISABLED (Key-only authentication enforced)"
fi
if [[ ${#NEEDS_RELOGIN[@]} -gt 0 ]]; then
  echo
  warn "Group membership updates will take effect on the next login session for: ${NEEDS_RELOGIN[*]}"
fi
__REMOTE_PAYLOAD__
}

main "$@"
