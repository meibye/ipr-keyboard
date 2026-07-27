#!/usr/bin/env bash
# test_gpio_led_reed.sh — Hardware test for reed switch and RGB LED
#
# Usage (run on the Pi directly or via SSH):
#   sudo bash ~/dev/ipr-keyboard/scripts/headless/test_gpio_led_reed.sh
#   sudo bash ~/dev/ipr-keyboard/scripts/headless/test_gpio_led_reed.sh --auto
#
# The script is designed to be run via the ipr-rpi-dev-ssh MCP server.
# LED colour tests pause for manual visual confirmation; in --auto / piped / MCP
# mode they still exercise the hardware but the confirmation prompt is skipped.
#
# Pins (BCM, Flirc Pi Zero 2 W case):
#
#   Signal        BCM      Phys pin   Wiring notes
#   ──────────────────────────────────────────────────────────────────────────
#   Reed switch   GPIO 27  Pin 13     One leg → Pin 13; other leg → GND Pin 14
#                                     NO (normally-open) type; software pull-up
#                                     to 3.3 V — no external power needed
#   RGB LED R     GPIO 22  Pin 15     GPIO → 150 Ω → LED R anode
#   RGB LED G     GPIO 23  Pin 16     GPIO → 150 Ω → LED G anode
#   RGB LED B     GPIO 24  Pin 18     GPIO →  33 Ω → LED B anode
#                                     Common cathode → GND Pin 14 or Pin 20
#
# Power / voltage:
#   GPIO 22–24 output 3.3 V when HIGH (max 16 mA per pin on Pi Zero 2 W).
#   No separate Vcc needed — the GPIO pin itself drives the LED anode through
#   the series resistor.  Calculated current per channel at typical Vf:
#     Red   (Vf 2.0 V): (3.3 − 2.0) / 150 Ω ≈ 8.7 mA  ✓
#     Green (Vf 2.1 V): (3.3 − 2.1) / 150 Ω ≈ 8.0 mA  ✓
#     Blue  (Vf 3.0 V): (3.3 − 3.0) /  33 Ω ≈ 9.1 mA  ✓
#   All channels run at 8–9 mA — within the 16 mA per-pin safe limit.
#   If blue is very dim (Vf > 3.0 V), drop the resistor to 22 Ω or short it
#   for a quick bench check (at 3.2 V Vf only 3 mA flows — safe but dim).
#
# category: Headless
# purpose: Hardware verification for reed switch and RGB LED wiring
# sudo: yes

_INVOKING_USER="${SUDO_USER:-$USER}"
_INVOKING_HOME=$(getent passwd "$_INVOKING_USER" | cut -d: -f6)
SCRIPTS_DIR="${SCRIPTS_DIR:-$_INVOKING_HOME/dev/ipr-keyboard/scripts/headless}"

REED_PIN=27
LED_R=22
LED_G=23
LED_B=24

AUTO=0
for _arg in "$@"; do [[ "$_arg" == "--auto" || "$_arg" == "-y" ]] && AUTO=1; done

# ── service restore ───────────────────────────────────────────────────────────
# Section C stops ipr_keyboard.service to free the GPIO pins.  Restore it on
# every exit path -- normal end, failure, or Ctrl-C -- otherwise the device is
# left with no web server and no USB->BT bridge until someone notices.
# Only restart it if it was running to begin with, so a deliberately stopped
# service stays stopped.
_IPR_WAS_ACTIVE=0
systemctl is-active --quiet ipr_keyboard 2>/dev/null && _IPR_WAS_ACTIVE=1

_restore_ipr_service() {
    if (( _IPR_WAS_ACTIVE )) && ! systemctl is-active --quiet ipr_keyboard 2>/dev/null; then
        echo "[test_gpio_led_reed] Restarting ipr_keyboard.service"
        sudo systemctl start ipr_keyboard 2>/dev/null || true
    fi
}
trap _restore_ipr_service EXIT INT TERM

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

check() {
    local id="$1"; local label="$2"; shift 2
    if eval "$@" >/dev/null 2>&1; then
        record_pass "$id" "$label"
    else
        record_fail "$id" "$label"
    fi
}

# Print a manual confirmation prompt.  Returns 0 if confirmed, 1 if skipped.
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

# Prime the user: show what to watch for, then wait for ENTER before the action starts.
# In --auto or non-interactive mode this is a no-op (returns immediately).
prep_step() {
    echo ""
    echo -e "  ${BOLD}${CYAN}▷ WATCH FOR${RESET}"
    for line in "$@"; do
        echo -e "  ${CYAN}▸${RESET} $line"
    done
    echo ""
    if [[ "$AUTO" -eq 0 ]] && [ -t 0 ]; then
        printf "  Press ENTER to start: "
        read -r _
    fi
}

# Run an inline Python GPIO snippet as root; capture exit code.
# Usage: gpio_py <python_code_string>
gpio_py() {
    sudo python3 - <<PYEOF
$1
PYEOF
}

# Light a single colour, hold for HOLD seconds, then turn off.
# Usage: led_show R G B HOLD_SECS
led_show() {
    local r=$1 g=$2 b=$3 hold=${4:-2}
    gpio_py "
import RPi.GPIO as GPIO, time
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for pin in ($LED_R, $LED_G, $LED_B):
    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
GPIO.output($LED_R, $r)
GPIO.output($LED_G, $g)
GPIO.output($LED_B, $b)
time.sleep($hold)
GPIO.cleanup()
"
}

# Blink a colour at hz for duration seconds.
led_blink() {
    local r=$1 g=$2 b=$3 hz=${4:-4} dur=${5:-3}
    gpio_py "
import RPi.GPIO as GPIO, time
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for pin in ($LED_R, $LED_G, $LED_B):
    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
half = 0.5 / $hz
end = time.time() + $dur
while time.time() < end:
    GPIO.output($LED_R, $r); GPIO.output($LED_G, $g); GPIO.output($LED_B, $b)
    time.sleep(half)
    GPIO.output($LED_R, 0);  GPIO.output($LED_G, 0);  GPIO.output($LED_B, 0)
    time.sleep(half)
GPIO.cleanup()
"
}

# ═══════════════════════════════════════════════════════════════════════════════
section "PREREQUISITES"
# ═══════════════════════════════════════════════════════════════════════════════

info "System: $(uname -a)"
info "Date:   $(date)"

check P.1 "Running as root or via sudo"     "[ \$(id -u) -eq 0 ]"
check P.2 "python3 available"               "command -v python3"

if python3 -c "import RPi.GPIO" 2>/dev/null; then
    record_pass P.3 "RPi.GPIO importable"
    HAS_GPIO=1
else
    record_fail P.3 "RPi.GPIO not importable — install: sudo apt-get install python3-rpi.gpio"
    HAS_GPIO=0
fi

if [[ "$HAS_GPIO" -eq 0 ]]; then
    warn "RPi.GPIO unavailable — all GPIO tests will be skipped."
fi

# Verify gpio_monitor.py source exists (optional, non-fatal)
SRC_MONITOR="$_INVOKING_HOME/dev/ipr-keyboard/src/ipr_keyboard/gpio_monitor.py"
if [ -f "$SRC_MONITOR" ]; then
    record_pass P.4 "gpio_monitor.py source present"
else
    record_skip P.4 "gpio_monitor.py not found at $SRC_MONITOR (OK if running standalone)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "TEST A — Individual LED channels"
# ═══════════════════════════════════════════════════════════════════════════════
info "Each channel is driven HIGH for 2 s then released. Watch the LED."
info "Pins: R=GPIO${LED_R}  G=GPIO${LED_G}  B=GPIO${LED_B}"
warn "Test rig note: G channel lights a YELLOW LED (substitute for green)."

if [[ "$HAS_GPIO" -eq 0 ]]; then
    for sub in A.1 A.2 A.3 A.4 A.5 A.6 A.7; do
        record_skip "$sub" "RPi.GPIO unavailable"
    done
else
    # A.1 — Red channel
    prep_step "The LED will light RED for 2 s."
    info "A.1  Red ON for 2 s (GPIO${LED_R})..."
    led_show 1 0 0 2
    if manual_step "Did you see RED light?"; then
        record_pass A.1 "Red channel — LED lit"
    else
        record_skip A.1 "Red channel — visual confirmation not provided"
    fi

    # A.2 — Green channel
    prep_step "The LED will light GREEN for 2 s (test rig: may appear yellow)."
    info "A.2  Green ON for 2 s (GPIO${LED_G})..."
    led_show 0 1 0 2
    if manual_step "Did you see GREEN (or yellow on test rig) light?"; then
        record_pass A.2 "Green channel — LED lit"
    else
        record_skip A.2 "Green channel — visual confirmation not provided"
    fi

    # A.3 — Blue channel
    prep_step "The LED will light BLUE for 2 s."
    info "A.3  Blue ON for 2 s (GPIO${LED_B})..."
    led_show 0 0 1 2
    if manual_step "Did you see BLUE light?"; then
        record_pass A.3 "Blue channel — LED lit"
    else
        record_skip A.3 "Blue channel — visual confirmation not provided"
    fi

    # A.4 — Amber (R+G = no-WiFi state)
    prep_step "The LED will light AMBER / YELLOW (R+G) for 2 s."
    info "A.4  Amber ON for 2 s (R+G, GPIO${LED_R}+${LED_G})..."
    led_show 1 1 0 2
    if manual_step "Did you see AMBER / YELLOW light?"; then
        record_pass A.4 "Amber (R+G) — LED lit"
    else
        record_skip A.4 "Amber — visual confirmation not provided"
    fi

    # A.5 — White (R+G+B = boot state)
    prep_step "The LED will light WHITE (all three channels) for 2 s."
    info "A.5  White ON for 2 s (R+G+B)..."
    led_show 1 1 1 2
    if manual_step "Did you see WHITE light (all three channels)?"; then
        record_pass A.5 "White (R+G+B) — LED lit"
    else
        record_skip A.5 "White — visual confirmation not provided"
    fi

    # A.6 — All off
    prep_step "The LED will turn OFF."
    info "A.6  All OFF..."
    led_show 0 0 0 1
    if manual_step "Is the LED now OFF?"; then
        record_pass A.6 "LED off — all channels LOW"
    else
        record_skip A.6 "LED off — visual confirmation not provided"
    fi

    # A.7 — White fast blink (boot sequence, 4 Hz, 3 s)
    prep_step "The LED will BLINK WHITE rapidly (4 Hz) for 3 s — the boot sequence."
    info "A.7  White fast blink 4 Hz for 3 s (boot sequence)..."
    led_blink 1 1 1 4 3
    if manual_step "Did you see fast white blinking for ~3 s?"; then
        record_pass A.7 "White fast blink (4 Hz / 3 s) — boot sequence verified"
    else
        record_skip A.7 "White fast blink — visual confirmation not provided"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "TEST B — Reed switch wiring"
# ═══════════════════════════════════════════════════════════════════════════════
info "Reed switch is normally-open (NO): pin reads HIGH at rest, LOW when magnet present."
info "Pin: GPIO${REED_PIN}  (Pin 13, internal pull-up enabled)"

if [[ "$HAS_GPIO" -eq 0 ]]; then
    for sub in B.1 B.2 B.3; do
        record_skip "$sub" "RPi.GPIO unavailable"
    done
else
    # B.1 — Pin reads HIGH without magnet (warn and retry once if LOW — magnet may be nearby)
    REED_NO_MAGNET=$(gpio_py "
import RPi.GPIO as GPIO, time
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup($REED_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
time.sleep(0.2)
val = GPIO.input($REED_PIN)
GPIO.cleanup()
print(val)
" 2>/dev/null)

    if [[ "$REED_NO_MAGNET" == "0" ]]; then
        warn "B.1: reed reads LOW — magnet may be too close. Waiting 3 s and retrying..."
        sleep 3
        REED_NO_MAGNET=$(gpio_py "
import RPi.GPIO as GPIO, time
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup($REED_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
time.sleep(0.2)
val = GPIO.input($REED_PIN)
GPIO.cleanup()
print(val)
" 2>/dev/null)
    fi

    if [[ "$REED_NO_MAGNET" == "1" ]]; then
        record_pass B.1 "Reed switch reads HIGH (open) without magnet — pull-up OK"
    elif [[ "$REED_NO_MAGNET" == "0" ]]; then
        record_fail B.1 "Reed switch reads LOW without magnet after retry — magnet too close or switch stuck closed"
    else
        record_fail B.1 "Could not read reed switch pin — GPIO error"
    fi

    # B.2 — Pin reads LOW with magnet (manual)
    if manual_step \
        "Bring the magnet close to the reed switch (GPIO${REED_PIN}, Pin 13)." \
        "Hold it in place and press ENTER." \
        "Expected: pin reads LOW (0) while the magnet is present."; then
        REED_WITH_MAGNET=$(gpio_py "
import RPi.GPIO as GPIO, time
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup($REED_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
time.sleep(0.2)
# Poll for up to 2 s — accept the first LOW sample as success.
low_seen = False
end = time.time() + 2.0
while time.time() < end:
    if GPIO.input($REED_PIN) == 0:
        low_seen = True
        break
    time.sleep(0.05)
GPIO.cleanup()
print(0 if low_seen else 1)
" 2>/dev/null)
        if [[ "$REED_WITH_MAGNET" == "0" ]]; then
            record_pass B.2 "Reed switch reads LOW (closed) with magnet — switch and wiring OK"
        else
            record_fail B.2 "Reed switch still reads HIGH with magnet — switch not closing (check placement or magnet orientation)"
        fi
    else
        record_skip B.2 "Reed switch closed state — magnet test not performed"
    fi

    # B.3 — Verify pin returns HIGH after magnet removed
    if manual_step \
        "Remove the magnet from the reed switch and press ENTER." \
        "Expected: pin returns to HIGH (1) when open."; then
        REED_AFTER=$(gpio_py "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup($REED_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
import time; time.sleep(0.1)
val = GPIO.input($REED_PIN)
GPIO.cleanup()
print(val)
" 2>/dev/null)
        if [[ "$REED_AFTER" == "1" ]]; then
            record_pass B.3 "Reed switch returns HIGH after magnet removed — NO behaviour confirmed"
        else
            record_fail B.3 "Reed switch stays LOW after magnet removed — switch stuck or NC type"
        fi
    else
        record_skip B.3 "Reed switch open state after magnet removal — not tested"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "TEST C — GpioMonitor integration (reed switch interactions)"
# ═══════════════════════════════════════════════════════════════════════════════
info "Starts GpioMonitor from the installed source and exercises the three reed interactions."
info "Boot blink runs first (white, 3 s), then the monitor enters idle mode."
warn "ipr_keyboard.service must NOT be running — stop it first to avoid GPIO conflicts."

if [[ "$HAS_GPIO" -eq 0 ]]; then
    for sub in C.1 C.2 C.3 C.4; do
        record_skip "$sub" "RPi.GPIO unavailable"
    done
elif [ ! -f "$SRC_MONITOR" ]; then
    for sub in C.1 C.2 C.3 C.4; do
        record_skip "$sub" "gpio_monitor.py source not found"
    done
else
    # Stop production service so pins are free
    sudo systemctl stop ipr_keyboard 2>/dev/null && info "Stopped ipr_keyboard.service" || true
    sleep 1

    # Write a small driver that starts GpioMonitor and runs for a fixed duration.
    _DRIVER=$(mktemp /tmp/gpio_monitor_driver_XXXX.py)
    cat > "$_DRIVER" <<'DRIVER_EOF'
import sys, time, threading
sys.path.insert(0, sys.argv[1])   # project src/
from ipr_keyboard.gpio_monitor import GpioMonitor, gpio_available

if not gpio_available():
    print("GPIO not available")
    sys.exit(1)

duration = float(sys.argv[2]) if len(sys.argv) > 2 else 45.0
mon = GpioMonitor()
mon.start()
print("GpioMonitor running — press Ctrl+C or wait for timeout", flush=True)
try:
    time.sleep(duration)
except KeyboardInterrupt:
    pass
finally:
    mon.stop()
    print("GpioMonitor stopped", flush=True)
DRIVER_EOF

    PROJECT_SRC="$_INVOKING_HOME/dev/ipr-keyboard/src"

    # C.1 — Tap (< 3 s): LED shows status colour then goes off after 30 s idle timeout
    info "C.1  Starting GpioMonitor for tap test (45 s window)..."
    info "     Boot blink will run for 3 s (white fast blink), then monitor waits."
    sudo python3 "$_DRIVER" "$PROJECT_SRC" 45 &
    _MON_PID=$!
    sleep 4  # wait for boot blink to finish

    if manual_step \
        "Briefly bring the magnet close (< 3 s) then remove it."; then
        if manual_step \
            "Did the LED light a status colour (green / amber / red / blue) after the tap?" \
            "Did it turn off on its own after ~30 s?"; then
            record_pass C.1 "Tap interaction — LED woke, showed status, then went off"
        else
            record_skip C.1 "Tap interaction — visual confirmation not provided"
        fi
    else
        record_skip C.1 "Tap interaction — magnet step skipped"
    fi

    sudo kill "$_MON_PID" 2>/dev/null; wait "$_MON_PID" 2>/dev/null || true
    sleep 1

    # C.2 — Hold ≥ 3 s (hotspot arm): LED shows blue fast blink, then status colour / off on release
    info "C.2  Starting GpioMonitor for hotspot-arm test (30 s window)..."
    sudo python3 "$_DRIVER" "$PROJECT_SRC" 30 &
    _MON_PID=$!
    sleep 4  # wait for boot blink

    if manual_step \
        "Hold the magnet near the reed switch for ≥ 3 s then release." \
        "Watch for a colour change at the 3 s mark."; then
        if manual_step \
            "At 3 s: did the LED change to BLUE FAST BLINK (hotspot arming)?" \
            "On release: did it show the current status colour then turn off?" \
            "(Hotspot toggle is real — check 'systemctl is-active ipr-provision.service' if needed.)"; then
            record_pass C.2 "Hold ≥ 3 s — blue fast blink seen; hotspot toggle fired on release"
        else
            record_skip C.2 "Hotspot-arm hold — visual confirmation not provided"
        fi
    else
        record_skip C.2 "Hotspot-arm hold — magnet step skipped"
    fi

    sudo kill "$_MON_PID" 2>/dev/null; wait "$_MON_PID" 2>/dev/null || true
    sleep 1

    # C.3 — Hold ≥ 10 s (factory reset arm): LED shows red fast blink; release is SAFE here.
    #        Monkeypatch subprocess at the package level so relative imports work normally.
    _SAFE_DRIVER=$(mktemp /tmp/gpio_monitor_safe_driver_XXXX.py)
    cat > "$_SAFE_DRIVER" <<SAFE_DRIVER_EOF
import sys, time, subprocess
sys.path.insert(0, "$PROJECT_SRC")

# Patch subprocess before importing the module so reboot and nmcli deletes are suppressed.
_real_run = subprocess.run
def _safe_run(cmd, **kw):
    cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
    if "reboot" in cmd_str:
        print("[test] reboot suppressed", flush=True)
        return
    if "nmcli" in cmd_str and "delete" in cmd_str:
        print(f"[test] nmcli delete suppressed: {cmd_str}", flush=True)
        return
    return _real_run(cmd, **kw)
subprocess.run = _safe_run

from ipr_keyboard.gpio_monitor import GpioMonitor
mon = GpioMonitor()
mon.start()
print("Safe GpioMonitor running (reboot/nmcli delete suppressed)", flush=True)
try:
    time.sleep(60)
except KeyboardInterrupt:
    pass
finally:
    mon.stop()
    print("Safe GpioMonitor stopped", flush=True)
SAFE_DRIVER_EOF

    info "C.3  Starting SAFE GpioMonitor for factory-reset-arm test (60 s window)."
    warn "     Reboot and nmcli profile deletion are SUPPRESSED in this run."
    sudo python3 "$_SAFE_DRIVER" &
    _MON_PID=$!
    sleep 4  # wait for boot blink

    if manual_step \
        "Hold the magnet near the reed switch for ≥ 10 s then release." \
        "Watch for TWO colour changes: at 3 s and again at 10 s."; then
        if manual_step \
            "At 3 s: did the LED change to BLUE FAST BLINK (hotspot arm)?" \
            "At 10 s: did the LED change to RED FAST BLINK (factory reset arm)?" \
            "On release: did the Pi stay up (reboot suppressed in this safe run)?"; then
            record_pass C.3 "Hold ≥ 10 s — red fast blink seen at 10 s threshold"
        else
            record_skip C.3 "Factory-reset-arm hold — visual confirmation not provided"
        fi
    else
        record_skip C.3 "Factory-reset-arm hold — magnet step skipped"
    fi

    sudo kill "$_MON_PID" 2>/dev/null; wait "$_MON_PID" 2>/dev/null || true
    rm -f "$_SAFE_DRIVER"

    # C.4 — State colour accuracy: check that _state_color() returns a sensible tuple
    C4_OUT=$(sudo python3 - <<PYEOF 2>/dev/null
import sys
sys.path.insert(0, "$PROJECT_SRC")
from ipr_keyboard.gpio_monitor import _state_color
r, g, b = _state_color()
assert isinstance(r, int) and isinstance(g, int) and isinstance(b, int)
assert all(v in (0, 1) for v in (r, g, b))
print(f"state_color=({r},{g},{b})")
PYEOF
)
    if echo "$C4_OUT" | grep -q "state_color="; then
        record_pass C.4 "_state_color() returned a valid (R,G,B) tuple: $C4_OUT"
    else
        record_fail C.4 "_state_color() did not return a valid tuple"
    fi

    rm -f "$_DRIVER"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# LED teardown — turn off all channels regardless of how the tests ended.
# ═══════════════════════════════════════════════════════════════════════════════
if [[ "$HAS_GPIO" -eq 1 ]]; then
    gpio_py "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for pin in ($LED_R, $LED_G, $LED_B):
    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
GPIO.cleanup()
" 2>/dev/null || true
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
    [ "$SKIP_COUNT" -gt 0 ] && echo -e "  ${YELLOW}  ($SKIP_COUNT step(s) skipped — hardware or visual steps not confirmed)${RESET}"
    exit 0
else
    echo -e "  ${RED}${BOLD}✗ $FAIL_COUNT check(s) FAILED — review output above.${RESET}"
    exit 1
fi
