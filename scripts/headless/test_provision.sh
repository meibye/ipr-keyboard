#!/usr/bin/env bash
#
# test_provision.sh — Post-provision validation for a fresh Raspberry Pi Zero W
#
# Verifies every artifact produced by the provisioning sequence:
#
#   Step 1  sys_install_packages.sh      → system packages, uv, /mnt/irispen
#   Step 2  sys_setup_venv.sh            → Python venv with dev extras
#   Step 3  svc_install_bt_gatt_hid.sh   → BLE agent + HID daemon + units
#   Step 4  ble_install_helper.sh        → bt_kb_send helper scripts
#   Step 5  install_provision_service.sh → hotspot service + TLS certificates
#   Step 6  deploy_full_update.sh        → all services up, health endpoint OK
#           (…which also runs install_gpio_support.sh and install_oled_support.sh)
#
# Can be run on the Pi directly or uploaded and executed via ipr-rpi-dev-ssh MCP.
# Pass --auto to skip all manual/interactive steps (suitable for MCP sessions).
#
# Everything printed is also written, without colour escapes, to
# /opt/ipr_state/provision_verify.log -- so the last audit a device ran can be
# read back later, and over SSH.  --report FILE writes elsewhere, --no-report
# writes nothing, and an unwritable path costs the report, not the run.
#
# Usage:
#   sudo bash ~/dev/ipr-keyboard/scripts/headless/test_provision.sh [--auto]
#                                                   [--report FILE | --no-report]
#
# Connection wiring diagram:
#   No hardware wiring required — this script tests software state only.
#   For hardware (GPIO/LED/reed) validation, run test_gpio_led_reed.sh separately.
#
# category: Headless
# purpose: Validate that all provisioning steps completed correctly on a new Pi
# sudo: yes

set -uo pipefail
# `cmd | grep -q` under pipefail is a race: grep exits at its first match,
# cmd can then die of SIGPIPE, and pipefail reports the whole pipeline as
# failed -- a running service reads as "inactive".  grepq reads to the end.
grepq() { grep "$@" >/dev/null; }


# ── invoking user resolution ───────────────────────────────────────────────────

# Which account is this audit about?
#
# Not "whoever typed the command": the checks are about the account that runs
# the application -- its venv, its home, its group membership, its sudoers
# grants.  `${SUDO_USER:-$USER}` got that right only for a human typing
# `sudo test_provision.sh`.  Started from the provisioning wizard's systemd
# resume unit there is no SUDO_USER, so it resolved to root and then checked
# /root/dev/ipr-keyboard: 14 checks failed on a perfectly good device, and the
# unattended run reported failure when it had succeeded.
#
# APP_USER from /opt/ipr_common.env is the authoritative answer and wins when
# it is there; SUDO_USER and $USER remain the fallbacks for a device that has
# not been provisioned yet.
# IPR_COMMON_ENV exists so this is testable off-device; it is the real path
# everywhere else.
IPR_COMMON_ENV="${IPR_COMMON_ENV:-/opt/ipr_common.env}"

_env_value() {  # _env_value KEY -- from the env file, empty if absent
    [ -r "$IPR_COMMON_ENV" ] || return 0
    awk -F= -v k="$1" '
        $0 ~ "^[[:space:]]*"k"[[:space:]]*=" { gsub(/["\r ]/,"",$2); print $2; exit }
    ' "$IPR_COMMON_ENV"
}

_INVOKING_USER="$(_env_value APP_USER)"
if [ -z "$_INVOKING_USER" ]; then
    _INVOKING_USER="${SUDO_USER:-$USER}"
fi
_INVOKING_HOME=$(getent passwd "$_INVOKING_USER" | cut -d: -f6)

_REPO_DIR="$(_env_value REPO_DIR)"
PROJECT_DIR="${IPR_PROJECT_ROOT:+$IPR_PROJECT_ROOT/ipr-keyboard}"
PROJECT_DIR="${PROJECT_DIR:-${_REPO_DIR:-$_INVOKING_HOME/dev/ipr-keyboard}}"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
VENV_PYTEST="$PROJECT_DIR/.venv/bin/pytest"

# ── arguments ─────────────────────────────────────────────────────────────────

AUTO=0
REPORT_FILE="${REPORT_FILE:-/opt/ipr_state/provision_verify.log}"
_args=("$@")
for _i in "${!_args[@]}"; do
    case "${_args[$_i]}" in
        --auto|-y)   AUTO=1 ;;
        --report)    REPORT_FILE="${_args[$((_i+1))]:-}" ;;
        --no-report) REPORT_FILE="" ;;
    esac
done

# ── report file ───────────────────────────────────────────────────────────────
#
# A standalone run used to leave nothing behind: the result lived in the
# terminal it was typed in, so neither a later reader nor an operator working
# over SSH could tell what the device last reported.  Everything printed below
# is therefore copied to REPORT_FILE as well, with the colour escapes removed
# so the file is readable.  The terminal keeps its colours.
#
# Never fatal: an unwritable location (a non-root run, a read-only /opt) costs
# the report, not the audit.
if [ -n "$REPORT_FILE" ]; then
    if mkdir -p "$(dirname "$REPORT_FILE")" 2>/dev/null && : > "$REPORT_FILE" 2>/dev/null; then
        exec > >(tee >(sed -u 's/\x1b\[[0-9;]*m//g' > "$REPORT_FILE")) 2>&1
        _REPORT_ACTIVE=1
    else
        echo "!! cannot write $REPORT_FILE - continuing without a report file" >&2
        REPORT_FILE=""
    fi
fi

# ── result tracking ────────────────────────────────────────────────────────────

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
RESULT_LOG=()

# ── colours ───────────────────────────────────────────────────────────────────

if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
    CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; RESET=''
fi

# ── helpers ───────────────────────────────────────────────────────────────────

section() {
    echo ""
    echo -e "${BOLD}${CYAN}══════════════════════════════════════════════════════════${RESET}"
    echo -e "${BOLD}${CYAN}  $*${RESET}"
    echo -e "${BOLD}${CYAN}══════════════════════════════════════════════════════════${RESET}"
}

info()  { echo -e "  ${CYAN}·${RESET} $*"; }
warn()  { echo -e "  ${YELLOW}⚠${RESET}  $*"; }

record_pass() {
    local id="$1"; shift
    echo -e "  ${GREEN}✓ PASS${RESET}  [$id] $*"
    RESULT_LOG+=("PASS|$id|$*")
    PASS_COUNT=$((PASS_COUNT + 1))
}

record_fail() {
    local id="$1"; shift
    echo -e "  ${RED}✗ FAIL${RESET}  [$id] $*"
    RESULT_LOG+=("FAIL|$id|$*")
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

record_skip() {
    local id="$1"; shift
    echo -e "  ${YELLOW}⊘ SKIP${RESET}  [$id] $*"
    RESULT_LOG+=("SKIP|$id|$*")
    SKIP_COUNT=$((SKIP_COUNT + 1))
}

# Run a shell expression; record pass/fail.
check() {
    local id="$1"; local label="$2"; shift 2
    if eval "$@" >/dev/null 2>&1; then
        record_pass "$id" "$label"
    else
        record_fail "$id" "$label"
    fi
}

# Print a manual-action prompt; skip in --auto or non-interactive mode.
manual_step() {
    echo ""
    echo -e "  ${BOLD}${YELLOW}⚡ MANUAL ACTION REQUIRED${RESET}"
    for line in "$@"; do
        echo -e "  ${YELLOW}▸${RESET} $line"
    done
    echo ""
    if [[ "$AUTO" -eq 1 ]]; then
        echo -e "  ${YELLOW}(--auto mode — manual step skipped)${RESET}"
        return 1
    elif [ -t 0 ]; then
        printf "  Press ENTER when done, or type 'skip' to skip: "
        read -r _resp
        [[ "$_resp" == "skip" ]] && return 1
        return 0
    else
        echo -e "  ${YELLOW}(Non-interactive session — manual step skipped)${RESET}"
        return 1
    fi
}

# ── header ────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}ipr-keyboard — Post-Provision Validation${RESET}"
echo -e "  Project root : $PROJECT_DIR"
echo -e "  User         : $_INVOKING_USER"
echo -e "  Date         : $(date)"
echo -e "  Auto mode    : $( [[ $AUTO -eq 1 ]] && echo yes || echo no )"

# ═══════════════════════════════════════════════════════════════════════════════
section "A — System packages  (sys_install_packages.sh)"
# ═══════════════════════════════════════════════════════════════════════════════

info "Checking required apt packages and OS-level configuration ..."

check A.1  "git installed"               "command -v git"
check A.2  "python3 installed"           "command -v python3"
check A.3  "python3-venv available"      "python3 -m venv --help"
check A.4  "bluez / bluetoothctl"        "command -v bluetoothctl"
check A.5  "nmcli available"             "command -v nmcli"
check A.6  "openssl available"           "command -v openssl"
check A.7  "curl available"              "command -v curl"
check A.8  "jmtpfs installed"            "command -v jmtpfs"
check A.9  "uv available"               "command -v uv"
# The pen's FUSE mount is private to the app user: as root, even [ -d ] on
# it fails with EACCES, so consult /proc/mounts first.
check A.10 "/mnt/irispen mount point"    "grep ' /mnt/irispen ' /proc/mounts || [ -d /mnt/irispen ]"
check A.11 "Bluetooth experimental mode" \
           "grep -q 'Experimental=true' /etc/bluetooth/main.conf"
check A.12 "bluetooth.service enabled"   \
           "systemctl is-enabled bluetooth.service"

# ═══════════════════════════════════════════════════════════════════════════════
section "B — Python virtual environment  (sys_setup_venv.sh)"
# ═══════════════════════════════════════════════════════════════════════════════

info "Venv path: $PROJECT_DIR/.venv"

check B.1 ".venv directory exists"          "[ -d '$PROJECT_DIR/.venv' ]"
check B.2 "Python binary in venv"           "[ -x '$VENV_PYTHON' ]"
check B.3 "pytest binary in venv"           "[ -x '$VENV_PYTEST' ]"
check B.4 "ipr_keyboard package importable" "'$VENV_PYTHON' -c 'import ipr_keyboard'"
check B.5 "Flask importable"                "'$VENV_PYTHON' -c 'import flask'"
check B.6 "werkzeug importable"             "'$VENV_PYTHON' -c 'import werkzeug'"

info "Running unit tests (this may take ~30 s) ..."
if [[ -x "$VENV_PYTEST" && -d "$PROJECT_DIR/tests" ]]; then
    # --timeout needs the pytest-timeout plugin, which is not part of the
    # project's [dev] extras; pass it only when the plugin is installed.
    _PYTEST_TIMEOUT=()
    if "$VENV_PYTHON" -c "import pytest_timeout" 2>/dev/null; then
        _PYTEST_TIMEOUT=(--timeout=60)
    fi
    # Run as the invoking user, never as root: the tests write
    # logs/ipr_keyboard.log through the app logger, and a root-owned log file
    # makes ipr_keyboard.service crash-loop with "Permission denied" at its
    # next restart.  (Seen on the dev board after a sudo run of this script.)
    _AS_USER=(sudo -u "$_INVOKING_USER" -H)
    if "${_AS_USER[@]}" "$VENV_PYTEST" "$PROJECT_DIR/tests" \
           --ignore="$PROJECT_DIR/tests/e2e" \
           -q --tb=no --no-header -p no:cacheprovider \
           "${_PYTEST_TIMEOUT[@]}" 2>/dev/null | grep -E '^[0-9]+ passed'; then
        record_pass B.7 "pytest unit tests pass"
    else
        # Capture a brief failure summary
        PYTEST_OUT=$("${_AS_USER[@]}" "$VENV_PYTEST" "$PROJECT_DIR/tests" \
            --ignore="$PROJECT_DIR/tests/e2e" \
            -q --tb=line --no-header -p no:cacheprovider \
            "${_PYTEST_TIMEOUT[@]}" 2>&1 | tail -20 || true)
        record_fail B.7 "pytest unit tests pass"
        warn "pytest output (last 20 lines):"
        echo "$PYTEST_OUT" | sed 's/^/    /'
    fi
else
    record_skip B.7 "pytest unit tests — venv or tests/ not found"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "C — BLE service installation  (svc_install_bt_gatt_hid.sh)"
# ═══════════════════════════════════════════════════════════════════════════════

check C.1 "bt_hid_agent_unified.py installed"  \
          "[ -x /usr/local/bin/bt_hid_agent_unified.py ]"
check C.2 "bt_hid_ble_daemon.py installed"      \
          "[ -x /usr/local/bin/bt_hid_ble_daemon.py ]"
check C.3 "bt_hid_agent_unified.service unit"   \
          "[ -f /etc/systemd/system/bt_hid_agent_unified.service ]"
check C.4 "bt_hid_ble.service unit"             \
          "[ -f /etc/systemd/system/bt_hid_ble.service ]"
check C.4b "FIFO /run/ipr_bt_keyboard_fifo writable by $_INVOKING_USER" \
          "[ -p /run/ipr_bt_keyboard_fifo ] && runuser -u '$_INVOKING_USER' -- test -w /run/ipr_bt_keyboard_fifo"
check C.5 "/opt/ipr_common.env present"         \
          "[ -f /opt/ipr_common.env ]"
check C.6 "bluetooth override.conf present"     \
          "[ -f /etc/systemd/system/bluetooth.service.d/override.conf ]"
check C.6b "adapter is LE-only (no br/edr in btmgmt current settings)" \
          "! script -qec 'btmgmt info' /dev/null 2>/dev/null | grep 'current settings' | grep 'br/edr'"
check C.7 "BT override disables unwanted plugins" \
          "grep -q -- '--noplugin' /etc/systemd/system/bluetooth.service.d/override.conf"

# ═══════════════════════════════════════════════════════════════════════════════
section "D — BT keyboard helper  (ble_install_helper.sh)"
# ═══════════════════════════════════════════════════════════════════════════════

check D.1 "bt_kb_send helper installed"       "[ -x /usr/local/bin/bt_kb_send ]"
check D.2 "bt_kb_send_file helper installed"  "[ -x /usr/local/bin/bt_kb_send_file ]"

# ═══════════════════════════════════════════════════════════════════════════════
section "E — Provision service installation  (install_provision_service.sh)"
# ═══════════════════════════════════════════════════════════════════════════════

check E.1 "ipr-provision.sh installed"       "[ -x /usr/local/sbin/ipr-provision.sh ]"
check E.2 "ipr-provision.service unit"       "[ -f /etc/systemd/system/ipr-provision.service ]"
check E.3 "ipr-cert-gen.sh installed"        "[ -x /usr/local/sbin/ipr-cert-gen.sh ]"
check E.4 "ipr-cert-renew.sh installed"      "[ -x /usr/local/sbin/ipr-cert-renew.sh ]"
check E.5 "ipr-cert-renew.service unit"      "[ -f /etc/systemd/system/ipr-cert-renew.service ]"
check E.6 "ipr-cert-renew.timer enabled"     \
          "systemctl is-enabled ipr-cert-renew.timer"

# ═══════════════════════════════════════════════════════════════════════════════
section "F — TLS certificates  (gen_ipr_ssl_cert.sh)"
# ═══════════════════════════════════════════════════════════════════════════════

check F.1 "/etc/ipr-ssl/ directory"            "[ -d /etc/ipr-ssl ]"
check F.2 "CA certificate present"             "[ -f /etc/ipr-ssl/ca.crt ]"
check F.3 "Server certificate present"         "[ -f /etc/ipr-ssl/server.crt ]"
check F.4 "Server key present"                 "[ -f /etc/ipr-ssl/server.key ]"
check F.5 "Server key permissions (0640)"      \
          "[ \"$(stat -c '%a' /etc/ipr-ssl/server.key 2>/dev/null)\" = '640' ]"
check F.6 "Server cert not expired"            \
          "openssl x509 -checkend 0 -noout -in /etc/ipr-ssl/server.crt"
check F.7 "Server cert covers 10.42.0.1"       \
          "openssl x509 -noout -text -in /etc/ipr-ssl/server.crt | grep '10.42.0.1'"
check F.8 "Server cert covers .local hostname" \
          "openssl x509 -noout -text -in /etc/ipr-ssl/server.crt | grep '.local'"

# Warn if server cert expires within 30 days
if [ -f /etc/ipr-ssl/server.crt ]; then
    if ! openssl x509 -checkend $((30 * 86400)) -noout -in /etc/ipr-ssl/server.crt 2>/dev/null; then
        warn "F.6: Server certificate expires within 30 days — run: sudo ipr-cert-renew.sh"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "G — Service stack health  (deploy_full_update.sh)"
# ═══════════════════════════════════════════════════════════════════════════════

info "Checking all services are active ..."

check G.1 "NetworkManager active"            "systemctl is-active NetworkManager"
check G.2 "bluetooth.service active"         "systemctl is-active bluetooth"
check G.3 "bt_hid_agent_unified active"      "systemctl is-active bt_hid_agent_unified"
check G.4 "bt_hid_ble active"               "systemctl is-active bt_hid_ble"
check G.5 "ipr_keyboard.service active"      "systemctl is-active ipr_keyboard"

# ipr-provision is oneshot+RemainAfterExit — check enabled, not active
# (it may be inactive if no hotspot trigger fired since last boot)
check G.6 "ipr-provision.service enabled"    "systemctl is-enabled ipr-provision"

info "Live service status:"
for unit in bluetooth.service bt_hid_agent_unified.service bt_hid_ble.service \
            ipr_keyboard.service ipr-provision.service; do
    state=$(systemctl is-active "$unit" 2>/dev/null || echo "unknown")
    printf "    %-42s %s\n" "$unit" "$state"
done

# ═══════════════════════════════════════════════════════════════════════════════
section "H — Application health"
# ═══════════════════════════════════════════════════════════════════════════════

# Allow a few seconds for ipr_keyboard to be ready if it just started
sleep 2

# The dashboard listens on LogPort from config.json (443 in production; the
# code default).  Probe that port, HTTPS first, then plain HTTP (dev, no certs).
_LOG_PORT=443
if [ -f "$PROJECT_DIR/config.json" ] && command -v python3 >/dev/null 2>&1; then
    _LOG_PORT=$(python3 -c "import json;print(json.load(open('$PROJECT_DIR/config.json')).get('LogPort',443))" 2>/dev/null || echo 443)
fi
info "Testing health endpoint on port $_LOG_PORT (LogPort from config.json) ..."
HEALTH_BODY=$(curl -sk --max-time 5 "https://localhost:${_LOG_PORT}/health" 2>/dev/null || true)
if echo "$HEALTH_BODY" | grep '"ok"'; then
    record_pass H.1 "HTTPS /health returns ok on port $_LOG_PORT"
else
    HEALTH_BODY_HTTP=$(curl -s --max-time 5 "http://localhost:${_LOG_PORT}/health" 2>/dev/null || true)
    if echo "$HEALTH_BODY_HTTP" | grep '"ok"'; then
        record_pass H.1 "HTTP /health returns ok on port $_LOG_PORT (HTTPS not available)"
    else
        record_fail H.1 "/health reachable on port $_LOG_PORT (HTTPS and HTTP both failed)"
        warn "HTTPS response: ${HEALTH_BODY:-<empty>}"
    fi
fi
if [ "$_LOG_PORT" != "443" ]; then
    warn "LogPort is $_LOG_PORT — production devices use 443 so https://<host>.local/ and https://10.42.0.1/setup/ work"
fi

check H.2 "config.json present (seeded on first run)" \
          "[ -f '$PROJECT_DIR/config.json' ]"
check H.3 "users.json present (seeded on first run)"  \
          "[ -f '$PROJECT_DIR/users.json' ]"
check H.4 "admin_initial_password.txt written"        \
          "[ -f '$PROJECT_DIR/admin_initial_password.txt' ]"

if [ -f "$PROJECT_DIR/admin_initial_password.txt" ]; then
    _INITIAL_PWD=$(cat "$PROJECT_DIR/admin_initial_password.txt")
    info "Initial admin password: $_INITIAL_PWD"
    info "(change this after first login)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "I — Script permissions"
# ═══════════════════════════════════════════════════════════════════════════════

info "Verifying all scripts under $PROJECT_DIR/scripts/ have the executable flag ..."

_MISSING_X=()
while IFS= read -r -d '' _f; do
    if [ ! -x "$_f" ]; then
        _MISSING_X+=("$_f")
    fi
done < <(find "$PROJECT_DIR/scripts" \( -name "*.sh" -o -name "*.py" \) -print0 2>/dev/null)

if [ ${#_MISSING_X[@]} -eq 0 ]; then
    record_pass I.1 "All scripts/  files are executable"
else
    record_fail I.1 "All scripts/ files are executable (${#_MISSING_X[@]} missing +x)"
    warn "Run: find $PROJECT_DIR/scripts \\( -name '*.sh' -o -name '*.py' \\) -exec chmod +x {} +"
    for _f in "${_MISSING_X[@]}"; do
        warn "  missing +x: $_f"
    done
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "K — Status LED and magnet  (install_gpio_support.sh)"
# ═══════════════════════════════════════════════════════════════════════════════

_BOOT_CFG=/boot/firmware/config.txt
[ -f "$_BOOT_CFG" ] || _BOOT_CFG=/boot/config.txt
check K.1 "RPi.GPIO importable from the app venv"           "'$PROJECT_DIR/.venv/bin/python' -c 'import RPi.GPIO'"
check K.2 "config.txt drives the LED at power-on (gpio= line)"           "grep -q '^gpio=.*=op,dh' '$_BOOT_CFG'"
check K.3 "ipr-led-boot.service installed and enabled"           "systemctl is-enabled --quiet ipr-led-boot.service"
check K.4 "ipr_keyboard.service hands over the LED (Conflicts drop-in)"           "grep -q 'Conflicts=ipr-led-boot.service' /etc/systemd/system/ipr_keyboard.service.d/10-led-boot.conf"
check K.5 "ipr_hotspot_ctl.sh installed"           "[ -x /usr/local/bin/ipr_hotspot_ctl.sh ]"
check K.6 "sudoers lets $_INVOKING_USER run ipr_hotspot_ctl.sh without a password"           "sudo -n -l -U '$_INVOKING_USER' 2>/dev/null | grep ipr_hotspot_ctl.sh"
check K.7 "ipr-provision.service has ExecStop (hotspot stops cleanly)"           "grep -q '^ExecStop=' /etc/systemd/system/ipr-provision.service"
check K.8 "hotspot script honours the runtime request file"           "grep -q 'ipr-hotspot.request' /usr/local/sbin/ipr-provision.sh"
check K.11 "ipr-led-halt.service enabled (LED off = safe to unplug)" \
          "systemctl is-enabled --quiet ipr-led-halt.service"
check K.10 "ipr_keyboard.service has no CapabilityBoundingSet (sudo works inside the service)" \
          "! grep -q '^CapabilityBoundingSet=' /etc/systemd/system/ipr_keyboard.service"
if journalctl -u ipr_keyboard.service -b --no-pager 2>/dev/null | grep 'GPIO monitor started'; then
    record_pass K.9 "GPIO monitor running in ipr_keyboard.service (this boot)"
elif journalctl -u ipr_keyboard.service -b --no-pager 2>/dev/null | grep 'GPIO monitor disabled'; then
    record_fail K.9 "GPIO monitor running in ipr_keyboard.service (disabled — see journal)"
    warn "$(journalctl -u ipr_keyboard.service -b --no-pager 2>/dev/null | grep 'GPIO monitor disabled' | tail -1)"
else
    record_skip K.9 "GPIO monitor running — no GPIO line in this boot's journal (GpioEnabled=false?)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "L — Network exposure  (install_firewall.sh)"
# ═══════════════════════════════════════════════════════════════════════════════

check L.1 "nftables installed"                       "command -v nft"
check L.2 "ipr-firewall.sh installed"                "[ -x /usr/local/sbin/ipr-firewall.sh ]"
check L.3 "ipr_mode_ctl.sh installed"                "[ -x /usr/local/bin/ipr_mode_ctl.sh ]"
check L.4 "ipr-firewall.service enabled"             "systemctl is-enabled --quiet ipr-firewall.service"
check L.5 "NetworkManager dispatcher hook installed" "[ -x /etc/NetworkManager/dispatcher.d/90-ipr-firewall ]"
check L.6 "mode file present"                        "[ -f /var/lib/ipr-keyboard/mode ]"
check L.7 "sudoers lets $_INVOKING_USER run ipr_mode_ctl.sh" \
          "sudo -n -l -U '$_INVOKING_USER' 2>/dev/null | grep ipr_mode_ctl.sh"
check L.8 "nftables table ipr_fw loaded with DROP policy" \
          "nft list table inet ipr_fw 2>/dev/null | grep 'policy drop'"
_MODE=$(cat /var/lib/ipr-keyboard/mode 2>/dev/null || echo production)
_HS_UP=0; nmcli -t -f NAME con show --active 2>/dev/null | grep -x ipr-hotspot && _HS_UP=1
if [ "$_MODE" = "development" ]; then
    check L.9 "development mode: ssh + dashboard rule present" \
              "nft list table inet ipr_fw 2>/dev/null | grep 'dport { 22, 443 } accept'"
    warn "Device is in DEVELOPMENT mode — switch to production when commissioning is done:"
    warn "  sudo ipr_mode_ctl.sh production   (or hold the magnet 6 s)"
else
    check L.9 "production mode: ssh/dashboard closed (reset for open sessions, drop for new)" \
              "nft list table inet ipr_fw 2>/dev/null | grep 'dport { 22, 443 } reject with tcp reset'"
fi
if [ "$_HS_UP" -eq 1 ]; then
    check L.10 "hotspot up: setup portal (443) allowed from 10.42.0.0/24 only" \
               "nft list table inet ipr_fw 2>/dev/null | grep '10.42.0.0/24 tcp dport 443'"
else
    record_skip L.10 "hotspot rules (hotspot not active)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "M — IrisPen automount and observability"
# ═══════════════════════════════════════════════════════════════════════════════

check M.1 "jmtpfs installed"                          "command -v jmtpfs"
check M.2 "udev rule exposes the pen to systemd"      "grep 'SYSTEMD_ALIAS' /etc/udev/rules.d/69-irispen-mtp.rules"
check M.3 "irispen-mount.service installed"           "[ -f /etc/systemd/system/irispen-mount.service ]"
if ls /sys/bus/usb/devices/*/idProduct >/dev/null 2>&1 && grep -lq 2008 /sys/bus/usb/devices/*/idProduct 2>/dev/null; then
    check M.4 "pen plugged in: mounted at /mnt/irispen" "grep ' /mnt/irispen fuse.jmtpfs ' /proc/mounts"
    check M.5 "irispen-mount.service active"           "systemctl is-active --quiet irispen-mount.service"
    if [ -n "${_INVOKING_USER:-}" ]; then
        check M.6 "app user can list the pen's files" "runuser -u '$_INVOKING_USER' -- ls /mnt/irispen"
    fi
else
    record_skip M.4 "pen mounted (pen not plugged in)"
fi
check M.7 "journal is persistent (journald.conf.d/ipr.conf)" "grep 'Storage=persistent' /etc/systemd/journald.conf.d/ipr.conf"
check M.8 "OnFailure incident handler installed"      "[ -f /etc/systemd/system/ipr-failure@.service ]"
check M.9 "core units carry OnFailure drop-in"        "grep OnFailure /etc/systemd/system/bt_hid_ble.service.d/20-onfailure.conf"
if [ -s /var/lib/ipr-keyboard/incidents.log ]; then
    warn "incidents.log is not empty — review it:"
    tail -5 /var/lib/ipr-keyboard/incidents.log | sed 's/^/    /'
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "N — OLED status display  (install_oled_support.sh)"
# ═══════════════════════════════════════════════════════════════════════════════
# A device without a display is a valid configuration: N.9/N.10 skip instead
# of failing when nothing answers on the bus.

check N.1 "config.txt enables I2C (dtparam=i2c_arm=on)"        "grep -q '^dtparam=i2c_arm=on' '$_BOOT_CFG'"
check N.2 "I2C bus runs at 400 kHz (i2c_arm_baudrate)"          "grep -q '^dtparam=i2c_arm_baudrate=400000' '$_BOOT_CFG'"
check N.3 "i2c-dev autoloaded (modules-load.d/ipr-oled.conf)"   "[ -f /etc/modules-load.d/ipr-oled.conf ] && lsmod | grepq '^i2c_dev'"
check N.4 "/dev/i2c-1 present"                                  "[ -c /dev/i2c-1 ]"
check N.5 "$_INVOKING_USER in group i2c"                        "id -nG '$_INVOKING_USER' | tr ' ' '\n' | grepq -x i2c"
check N.6 "python3-pil, fonts-dejavu-core, i2c-tools installed" "dpkg -s python3-pil fonts-dejavu-core i2c-tools"
check N.7 "Pillow importable from the app venv"                 "'$PROJECT_DIR/.venv/bin/python' -c 'from PIL import Image, ImageDraw, ImageFont'"
check N.8 "ipr-led-halt.sh blanks the OLED at halt (0xAE)"      "grep -q '0xAE' /usr/local/sbin/ipr-led-halt.sh"
check N.11 "/etc/default/ipr-oled names the repo (boot screen)"  "grep -q '^REPO_DIR=' /etc/default/ipr-oled"
check N.12 "ipr-oled-boot.service installed and enabled"         "systemctl is-enabled --quiet ipr-oled-boot.service"
check N.13 "ipr_keyboard.service takes the panel over (drop-in)" "grep -q 'Conflicts=ipr-oled-boot.service' /etc/systemd/system/ipr_keyboard.service.d/11-oled-boot.conf"
if [ -c /dev/i2c-1 ] && /usr/sbin/i2cdetect -y 1 2>/dev/null | grep -iE ' (3c|UU)( |$)' >/dev/null; then
    record_pass N.9 "SSD1306 answers at 0x3c (or is held by the app)"
else
    record_skip N.9 "no device at 0x3c — display not connected"
fi
if journalctl -u ipr_keyboard.service -b --no-pager 2>/dev/null | grep 'OLED display started' >/dev/null; then
    record_pass N.10 "OLED display running in ipr_keyboard.service (this boot)"
elif journalctl -u ipr_keyboard.service -b --no-pager 2>/dev/null | grep 'OLED display disabled' >/dev/null; then
    record_skip N.10 "OLED display disabled — $(journalctl -u ipr_keyboard.service -b --no-pager 2>/dev/null | grep 'OLED display disabled' | tail -1 | sed 's/.*OLED display disabled//')"
else
    record_skip N.10 "OLED display — no OLED line in this boot's journal"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "O — Typing speed and the daemon/application runtime files"
# ═══════════════════════════════════════════════════════════════════════════════
# Three small files on tmpfs carry state between the BLE daemon and the
# application.  None is required for a send to work, which is the problem: when
# one is missing the device degrades quietly -- no progress on the panel, no
# typing measurement, or a typing speed that cannot be changed without
# dropping the PC's connection.  Worth an audit entry each.

check O.1 "BT_KEY_DELAY_MS set in /opt/ipr_common.env"     "grep -qE '^BT_KEY_DELAY_MS=' /opt/ipr_common.env"
check O.2 "installed BLE daemon reads the runtime typing speed"     "grep -q 'KEY_DELAY_PATH' /usr/local/bin/bt_hid_ble_daemon.py"
check O.3 "installed BLE daemon publishes typing progress"     "grep -q 'PROGRESS_FILE' /usr/local/bin/bt_hid_ble_daemon.py"
check O.4 "installed BLE daemon publishes the bond state"     "grep -q 'LINK_FILE' /usr/local/bin/bt_hid_ble_daemon.py"
check O.5 "installed BLE daemon does NOT register GATT 0x1801"     "! grep -q 'UUID_GATT_SERVICE' /usr/local/bin/bt_hid_ble_daemon.py"
check O.6 "BLE daemon registered its GATT application"     "journalctl -u bt_hid_ble.service -b 0 --no-pager | grepq 'GATT application registered'"
check O.7 "BLE daemon is advertising, with an interval it chose"     "journalctl -u bt_hid_ble.service -b 0 --no-pager | grepq -E 'Registered GATT\+ADV.*(fast|medium|slow)'"
check O.8 "an advertising instance is actually active"     "busctl --system get-property org.bluez /org/bluez/hci0 org.bluez.LEAdvertisingManager1 ActiveInstances | grepq -v ' 0$'"

# The runtime files: the daemon creates two at startup, the application writes
# the third on its first loop.  The progress file only appears after a send, so
# it is a skip rather than a failure on a device that has not typed yet.
check O.9  "/run/ipr_bt_key_delay exists and holds a number"     "grep -qE '^[0-9]+$' /run/ipr_bt_key_delay"
check O.10 "/run/ipr_bt_key_delay is writable by $_INVOKING_USER"     "sudo -u '$_INVOKING_USER' test -w /run/ipr_bt_key_delay"
check O.11 "/run/ipr_bt_link.json names the paired hosts"     "grep -q '\"bonded\"' /run/ipr_bt_link.json"
check O.12 "/dev/shm writable by $_INVOKING_USER (the typing-speed hold)"     "sudo -u '$_INVOKING_USER' test -w /dev/shm"

if [ -f /run/ipr_bt_progress.json ]; then
    record_pass O.13 "/run/ipr_bt_progress.json present (something has been typed)"
else
    record_skip O.13 "nothing typed since boot — the progress file appears on the first send"
fi

# The env default and the saved setting must agree, or the device silently
# types at a speed nobody chose: this one bit a production device.
_env_delay="$(grep -oE '^BT_KEY_DELAY_MS="?[0-9]+' /opt/ipr_common.env 2>/dev/null | grep -oE '[0-9]+$' || true)"
_cfg_delay="$(grep -oE '"TypingDelayMs"[[:space:]]*:[[:space:]]*[0-9]+' "$PROJECT_DIR/config.json" 2>/dev/null | grep -oE '[0-9]+$' || true)"
if [ -z "$_cfg_delay" ]; then
    record_skip O.14 "TypingDelayMs not yet saved in config.json (the default applies)"
elif [ "$_env_delay" = "$_cfg_delay" ]; then
    record_pass O.14 "typing speed agrees: env ${_env_delay} ms = config ${_cfg_delay} ms"
else
    record_fail O.14 "typing speed disagrees: /opt/ipr_common.env says ${_env_delay} ms, config.json says ${_cfg_delay} ms"
fi

# A keyboard should present itself as a keyboard.  BlueZ's LE Audio servers
# (vcp, micp, bass) otherwise register Volume Control, Microphone Control and
# Broadcast Audio Scan in the GATT database -- services a PC then tries to set
# up for an audio device that does not exist.
check O.15 "bluetoothd runs without the LE Audio plugins (vcp, micp, bass)"     "grep -q -- 'vcp,micp,bass' /etc/systemd/system/bluetooth.service.d/override.conf"
check O.16 "the adapter advertises no audio services"     "! bluetoothctl show | grepq -E 'Volume Control|Microphone Control|Broadcast Audio Scan|Audio Input Control|Volume Offset Control'"

# ═══════════════════════════════════════════════════════════════════════════════
section "J — Manual / interactive checks  (skipped with --auto)"
# ═══════════════════════════════════════════════════════════════════════════════
# These steps cannot be automated from SSH — they require a phone, browser, or
# physical interaction with the device.

if manual_step \
    "Open Wi-Fi settings on a phone or laptop." \
    "The hotspot SSID 'ipr-setup-XXXX' should be visible." \
    "(If not visible, trigger it: hold reed switch ≥ 3 s or triple power-cycle)"; then
    record_pass J.1 "Hotspot SSID visible on client device"
else
    record_skip J.1 "Hotspot SSID visible on client device"
fi

if manual_step \
    "Connect to the 'ipr-setup-XXXX' hotspot." \
    "Open https://10.42.0.1/setup/ in a browser." \
    "Expected: setup portal login page renders (browser may warn about certificate)."; then
    record_pass J.2 "Setup portal reachable at https://10.42.0.1/setup/"
else
    record_skip J.2 "Setup portal reachable at https://10.42.0.1/setup/"
fi

if [ -f "$PROJECT_DIR/admin_initial_password.txt" ]; then
    _HOTSPOT_CRED=$(grep '^PASS=' /etc/ipr-hotspot.secret 2>/dev/null | cut -d= -f2 || echo "<see /etc/ipr-hotspot.secret>")
    if manual_step \
        "In the setup portal, log in with:" \
        "  Username: ipr" \
        "  Password: $_HOTSPOT_CRED  (from /etc/ipr-hotspot.secret)" \
        "Expected: setup home page loads after login."; then
        record_pass J.3 "Setup portal login succeeds"
    else
        record_skip J.3 "Setup portal login succeeds"
    fi
else
    record_skip J.3 "Setup portal login succeeds — admin_initial_password.txt not found"
fi

if manual_step \
    "In the browser, go to https://10.42.0.1/setup/ca.crt" \
    "Download and install the CA certificate in your OS trust store." \
    "Reload the setup portal — it should now open without a security warning."; then
    record_pass J.4 "CA cert downloaded and HTTPS trusted"
else
    record_skip J.4 "CA cert downloaded and HTTPS trusted"
fi

if manual_step \
    "Open the main dashboard on the local network:" \
    "  https://$(hostname -s).local/" \
    "Log in as admin (password in $PROJECT_DIR/admin_initial_password.txt)." \
    "Expected: dashboard renders with correct WiFi/BT status."; then
    record_pass J.5 "Main dashboard accessible and renders"
else
    record_skip J.5 "Main dashboard accessible and renders"
fi

if manual_step \
    "Bluetooth pairing: open Bluetooth settings on a host (PC/phone)." \
    "The device should appear as 'IPR Keyboard (Dev)' or similar." \
    "Pair and confirm the pairing code." \
    "Expected: paired device listed in dashboard Bluetooth status."; then
    record_pass J.6 "BT pairing completes successfully"
else
    record_skip J.6 "BT pairing completes successfully"
fi

if manual_step     "Status LED: power-cycle the device and watch the LED."     "Expected: solid white (power) -> white blink (booting) -> status colour for 30 s -> off.  In development mode there is no periodic blip: the mode is on the OLED badge."     "Tap the magnet: LED shows status again."     "Hold the magnet: three quick white blinks (magnet registered), then dark, then solid blue at 3 s; release -> hotspot comes up, LED stays solid blue."     "Hold 3 s again: hotspot stops and the LED returns to the status colour." \
    "Hold on to 6 s: solid white; release -> white while shutting down, then OFF = safe to unplug."; then
    record_pass J.7 "Status LED boot sequence and magnet gestures"
else
    record_skip J.7 "Status LED boot sequence and magnet gestures"
fi

if manual_step \
    "OLED display: watch the panel through a boot and a magnet tap." \
    "Expected: STARTING… with a checklist a few seconds after power-on (ipr-oled-boot.service), continuing into the application's own checklist -> READY (or PROBLEM) with PC, pen and Wi-Fi lines -> blank after 30 s." \
    "The mode badge (DEV / PROD) sits in the top right corner of every screen." \
    "Tap the magnet: the LED blinks white to acknowledge it and the status page comes back." \
    "Hold the magnet: the activity list shows one activity per line, the selected one in bold with a marker; activities already passed disappear and the rest roll up." \
    "Long lines (a long network name or IP) roll slowly instead of being cut." \
    "Hold 6 s and release: SHUTTING DOWN stays until the LED goes off, then the panel is dark too."; then
    record_pass J.8 "OLED display boot, status, gestures and blanking"
else
    record_skip J.8 "OLED display boot, status, gestures and blanking"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "SUMMARY"
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "  ${BOLD}Passed: $PASS_COUNT  |  Failed: $FAIL_COUNT  |  Skipped: $SKIP_COUNT${RESET}"
echo ""

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo -e "  ${RED}${BOLD}✗ Failures:${RESET}"
    for entry in "${RESULT_LOG[@]}"; do
        IFS='|' read -r status id label <<< "$entry"
        if [[ "$status" == "FAIL" ]]; then
            echo -e "    ${RED}[$id]${RESET} $label"
        fi
    done
    echo ""
    echo -e "  ${RED}Provisioning incomplete — address the failures above before use.${RESET}"
else
    if [ "$SKIP_COUNT" -gt 0 ]; then
        echo -e "  ${GREEN}✓ All automated checks passed.${RESET}"
        echo -e "  ${YELLOW}  ($SKIP_COUNT step(s) skipped — require manual or interactive confirmation)${RESET}"
    else
        echo -e "  ${GREEN}${BOLD}✓ All checks passed. Device is ready for use.${RESET}"
    fi
fi

if [ -n "$REPORT_FILE" ]; then
    echo -e "  ${CYAN}Report written to $REPORT_FILE${RESET}"
    echo ""
fi

# Let the tee subprocess flush before the shell exits, or the last lines of the
# report are lost.
if [ -n "${_REPORT_ACTIVE:-}" ]; then
    exec 1>&- 2>&-
    wait 2>/dev/null || true
fi
exit "$FAIL_COUNT"
