#!/usr/bin/env bash
#
# svc_status_monitor.sh
#
# Real-time status monitor for ipr-keyboard services, daemons, and applications.
# Groups services by Bluetooth backend (uinput/BLE), shows color-coded status, and allows user control.
# Usage: ./scripts/svc_status_monitor.sh [delay_seconds]

set -euo pipefail

# Color codes
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
RESET="\033[0m"
BOLD="\033[1m"

# Default delay
DELAY="${1:-2}"

# Service definitions
# Format: name:type:description:backend
SERVICES=(
  "ipr_keyboard.service:app:Main Application:both"
  "bt_hid_uinput.service:daemon:UInput HID Daemon:uinput"
  "bt_hid_ble.service:daemon:BLE HID Daemon:ble"
  "bt_hid_agent.service:daemon:BLE Pairing Agent:ble"
  "ipr_backend_manager.service:daemon:Backend Manager:both"
)

# Helper to get status
get_status() {
  local svc="$1"
  if systemctl is-active --quiet "$svc"; then
    echo -e "${GREEN}active${RESET}"
  elif systemctl is-enabled --quiet "$svc"; then
    echo -e "${YELLOW}inactive${RESET}"
  else
    echo -e "${RED}disabled${RESET}"
  fi
}

# Helper to print journal logs
print_journal() {
  local svc="$1"
  echo -e "${CYAN}--- Journal for $svc ---${RESET}"
  journalctl -u "$svc" -n 10 --no-pager
}

# Main loop
while true; do
  clear
  echo -e "${BOLD}IPR-KEYBOARD SERVICE STATUS MONITOR${RESET} (delay: ${DELAY}s)"
  echo
  echo -e "${BOLD}UINPUT Backend Services:${RESET}"
  for entry in "${SERVICES[@]}"; do
    IFS=":" read -r name type desc backend <<< "$entry"
    if [[ "$backend" == "uinput" || "$backend" == "both" ]]; then
      status=$(get_status "$name")
      printf "  %-25s %-10s %s\n" "$name" "$status" "$desc"
    fi
  done
  echo
  echo -e "${BOLD}BLE Backend Services:${RESET}"
  for entry in "${SERVICES[@]}"; do
    IFS=":" read -r name type desc backend <<< "$entry"
    if [[ "$backend" == "ble" || "$backend" == "both" ]]; then
      status=$(get_status "$name")
      printf "  %-25s %-10s %s\n" "$name" "$status" "$desc"
    fi
  done
  echo
  echo -e "${BOLD}Commands:${RESET}"
  echo "  [s] Start service   [t] Stop service   [r] Restart service   [j] Show journal   [q] Quit"
  echo "  Enter: <cmd> <service> (e.g. s bt_hid_ble.service)"
  echo
  read -t "$DELAY" -p "Action: " cmd svc || true
  if [[ -n "${cmd:-}" && -n "${svc:-}" ]]; then
    case "$cmd" in
      s) sudo systemctl start "$svc" ;;
      t) sudo systemctl stop "$svc" ;;
      r) sudo systemctl restart "$svc" ;;
      j) print_journal "$svc"; read -n 1 -s -p "Press any key to continue..." ;;
      q) exit 0 ;;
      *) echo "Unknown command" ;;
    esac
  fi
  unset cmd svc
  sleep "$DELAY"
done
