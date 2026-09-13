#!/usr/bin/env bash
#
# install_gpio_support.sh — everything the status LED and magnet need
#
# Installs, idempotently:
#   1. gpio= lines in /boot/firmware/config.txt  → LED solid white from power-on
#   2. /usr/local/sbin/ipr-led-boot.sh + ipr-led-boot.service
#                                                → white blink during OS boot
#   3. systemd drop-in for ipr_keyboard.service  → Conflicts=ipr-led-boot.service
#                                                  (hands the pins to the app)
#   4. /usr/local/bin/ipr_hotspot_ctl.sh + sudoers entry
#                                                → magnet can start/stop the
#                                                  hotspot and reset WiFi
#   5. /etc/default/ipr-led                      → pin numbers for the boot blink
#   6. python3-rpi-lgpio / gpiod packages, and include-system-site-packages
#      in the app venv                           → RPi.GPIO importable by the app
#
# Usage:
#   sudo ./scripts/headless/install_gpio_support.sh
#
# Called by provision/04_enable_services.sh and deploy_full_update.sh.
# Safe to re-run.  A reboot is needed for step 1; the rest is live after
# `systemctl restart ipr_keyboard.service`.
#
# category: Headless
# purpose: Install boot LED unit, hotspot helper, sudoers and GPIO packages
# sudo: yes

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()   { echo -e "${GREEN}[gpio-support]${NC} $*"; }
warn()  { echo -e "${YELLOW}[gpio-support]${NC} $*"; }
error() { echo -e "${RED}[gpio-support ERROR]${NC} $*" >&2; }

if [[ $EUID -ne 0 ]]; then
  error "Run as root: sudo bash $0"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ---------------------------------------------------------------------------
# Resolve the app user (same rules as install_network_helper.sh)
# ---------------------------------------------------------------------------
if [[ -f /opt/ipr_common.env ]]; then
  # shellcheck disable=SC1091
  source /opt/ipr_common.env
fi
APP_USER="${APP_USER:-$(systemctl show -p User ipr_keyboard.service 2>/dev/null | cut -d= -f2 || true)}"
APP_USER="${APP_USER:-${SUDO_USER:-}}"
if [[ -z "${APP_USER}" ]]; then
  error "Could not determine APP_USER. Set it in /opt/ipr_common.env or run: sudo APP_USER=<user> bash $0"
  exit 1
fi
log "App user: ${APP_USER}   repo: ${REPO_DIR}"

# ---------------------------------------------------------------------------
# Pin numbers — from config.json when present, else the documented defaults
# ---------------------------------------------------------------------------
REED_PIN=27; LED_R=22; LED_G=23; LED_B=24
CONFIG_JSON="${REPO_DIR}/config.json"
if [[ -f "${CONFIG_JSON}" ]] && command -v python3 >/dev/null 2>&1; then
  read -r REED_PIN LED_R LED_G LED_B < <(python3 - "${CONFIG_JSON}" <<'PY' || echo "27 22 23 24"
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get("GpioReedPin", 27), d.get("GpioLedRPin", 22),
      d.get("GpioLedGPin", 23), d.get("GpioLedBPin", 24))
PY
)
fi
log "Pins: reed=GPIO${REED_PIN}  LED R/G/B=GPIO${LED_R}/${LED_G}/${LED_B}"

# ---------------------------------------------------------------------------
# 1. Firmware: LED solid white from power-on, reed pull-up
# ---------------------------------------------------------------------------
BOOT_CONFIG=""
for c in /boot/firmware/config.txt /boot/config.txt; do
  [[ -f "$c" ]] && { BOOT_CONFIG="$c"; break; }
done
if [[ -n "${BOOT_CONFIG}" ]]; then
  MARK_BEGIN="# >>> ipr-keyboard status LED >>>"
  MARK_END="# <<< ipr-keyboard status LED <<<"
  BLOCK="${MARK_BEGIN}
# Drive the RGB status LED high (white) from the moment the firmware runs,
# so the user sees power before the kernel or any service is up.
# Managed by scripts/headless/install_gpio_support.sh
gpio=${LED_R},${LED_G},${LED_B}=op,dh
gpio=${REED_PIN}=ip,pu
${MARK_END}"
  if grep -qF "${MARK_BEGIN}" "${BOOT_CONFIG}"; then
    # replace the managed block in place
    python3 - "${BOOT_CONFIG}" "${MARK_BEGIN}" "${MARK_END}" "${BLOCK}" <<'PY'
import re, sys
path, b, e, block = sys.argv[1:5]
s = open(path).read()
s = re.sub(re.escape(b) + r".*?" + re.escape(e), block, s, flags=re.S)
open(path, "w").write(s)
PY
    log "Updated LED block in ${BOOT_CONFIG}"
  else
    printf '\n%s\n' "${BLOCK}" >> "${BOOT_CONFIG}"
    log "Added LED block to ${BOOT_CONFIG} (takes effect at next reboot)"
  fi
else
  warn "No config.txt found — skipping firmware LED line (not a Raspberry Pi?)"
fi

# ---------------------------------------------------------------------------
# 2. Boot blink script + unit
# ---------------------------------------------------------------------------
cat > /etc/default/ipr-led <<EOF
# Pin numbers for ipr-led-boot.sh — managed by install_gpio_support.sh
LED_R=${LED_R}
LED_G=${LED_G}
LED_B=${LED_B}
EOF
install -m 0755 -o root -g root "${SCRIPT_DIR}/ipr_led_boot.sh" /usr/local/sbin/ipr-led-boot.sh
install -m 0644 -o root -g root "${SCRIPT_DIR}/ipr-led-boot.service" /etc/systemd/system/ipr-led-boot.service
install -m 0755 -o root -g root "${SCRIPT_DIR}/ipr_led_halt.sh" /usr/local/sbin/ipr-led-halt.sh
install -m 0644 -o root -g root "${SCRIPT_DIR}/ipr-led-halt.service" /etc/systemd/system/ipr-led-halt.service
log "Installed ipr-led-boot (white blink at boot) and ipr-led-halt (LED off at the end of a shutdown)"

# ---------------------------------------------------------------------------
# 3. Hand-over: the app stops the boot blinker when it starts
# ---------------------------------------------------------------------------
DROPIN_DIR=/etc/systemd/system/ipr_keyboard.service.d
mkdir -p "${DROPIN_DIR}"
cat > "${DROPIN_DIR}/10-led-boot.conf" <<'EOF'
# Managed by scripts/headless/install_gpio_support.sh
# Stop the early white-blink unit so the application can claim the LED pins.
#
# Conflicts= alone is not enough: at boot both units sit in the same start
# transaction and systemd resolves the conflict by dropping a job, not by
# stopping the blinker, so gpioset kept the lines and the app saw "GPIO busy".
# The "+" prefix runs the stop as root even though the service runs as the
# app user.  "-" makes a missing unit non-fatal.
[Unit]
Conflicts=ipr-led-boot.service
After=ipr-led-boot.service

[Service]
ExecStartPre=-+/usr/bin/systemctl stop ipr-led-boot.service
EOF
log "Installed ${DROPIN_DIR}/10-led-boot.conf"

# Older unit files carry CapabilityBoundingSet=CAP_NET_BIND_SERVICE, which
# strips the setuid capabilities sudo needs: every `sudo` from inside the
# service then fails with "unable to change to root gid".  Remove it.
UNIT_FILE=/etc/systemd/system/ipr_keyboard.service
if [[ -f "${UNIT_FILE}" ]] && grep -q '^CapabilityBoundingSet=' "${UNIT_FILE}"; then
  sed -i '/^CapabilityBoundingSet=/d' "${UNIT_FILE}"
  log "Removed CapabilityBoundingSet from ${UNIT_FILE} (sudo would fail inside the service)"
fi

# ---------------------------------------------------------------------------
# 4. Privileged helper + sudoers
# ---------------------------------------------------------------------------
HELPER_DST=/usr/local/bin/ipr_hotspot_ctl.sh
install -m 0755 -o root -g root "${SCRIPT_DIR}/ipr_hotspot_ctl.sh" "${HELPER_DST}"

SUDOERS_DST="/etc/sudoers.d/${APP_USER}-ipr-gpio"
SUDOERS_TMP="$(mktemp)"
trap 'rm -f "${SUDOERS_TMP}"' EXIT
cat > "${SUDOERS_TMP}" <<EOF
# Managed by install_gpio_support.sh — do not edit by hand.
# Magnet gestures (gpio_monitor.py) and the dashboard's reboot/shutdown buttons.
${APP_USER} ALL=(root) NOPASSWD: ${HELPER_DST}, /usr/sbin/reboot, /usr/sbin/shutdown, /usr/bin/systemctl reboot, /usr/bin/systemctl poweroff
EOF
if visudo -cf "${SUDOERS_TMP}" >/dev/null; then
  install -m 0440 -o root -g root "${SUDOERS_TMP}" "${SUDOERS_DST}"
  log "Installed sudoers entry ${SUDOERS_DST}"
else
  error "sudoers validation failed — not installed"
  exit 1
fi

# ---------------------------------------------------------------------------
# 5. GPIO packages and venv visibility
# ---------------------------------------------------------------------------
# rpi-lgpio provides the RPi.GPIO API on top of lgpio and works on both the
# Zero W (armhf) and the Zero 2 W (arm64) with current kernels.  gpiod
# provides gpioset for the boot blink.
MISSING=()
for pkg in python3-rpi-lgpio gpiod; do
  dpkg -s "$pkg" >/dev/null 2>&1 || MISSING+=("$pkg")
done
if (( ${#MISSING[@]} )); then
  log "Installing packages: ${MISSING[*]}"
  if ! DEBIAN_FRONTEND=noninteractive apt-get install -y "${MISSING[@]}"; then
    warn "apt-get failed (offline?). Install later: sudo apt-get install ${MISSING[*]}"
  fi
fi

VENV_CFG="${REPO_DIR}/.venv/pyvenv.cfg"
if [[ -f "${VENV_CFG}" ]]; then
  if grep -q '^include-system-site-packages = false' "${VENV_CFG}"; then
    sed -i 's/^include-system-site-packages = false/include-system-site-packages = true/' "${VENV_CFG}"
    log "Enabled system site-packages in ${VENV_CFG} (so the app can import RPi.GPIO)"
  fi
  if "${REPO_DIR}/.venv/bin/python" -c 'import RPi.GPIO' 2>/dev/null; then
    log "RPi.GPIO importable from the app venv"
  else
    warn "RPi.GPIO still not importable from the app venv — is python3-rpi-lgpio installed?"
  fi
else
  warn "No venv at ${REPO_DIR}/.venv — run scripts/sys_setup_venv.sh first"
fi

# ---------------------------------------------------------------------------
# Activate
# ---------------------------------------------------------------------------
systemctl daemon-reload
systemctl enable ipr-led-boot.service >/dev/null 2>&1 || true
systemctl enable --now ipr-led-halt.service >/dev/null 2>&1 || true
log "ipr-led-boot.service enabled (runs at next boot); ipr-led-halt.service armed for the next shutdown"

# Smoke test the sudo grant as the app user
if su -s /bin/sh "${APP_USER}" -c "sudo -n ${HELPER_DST} status" >/dev/null 2>&1 \
   || [[ $? -eq 1 ]]; then
  log "sudo grant OK — ${APP_USER} can run ${HELPER_DST}"
else
  warn "sudo smoke test failed — check ${SUDOERS_DST}"
fi

log "Done. Restart the app to pick up the LED changes:"
log "  sudo systemctl restart ipr_keyboard.service"
log "Reboot once to see the firmware/boot phases of the LED."
