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
#
# Can be run on the Pi directly or uploaded and executed via ipr-rpi-dev-ssh MCP.
# Pass --auto to skip all manual/interactive steps (suitable for MCP sessions).
#
# Usage:
#   sudo bash ~/dev/ipr-keyboard/scripts/headless/test_provision.sh [--auto]
#
# Connection wiring diagram:
#   No hardware wiring required — this script tests software state only.
#   For hardware (GPIO/LED/reed) validation, run test_gpio_led_reed.sh separately.
#
# category: Headless
# purpose: Validate that all provisioning steps completed correctly on a new Pi
# sudo: yes

set -uo pipefail

# ── invoking user resolution ───────────────────────────────────────────────────

_INVOKING_USER="${SUDO_USER:-$USER}"
_INVOKING_HOME=$(getent passwd "$_INVOKING_USER" | cut -d: -f6)
PROJECT_DIR="${IPR_PROJECT_ROOT:-$_INVOKING_HOME/dev}/ipr-keyboard"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
VENV_PYTEST="$PROJECT_DIR/.venv/bin/pytest"

# ── arguments ─────────────────────────────────────────────────────────────────

AUTO=0
for _arg in "$@"; do [[ "$_arg" == "--auto" || "$_arg" == "-y" ]] && AUTO=1; done

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
check A.10 "/mnt/irispen mount point"    "[ -d /mnt/irispen ]"
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
    if "$VENV_PYTEST" "$PROJECT_DIR/tests" \
           --ignore="$PROJECT_DIR/tests/e2e" \
           -q --tb=no --no-header \
           --timeout=60 2>/dev/null | grep -qE '^\d+ passed'; then
        record_pass B.7 "pytest unit tests pass"
    else
        # Capture a brief failure summary
        PYTEST_OUT=$("$VENV_PYTEST" "$PROJECT_DIR/tests" \
            --ignore="$PROJECT_DIR/tests/e2e" \
            -q --tb=line --no-header \
            --timeout=60 2>&1 | tail -20 || true)
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
check C.5 "/opt/ipr_common.env present"         \
          "[ -f /opt/ipr_common.env ]"
check C.6 "bluetooth override.conf present"     \
          "[ -f /etc/systemd/system/bluetooth.service.d/override.conf ]"
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
          "openssl x509 -noout -text -in /etc/ipr-ssl/server.crt | grep -q '10.42.0.1'"
check F.8 "Server cert covers .local hostname" \
          "openssl x509 -noout -text -in /etc/ipr-ssl/server.crt | grep -q '.local'"

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

info "Testing HTTPS health endpoint ..."
HEALTH_BODY=$(curl -sk --max-time 5 https://localhost/health 2>/dev/null || true)
if echo "$HEALTH_BODY" | grep -q '"ok"'; then
    record_pass H.1 "HTTPS /health returns ok"
else
    # Fall back to HTTP (dev mode, no certs)
    HEALTH_BODY_HTTP=$(curl -s --max-time 5 http://localhost:8080/health 2>/dev/null || true)
    if echo "$HEALTH_BODY_HTTP" | grep -q '"ok"'; then
        record_pass H.1 "HTTP /health returns ok (HTTPS not available)"
    else
        record_fail H.1 "/health reachable (HTTPS and HTTP both failed)"
        warn "HTTPS response: ${HEALTH_BODY:-<empty>}"
    fi
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

echo ""
exit "$FAIL_COUNT"
