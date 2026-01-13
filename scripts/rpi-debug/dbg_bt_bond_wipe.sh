#!/usr/bin/env bash
#
# Remove Bluetooth bond(s) for Copilot/MCP diagnostics (DANGEROUS: removes pairing info)
#
# Usage:
#   sudo dbg_bt_bond_wipe.sh [MAC|all]
#     (no argument = interactive mode)
#
# Prerequisites:
#   - Must be run as root
#   - /etc/ipr_dbg.env should exist (written by install_dbg_tools.sh)
#
# category: Debug
# purpose: Remove Bluetooth bond(s) for troubleshooting (DANGEROUS)
# parameters: [MAC|all]
# sudo: yes
set -euo pipefail

DBG_ENV="/etc/ipr_dbg.env"
[[ -f "$DBG_ENV" ]] && source "$DBG_ENV"

# Source common environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dbg_common.env"

HCI="${DBG_HCI:-$HCI}"
LOG_ROOT="${DBG_LOG_ROOT:-$LOG_ROOT}"
BLE_SERVICE="${DBG_BLE_SERVICE:-$BLE_SERVICE}"
AGENT_SERVICE="${DBG_AGENT_SERVICE:-$AGENT_SERVICE}"
MAC="${1:-}"

TS="$(date -Is | tr ':' '-')"
OUT_DIR="$LOG_ROOT/bondwipe_${TS}"
mkdir -p "$OUT_DIR"
ln -sfn "$OUT_DIR" "$LOG_ROOT/latest_bondwipe"

LOG="$OUT_DIR/run.log"
exec > >(tee -a "$LOG") 2>&1

echo "== dbg_bt_bond_wipe: START $(date -Is) =="
echo "Adapter: $HCI"
echo "Agent:   $AGENT_SERVICE"
echo "BLE:     $BLE_SERVICE"
echo "Log dir: $OUT_DIR"
echo

echo "## Controller info"
sudo btmgmt -i "$HCI" info || true
echo

echo "## Known devices (bluetoothctl devices)"
bluetoothctl devices || true
echo

echo "## Stored devices on disk (/var/lib/bluetooth)"
CTRL_DIRS=(/var/lib/bluetooth/*)
FOUND_CTRL_DIR=""
for d in "${CTRL_DIRS[@]}"; do
  [[ -d "$d" ]] || continue
  FOUND_CTRL_DIR="$d"
  break
done

if [[ -n "$FOUND_CTRL_DIR" && -d "$FOUND_CTRL_DIR" ]]; then
  echo "Controller dir: $FOUND_CTRL_DIR"
  find "$FOUND_CTRL_DIR" -maxdepth 1 -type d -name '*:*:*:*:*:*' -print | sed 's|.*/||' || true
else
  echo "WARNING: Could not locate /var/lib/bluetooth controller directory."
fi
echo

if [[ -z "$MAC" ]]; then
  echo "ERROR: No MAC provided."
  echo "Usage: dbg_bt_bond_wipe.sh AA:BB:CC:DD:EE:FF"
  echo "No changes were made."
  exit 2
fi

MAC_UP="$(echo "$MAC" | tr '[:lower:]' '[:upper:]')"
if ! [[ "$MAC_UP" =~ ^([0-9A-F]{2}:){5}[0-9A-F]{2}$ ]]; then
  echo "ERROR: Invalid MAC format: '$MAC'"
  exit 3
fi

echo "== Target device MAC =="
echo "$MAC_UP"
echo

echo "## Device details (bluetoothctl info)"
bluetoothctl info "$MAC_UP" || true
echo

echo "== SAFETY CHECKS =="
echo "This will REMOVE the bond/known device from the Pi for: $MAC_UP"
echo "You will likely need to remove it on Windows and re-pair."
echo

read -r -p "Type EXACT MAC to confirm: " CONFIRM1
CONFIRM1_UP="$(echo "$CONFIRM1" | tr '[:lower:]' '[:upper:]')"
if [[ "$CONFIRM1_UP" != "$MAC_UP" ]]; then
  echo "ERROR: MAC confirmation did not match. Aborting."
  exit 4
fi

read -r -p "Type 'WIPE' to proceed: " CONFIRM2
if [[ "$CONFIRM2" != "WIPE" ]]; then
  echo "ERROR: Second confirmation not received. Aborting."
  exit 5
fi

echo
echo "== EXECUTING WIPE =="
echo

echo "## Remove device via bluetoothctl"
bluetoothctl remove "$MAC_UP" || true
echo

echo "## Remove device via btmgmt (unpair)"
sudo btmgmt -i "$HCI" unpair "$MAC_UP" || true
echo

echo "## Remove cached device directory (filesystem) if present"
if [[ -n "$FOUND_CTRL_DIR" && -d "$FOUND_CTRL_DIR/$MAC_UP" ]]; then
  echo "Removing: $FOUND_CTRL_DIR/$MAC_UP"
  sudo rm -rf "$FOUND_CTRL_DIR/$MAC_UP"
else
  echo "No device dir found at: ${FOUND_CTRL_DIR:-<unknown>}/$MAC_UP"
fi
echo

echo "## Restart bluetooth stack to apply clean state"
sudo systemctl stop "$BLE_SERVICE" || true
sudo systemctl stop "$AGENT_SERVICE" || true
sudo systemctl restart bluetooth
sudo systemctl start "$AGENT_SERVICE" || true
sudo systemctl start "$BLE_SERVICE" || true
echo

echo "== Post-state check =="
bluetoothctl devices || true
echo

echo "== dbg_bt_bond_wipe: DONE $(date -Is) =="
echo "Log: $LOG"
echo "Dir: $OUT_DIR"
