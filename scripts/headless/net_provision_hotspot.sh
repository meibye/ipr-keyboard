#!/usr/bin/env bash
#
# Hotspot and auto-switch provisioning script for ipr-keyboard
# Creates a Wi-Fi hotspot when the Pi cannot connect to a known network
#
# Purpose:
#   - Waits for Wi-Fi connection (45 seconds)
#   - If no connection, creates a hotspot named "ipr-setup-XXXX"
#   - Hotspot provides access to web provisioning interface at http://10.42.0.1/
#
# Installation:
#   sudo cp scripts/headless/net_provision_hotspot.sh /usr/local/sbin/ipr-provision.sh
#   sudo chmod +x /usr/local/sbin/ipr-provision.sh
#
# Service:
#   Managed by ipr-provision.service
#
# category: Headless
# purpose: Auto-hotspot provisioning for headless Pi
# sudo: yes

set -euo pipefail

HOTSPOT_CON="ipr-hotspot"
WLAN_IF="wlan0"
AP_SSID_PREFIX="ipr-setup"
AP_PASS_MINLEN=10

log() { echo "[ipr-provision] $*"; }

machine_suffix() {
  (cat /etc/machine-id 2>/dev/null || echo "0000") | head -c 4
}

ensure_hotspot_connection() {
  local ssid="${AP_SSID_PREFIX}-$(machine_suffix)"
  # Use a stable password derived from machine-id
  local pass="ipr-$(cat /etc/machine-id | tr -d '\n' | head -c 12)"
  if ((${#pass} < AP_PASS_MINLEN)); then pass="ipr-setup-12345678"; fi

  if nmcli -t -f NAME con show | grep -qx "${HOTSPOT_CON}"; then
    log "Hotspot connection exists: ${HOTSPOT_CON}"
  else
    log "Creating hotspot connection: ${HOTSPOT_CON} (${ssid})"
    nmcli con add type wifi ifname "${WLAN_IF}" con-name "${HOTSPOT_CON}" autoconnect no ssid "${ssid}"
    nmcli con modify "${HOTSPOT_CON}" 802-11-wireless.mode ap 802-11-wireless.band bg
    nmcli con modify "${HOTSPOT_CON}" ipv4.method shared ipv6.method ignore
    nmcli con modify "${HOTSPOT_CON}" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "${pass}"
  fi

  log "Activating hotspot…"
  nmcli con up "${HOTSPOT_CON}"
  log "Hotspot is up. SSID=${ssid}  URL=http://10.42.0.1/  PASS=${pass}"
}

wifi_connected() {
  nmcli -t -f DEVICE,STATE dev status | awk -F: '$1=="'"${WLAN_IF}"'" {print $2}' | grep -q '^connected$'
}

main() {
  nmcli radio wifi on || true

  # Wait for normal Wi-Fi connection (45 seconds)
  for i in {1..45}; do
    if wifi_connected; then
      log "Wi-Fi already connected; nothing to do."
      exit 0
    fi
    sleep 1
  done

  log "No Wi-Fi connection detected, starting hotspot provisioning mode..."
  ensure_hotspot_connection
}

main "$@"
