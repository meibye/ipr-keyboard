#!/usr/bin/env bash
#
# IPR Keyboard permanent management hotspot
#
# Purpose:
#   - Always starts a WPA2-secured Wi-Fi hotspot on wlan0 at boot
#   - Hotspot is permanent — users connect to it at any time to reach the
#     management web UI at http://10.42.0.1/ (no cable required)
#   - Credentials are generated once and stored in /etc/ipr-hotspot.secret
#   - On devices with eth0 (dev Pi), eth0 handles wired connectivity while
#     wlan0 runs the management hotspot simultaneously
#
# GPIO gate (optional):
#   Set HOTSPOT_GPIO_PIN (e.g. in /etc/default/ipr-provision) to a BCM GPIO
#   pin number.  The hotspot only starts when that pin is held LOW for ≥ 2 s
#   at script start.  Recommended: GPIO 27 (Pin 13).  GPIO 17 is reserved for
#   factory reset.  Leave unset (default) for always-on behaviour.
#
# Installation:
#   sudo cp scripts/headless/net_provision_hotspot.sh /usr/local/sbin/ipr-provision.sh
#   sudo chmod +x /usr/local/sbin/ipr-provision.sh
#
# Service:
#   Managed by ipr-provision.service
#
# category: Headless
# purpose: Permanent management hotspot for headless Pi
# sudo: yes

set -euo pipefail

HOTSPOT_CON="ipr-hotspot"
WLAN_IF="wlan0"
AP_SSID_PREFIX="ipr-setup"
SECRET_FILE="/etc/ipr-hotspot.secret"

# Optional env override — set in /etc/default/ipr-provision
HOTSPOT_GPIO_PIN="${HOTSPOT_GPIO_PIN:-}"

log() { echo "[ipr-provision] $*"; }

# ---------------------------------------------------------------------------
# Credential management
# ---------------------------------------------------------------------------

machine_suffix() {
  (cat /etc/machine-id 2>/dev/null || hostname | tr -d '\n') | head -c 4
}

load_or_generate_secret() {
  if [[ -f "${SECRET_FILE}" ]]; then
    # shellcheck source=/dev/null
    source "${SECRET_FILE}"
    [[ -n "${SSID:-}" && -n "${PASS:-}" ]] && return
    log "Secret file incomplete — regenerating."
  fi

  local ssid="${AP_SSID_PREFIX}-$(machine_suffix)"
  local pass
  pass="$(openssl rand -hex 16)"

  install -m 0600 -o root -g root /dev/null "${SECRET_FILE}"
  printf 'SSID=%s\nPASS=%s\n' "${ssid}" "${pass}" >"${SECRET_FILE}"
  log "Generated new credentials in ${SECRET_FILE}"

  SSID="${ssid}"
  PASS="${pass}"
}

# ---------------------------------------------------------------------------
# Optional GPIO gate
# ---------------------------------------------------------------------------

gpio_pin_held_low() {
  local pin="${1}" hold_sec=2 interval=0.1 elapsed=0
  # raspi-gpio is available on Raspberry Pi OS; skip gate if missing
  if ! command -v raspi-gpio &>/dev/null; then
    log "raspi-gpio not found — skipping GPIO gate, hotspot will start."
    return 0
  fi

  raspi-gpio set "${pin}" ip pu 2>/dev/null || true
  log "GPIO gate enabled on pin ${pin}. Waiting ${hold_sec}s hold to start hotspot..."

  while (( $(echo "${elapsed} < ${hold_sec}" | bc -l) )); do
    local state
    state=$(raspi-gpio get "${pin}" 2>/dev/null | grep -oP 'level=\K[01]' || echo "1")
    if [[ "${state}" != "0" ]]; then
      log "GPIO ${pin} not held — hotspot not started."
      return 1
    fi
    sleep "${interval}"
    elapsed=$(echo "${elapsed} + ${interval}" | bc -l)
  done
  log "GPIO ${pin} held low — activating hotspot."
  return 0
}

# ---------------------------------------------------------------------------
# Hotspot setup — WPA2-RSN+CCMP (maximum client compatibility)
# ---------------------------------------------------------------------------

apply_wpa2_rsn() {
  # proto=rsn: WPA2 only (no legacy WPA/TKIP)
  # pairwise/group=ccmp: AES only
  # pmf=1 (disabled): avoids iOS/Android rejection on WPA2-only AP modes
  nmcli con modify "${HOTSPOT_CON}" \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.proto rsn \
    wifi-sec.pairwise ccmp \
    wifi-sec.group ccmp \
    wifi-sec.pmf 1 \
    wifi-sec.psk "${PASS}"
}

ensure_hotspot_connection() {
  if nmcli -t -f NAME con show | grep -qx "${HOTSPOT_CON}"; then
    log "Updating existing hotspot connection: ${HOTSPOT_CON}"
    nmcli con modify "${HOTSPOT_CON}" 802-11-wireless.ssid "${SSID}"
  else
    log "Creating hotspot connection: ${HOTSPOT_CON} (${SSID})"
    nmcli con add type wifi ifname "${WLAN_IF}" con-name "${HOTSPOT_CON}" \
      autoconnect no ssid "${SSID}"
    nmcli con modify "${HOTSPOT_CON}" \
      802-11-wireless.mode ap \
      802-11-wireless.band bg \
      ipv4.method shared \
      ipv6.method ignore
  fi

  apply_wpa2_rsn
  nmcli con up "${HOTSPOT_CON}"
  log "Hotspot up with WPA2-RSN+CCMP. SSID=${SSID}  URL=http://10.42.0.1/"
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

main() {
  nmcli radio wifi on || true

  if [[ -n "${HOTSPOT_GPIO_PIN}" ]]; then
    gpio_pin_held_low "${HOTSPOT_GPIO_PIN}" || exit 0
  fi

  load_or_generate_secret

  ensure_hotspot_connection

  log "Starting management web UI on http://10.42.0.1/ ..."
  if ss -tlnp 2>/dev/null | grep -q ':80 '; then
    log "Web UI already running on port 80, skipping launch."
    exit 0
  fi
  exec python3 /usr/local/sbin/ipr-provision-web.py
}

main "$@"
