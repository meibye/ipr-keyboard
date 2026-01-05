#!/usr/bin/env bash
#
# diag_bt_visibility.sh
#
# Diagnose why the BLE HID device is not visible on PC/phone scans.
#
# Usage:
#   sudo ./diag_bt_visibility.sh              # diagnose only
#   sudo ./diag_bt_visibility.sh --fix        # apply best-effort fixes + restart services
#   sudo ./diag_bt_visibility.sh --fix --hci hci1
#
set -euo pipefail

FIX=0
HCI="hci0"

for arg in "$@"; do
  case "$arg" in
    --fix) FIX=1 ;;
    --hci=*) HCI="${arg#*=}" ;;
    --hci) shift; HCI="${1:-hci0}" ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0 [--fix] [--hci hci0]"
  exit 1
fi

AGENT_SVC="bt_hid_agent_unified.service"
BLE_SVC="bt_hid_ble.service"
ENV_FILE="/opt/ipr_common.env"

RED=$'\033[31m'
GRN=$'\033[32m'
YEL=$'\033[33m'
BLU=$'\033[34m'
RST=$'\033[0m'

pass() { echo "${GRN}PASS${RST} - $*"; }
warn() { echo "${YEL}WARN${RST} - $*"; }
fail() { echo "${RED}FAIL${RST} - $*"; }
info() { echo "${BLU}INFO${RST} - $*"; }

have_cmd() { command -v "$1" >/dev/null 2>&1; }

section() {
  echo
  echo "================================================================================"
  echo "$*"
  echo "================================================================================"
}

need_cmds=(btmgmt systemctl journalctl bluetoothctl)
for c in "${need_cmds[@]}"; do
  if ! have_cmd "$c"; then
    fail "Missing command: $c (install it / ensure PATH)"
    exit 2
  fi
done

section "1) Environment"
info "Using HCI=${HCI}"
if [[ -f "$ENV_FILE" ]]; then
  pass "Found ${ENV_FILE}"
  # Show the most relevant env knobs (don’t spam whole file)
  grep -E '^(BT_CONTROLLER_MODE|BT_ENABLE_CLASSIC_DISCOVERABLE|BT_HCI|BT_DEVICE_NAME|BT_AGENT_DEBUG|BT_BLE_DEBUG)=' "$ENV_FILE" || true
else
  warn "Missing ${ENV_FILE} (services may still run, but defaults may differ)"
fi

section "2) Adapter state via btmgmt"
BTINFO="$(btmgmt -i "$HCI" info 2>&1 || true)"
echo "$BTINFO"

if echo "$BTINFO" | grep -qi "No such controller"; then
  fail "Controller ${HCI} not found. Check: btmgmt list ; hciconfig -a"
  exit 3
fi

# Very coarse checks (btmgmt output varies by version)
echo "$BTINFO" | grep -qi "current settings:.*powered"      && pass "Adapter is Powered"      || fail "Adapter is NOT powered"
echo "$BTINFO" | grep -qi "current settings:.*connectable"  && pass "Adapter is Connectable" || warn "Adapter is NOT connectable"
echo "$BTINFO" | grep -qi "current settings:.*discoverable" && pass "Adapter is Discoverable" || warn "Adapter is NOT discoverable (host scanning won't see it)"
echo "$BTINFO" | grep -qi "current settings:.*le"           && pass "LE is enabled"          || warn "LE not shown as enabled (should be ON for BLE HID)"

# Advertising state is not always shown in `info`, but we still attempt to read it:
ADVSTATE="$(btmgmt -i "$HCI" info 2>&1 || true)"
if echo "$ADVSTATE" | grep -qi "current settings:.*advertising"; then
  pass "Adapter is ADVERTISING"
else
  fail "Adapter is NOT advertising"
fi

section "3) bluetoothd ExecStart / experimental mode"
# Show effective unit file
systemctl cat bluetooth.service || true

# Show running process line (most reliable)
BTD_PS="$(ps -ef | grep -E '[b]luetoothd' || true)"
echo "$BTD_PS"

if echo "$BTD_PS" | grep -q -- "--experimental"; then
  pass "bluetoothd is running with --experimental"
else
  warn "bluetoothd does NOT show --experimental (some stacks need it for LE adv/GATT behaviors)"
fi

section "4) Service status"
systemctl --no-pager -l status bluetooth.service || true
echo
systemctl --no-pager -l status "$AGENT_SVC" || true
echo
systemctl --no-pager -l status "$BLE_SVC" || true

section "5) Recent logs (most useful signals)"
echo "---- ${AGENT_SVC} (last 120 lines) ----"
journalctl -u "$AGENT_SVC" -n 120 --no-pager || true
echo
echo "---- ${BLE_SVC} (last 200 lines) ----"
journalctl -u "$BLE_SVC" -n 200 --no-pager || true

# Highlight key lines
echo
info "Key BLE lines:"
journalctl -u "$BLE_SVC" -n 300 --no-pager | grep -E "Advertisement registered|GATT application registered|RegisterAdvertisement|RegisterApplication|ERROR|Advertising LocalName" || true

section "6) Quick check: bluetoothctl show"
# bluetoothctl is sometimes blocked by rfkill / permissions; still try
BTCTL_SHOW="$(bluetoothctl show 2>&1 || true)"
echo "$BTCTL_SHOW"
echo "$BTCTL_SHOW" | grep -qi "Powered: yes" && pass "bluetoothctl: Powered yes" || warn "bluetoothctl: Powered not yes"
echo "$BTCTL_SHOW" | grep -qi "Discoverable: yes" && pass "bluetoothctl: Discoverable yes" || warn "bluetoothctl: Discoverable not yes"

section "7) Optional: apply best-effort fixes"
if [[ "$FIX" -eq 1 ]]; then
  info "Applying fixes: set LE-only + enable advertising + discoverable + restart services"

  # Best-effort: clear and set adapter state
  btmgmt -i "$HCI" power on || true
  btmgmt -i "$HCI" le on || true
  btmgmt -i "$HCI" bredr off || true
  btmgmt -i "$HCI" connectable on || true
  btmgmt -i "$HCI" advertising on || true
  btmgmt -i "$HCI" discoverable on || true

  # Restart stack and services in safe order
  systemctl restart bluetooth.service || true
  sleep 2
  systemctl restart "$AGENT_SVC" || true
  sleep 2
  systemctl restart "$BLE_SVC" || true

  echo
  info "Re-check adapter state after fixes:"
  btmgmt -i "$HCI" info || true

  echo
  info "Re-check key BLE logs after fixes:"
  journalctl -u "$BLE_SVC" -n 80 --no-pager | tail -n 80 || true

  echo
  pass "Fix attempt completed. Now rescan from PC/phone."
else
  info "Diagnosis complete. Re-run with --fix to apply best-effort settings + restarts."
fi
