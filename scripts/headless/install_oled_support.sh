#!/usr/bin/env bash
#
# install_oled_support.sh — everything the OLED status display needs
#
# Installs, idempotently:
#   1. dtparam=i2c_arm=on (+ 400 kHz) in /boot/firmware/config.txt
#                                                → I2C bus 1 (GPIO 2/3)
#   2. /etc/modules-load.d/ipr-oled.conf        → /dev/i2c-1 at boot
#   3. i2c-tools, python3-pil, fonts-dejavu-core → i2cdetect/i2cset, Pillow
#                                                  and the display font
#   4. app user in group i2c                    → /dev/i2c-1 without root
#   5. /etc/default/ipr-oled + ipr-led-halt.sh  → panel blanked at halt
#   6. include-system-site-packages in the venv → Pillow importable by the app
#
# Usage:
#   sudo ./scripts/headless/install_oled_support.sh
#
# Called by provision/04_enable_services.sh and deploy_full_update.sh after
# install_gpio_support.sh.  Safe to re-run.  A reboot is needed for step 1
# on a device where I2C was off; the rest is live after
# `systemctl restart ipr_keyboard.service`.  No display connected is fine:
# the app logs "OLED display disabled" and runs as before.
#
# category: Headless
# purpose: Enable I2C, install Pillow/i2c-tools, group and halt hook for the OLED
# sudo: yes

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()   { echo -e "${GREEN}[oled-support]${NC} $*"; }
warn()  { echo -e "${YELLOW}[oled-support]${NC} $*"; }
error() { echo -e "${RED}[oled-support ERROR]${NC} $*" >&2; }

if [[ $EUID -ne 0 ]]; then
  error "Run as root: sudo bash $0"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ---------------------------------------------------------------------------
# Resolve the app user (same rules as install_gpio_support.sh)
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
# Bus and address — from config.json when present, else the defaults
# ---------------------------------------------------------------------------
OLED_BUS=1; OLED_ADDR=60
CONFIG_JSON="${REPO_DIR}/config.json"
if [[ -f "${CONFIG_JSON}" ]] && command -v python3 >/dev/null 2>&1; then
  read -r OLED_BUS OLED_ADDR < <(python3 - "${CONFIG_JSON}" <<'PY' || echo "1 60"
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get("OledI2cBus", 1), d.get("OledI2cAddress", 60))
PY
)
fi
OLED_ADDR_HEX="$(printf '0x%02x' "${OLED_ADDR}")"
log "Display: I2C bus ${OLED_BUS}, address ${OLED_ADDR_HEX}"

# ---------------------------------------------------------------------------
# 1. Firmware: I2C on, 400 kHz (a full 1 KB frame is ~25 ms instead of ~90 ms)
# ---------------------------------------------------------------------------
BOOT_CONFIG=""
for c in /boot/firmware/config.txt /boot/config.txt; do
  [[ -f "$c" ]] && { BOOT_CONFIG="$c"; break; }
done
I2C_WAS_ON=0
if [[ -n "${BOOT_CONFIG}" ]]; then
  grep -q '^dtparam=i2c_arm=on' "${BOOT_CONFIG}" && I2C_WAS_ON=1
  MARK_BEGIN="# >>> ipr-keyboard OLED display >>>"
  MARK_END="# <<< ipr-keyboard OLED display <<<"
  BLOCK="${MARK_BEGIN}
# I2C bus 1 for the SSD1306 status display (GPIO 2/3, addr ${OLED_ADDR_HEX}).
# Managed by scripts/headless/install_oled_support.sh
dtparam=i2c_arm=on
dtparam=i2c_arm_baudrate=400000
${MARK_END}"
  if grep -qF "${MARK_BEGIN}" "${BOOT_CONFIG}"; then
    python3 - "${BOOT_CONFIG}" "${MARK_BEGIN}" "${MARK_END}" "${BLOCK}" <<'PY'
import re, sys
path, b, e, block = sys.argv[1:5]
s = open(path).read()
s = re.sub(re.escape(b) + r".*?" + re.escape(e), block, s, flags=re.S)
open(path, "w").write(s)
PY
    log "Updated OLED block in ${BOOT_CONFIG}"
  else
    printf '\n%s\n' "${BLOCK}" >> "${BOOT_CONFIG}"
    log "Added OLED block to ${BOOT_CONFIG} (takes effect at next reboot)"
  fi
else
  warn "No config.txt found — skipping I2C dtparam (not a Raspberry Pi?)"
fi

# ---------------------------------------------------------------------------
# 2. i2c-dev at boot (and now, when the overlay is already active)
# ---------------------------------------------------------------------------
printf 'i2c-dev\n' > /etc/modules-load.d/ipr-oled.conf
modprobe i2c-dev 2>/dev/null || true
log "i2c-dev autoload: /etc/modules-load.d/ipr-oled.conf"

# ---------------------------------------------------------------------------
# 3. Packages: Pillow + font from Debian (no ARMv6 wheel on PyPI), i2c-tools
# ---------------------------------------------------------------------------
MISSING=()
for pkg in i2c-tools python3-pil fonts-dejavu-core; do
  dpkg -s "$pkg" >/dev/null 2>&1 || MISSING+=("$pkg")
done
if (( ${#MISSING[@]} )); then
  log "Installing packages: ${MISSING[*]}"
  if ! DEBIAN_FRONTEND=noninteractive apt-get install -y "${MISSING[@]}"; then
    warn "apt-get failed (offline?). Install later: sudo apt-get install ${MISSING[*]}"
  fi
fi

# ---------------------------------------------------------------------------
# 4. Group i2c — /dev/i2c-N is root:i2c 0660; no sudoers entry needed
# ---------------------------------------------------------------------------
if getent group i2c >/dev/null; then
  if id -nG "${APP_USER}" | tr ' ' '\n' | grep -qx i2c; then
    log "${APP_USER} already in group i2c"
  else
    usermod -aG i2c "${APP_USER}"
    log "Added ${APP_USER} to group i2c (applies after: systemctl restart ipr_keyboard.service)"
  fi
else
  warn "Group i2c does not exist (i2c-tools not installed?) — the app cannot open /dev/i2c-${OLED_BUS}"
fi

# ---------------------------------------------------------------------------
# 5. Halt hook: ipr-led-halt.sh also blanks the panel (0xAE via i2cset)
# ---------------------------------------------------------------------------
cat > /etc/default/ipr-oled <<EOF
# Bus/address for ipr-led-halt.sh — managed by install_oled_support.sh
OLED_BUS=${OLED_BUS}
OLED_ADDR=${OLED_ADDR_HEX}
EOF
install -m 0755 -o root -g root "${SCRIPT_DIR}/ipr_led_halt.sh" /usr/local/sbin/ipr-led-halt.sh
log "Installed /etc/default/ipr-oled and refreshed ipr-led-halt.sh (panel off at the end of a shutdown)"

# ---------------------------------------------------------------------------
# 6. Venv visibility: the app imports Pillow from the Debian package
# ---------------------------------------------------------------------------
VENV_CFG="${REPO_DIR}/.venv/pyvenv.cfg"
if [[ -f "${VENV_CFG}" ]]; then
  if grep -q '^include-system-site-packages = false' "${VENV_CFG}"; then
    sed -i 's/^include-system-site-packages = false/include-system-site-packages = true/' "${VENV_CFG}"
    log "Enabled system site-packages in ${VENV_CFG} (so the app can import PIL)"
  fi
  if "${REPO_DIR}/.venv/bin/python" -c 'from PIL import Image, ImageDraw, ImageFont' 2>/dev/null; then
    log "Pillow importable from the app venv"
  else
    VENV_PYVER="$("${REPO_DIR}/.venv/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)"
    SYS_PYVER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)"
    if [[ -n "${VENV_PYVER}" && "${VENV_PYVER}" != "${SYS_PYVER}" ]]; then
      warn "Pillow not importable: the venv runs Python ${VENV_PYVER} (uv-managed) but Debian python3-pil is for ${SYS_PYVER}."
      warn "On a production image the system Python satisfies requires-python and the venv uses it;"
      warn "on this board either re-create the venv with the system Python or, for a dev board only:"
      warn "  ${REPO_DIR}/.venv/bin/python -m pip install pillow   (or: uv pip install pillow)"
    else
      warn "Pillow still not importable from the app venv — is python3-pil installed?"
    fi
  fi
else
  warn "No venv at ${REPO_DIR}/.venv — run scripts/sys_setup_venv.sh first"
fi

# ---------------------------------------------------------------------------
# Verify (non-fatal: no display is a valid configuration)
# ---------------------------------------------------------------------------
systemctl daemon-reload
DEV="/dev/i2c-${OLED_BUS}"
ADDR_SHORT="${OLED_ADDR_HEX#0x}"
if [[ -c "${DEV}" ]]; then
  # No grep -q here: with pipefail an early grep exit makes i2cdetect fail the pipeline.
  if [[ -x /usr/sbin/i2cdetect ]] && /usr/sbin/i2cdetect -y "${OLED_BUS}" 2>/dev/null | grep -iE " (${ADDR_SHORT}|UU)( |$)" >/dev/null; then
    log "SSD1306 answers at ${OLED_ADDR_HEX} on ${DEV}"
  else
    warn "Nothing at ${OLED_ADDR_HEX} on ${DEV} — display not connected? The app runs without it."
  fi
elif [[ "${I2C_WAS_ON}" -eq 0 ]]; then
  warn "${DEV} does not exist yet — reboot to activate dtparam=i2c_arm=on"
else
  warn "${DEV} missing although I2C is enabled — check 'dmesg | grep i2c'"
fi

log "Done. Restart the app to pick up the display (and the i2c group):"
log "  sudo systemctl restart ipr_keyboard.service"
