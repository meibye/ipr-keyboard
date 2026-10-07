#!/usr/bin/env bash
# test_oled.sh — Hardware test for the SSD1306 OLED status display
#
# Usage (run on the Pi directly or via SSH):
#   sudo bash ~/dev/ipr-keyboard/scripts/headless/test_oled.sh
#   sudo bash ~/dev/ipr-keyboard/scripts/headless/test_oled.sh --auto
#
# Designed to be run via the ipr-rpi-dev-ssh MCP server.  Visual tests pause
# for confirmation; in --auto / piped / MCP mode they still drive the panel
# but the confirmation prompt is skipped.
#
# Wiring (I2C bus 1):
#
#   Signal   BCM      Phys pin   Notes
#   ──────────────────────────────────────────────────────────────────────
#   VCC      —        Pin 1      3.3 V (the module regulates nothing; 3V3 only)
#   GND      —        Pin 6      (or 9, 14, 20, 25)
#   SDA      GPIO 2   Pin 3      on-board 1.8 kΩ pull-ups on the Pi
#   SCL      GPIO 3   Pin 5
#
#   Address 0x3C is the module default; a solder jumper on the back selects
#   0x3D — then set "OledI2cAddress": 61 in config.json.
#
# category: Headless
# purpose: Hardware verification for the OLED status display (I2C, driver, screens)
# sudo: yes

_INVOKING_USER="${SUDO_USER:-$USER}"
_INVOKING_HOME=$(getent passwd "$_INVOKING_USER" | cut -d: -f6)
PROJECT_DIR="${IPR_PROJECT_ROOT:-$_INVOKING_HOME/dev}/ipr-keyboard"
PROJECT_SRC="$PROJECT_DIR/src"
VENV_PY="$PROJECT_DIR/.venv/bin/python"
[ -x "$VENV_PY" ] || VENV_PY=python3

OLED_BUS=1
OLED_ADDR=0x3c
if [ -f "$PROJECT_DIR/config.json" ]; then
    read -r OLED_BUS OLED_ADDR < <("$VENV_PY" - "$PROJECT_DIR/config.json" <<'PY' || echo "1 0x3c"
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get("OledI2cBus", 1), "0x%02x" % d.get("OledI2cAddress", 60))
PY
)
fi

AUTO=0
for _arg in "$@"; do [[ "$_arg" == "--auto" || "$_arg" == "-y" ]] && AUTO=1; done

# ── service restore ───────────────────────────────────────────────────────────
# The application holds the panel while it runs; section A stops it and the
# trap restarts it on every exit path if it was running before.
_IPR_WAS_ACTIVE=0
systemctl is-active --quiet ipr_keyboard 2>/dev/null && _IPR_WAS_ACTIVE=1

_restore_ipr_service() {
    if (( _IPR_WAS_ACTIVE )) && ! systemctl is-active --quiet ipr_keyboard 2>/dev/null; then
        echo "[test_oled] Restarting ipr_keyboard.service"
        sudo systemctl start ipr_keyboard 2>/dev/null || true
    fi
}
trap _restore_ipr_service EXIT INT TERM

# ── result tracking ────────────────────────────────────────────────────────────

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
RESULT_LOG=()

if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
    CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; RESET=''
fi

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

check() {
    local id="$1"; local label="$2"; shift 2
    if eval "$@" >/dev/null 2>&1; then
        record_pass "$id" "$label"
    else
        record_fail "$id" "$label"
    fi
}

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

# Run a Python snippet with the project on sys.path, as the invoking user
# (group i2c), so the test exercises the same access path as the service.
py() {
    sudo -u "$_INVOKING_USER" env PROJECT_SRC="$PROJECT_SRC" OLED_BUS="$OLED_BUS" OLED_ADDR="$OLED_ADDR" \
        "$VENV_PY" - <<PYEOF
import os, sys
sys.path.insert(0, os.environ["PROJECT_SRC"])
BUS = int(os.environ["OLED_BUS"]); ADDR = int(os.environ["OLED_ADDR"], 16)
$1
PYEOF
}

# ═══════════════════════════════════════════════════════════════════════════════
section "P — Prerequisites"
# ═══════════════════════════════════════════════════════════════════════════════

check P.1 "Running as root"                     "[ \"\$(id -u)\" -eq 0 ]"
check P.2 "/dev/i2c-$OLED_BUS present"          "[ -c /dev/i2c-$OLED_BUS ]"
check P.3 "$_INVOKING_USER in group i2c"        "id -nG '$_INVOKING_USER' | tr ' ' '\n' | grep -qx i2c"
check P.4 "Pillow importable ($VENV_PY)"        "'$VENV_PY' -c 'from PIL import Image, ImageDraw, ImageFont'"
if /usr/sbin/i2cdetect -y "$OLED_BUS" 2>/dev/null | grep -iE " (${OLED_ADDR#0x}|UU)( |$)" >/dev/null; then
    record_pass P.5 "i2cdetect sees a device at $OLED_ADDR"
else
    record_fail P.5 "i2cdetect sees a device at $OLED_ADDR (check wiring / address jumper)"
fi

if [ "$FAIL_COUNT" -gt 0 ]; then
    warn "Prerequisites failed — sections A/B need a working bus and panel."
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "A — Driver  (ipr_keyboard.oled.ssd1306)"
# ═══════════════════════════════════════════════════════════════════════════════

sudo systemctl stop ipr_keyboard 2>/dev/null && info "Stopped ipr_keyboard.service (it holds the panel)" || true
sleep 1

if py 'from ipr_keyboard.oled.ssd1306 import probe
sys.exit(0 if probe(BUS, ADDR) else 1)'; then
    record_pass A.1 "probe() acknowledges the panel at $OLED_ADDR"
else
    record_fail A.1 "probe() acknowledges the panel at $OLED_ADDR"
fi

info "A.2  Full white for 2 s, then a checkerboard for 2 s…"
if py 'import time
from PIL import Image
from ipr_keyboard.oled.ssd1306 import Ssd1306
d = Ssd1306(BUS, ADDR); d.setup()
d.show(Image.new("1", (128, 64), 1)); time.sleep(2)
img = Image.new("1", (128, 64), 0)
px = img.load()
for y in range(64):
    for x in range(128):
        px[x, y] = 1 if ((x // 8) + (y // 8)) % 2 == 0 else 0
d.show(img); time.sleep(2)
print("frame %.1f ms" % d.last_frame_ms)
d.clear(); d.close()'; then
    if manual_step "Did the panel light fully white, then show an 8x8 checkerboard reaching every edge?"; then
        record_pass A.2 "Full-frame writes (white, checkerboard) reach the whole panel"
    else
        record_skip A.2 "Full-frame writes — not visually confirmed"
    fi
else
    record_fail A.2 "Full-frame writes (driver raised an error)"
fi

info "A.3  Contrast sweep, sleep 2 s, wake…"
if py 'import time
from PIL import Image
from ipr_keyboard.oled.ssd1306 import Ssd1306
d = Ssd1306(BUS, ADDR); d.setup()
d.show(Image.new("1", (128, 64), 1))
for c in (255, 128, 32, 1, 128):
    d.contrast(c); time.sleep(0.6)
d.sleep(); time.sleep(2); d.wake(); time.sleep(1)
d.clear(); d.close()'; then
    if manual_step "Did the brightness step down then back up, go dark for 2 s, and return?"; then
        record_pass A.3 "Contrast, sleep (0xAE) and wake (0xAF)"
    else
        record_skip A.3 "Contrast / sleep / wake — not visually confirmed"
    fi
else
    record_fail A.3 "Contrast / sleep / wake (driver raised an error)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "B — Screens  (ipr_keyboard.oled.screens + render)"
# ═══════════════════════════════════════════════════════════════════════════════

info "B.1  Every screen for 3 s each (one rolls a long line, five are gesture stages)…"
if py 'import time
from ipr_keyboard.oled import screens as sc
from ipr_keyboard.oled.render import Renderer
from ipr_keyboard.oled.ssd1306 import Ssd1306
d = Ssd1306(BUS, ADDR); d.setup(); r = Renderer()
ready = dict(phase=sc.STATUS, ready=True, bt_connected=True, bt_host="Laptop-MSE", pen="ready",
             wifi_connected=True, ssid="HomeNet", ip="192.168.1.23")
snaps = [
    sc.Snapshot(),
    sc.Snapshot(**ready),
    sc.Snapshot(**{**ready, "development": True, "ssid": "A-rather-long-network-name", "ip": "192.168.100.200"}),
    sc.Snapshot(**{**ready, "services_ok": False, "failed_services": ("bt_hid_ble.service",)}),
    sc.Snapshot(**{**ready, "tx_state": "sending", "tx_chars": 142}),
    sc.Snapshot(**{**ready, "tx_state": "success", "tx_recent": True, "tx_chars": 142, "tx_total": 13, "tx_last_at": time.time()}),
    sc.Snapshot(**{**ready, "phase": sc.HOTSPOT_ON, "hotspot_active": True, "hotspot_ssid": "ipr-setup-a1b2"}),
    sc.Snapshot(**{**ready, "held_secs": 1.0}),
    sc.Snapshot(**{**ready, "held_secs": 4.0, "armed": "hotspot"}),
    sc.Snapshot(**{**ready, "held_secs": 7.0, "armed": "shutdown"}),
    sc.Snapshot(**{**ready, "held_secs": 12.0, "armed": "mode"}),
    sc.Snapshot(**{**ready, "held_secs": 16.0, "armed": "reset"}),
    sc.Snapshot(**{**ready, "phase": sc.SHUTTING_DOWN}),
]
t0 = time.monotonic()
for snap in snaps:
    screen = sc.compose(snap)
    print("  " + screen.header, flush=True)
    end = time.monotonic() + 3.0
    while time.monotonic() < end:
        img, rolling = r.render(screen, time.monotonic() - t0)
        d.show(img)
        time.sleep(0.125 if rolling else 0.5)
d.sleep(); d.close()'; then
    if manual_step "Did each screen show a header in the yellow band and readable lines below?" \
                   "Did every screen carry a DEV or PROD badge in the top right corner?" \
                   "On the HOLD screens: one activity per line, the selected one in bold with a marker, and the list shrinking as the selection moved down?" \
                   "Did the long network line on the DEV screen roll slowly left, pause, and restart?"; then
        record_pass B.1 "All screens render; long line rolls"
    else
        record_skip B.1 "Screens — not visually confirmed"
    fi
else
    record_fail B.1 "Screens (render/driver raised an error)"
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

if [ "$FAIL_COUNT" -eq 0 ] && [ "$PASS_COUNT" -gt 0 ]; then
    echo -e "  ${GREEN}${BOLD}✓ All automated checks passed.${RESET}"
    [ "$SKIP_COUNT" -gt 0 ] && echo -e "  ${YELLOW}  ($SKIP_COUNT step(s) skipped — visual steps not confirmed)${RESET}"
    exit 0
else
    echo -e "  ${RED}${BOLD}✗ $FAIL_COUNT check(s) FAILED — review output above.${RESET}"
    exit 1
fi
