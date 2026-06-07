#!/usr/bin/env bash
# test_headless_rpi4.sh — Automated + interactive test runner for scripts/headless/ on RPi 4
#
# Usage (run on the Pi directly or via SSH):
#   sudo bash ~/dev/ipr-keyboard/scripts/headless/test_headless_rpi4.sh
#
# The script is designed to be uploaded and executed via the ipr-rpi-dev-ssh MCP server.
# Tests that require manual hardware interaction pause and instruct the user; in non-interactive
# (piped/MCP) mode those steps are automatically skipped and marked accordingly.
#
# Safe variants: tests that would normally reboot are patched to suppress the reboot so
# the SSH session stays alive throughout.
#
# category: Headless
# purpose: Automated and interactive test runner for headless provisioning scripts
# sudo: yes

# When run via "sudo bash", $HOME becomes /root — resolve the invoking user's home instead.
_INVOKING_USER="${SUDO_USER:-$USER}"
_INVOKING_HOME=$(getent passwd "$_INVOKING_USER" | cut -d: -f6)
SCRIPTS_DIR="${SCRIPTS_DIR:-$_INVOKING_HOME/dev/ipr-keyboard/scripts/headless}"

# --auto / -y: skip all manual steps (used when running non-interactively via MCP).
AUTO=0
for _arg in "$@"; do [[ "$_arg" == "--auto" || "$_arg" == "-y" ]] && AUTO=1; done

# ── result tracking ────────────────────────────────────────────────────────────

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
# Ordered result log: "PASS|FAIL|SKIP <id> <description>"
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

# Run a shell expression; record pass/fail against the given test ID and label.
check() {
    local id="$1"; local label="$2"; shift 2
    if eval "$@" >/dev/null 2>&1; then
        record_pass "$id" "$label"
    else
        record_fail "$id" "$label"
    fi
}

# Print a manual-action prompt and wait for Enter (interactive) or skip (non-interactive).
# Returns 0 if user confirmed, 1 if skipped.
manual_step() {
    echo ""
    echo -e "  ${BOLD}${YELLOW}⚡ MANUAL ACTION REQUIRED${RESET}"
    # Print each argument on its own indented line
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

net_status() {
    echo ""
    info "Network snapshot:"
    ip addr show wlan0 2>/dev/null | grep -E '^\s*(inet |link)' | sed 's/^/    /' \
        || echo "    wlan0 not found"
    nmcli -f NAME,TYPE,STATE,DEVICE con show --active 2>/dev/null | sed 's/^/    /' || true
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════════════
section "PREREQUISITES"
# ═══════════════════════════════════════════════════════════════════════════════

info "System: $(uname -a)"
info "Date:   $(date)"

check P.1 "NetworkManager is active"        "systemctl is-active NetworkManager"
check P.2 "python3 available"               "command -v python3"
check P.3 "openssl available"               "command -v openssl"
check P.4 "nmcli available"                 "command -v nmcli"
check P.5 "curl available"                  "command -v curl"
check P.6 "/boot/firmware is a mount point" "mountpoint -q /boot/firmware"

for script in net_provision_hotspot.sh net_provision_web.py gpio_factory_reset.py net_factory_reset.sh ipr-provision.service; do
    check "P.7.$script" "Script present: $script" "[ -f '$SCRIPTS_DIR/$script' ]"
done

if ! command -v raspi-gpio >/dev/null 2>&1; then
    warn "raspi-gpio not installed — GPIO gate variant cannot be tested"
fi
if ! python3 -c "import RPi.GPIO" 2>/dev/null; then
    warn "RPi.GPIO not importable — GPIO factory reset test will be skipped"
    HAS_GPIO=0
else
    HAS_GPIO=1
fi

net_status

# ═══════════════════════════════════════════════════════════════════════════════
section "TEST 1 — net_provision_hotspot.sh: Permanent Management Hotspot"
# ═══════════════════════════════════════════════════════════════════════════════
info "Goal: hotspot starts on wlan0 and /etc/ipr-hotspot.secret is generated."
info "The script sets up the NM hotspot connection and exits (oneshot)."
info "Port 443 is served by ipr_keyboard.service (tested in Test 6), not here."

info "Cleaning prior state..."
sudo systemctl stop ipr-provision 2>/dev/null && info "Stopped ipr-provision service" || true
sudo fuser -k 443/tcp 2>/dev/null && info "Killed existing process on port 443" || true
sudo fuser -k 80/tcp  2>/dev/null && info "Killed existing process on port 80"  || true
sleep 2
sudo nmcli con delete ipr-hotspot >/dev/null 2>&1 && info "Deleted existing ipr-hotspot" || true
# Credentials in /etc/ipr-hotspot.secret are intentionally preserved so the hotspot
# SSID/password stays consistent across test runs and service restarts.

info "Running net_provision_hotspot.sh (exits after hotspot setup)..."
sudo bash "$SCRIPTS_DIR/net_provision_hotspot.sh"
T1_BG_PID=0  # script exits immediately; no background process to track
info "Waiting 5s for NM to settle..."
sleep 5

check 1.1 "ipr-hotspot NM connection exists"            "sudo nmcli con show ipr-hotspot"
check 1.2 "wlan0 has address 10.42.0.1"                 "ip addr show wlan0 | grep -q '10\.42\.0\.1'"
check 1.3 "/etc/ipr-hotspot.secret created"             "[ -f /etc/ipr-hotspot.secret ]"
check 1.4 "SSID starts with 'ipr-setup-'"               "grep -q 'SSID=ipr-setup-' /etc/ipr-hotspot.secret"
check 1.5 "PASS field present in secret"                "grep -q 'PASS=' /etc/ipr-hotspot.secret"
record_skip 1.6 "Web UI on port 443 (now served by ipr_keyboard.service, not ipr-provision.sh)"

net_status

HOTSPOT_SSID=$(grep 'SSID=' /etc/ipr-hotspot.secret 2>/dev/null | cut -d= -f2 || echo "unknown")
HOTSPOT_PASS=$(grep 'PASS=' /etc/ipr-hotspot.secret 2>/dev/null | cut -d= -f2 || echo "unknown")
echo -e "  Hotspot SSID: ${BOLD}$HOTSPOT_SSID${RESET}   PASS: ${BOLD}$HOTSPOT_PASS${RESET}"

# Re-run check: run again with secret present — should reuse credentials without regenerating
info "Re-run check: running script again (should reuse existing credentials from secret file)..."
T1_RERUN_OUT=$(sudo bash "$SCRIPTS_DIR/net_provision_hotspot.sh" 2>&1 || true)
check 1.7 "Re-run reuses existing SSID (not regenerated)" \
    "grep -q 'SSID=$HOTSPOT_SSID' /etc/ipr-hotspot.secret"

# ═══════════════════════════════════════════════════════════════════════════════
section "TEST 2 — net_provision_web.py: Wi-Fi Provisioning UI"
# ═══════════════════════════════════════════════════════════════════════════════
info "Goal: provisioning web UI at https://10.42.0.1/setup/ responds and serves a network scan page."
info "NOTE: The web UI is now served by ipr_keyboard.service (Flask /setup/ Blueprint),"
info "      not by net_provision_web.py (which is retired). ipr_keyboard.service must be"
info "      running for these checks to pass."
info "NOTE: Auth is form-based (POST to /setup/login, session cookie). Not HTTP Basic Auth."

_T2_COOKIE_JAR=$(mktemp /tmp/ipr_t2_cookies_XXXX.txt)
_cleanup_t2() { rm -f "$_T2_COOKIE_JAR"; }
trap _cleanup_t2 EXIT

# 2.1 — unauthenticated /setup/ must redirect to /setup/login (302)
HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 8 \
    https://10.42.0.1/setup/ 2>/dev/null; true)
if [[ "$HTTP_CODE" == "302" ]]; then
    record_pass 2.1 "Unauthenticated /setup/ returns 302 (redirects to /setup/login)"
elif [[ "$HTTP_CODE" == "000" ]]; then
    record_skip 2.1 "HTTPS server not reachable — ipr_keyboard.service not running on this host"
else
    record_fail 2.1 "Unexpected HTTP code from /setup/: $HTTP_CODE (expected 302 redirect)"
fi

# 2.2/2.3/2.4 — form login then authenticated requests
if [[ -n "$HOTSPOT_PASS" && "$HOTSPOT_PASS" != "unknown" && "$HTTP_CODE" != "000" ]]; then
    # POST login form; server sets session cookie and returns 302 on success
    LOGIN_CODE=$(curl -sk -c "$_T2_COOKIE_JAR" -o /dev/null -w "%{http_code}" --max-time 8 \
        -X POST \
        --data-urlencode "username=ipr" \
        --data-urlencode "password=$HOTSPOT_PASS" \
        https://10.42.0.1/setup/login 2>/dev/null; true)
    check 2.2 "Login POST to /setup/login returns 302 (session cookie set)" \
        "[[ '$LOGIN_CODE' == '302' ]]"

    # Follow up with session cookie — /setup/ should now return 200
    AUTH_CODE=$(curl -sk -b "$_T2_COOKIE_JAR" -o /dev/null -w "%{http_code}" --max-time 8 \
        https://10.42.0.1/setup/ 2>/dev/null; true)
    check 2.3 "Authenticated /setup/ returns 200 (session accepted)" \
        "[[ '$AUTH_CODE' == '200' ]]"

    PAGE=$(curl -sk -b "$_T2_COOKIE_JAR" --max-time 8 \
        https://10.42.0.1/setup/ 2>/dev/null || echo "")
    if echo "$PAGE" | grep -qi "ssid\|network\|scan\|wifi\|setup\|hotspot"; then
        record_pass 2.4 "Page body references networks/SSID/setup/hotspot"
    else
        record_fail 2.4 "Page body does not mention network/SSID/setup — unexpected content"
    fi
else
    record_skip 2.2 "Login POST (server unreachable or credentials unavailable)"
    record_skip 2.3 "Authenticated request (server unreachable or credentials unavailable)"
    record_skip 2.4 "Page content check (server unreachable or credentials unavailable)"
fi

# Manual: connect a device and browse
if manual_step \
    "Connect a phone or laptop to Wi-Fi SSID: ${BOLD}${HOTSPOT_SSID}${RESET}" \
    "Password: ${BOLD}${HOTSPOT_PASS}${RESET}" \
    "Open https://10.42.0.1/setup/ in a browser (accept the self-signed cert warning)." \
    "You will be redirected to https://10.42.0.1/setup/login (form-based sign in)." \
    "Username is pre-filled as 'ipr'. Enter the hotspot password above and sign in." \
    "If already signed in from a previous session, visit /setup/logout first to clear it." \
    "Verify: after login, shows device info; nav bar has Home/Status/Wi-Fi/Logs/System/Sign out."; then
    record_pass 2.5 "Manual: web UI visible and functional from connected device"
else
    record_skip 2.5 "Manual: web UI from connected device (not confirmed)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "TEST 3 — gpio_factory_reset.py: GPIO-Triggered Wi-Fi Reset (SAFE — no reboot)"
# ═══════════════════════════════════════════════════════════════════════════════
info "Goal: grounding GPIO 17 for ≥2s deletes non-hotspot Wi-Fi profiles and creates marker files."
warn "SAFE VARIANT: 'reboot' call is patched out — the Pi will NOT reboot."
warn "Hardware needed: jumper wire, GPIO 17 (Pin 11) → GND (Pin 9 or 14)."

if [[ "$HAS_GPIO" -eq 0 ]]; then
    record_skip 3.1 "test-wifi profile created (RPi.GPIO unavailable — skipping all T3)"
    record_skip 3.2 "GPIO script detects held pin (RPi.GPIO unavailable)"
    record_skip 3.3 "test-wifi deleted after GPIO trigger"
    record_skip 3.4 "ipr-hotspot preserved after GPIO trigger"
    record_skip 3.5 "/var/run/ipr_gpio_reset_triggered marker created"
    record_skip 3.6 "/boot/firmware/IPR_RESET_WIFI marker created"
else
    # Build safe copy — suppress reboot
    SAFE_GPIO=$(mktemp /tmp/gpio_factory_reset_XXXX.py)
    sed 's/subprocess\.run(\[.*reboot.*\][^)]*)/print("[test] reboot suppressed")/' \
        "$SCRIPTS_DIR/gpio_factory_reset.py" > "$SAFE_GPIO"
    info "Safe copy written to $SAFE_GPIO"

    # Clean previous run markers so the script doesn't short-circuit
    sudo rm -f /var/run/ipr_gpio_reset_triggered /boot/firmware/IPR_RESET_WIFI

    # Create dummy profile
    sudo nmcli con delete test-wifi >/dev/null 2>&1 || true
    sudo nmcli con add type wifi con-name "test-wifi" ssid "TestSSID" >/dev/null 2>&1
    check 3.1 "test-wifi dummy profile created" "sudo nmcli con show test-wifi"

    # The GPIO script is a boot-time oneshot: it reads the pin immediately on startup
    # and exits if the pin is not already LOW. The jumper must be in place BEFORE
    # the script runs, so prompt the user to connect it first.
    if manual_step \
        "Connect GPIO 17 (Pin 11) to GND (Pin 9 or 14) using a jumper NOW." \
        "Keep the jumper in place — do NOT remove it yet." \
        "Press ENTER once the jumper is connected and you are ready."; then

        info "Starting GPIO monitor (jumper should be in place)..."
        sudo python3 "$SAFE_GPIO"
        T3_EXIT=$?
        info "GPIO script exited (code $T3_EXIT)."

        info "Waiting 2s for NM profile deletion to settle..."
        sleep 2

        check 3.2 "GPIO script detected held pin (marker created)"  \
            "[ -f /var/run/ipr_gpio_reset_triggered ]"
        check 3.3 "test-wifi profile deleted"                        \
            "! sudo nmcli con show test-wifi 2>/dev/null | grep -q test-wifi"
        check 3.4 "ipr-hotspot preserved"                            \
            "sudo nmcli con show ipr-hotspot"
        check 3.5 "/var/run/ipr_gpio_reset_triggered exists"         \
            "[ -f /var/run/ipr_gpio_reset_triggered ]"
        check 3.6 "/boot/firmware/IPR_RESET_WIFI exists"             \
            "[ -f /boot/firmware/IPR_RESET_WIFI ]"
    else
        for sub in 3.2 3.3 3.4 3.5 3.6; do
            record_skip "$sub" "GPIO trigger step skipped"
        done
    fi

    rm -f "$SAFE_GPIO"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "TEST 4 — net_factory_reset.sh: Marker-File-Triggered Wi-Fi Reset (SAFE — no reboot)"
# ═══════════════════════════════════════════════════════════════════════════════
info "Goal: presence of IPR_RESET_WIFI on /boot/firmware wipes Wi-Fi profiles."
warn "SAFE VARIANT: reboot suppressed so the SSH session is preserved."

# Build safe copy — suppress reboot line
SAFE_RESET=$(mktemp /tmp/net_factory_reset_XXXX.sh)
sed 's/^\s*\breboot\b/echo "[test] reboot suppressed"/' \
    "$SCRIPTS_DIR/net_factory_reset.sh" > "$SAFE_RESET"
info "Safe copy written to $SAFE_RESET"

# Setup: create dummy profile and plant marker
sudo nmcli con delete test-wifi >/dev/null 2>&1 || true
sudo nmcli con add type wifi con-name "test-wifi" ssid "TestSSID" >/dev/null 2>&1
sudo touch /boot/firmware/IPR_RESET_WIFI

check 4.1 "test-wifi dummy profile created"     "sudo nmcli con show test-wifi"
check 4.2 "IPR_RESET_WIFI marker planted"        "[ -f /boot/firmware/IPR_RESET_WIFI ]"

info "Running safe net_factory_reset.sh (marker present)..."
sudo bash "$SAFE_RESET"

check 4.3 "test-wifi profile deleted"            \
    "! sudo nmcli con show test-wifi 2>/dev/null | grep -q test-wifi"
check 4.4 "ipr-hotspot preserved"                "sudo nmcli con show ipr-hotspot"
check 4.5 "IPR_RESET_WIFI marker removed"        "[ ! -f /boot/firmware/IPR_RESET_WIFI ]"

# Negative test: no marker → script should exit 0 with no changes
info "Negative test: no marker present (should exit silently with no changes)..."
sudo nmcli con add type wifi con-name "test-wifi" ssid "TestSSID" >/dev/null 2>&1 || true
BEFORE_COUNT=$(sudo nmcli -t -f NAME con show | wc -l)
sudo bash "$SAFE_RESET"
AFTER_COUNT=$(sudo nmcli -t -f NAME con show | wc -l)
check 4.6 "No-marker run makes no profile changes" \
    "[ '$BEFORE_COUNT' -eq '$AFTER_COUNT' ]"

# Cleanup dummy profile
sudo nmcli con delete test-wifi >/dev/null 2>&1 || true
rm -f "$SAFE_RESET"

# ═══════════════════════════════════════════════════════════════════════════════
section "TEST 5 — usb_otg_setup.sh: USB OTG Gadget Ethernet"
# ═══════════════════════════════════════════════════════════════════════════════
warn "POSTPONED — no USB OTG cable available; RPi 4 USB-C is power-only."
warn "Full test requires Zero 2 W hardware. Skipping."
record_skip 5.1 "USB OTG test (postponed — no cable; RPi 4 incompatible)"

# ═══════════════════════════════════════════════════════════════════════════════
section "TEST 6 — ipr-provision.service: systemd Service Unit"
# ═══════════════════════════════════════════════════════════════════════════════
info "Goal: service unit installs, enables, and sets up the hotspot at boot."
info "ipr-provision.service is Type=oneshot/RemainAfterExit — it runs once to set up"
info "the hotspot then exits. Port 443 is served by ipr_keyboard.service (not this unit)."
info "Boot persistence requires a manual reboot — that step is optional."

# Stop any running instance of the service before installing.
sudo systemctl stop ipr-provision 2>/dev/null || true
sudo fuser -k 443/tcp 2>/dev/null || true
sudo fuser -k 80/tcp  2>/dev/null || true
# reset-failed clears the failed state, but systemd's StartLimitBurst window (default 10s)
# must also expire before a new start is allowed.
sudo systemctl reset-failed ipr-provision 2>/dev/null || true
info "Waiting 5s for systemd to settle..."
sleep 5

# Install script to the expected system path
sudo cp "$SCRIPTS_DIR/net_provision_hotspot.sh" /usr/local/sbin/ipr-provision.sh
sudo chmod +x /usr/local/sbin/ipr-provision.sh

check 6.1 "/usr/local/sbin/ipr-provision.sh installed (+x)"     \
    "[ -x /usr/local/sbin/ipr-provision.sh ]"
record_skip 6.2 "ipr-provision-web.py install (net_provision_web.py is retired — web UI in ipr_keyboard.service)"

sudo cp "$SCRIPTS_DIR/ipr-provision.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ipr-provision 2>/dev/null

check 6.3 "Service unit installed and enabled"  "systemctl is-enabled ipr-provision"

info "Starting ipr-provision service..."
sudo systemctl start ipr-provision
info "Waiting 8s for hotspot setup to complete..."
sleep 8

check 6.4 "Service reports active (RemainAfterExit)"  "systemctl is-active ipr-provision"
record_skip 6.5 "Web UI on port 443 (served by ipr_keyboard.service, not ipr-provision.service)"
check 6.6 "wlan0 has 10.42.0.1 address"         "ip addr show wlan0 | grep -q '10\.42\.0\.1'"

net_status

info "Service status output:"
systemctl status ipr-provision --no-pager -l 2>/dev/null | head -20 | sed 's/^/  /'

# Boot persistence — manual, requires reboot
if manual_step \
    "To test boot persistence: reboot the Pi (sudo reboot) and SSH back in." \
    "Then run: systemctl status ipr-provision" \
    "And:      journalctl -u ipr-provision --boot" \
    "Verify service shows 'active (exited)' and log shows it started at boot." \
    "Come back here and press ENTER to record the result."; then
    record_pass 6.7 "Manual: service active and logged after reboot"
else
    record_skip 6.7 "Manual: boot persistence (requires manual reboot to verify)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "TEST SUMMARY"
# ═══════════════════════════════════════════════════════════════════════════════
echo ""
printf "  ${BOLD}%-6s  %-8s  %s${RESET}\n" "Result" "Test ID" "Description"
printf "  %-6s  %-8s  %s\n"               "------" "-------" "-----------"

for entry in "${RESULT_LOG[@]}"; do
    IFS='|' read -r status id desc <<< "$entry"
    case "$status" in
        PASS) color="$GREEN" ;;
        FAIL) color="$RED"   ;;
        SKIP) color="$YELLOW";;
        *)    color="$RESET" ;;
    esac
    printf "  ${color}%-6s${RESET}  %-8s  %s\n" "$status" "$id" "$desc"
done

echo ""
echo -e "  ${GREEN}Passed: $PASS_COUNT${RESET}  |  ${RED}Failed: $FAIL_COUNT${RESET}  |  ${YELLOW}Skipped: $SKIP_COUNT${RESET}"
echo ""

# Final verdict
if [ "$FAIL_COUNT" -eq 0 ] && [ "$PASS_COUNT" -gt 0 ]; then
    echo -e "  ${GREEN}${BOLD}✓ All automated checks passed.${RESET}"
    [ "$SKIP_COUNT" -gt 0 ] && echo -e "  ${YELLOW}  ($SKIP_COUNT step(s) skipped — hardware or manual steps not completed)${RESET}"
    exit 0
else
    echo -e "  ${RED}${BOLD}✗ $FAIL_COUNT check(s) FAILED — review output above.${RESET}"
    exit 1
fi
